from abc import ABC, abstractmethod
import math
import numpy as np
from numpy import square
from scipy.stats import t
import pandas as pd
import copy
from dateutil.relativedelta import *
import random

from event import Event
from utils.errors import MarketDataNotAvailableError, BalanceTooLowError
from utils.logger import Logger
from utils.utils import Signal
from utils.types import BrokerBase # prob fail, need to pull out base/abastract classes and use that for typing
from data_handler import DataHandler
from utils.types import PortfolioBase, Strategy

class Portfolio(PortfolioBase):
    def __init__(
        self, 
        market_data: DataHandler, 
        broker: BrokerBase, 
        strategy: Strategy, 
        logger: Logger,
        balance: float, 
        initial_margin_requirement: float=0.5,
        maintenance_margin_requirement: float=0.3,
    ):
    
        self.market_data = market_data # Shared with backtester and broker
        self.broker = broker # this makes it possible for the portfolio to query the broker for active trades.
        self.strategy = strategy

        self.logger = logger
        
        self.initial_balance = balance
        self.balance = balance
        self.margin_account = 0
        
        self.initial_margin_requirement = initial_margin_requirement
        self.maintenance_margin_requirement = maintenance_margin_requirement

        # Allows tracking of portfolio/strategy output
        self.signals = [] # All signals ever produced
        self.order_history = [] # All orders ever created and sent to the broker


        self.costs = pd.DataFrame(index=self.market_data.date_index_to_iterate) # Not implemented
        self.costs["commission"] = 0
        self.costs["slippage"] = 0
        self.costs["charged"]  = 0
        self.costs["margin_interest"] = 0
        self.costs["account_interest"] = 0
        self.costs["short_dividends"] = 0
        self.costs["short_losses"] = 0

        self.received = pd.DataFrame(index=self.market_data.date_index_to_iterate)
        self.received["dividends"] = 0
        self.received["interest"] = 0
        self.received["proceeds"] = 0

        # Can the above just be merged with the portfolio_value dataframe?
        self.portfolio_value = pd.DataFrame(index=self.market_data.date_index_to_iterate) # This is the basis for portfolio return calculations
        self.portfolio_value["balance"] = pd.NaT
        self.portfolio_value["margin_account"] = pd.NaT
        self.portfolio_value["market_value"] = pd.NaT
        self.portfolio_value["total"] = pd.NaT # NOTE: Calculate at the end of the Backtest

        self.seen_signal_ids = set()

    # ___________ STRATEGY RELATED _________________

    def generate_signals(self):
        signals_event =  self.strategy.generate_signals(self.market_data.cur_date, self.market_data)
        if signals_event is not None:
            for signal in signals_event.data:
                if signal.signal_id in self.seen_signal_ids:
                    continue
                else:
                    self.signals.append(signal)
                    self.seen_signal_ids.add(signal.signal_id)
            
        return signals_event

    def generate_orders_from_signals(self, signals_event):
        orders_event = self.strategy.generate_orders_from_signals(self, signals_event)
        if orders_event is not None:
            self.order_history.extend(orders_event.data)
        return orders_event


    def handle_trades_event(self, event: Event):
        trades = event.data
        for trade in trades:
            self.costs.loc[trade.date, "slippage"] += trade.get_total_slippage() # All other costs are recorded in their respective method
        
        self.strategy.handle_event(self, event)

    def handle_cancelled_orders_event(self, event: Event):
        self.strategy.handle_event(self, event)


    # ___________ RECEIVE MONEY __________________

    def receive_proceeds(self, amount: float):
        if amount < 0:
            raise ValueError("Cannot receive negative proceeds, got {}.".format(amount))

        self.received.loc[self.market_data.cur_date, "proceeds"] += amount
        self.balance += amount

    def receive_interest(self, interest: float):
        if interest < 0:
            raise ValueError("Cannot receive negative interests, got {}.".format(interest))

        self.received.loc[self.market_data.cur_date, "interest"] += interest
        self.balance += interest

    def receive_dividends(self, dividends):
        if dividends < 0:
            raise ValueError("Cannot receive negative dividends, got {}".format(dividends))

        self.received.loc[self.market_data.cur_date, "dividends"] += dividends
        self.balance += dividends

    # ____________ PAY MONEY ____________________

    def charge(self, amount):
        """
        Amount must be a positive value to deduct from the portfolios balance.
        """
        if amount < 0:
            raise ValueError("Amount must be a positive number, amount was {}".format(amount))

        if self.balance >= amount:
            self.costs.loc[self.market_data.cur_date, "charged"] += amount
            self.balance -= amount
        else:
            raise BalanceTooLowError("Cannot charge portfolio because balance is {} and wanted to charge {}".format(self.balance, amount))


    def charge_commission(self, commission):
        """
        Charge the portfolio the commission.
        To avoid scenarios where the portfolios balance is too low to even exit its current positions, this will not cause errors.
        """
        if commission < 0:
            raise ValueError("Cannot charge negative commission, got {}".format(commission))

        self.costs.loc[self.market_data.cur_date, "commission"] += commission 
        self.balance -= commission

    def charge_margin_interest(self, margin_interest):
        """
        Since I don't want the portfolio to get margin calls where additional funds must be added because it cannot meet payments, I allways
        assume margin interest can be payed. This can cause the portfolio to end up with a negative balance. This will trigger sales to get back 
        to positive balance next time rebalancing happens.
        """
        if margin_interest < 0:
            raise ValueError("Cannot charge negative margin interest, got {}.".format(margin_interest))

        self.costs.loc[self.market_data.cur_date, "margin_interest"] += margin_interest 
        self.balance -= margin_interest

    def charge_interest(self, interest):
        if interest < 0:
            raise ValueError("Cannot charge negative interest, got {}.".format(interest))

        self.costs.loc[self.market_data.cur_date, "account_interest"] += interest
        self.balance -= interest


    def charge_margin_account(self, amount):
        """
        When short positions end up in a loss, these losses are covered by subtracting the amount from the margin_account.
        """
        if amount < 0:
            raise ValueError("Cannot charge the margin account a negative amount, got {}.".format(amount))

        self.costs.loc[self.market_data.cur_date, "short_losses"] += amount
        self.margin_account -= amount

    def charge_for_dividends(self, dividends):
        if dividends < 0:
            raise ValueError("Connot charge for negative dividends, got {}.".format(dividends))

        self.costs.loc[self.market_data.cur_date, "short_dividends"] += dividends
        self.margin_account -= dividends

    # _____________ MARGIN ACCOUNT RELATED METHODS _____________________

    def update_margin_account(self, new_margin_size_requirement):
        """
        Move money from the balance to the margin_account.
        This method is intended to use when processing orders for short positions. To tell the user that the portfolio
        has insufficient funds to update the margin account, a BalanceTooLowError is raised.
        """
        diff = new_margin_size_requirement - self.margin_account
        if diff > 0:
            try:    
                self.charge(diff)
            except BalanceTooLowError:
                raise BalanceTooLowError("Cannot increase margin account, because balance is too low. Balance is {} and wanted to move {}".format(self.balance, diff))
            else: 
                self.margin_account += diff
        if diff < 0:
            self.margin_account -= abs(diff)
            self.balance += diff


    def handle_margin_account_update(self, margin_account_update_event):
        """
        Update the margin account size to the new required size. If the balance is insufficient the money still gets moved
        and no error will occur. The new balance will restrict the portfolio going forward and any negative balance will get
        charged interests. 
        """
        required_margin_account_size = margin_account_update_event.data

        if self.margin_account < required_margin_account_size:
            money_to_move = required_margin_account_size - self.margin_account
            self.balance -= money_to_move
            self.margin_account += money_to_move

        elif self.margin_account > required_margin_account_size:
            money_to_move = self.margin_account - required_margin_account_size
            self.margin_account -= money_to_move
            self.balance += money_to_move


    def get_num_trades(self):
        return len(self.broker.blotter.active_trades)

    def get_num_short_trades(self):
        return len([signal for signal in self.broker.blotter.active_trades if signal.direction == -1])


    # ______________ END OF BACKTEST STATE CALCULATIONS _____________________

    def calculate_portfolio_value(self):
        """
        Calculates and returns portfolio value at the end of the current day for both long and short positions.
        This is called after all the days orders have been placed and processed, the margin account has been updated
        and liquidated positions have updated the balance and portfolio state

        Short positions need fill price and current price to calculate value. (An exit price is never relevant, because exited position will have
        its value added to the balance)
        """
        value_of_trades = 0

        for trade in self.broker.blotter.active_trades:
            # NOTE: NEED TO UPDATE
            try:
                daily_data = self.market_data.current_for_ticker(trade.ticker)
            except MarketDataNotAvailableError:
                return None

            if trade.direction == 1:
                trade_value = trade.amount * daily_data["close"]

            elif trade.direction == -1:
                trade_value = abs(trade.amount) * (trade.fill_price - daily_data["close"]) # NOTE: IS THIS CORRECT?

            value_of_trades += trade_value

        total_value = value_of_trades + self.balance + self.margin_account
        return total_value

    def calculate_return_over_period(self, start_date, end_date):
        if (start_date < self.market_data.start) or (end_date > self.market_data.cur_date):
            raise ValueError("Attempted to calculate return over period where the start date was lower\
                 than backtest's start date or the end date was higher than the current date.")

        start_value = self.portfolio_value.loc[start_date, "total"]
        end_value = self.portfolio_value.loc[end_date, "total"]

        return (end_value / start_value) - 1


    def calculate_market_value_of_trades(self):
        """
        Calculate market value of portfolio. Not including cash and margin account.
        """
        portfolio_value = 0

        for trade in self.broker.blotter.active_trades:
            try:
                daily_data = self.market_data.current_for_ticker(trade.ticker)
            except MarketDataNotAvailableError:
                return None

            if trade.direction == 1:
                trade_value = trade.amount * daily_data["close"]

            elif trade.direction == -1:
                trade_value = abs(trade.amount) * (trade.fill_price - daily_data["close"])

            portfolio_value += trade_value

        return portfolio_value
    
    def calculate_aum(self):
        aum = 0
        for trade in self.broker.blotter.active_trades:
            try:
                daily_data = self.market_data.current_for_ticker(trade.ticker)
            except MarketDataNotAvailableError:
                return None
            
            aum += abs(trade.amount * daily_data["close"])

        return aum

    def get_monthly_returns(self):
        port_val = self.portfolio_value.copy(deep=True)
        snp500 = self.broker.market_data.get_ticker_data("snp500")

        date_index = port_val.index

        snp500 = snp500.loc[date_index]

        ahead_1m_snp500 = snp500.shift(periods=-30)
        ahead_1m_portfolio = port_val.shift(periods=-30)

        returns = pd.DataFrame(index=date_index)

        returns["snp500"] = (ahead_1m_snp500["close"] / snp500["close"]) - 1
        returns["portfolio"] = (ahead_1m_portfolio["total"] / port_val["total"]) - 1
        
        def custom_resample(array_like):
            return array_like[-1] # sample last day of the month

        returns = returns.resample('M').apply(custom_resample)
        returns = returns.dropna(axis=0)
        return returns
    

    def normality_test_on_returns(self, alpha: float=0.05):
        from scipy.stats import shapiro

        returns = self.get_monthly_returns()
        
        W, p = shapiro(np.array(returns["portfolio"])) # H0: samples are from a gausian distribution
        print('W Statistic=%.3f, p=%.3f' % (W, p))

        if p > alpha:
            # High enough probability the samples are from a gausian distribution, failing to reject the null hypothesis
            return "Shapiro-Wilk test: Returns are normal (tested at %.0f %% significance level), test-statistic W=%.3f" % (alpha*100, W)
        else:
            # Reject H0, returns are non-normal
            return "Shapiro-Wilk test: Returns are non-normal (tested at %.0f %% significance level), test-statistic W=%.3f" % (alpha*100, W)


    def calculate_sharpe_ratio(self):
        returns = self.get_monthly_returns()

        std = returns["portfolio"].std()
        mean = returns["portfolio"].mean()
        rf = self.broker.market_data.rf_rate["monthly"].mean()

        return (mean - rf) / std

    def calculate_adjusted_sharpe_ratio(self):
        from scipy.stats import skew, kurtosis

        returns = self.get_monthly_returns()
        sharpe_ratio = self.calculate_sharpe_ratio()
        
        sk = skew(returns["portfolio"])
        kur = kurtosis(returns["portfolio"], )
        print("skew: ", sk)
        print("Kurtosis: ", kur)
        
        asr = sharpe_ratio + (sk/6)*(sharpe_ratio**2) - (kur/24)*(sharpe_ratio**3)
        print("sr: ", sharpe_ratio)
        print("asr: ", asr)
        return asr

    def calculate_correlation_of_monthly_returns(self):
        returns = self.get_monthly_returns()
        return returns["portfolio"].corr(returns["snp500"])

    def calculate_std_of_portfolio_returns(self):
        returns = self.get_monthly_returns()
        return returns["portfolio"].std()

    def calculate_std_of_snp500_returns(self):
        returns = self.get_monthly_returns()
        return returns["snp500"].std()

    def calculate_statistical_significance_of_outperformance_single_sample(self, mean0: float=0, alpha: float=0.05):
        """
        This is an implementation of single-sided and single sample test of the mean of a normal distribution
        with unknown variance.
        """
        returns = self.get_monthly_returns()
        observations = returns["portfolio"] - returns["snp500"]
        
        mean_obs = observations.mean()
        sample_std = math.sqrt(square(observations - mean_obs).sum() / (len(observations) - 1))

        t_statistic = (mean_obs - mean0) / (sample_std / math.sqrt(len(observations)))

        # test if t_statistic > t(alpha, n-1)
        # ppf(q, df, loc=0, scale=1)	Percent point function (inverse of cdf — percentiles).
        critical_value = t.ppf(1 - alpha, df=len(observations)-1)
        p_value = (1.0 - t.cdf(t_statistic, df=len(observations)-1))

        if t_statistic > critical_value:
            return "Reject H0 with t_statistic={}, p-value={}, critical_value={} and alpha={}".format(t_statistic, p_value, critical_value, alpha)

        else:
            return "Filed to reject H0 with t_statistic={}, p-value={}, critical_value={} and alpha={}".format(t_statistic, p_value, critical_value, alpha)

    def calculate_average_aum(self):
        return self.portfolio_value["aum"].mean()

    def calculate_annulized_rate_of_return(self, start_date, end_date): 
        if (start_date < self.market_data.start) or (end_date > self.market_data.cur_date):
            raise ValueError("Attempted to calculate return over period where the start date was lower\
                 than backtest's start date or the end date was higher than the current date.")

        start_value = self.portfolio_value.loc[start_date, "total"]
        end_value = self.portfolio_value.loc[end_date, "total"]
        days = int((end_date - start_date).days)
        n = days / 365

        ar = (end_value/start_value)**(1/n) - 1
        return ar 

    def calculate_annulized_rate_of_index_return(self, start_date, end_date):
        if (start_date < self.market_data.start) or (end_date > self.market_data.cur_date):
            raise ValueError("Attempted to calculate return over period where the start date was lower\
                 than backtest's start date or the end date was higher than the current date.")
        snp500 = self.broker.market_data.get_ticker_data("snp500")
        start_value = snp500.loc[start_date, "close"]
        end_value = snp500.loc[end_date, "close"]
        days = int((end_date - start_date).days)
        n = days / 365

        ar = (end_value/start_value)**(1/n) - 1
        return ar 

    def calculate_broker_fees_per_turnover(self):
        return "NOT IMPLEMENTED"


    # This got complicated, I think I can make it simpler by calculating everything from active_positions
    def capture_state(self):
        self.portfolio_value.loc[self.market_data.cur_date, "balance"] = self.balance
        self.portfolio_value.loc[self.market_data.cur_date, "margin_account"] = self.margin_account
        market_value_of_trades = self.calculate_market_value_of_trades() # NOTE: CHECK IF CORRECT
        self.portfolio_value.loc[self.market_data.cur_date, "market_value"] = market_value_of_trades
        self.portfolio_value.loc[self.market_data.cur_date, "total"] = self.balance + self.margin_account + market_value_of_trades
        self.portfolio_value.loc[self.market_data.cur_date, "aum"] = self.calculate_aum()

    def order_history_to_df(self):
        df = pd.DataFrame(columns=["order_id", "date", "ticker", "amount", "direction", "stop_loss", "take_profit", "time_out", "type", "signal_id"]) # SET COLUMNS, so sorting and set index does not fail
        for index, order in enumerate(self.order_history):
            df.at[index, "order_id"] = order.id
            df.at[index, "date"] = order.date
            df.at[index, "ticker"] = order.ticker
            df.at[index, "amount"] = order.amount
            df.at[index, "direction"] = order.direction
            df.at[index, "stop_loss"] = order.stop_loss
            df.at[index, "take_profit"] = order.take_profit
            df.at[index, "timeout"] = order.timeout
            df.at[index, "type"] = order.type
            df.at[index, "signal_id"] = order.signal.signal_id

        df = df.sort_values(by=["order_id"])
        return df


    def signals_to_df(self):
        df = pd.DataFrame(columns=["signal_id", "ticker", "direction", "certainty", "ewmstd", "features_date"])
        for index, signal in enumerate(self.signals):
            df.at[index, "signal_id"] = signal.signal_id
            df.at[index, "ticker"] = signal.ticker
            df.at[index, "direction"] = signal.direction
            df.at[index, "certainty"] = signal.certainty
            df.at[index, "ewmstd"] = signal.ewmstd      
            df.at[index, "features_date"] = signal.features_date

        df = df.sort_values(by=["signal_id"])
        return df
