import sys, os
import pandas as pd
import pytest
import math
from dateutil.relativedelta import *
import numpy as np

import plotly as py
import plotly.graph_objs as go
import plotly.tools as tls

myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(myPath, ".."))
# sys.path.insert(0, os.path.join(myPath))


from data_handler import DailyBarsDataHander, dividend_adjusting_prices_backwards, MLFeaturesDataHandler
from event import EventQueue, MarketDataEvent, Event

@pytest.fixture(scope='module', autouse=True)
def setup():
    """
    import shutil
    if os.path.exists("../test_bundles"):
        shutil.rmtree("../test_bundles") 
    """
    yield

@pytest.mark.skip()
def test_data_handler_ingest():

    start_date = pd.to_datetime("2010-01-01")
    end_date = pd.to_datetime("2010-06-01")

    dh = DailyBarsDataHander( 
        path_prices="../../dataset_development/datasets/testing/sep.csv",
        path_snp500="../../dataset_development/datasets/macro/snp500.csv",
        path_interest="../../dataset_development/datasets/macro/t_bill_rate_3m.csv",
        path_corp_actions="../../dataset_development/datasets/sharadar/SHARADAR_EVENTS.csv",
        store_path="../test_bundles",
        start=start_date,
        end=end_date
    )

    assert isinstance(dh.time_data.index.get_level_values(0).drop_duplicates(keep='first'), pd.DatetimeIndex)
    try:
        dh.time_data.loc["1998-01-20", "AAPL"]["close"]
        dh.ticker_data.loc["snp500", "1998-01-20"]["close"]
        dh.rf_rate.loc["1998-01-20"]["daily"]
        dh.corp_actions.loc[dh.corp_actions.date == "1998-01-20"]
    except KeyError as e:
        pytest.fail(e)
    
    assert dh.ticker_data.loc["snp500", "2019-04-24"]["close"] == 2927.25 # 24.04.2019,2927.25

@pytest.mark.skip()
def test_data_handler_can_trade():
    start_date = pd.to_datetime("2010-01-01")
    end_date = pd.to_datetime("2010-06-01")

    dh = DailyBarsDataHander( 
        path_prices="../../dataset_development/datasets/testing/sep.csv",
        path_snp500="../../dataset_development/datasets/macro/snp500.csv",
        path_interest="../../dataset_development/datasets/macro/t_bill_rate_3m.csv",
        path_corp_actions="../../dataset_development/datasets/sharadar/SHARADAR_EVENTS.csv",
        store_path="../test_bundles",
        start=start_date,
        end=end_date
    )

    # print(dh.ticker_data.loc["AAPL"].head(50))
    assert dh.can_trade("AAPL", "1998-01-20") == True


@pytest.mark.skip()
def test_data_handler_is_business_day():
    start_date = pd.to_datetime("2010-01-01")
    end_date = pd.to_datetime("2010-06-01")

    dh = DailyBarsDataHander( 
        path_prices="../../dataset_development/datasets/testing/sep.csv",
        path_snp500="../../dataset_development/datasets/macro/snp500.csv",
        path_interest="../../dataset_development/datasets/macro/t_bill_rate_3m.csv",
        path_corp_actions="../../dataset_development/datasets/sharadar/SHARADAR_EVENTS.csv",
        store_path="../test_bundles",
        start=start_date,
        end=end_date
    )
    
    assert dh.is_business_day("1998-01-20") == True
    assert dh.is_business_day("2013-02-16") == False


@pytest.mark.skip()
def test_market_data_generator():

    start_date = pd.to_datetime("2010-01-01")
    end_date = pd.to_datetime("2010-06-01")

    market_data = DailyBarsDataHander( 
        path_prices="../../dataset_development/datasets/testing/sep.csv",
        path_snp500="../../dataset_development/datasets/macro/snp500.csv",
        path_interest="../../dataset_development/datasets/macro/t_bill_rate_3m.csv",
        path_corp_actions="../../dataset_development/datasets/sharadar/SHARADAR_EVENTS.csv",
        store_path="../test_bundles",
        start=start_date,
        end=end_date
    )

    event_queue = EventQueue()

    i = 0

    while True: # This loop generates new "ticks" until the backtest is completed.
        try:
            market_data_event = next(market_data.tick) # THIS MUST ONLY BE CALLED HERE!
        except Exception as e: # What error does the generator give?
            print(e)
            break
        else:
            event_queue.add(market_data_event)
        
        i += 1
        if i >= 5:
            break

    assert len(event_queue.queue) == 5
    assert isinstance(event_queue.get(), MarketDataEvent)


@pytest.mark.skip()
def test_data_handler_corporate_actions():
    """
    How to to this..., probably sepearate dataframe like rf_rate 
    """
    # Corporate actions: bankruptcies, delisting (not dividends, it is read directly from sep)
    start_date = pd.to_datetime("2010-01-01")
    end_date = pd.to_datetime("2010-06-01")

    dh = DailyBarsDataHander( 
        path_prices="../../dataset_development/datasets/testing/sep.csv",
        path_snp500="../../dataset_development/datasets/macro/snp500.csv",
        path_interest="../../dataset_development/datasets/macro/t_bill_rate_3m.csv",
        path_corp_actions="../../dataset_development/datasets/sharadar/SHARADAR_EVENTS.csv",
        store_path="../test_bundles",
        start=start_date,
        end=end_date
    )
    """
    Datastructure:
            ticker  action
    date    
    2010-01-01 AAPL "bankruptcy"
    2010-01-01 AAPL "delisted"

    delisted tickers gets added at the date of last row in sep
    """

    data = {
                    # Before delisting           # After desliting              # C has the maximum index       # D was just delisted
        "date": [pd.to_datetime("2010-06-15"), pd.to_datetime("2011-01-10"), pd.to_datetime("2010-05-10"), pd.to_datetime("2010-05-10")],
        'ticker': ["A", "B", "C", "D"], 
        'eventcodes': ["12|14|13", "13|52|9|51", "14|25", "24|16"], 
    }
    test_actions = pd.DataFrame(data=data)

    A_df = pd.DataFrame(index=pd.date_range("2010-01-01", "2010-6-30"))
    A_df["ticker"] = "A"
    A_df["close"] = 10
    B_df = pd.DataFrame(index=pd.date_range("2010-01-01", "2010-12-31"))
    B_df["ticker"] = "B"
    B_df["close"] = 10
    C_df = pd.DataFrame(index=pd.date_range("2010-01-01", "2011-12-31")) # Represent max index size of sep
    C_df["ticker"] = "C"
    C_df["close"] = 10
    D_df = pd.DataFrame(index=pd.date_range("2010-01-01", "2010-12-31"))
    D_df["ticker"] = "D"
    D_df["close"] = 10

    test_sep = A_df.append(B_df, sort=True).append(C_df, sort=True).append(D_df, sort=True)

    date_index = pd.date_range(test_sep.index.min(), test_sep.index.max())

    corp_actions = dh.ingest_corporate_actions(test_sep, date_index, test_actions)
    
    print(corp_actions)
    assert False

    # Extract path to argument...

@pytest.mark.skip()
def test_data_handler_corporate_actions_real():
    start_date = pd.to_datetime("2010-01-01")
    end_date = pd.to_datetime("2010-06-01")

    dh = DailyBarsDataHander( 
        path_prices="../../dataset_development/datasets/testing/sep.csv",
        path_snp500="../../dataset_development/datasets/macro/snp500.csv",
        path_interest="../../dataset_development/datasets/macro/t_bill_rate_3m.csv",
        path_corp_actions="../../dataset_development/datasets/sharadar/SHARADAR_EVENTS.csv",
        store_path="../test_bundles",
        start=start_date,
        end=end_date
    )

    sep = pd.read_csv("../../dataset_development/datasets/sharadar/SEP_PURGED.csv", parse_dates=["date"], index_col="date", low_memory=False)
    actions = pd.read_csv("../../dataset_development/datasets/sharadar/SHARADAR_EVENTS.csv", parse_dates=["date"], low_memory=False)

    date_index = pd.date_range(sep.index.min(), sep.index.max())
    corp_actions = dh.ingest_corporate_actions(sep, date_index, actions)

    corp_actions.to_csv("./test_bundles/corp_actions.csv")
    # Do visual inspection.

@pytest.mark.skip()
def test_ml_feature_data_handler():

    data_handler = MLFeaturesDataHandler(
        path_features="../../dataset_development/datasets/testing/ml_dataset.csv",
        store_path="./test_bundles",
        start=pd.to_datetime("2001-02-12"),
        end=pd.to_datetime("2002-05-14")
    )

    # print(data_handler.feature_data.loc["2001-06-14", :])

    try: 
        data_handler.feature_data.loc["2001-06-14", :]
    except Exception as e:
        pytest.fail(e)

    # print(data_handler.get_range("2001-02-12", "2001-06-14"))

    # Test get range
    assert isinstance(data_handler.get_range("2001-02-12", "2001-06-14"), pd.DataFrame)
    assert data_handler.get_range("2001-02-12", "2001-06-14").shape[0] == 8
    assert "2001-06-14" not in list(data_handler.get_range("2001-02-12", "2001-06-14").index)

    # Test get batch
    batch_1_event = data_handler.next_batch("2001-04-12") # 4 rows i think
    batch_2_event = data_handler.next_batch("2001-07-13") # 6 rows i think

    batch_3_event = data_handler.next_batch("2020-01-01") # Should not fail, but return all available data until 2020-01-01

    """
    print("Batch_1: ", batch_1_event.data)
    print("Batch_2: ", batch_2_event.data)
    print(data_handler.feature_data.loc["2001-04-12":"2001-07-13"])
    print("Batch_3: ", batch_3_event.data)
    """

    assert isinstance(batch_1_event, Event)
    assert isinstance(batch_2_event, Event)
    assert isinstance(batch_1_event.data, pd.DataFrame)
    assert batch_1_event.data.shape[0] == 4 
    assert batch_2_event.data.shape[0] == 6
    assert "2001-04-12" not in list(batch_1_event.data.index)


    """
    Sample Dates for AAPL:
    2001-02-12
    2001-03-12
    2001-04-12
    2001-05-14
    2001-06-14

    2001-07-13
    2001-08-13
    2001-09-10
    2001-10-12
    2001-11-13
    2001-12-21
    2002-01-22
    2002-02-11
    2002-03-11
    2002-04-11
    2002-05-14
    """


def test_current_dividends():
    start_date = pd.to_datetime("2010-01-01")
    end_date = pd.to_datetime("2010-06-01")

    dh = DailyBarsDataHander( 
        path_prices="../../dataset_development/datasets/testing/sep.csv",
        path_snp500="../../dataset_development/datasets/macro/snp500.csv",
        path_interest="../../dataset_development/datasets/macro/t_bill_rate_3m.csv",
        path_corp_actions="../../dataset_development/datasets/sharadar/SHARADAR_EVENTS.csv",
        store_path="../test_bundles",
        start=start_date,
        end=end_date
    )


    dividends_with = dh.get_dividends(pd.to_datetime("2017-05-11"))
    dividends_without = dh.get_dividends(pd.to_datetime("2017-05-12"))

    print(dividends_with)
    print(dividends_without)

    assert isinstance(dividends_with, pd.DataFrame)
    assert isinstance(dividends_with.loc["AAPL"]["dividends"], float)











"""
My prices are not adjusted for dividends, so I need to adjust for dividends in feature calculation and label calculation.
But data is ready to be used as is in the back teseter

"""
@pytest.mark.skip()
def test_dividend_adjustment():
    # Maybe I can use the unadjusted close to check my math...
    # And just try to find the correct formula that gives me the same close series

    # Need to find ticker and data range to test against...
    sep = pd.read_csv("../dataset_development/datasets/testing/sep.csv", parse_dates=["date"], index_col="date")
    sep_aapl = sep.loc[sep.ticker == "AAPL"]
    # sep_aapl = sep_aapl.loc[(sep_aapl.index >= "2016-04-14") & (sep_aapl.index <= "2017-08-16")]

    ticker = "AAPL"
    start = pd.to_datetime("2016-04-14")
    end = pd.to_datetime("2017-08-16")

    adj = dividend_adjusting_prices_backwards(sep_aapl)

    for date, row in sep.iterrows():
        if row["close"] != sep_aapl.loc[date]["closeunadj"]:
            print(date, row["close"], sep_aapl.loc[date]["closeunadj"])




""" Originally from test_data_handler_corporate_actions_real
I end up with 1502 bankruptcies in the corp_actions dataframe, and this is not far from correct if not completely correct.


drop_indexes = []
for index, row in actions.iterrows():
    codes = [int(s) for s in str(row["eventcodes"]).split("|")]
    if 13 in codes:
        actions.loc[index, "eventcodes"] = 13
    else:
        drop_indexes.append(index)

actions = actions.drop(drop_indexes, axis=0)
actions.to_csv("./test_bundles/actions.csv", index=False)

mask = actions.ticker.duplicated(keep=False)
actions = actions[mask]
actions = actions.sort_values(by=["ticker", "date"])
actions.to_csv("./test_bundles/duplicated_actions.csv", index=False)
"""

""" Conclusion: There is no significant difference in ticker coverage
ticker_difference = list(set(sep.ticker.unique()) - set(actions.ticker.unique()))
ticker_df = pd.DataFrame(data={"ticker": ticker_difference})
ticker_df.to_csv("./test_bundles/ticker_difference.csv", index=False)

ticker_difference = list(set(actions.ticker.unique()) - set(sep.ticker.unique()))
ticker_df = pd.DataFrame(data={"ticker": ticker_difference})
ticker_df.to_csv("./test_bundles/ticker_difference_2.csv", index=False)

sys.exit()
"""


"""
ticker,date,open,high,low,close,volume,dividends,closeunadj
AAPL	2016-04-14	111.62	112.39	111.33	112.1	25473923	0	112.1
AAPL	2016-04-15	112.11	112.3	109.73	109.85	46938969	0	109.85
AAPL	2016-04-18	108.89	108.95	106.94	107.48	60821461	0	107.48
AAPL	2016-04-19	107.88	108	    106.23	106.91	32384879	0	106.91
AAPL	2016-04-20	106.64	108.09	106.06	107.13	30611030	0	107.13
AAPL	2016-04-21	106.93	106.93	105.52	105.97	31552525	0	105.97
AAPL	2016-04-22	105.01	106.48	104.62	105.68	33683121	0	105.68
AAPL	2016-04-25	105	    105.65	104.51	105.08	28031588	0	105.08
AAPL	2016-04-26	103.91	105.3	103.91	104.35	56016165	0	104.35
AAPL	2016-04-27	96	    98.71	95.68	97.82	114602142	0	97.82
AAPL	2016-04-28	97.61	97.88	94.25	94.83	82242690	0	94.83
AAPL	2016-04-29	93.99	94.72	92.51	93.74	68531478	0	93.74
AAPL	2016-05-02	93.97	94.08	92.4	93.64	48160104	0	93.64
AAPL	2016-05-03	94.2	95.74	93.68	95.18	56831277	0	95.18
AAPL	2016-05-04	95.2	95.9	93.82	94.19	41025475	0	94.19
AAPL	2016-05-05	94	    94.07	92.68	93.24	35890500	0.57	93.24
AAPL	2016-05-06	93.37	93.45	91.85	92.72	43699886	0	92.72
AAPL	2016-05-09	93	93.77	92.59	92.79	32936436	0	92.79
AAPL	2016-05-10	93.33	93.57	92.11	93.42	33686836	0	93.42
AAPL	2016-05-11	93.48	93.57	92.46	92.51	28719109	0	92.51
AAPL	2016-05-12	92.72	92.78	89.47	90.34	76314690	0	90.34
AAPL	2016-05-13	90	91.67	90	90.52	44392765	0	90.52
AAPL	2016-05-16	92.39	94.39	91.65	93.88	61259756	0	93.88
AAPL	2016-05-17	94.55	94.7	93.01	93.49	46916939	0	93.49
AAPL	2016-05-18	94.16	95.21	93.89	94.56	42062391	0	94.56
AAPL	2016-05-19	94.64	94.64	93.57	94.2	30442100	0	94.2
AAPL	2016-05-20	94.64	95.43	94.52	95.22	32025968	0	95.22
AAPL	2016-05-23	95.87	97.19	95.67	96.43	38018643	0	96.43
AAPL	2016-05-24	97.22	98.09	96.84	97.9	35140174	0	97.9
AAPL	2016-05-25	98.67	99.74	98.11	99.62	38642108	0	99.62
AAPL	2016-05-26	99.68	100.73	98.64	100.41	56331159	0	100.41
AAPL	2016-05-27	99.44	100.47	99.25	100.35	36341240	0	100.35
AAPL	2016-05-31	99.6	100.4	98.82	99.86	42307212	0	99.86
AAPL	2016-06-01	99.02	99.54	98.33	98.46	29173285	0	98.46
AAPL	2016-06-02	97.6	97.84	96.63	97.72	40191600	0	97.72
AAPL	2016-06-03	97.79	98.27	97.45	97.92	28504888	0	97.92
AAPL	2016-06-06	97.99	101.89	97.55	98.63	23292504	0	98.63
AAPL	2016-06-07	99.25	99.87	98.96	99.03	22409450	0	99.03
AAPL	2016-06-08	99.02	99.56	98.68	98.94	20848131	0	98.94
AAPL	2016-06-09	98.5	99.99	98.46	99.65	26601354	0	99.65
AAPL	2016-06-10	98.53	99.35	98.48	98.83	31712936	0	98.83
AAPL	2016-06-13	98.69	99.12	97.1	97.34	38020494	0	97.34
AAPL	2016-06-14	97.32	98.48	96.75	97.46	31931944	0	97.46
AAPL	2016-06-15	97.82	98.41	97.03	97.14	29445227	0	97.14
AAPL	2016-06-16	96.45	97.75	96.07	97.55	31326815	0	97.55
AAPL	2016-06-17	96.62	96.65	95.3	95.33	61008219	0	95.33
AAPL	2016-06-20	96	96.57	95.03	95.1	34411901	0	95.1
AAPL	2016-06-21	94.94	96.35	94.68	95.91	35546358	0	95.91
AAPL	2016-06-22	96.25	96.89	95.35	95.55	29219122	0	95.55
AAPL	2016-06-23	95.94	96.29	95.25	96.1	32240187	0	96.1
AAPL	2016-06-24	92.91	94.66	92.65	93.4	75311356	0	93.4
AAPL	2016-06-27	93	93.05	91.5	92.04	46622188	0	92.04
AAPL	2016-06-28	92.9	93.66	92.14	93.59	40444914	0	93.59
AAPL	2016-06-29	93.97	94.55	93.63	94.4	36531006	0	94.4
AAPL	2016-06-30	94.44	95.77	94.3	95.6	35836356	0	95.6
AAPL	2016-07-01	95.49	96.47	95.33	95.89	26026540	0	95.89
AAPL	2016-07-05	95.39	95.4	94.46	94.99	27705210	0	94.99
AAPL	2016-07-06	94.6	95.66	94.37	95.53	30949090	0	95.53
AAPL	2016-07-07	95.7	96.5	95.62	95.94	25139558	0	95.94
AAPL	2016-07-08	96.49	96.89	96.05	96.68	28912103	0	96.68
AAPL	2016-07-11	96.75	97.65	96.73	96.98	23794945	0	96.98
AAPL	2016-07-12	97.17	97.7	97.12	97.42	24167463	0	97.42
AAPL	2016-07-13	97.41	97.67	96.84	96.87	25892171	0	96.87
AAPL	2016-07-14	97.39	98.99	97.32	98.79	38918997	0	98.79
AAPL	2016-07-15	98.92	99.3	98.5	98.78	30136990	0	98.78
AAPL	2016-07-18	98.7	100.13	98.6	99.83	36493867	0	99.83
AAPL	2016-07-19	99.56	100	99.34	99.87	23779924	0	99.87
AAPL	2016-07-20	100	100.46	99.74	99.96	26275968	0	99.96
AAPL	2016-07-21	99.83	101	99.13	99.43	32702028	0	99.43
AAPL	2016-07-22	99.26	99.3	98.31	98.66	28313669	0	98.66
AAPL	2016-07-25	98.25	98.84	96.92	97.34	40382921	0	97.34
AAPL	2016-07-26	96.82	97.97	96.42	96.67	56239822	0	96.67
AAPL	2016-07-27	104.27	104.35	102.75	102.95	92344820	0	102.95
AAPL	2016-07-28	102.83	104.45	102.82	104.34	39869839	0	104.34
AAPL	2016-07-29	104.19	104.55	103.68	104.21	27733688	0	104.21
AAPL	2016-08-01	104.41	106.15	104.41	106.05	38167871	0	106.05
AAPL	2016-08-02	106.05	106.07	104	104.48	33816556	0	104.48
AAPL	2016-08-03	104.81	105.84	104.77	105.79	30202641	0	105.79
AAPL	2016-08-04	105.58	106	105.28	105.87	27408650	0.57	105.87
AAPL	2016-08-05	106.27	107.65	106.18	107.48	40553402	0	107.48
AAPL	2016-08-08	107.52	108.37	107.16	108.37	28037220	0	108.37
AAPL	2016-08-09	108.23	108.94	108.01	108.81	26315204	0	108.81
AAPL	2016-08-10	108.71	108.9	107.76	108	24008505	0	108
AAPL	2016-08-11	108.52	108.93	107.85	107.93	27484506	0	107.93
AAPL	2016-08-12	107.78	108.44	107.78	108.18	18660434	0	108.18
AAPL	2016-08-15	108.14	109.54	108.08	109.48	25868209	0	109.48
AAPL	2016-08-16	109.63	110.23	109.21	109.38	33794448	0	109.38
AAPL	2016-08-17	109.1	109.37	108.34	109.22	25355976	0	109.22
AAPL	2016-08-18	109.23	109.6	109.02	109.08	21984703	0	109.08
AAPL	2016-08-19	108.77	109.69	108.36	109.36	25368072	0	109.36
AAPL	2016-08-22	108.86	109.1	107.85	108.51	25820230	0	108.51
AAPL	2016-08-23	108.59	109.32	108.53	108.85	21257669	0	108.85
AAPL	2016-08-24	108.57	108.75	107.68	108.03	23675081	0	108.03
AAPL	2016-08-25	107.39	107.88	106.68	107.57	25086248	0	107.57
AAPL	2016-08-26	107.41	107.95	106.31	106.94	27766291	0	106.94
AAPL	2016-08-29	106.62	107.44	106.29	106.82	24970300	0	106.82
AAPL	2016-08-30	105.8	106.5	105.5	106	24863945	0	106
AAPL	2016-08-31	105.66	106.57	105.64	106.1	29662406	0	106.1
AAPL	2016-09-01	106.14	106.8	105.62	106.73	26701523	0	106.73
AAPL	2016-09-02	107.7	108	106.82	107.73	26802450	0	107.73
AAPL	2016-09-06	107.9	108.3	107.51	107.7	26880391	0	107.7
AAPL	2016-09-07	107.83	108.76	107.07	108.36	42364328	0	108.36
AAPL	2016-09-08	107.25	107.27	105.24	105.52	53002026	0	105.52
AAPL	2016-09-09	104.64	105.72	103.13	103.13	46556984	0	103.13
AAPL	2016-09-12	102.65	105.72	102.53	105.44	45292770	0	105.44
AAPL	2016-09-13	107.51	108.79	107.24	107.95	62176190	0	107.95
AAPL	2016-09-14	108.73	113.03	108.6	111.77	112340318	0	111.77
AAPL	2016-09-15	113.86	115.73	113.49	115.57	90613177	0	115.57
AAPL	2016-09-16	115.12	116.13	114.04	114.92	79886911	0	114.92
AAPL	2016-09-19	115.19	116.18	113.25	113.58	47023046	0	113.58
AAPL	2016-09-20	113.05	114.12	112.51	113.57	34514269	0	113.57
AAPL	2016-09-21	113.85	113.99	112.44	113.55	36003185	0	113.55
AAPL	2016-09-22	114.35	114.94	114	114.62	31073984	0	114.62
AAPL	2016-09-23	114.42	114.79	111.55	112.71	52481151	0	112.71
AAPL	2016-09-26	111.64	113.39	111.55	112.88	29869442	0	112.88
AAPL	2016-09-27	113	113.18	112.34	113.09	24607412	0	113.09
AAPL	2016-09-28	113.69	114.64	113.43	113.95	29641085	0	113.95
AAPL	2016-09-29	113.16	113.8	111.8	112.18	35886990	0	112.18
AAPL	2016-09-30	112.46	113.37	111.8	113.05	36379106	0	113.05
AAPL	2016-10-03	112.71	113.05	112.28	112.52	21701760	0	112.52
AAPL	2016-10-04	113.06	114.31	112.63	113	29736835	0	113
AAPL	2016-10-05	113.4	113.66	112.69	113.05	21453089	0	113.05
AAPL	2016-10-06	113.7	114.34	113.13	113.89	28779313	0	113.89
AAPL	2016-10-07	114.31	114.56	113.51	114.06	24358443	0	114.06
AAPL	2016-10-10	115.02	116.75	114.72	116.05	36235956	0	116.05
AAPL	2016-10-11	117.7	118.69	116.2	116.3	64041043	0	116.3
AAPL	2016-10-12	117.35	117.98	116.75	117.34	37586787	0	117.34
AAPL	2016-10-13	116.79	117.44	115.72	116.98	35192406	0	116.98
AAPL	2016-10-14	117.88	118.17	117.13	117.63	35652191	0	117.63
AAPL	2016-10-17	117.33	117.84	116.78	117.55	23624896	0	117.55
AAPL	2016-10-18	118.18	118.21	117.45	117.47	24553478	0	117.47
AAPL	2016-10-19	117.25	117.76	113.8	117.12	20034594	0	117.12
AAPL	2016-10-20	116.86	117.38	116.33	117.06	24125801	0	117.06
AAPL	2016-10-21	116.81	116.91	116.28	116.6	23192665	0	116.6
AAPL	2016-10-24	117.1	117.74	117	117.65	23538673	0	117.65
AAPL	2016-10-25	117.95	118.36	117.31	118.25	48128970	0	118.25
AAPL	2016-10-26	114.31	115.7	113.31	115.59	66134219	0	115.59
AAPL	2016-10-27	115.39	115.86	114.1	114.48	34562045	0	114.48
AAPL	2016-10-28	113.87	115.21	113.45	113.72	37861662	0	113.72
AAPL	2016-10-31	113.65	114.23	113.2	113.54	26419398	0	113.54
AAPL	2016-11-01	113.46	113.77	110.53	111.49	43825812	0	111.49
AAPL	2016-11-02	111.4	112.35	111.23	111.59	28331709	0	111.59
AAPL	2016-11-03	110.98	111.46	109.55	109.83	26932602	0.57	109.83
AAPL	2016-11-04	108.53	110.25	108.11	108.84	30836997	0	108.84
AAPL	2016-11-07	110.08	110.51	109.46	110.41	32560000	0	110.41
AAPL	2016-11-08	110.31	111.72	109.7	111.06	24254179	0	111.06
AAPL	2016-11-09	109.88	111.32	108.05	110.88	59176361	0	110.88
AAPL	2016-11-10	111.09	111.09	105.83	107.79	57134541	0	107.79
AAPL	2016-11-11	106.92	108.87	106.55	108.43	34143898	0	108.43
AAPL	2016-11-14	107.32	107.81	104.08	105.71	51175504	0	105.71
AAPL	2016-11-15	106.57	107.68	106.16	107.11	32264510	0	107.11
AAPL	2016-11-16	106.7	110.23	106.6	109.99	58840522	0	109.99
AAPL	2016-11-17	109.81	110.35	108.83	109.95	27632003	0	109.95
AAPL	2016-11-18	109.72	110.54	109.66	110.06	28428917	0	110.06
AAPL	2016-11-21	110.12	111.99	110.01	111.73	29264571	0	111.73
AAPL	2016-11-22	111.95	112.42	111.4	111.8	25965534	0	111.8
AAPL	2016-11-23	111.36	111.51	110.33	111.23	27426394	0	111.23
AAPL	2016-11-25	111.13	111.87	110.95	111.79	11475922	0	111.79
AAPL	2016-11-28	111.43	112.47	111.39	111.57	27193983	0	111.57
AAPL	2016-11-29	110.78	112.03	110.07	111.46	28528750	0	111.46
AAPL	2016-11-30	111.56	112.2	110.27	110.52	36162258	0	110.52
AAPL	2016-12-01	110.37	110.94	109.03	109.49	37086862	0	109.49
AAPL	2016-12-02	109.17	110.09	108.85	109.9	26527997	0	109.9
AAPL	2016-12-05	110	110.03	108.25	109.11	34324540	0	109.11
AAPL	2016-12-06	109.5	110.36	109.19	109.95	26195462	0	109.95
AAPL	2016-12-07	109.26	111.19	109.16	111.03	29998719	0	111.03
AAPL	2016-12-08	110.86	112.43	110.6	112.12	27068316	0	112.12
AAPL	2016-12-09	112.31	114.7	112.31	113.95	34402627	0	113.95
AAPL	2016-12-12	113.29	115	112.49	113.3	26374377	0	113.3
AAPL	2016-12-13	113.84	115.92	113.75	115.19	43733811	0	115.19
AAPL	2016-12-14	115.04	116.2	114.98	115.19	34031834	0	115.19
AAPL	2016-12-15	115.38	116.73	115.23	115.82	46524544	0	115.82
AAPL	2016-12-16	116.47	116.5	115.65	115.97	44351134	0	115.97
AAPL	2016-12-19	115.8	117.38	115.75	116.64	27779423	0	116.64
AAPL	2016-12-20	116.74	117.5	116.68	116.95	21424965	0	116.95
AAPL	2016-12-21	116.8	117.4	116.78	117.06	23783165	0	117.06
AAPL	2016-12-22	116.35	116.51	115.64	116.29	26085854	0	116.29
AAPL	2016-12-23	115.59	116.52	115.59	116.52	14249484	0	116.52
AAPL	2016-12-27	116.52	117.8	116.49	117.26	18296855	0	117.26
AAPL	2016-12-28	117.52	118.02	116.2	116.76	20905892	0	116.76
AAPL	2016-12-29	116.45	117.11	116.4	116.73	15039519	0	116.73
AAPL	2016-12-30	116.65	117.2	115.43	115.82	30586265	0	115.82
AAPL	2017-01-03	115.8	116.33	114.76	116.15	28781865	0	116.15
AAPL	2017-01-04	115.85	116.51	115.75	116.02	21118116	0	116.02
AAPL	2017-01-05	115.92	116.86	115.81	116.61	22193587	0	116.61
AAPL	2017-01-06	116.78	118.16	116.47	117.91	31751900	0	117.91
AAPL	2017-01-09	117.95	119.43	117.94	118.99	33561948	0	118.99
AAPL	2017-01-10	118.77	119.38	118.3	119.11	24462051	0	119.11
AAPL	2017-01-11	118.74	119.93	118.6	119.75	27588593	0	119.75
AAPL	2017-01-12	118.9	119.3	118.21	119.25	27086220	0	119.25
AAPL	2017-01-13	119.11	119.62	118.81	119.04	26111948	0	119.04
AAPL	2017-01-17	118.34	120.24	118.22	120	34439843	0	120
AAPL	2017-01-18	120	120.5	119.71	119.99	23712961	0	119.99
AAPL	2017-01-19	119.4	120.09	119.37	119.78	25597291	0	119.78
AAPL	2017-01-20	120.45	120.45	119.74	120	32597892	0	120
AAPL	2017-01-23	120	120.81	119.77	120.08	22050218	0	120.08
AAPL	2017-01-24	119.55	120.1	119.5	119.97	23211038	0	119.97
AAPL	2017-01-25	120.42	122.1	120.28	121.88	32586673	0	121.88
AAPL	2017-01-26	121.67	122.44	121.6	121.94	26337576	0	121.94
AAPL	2017-01-27	122.14	122.35	121.6	121.95	20562944	0	121.95
AAPL	2017-01-30	120.93	121.63	120.66	121.63	30377503	0	121.63
AAPL	2017-01-31	121.15	121.39	120.62	121.35	49200993	0	121.35
AAPL	2017-02-01	127.03	130.49	127.01	128.75	111985040	0	128.75
AAPL	2017-02-02	127.98	129.39	127.78	128.53	33710411	0	128.53
AAPL	2017-02-03	128.31	129.19	128.16	129.08	24507301	0	129.08
AAPL	2017-02-06	129.13	130.5	128.9	130.29	26845924	0	130.29
AAPL	2017-02-07	130.54	132.09	130.45	131.53	38183841	0	131.53
AAPL	2017-02-08	131.35	132.22	131.22	132.04	23004072	0	132.04
AAPL	2017-02-09	131.65	132.44	131.12	132.42	28349859	0.57	132.42
AAPL	2017-02-10	132.46	132.94	132.05	132.12	20065458	0	132.12
AAPL	2017-02-13	133.08	133.82	132.75	133.29	23035421	0	133.29
AAPL	2017-02-14	133.47	135.09	133.25	135.02	33226223	0	135.02
AAPL	2017-02-15	135.52	136.27	134.62	135.51	35623100	0	135.51
AAPL	2017-02-16	135.67	135.9	134.84	135.34	22584555	0	135.34
AAPL	2017-02-17	135.1	135.83	135.1	135.72	22198197	0	135.72
AAPL	2017-02-21	136.23	136.75	135.98	136.7	24507156	0	136.7
AAPL	2017-02-22	136.43	137.12	136.11	137.11	20836932	0	137.11
AAPL	2017-02-23	137.38	137.48	136.3	136.53	20788186	0	136.53
AAPL	2017-02-24	135.91	136.66	135.28	136.66	21776585	0	136.66
AAPL	2017-02-27	137.14	137.44	136.28	136.93	20257426	0	136.93
AAPL	2017-02-28	137.08	137.44	136.7	136.99	23482860	0	136.99
AAPL	2017-03-01	137.89	140.15	137.59	139.79	36414585	0	139.79
AAPL	2017-03-02	140	140.28	138.76	138.96	26210984	0	138.96
AAPL	2017-03-03	138.78	139.83	138.59	139.78	21571121	0	139.78
AAPL	2017-03-06	139.37	139.77	138.6	139.34	21750044	0	139.34
AAPL	2017-03-07	139.06	139.98	138.79	139.52	17446297	0	139.52
AAPL	2017-03-08	138.95	139.8	138.82	139	18707236	0	139
AAPL	2017-03-09	138.74	138.79	137.05	138.68	22155904	0	138.68
AAPL	2017-03-10	139.25	139.36	138.64	139.14	19612801	0	139.14
AAPL	2017-03-13	138.85	139.43	138.82	139.2	17421717	0	139.2
AAPL	2017-03-14	139.3	139.65	138.84	138.99	15309065	0	138.99
AAPL	2017-03-15	139.41	140.75	139.03	140.46	25691774	0	140.46
AAPL	2017-03-16	140.72	141.02	140.26	140.69	19231998	0	140.69
AAPL	2017-03-17	141	141	139.89	139.99	43884952	0	139.99
AAPL	2017-03-20	140.4	141.5	140.23	141.46	21542038	0	141.46
AAPL	2017-03-21	142.11	142.8	139.73	139.84	39529912	0	139.84
AAPL	2017-03-22	139.84	141.6	139.76	141.42	25860165	0	141.42
AAPL	2017-03-23	141.26	141.58	140.61	140.92	20346301	0	140.92
AAPL	2017-03-24	141.5	141.74	140.35	140.64	22395563	0	140.64
AAPL	2017-03-27	139.39	141.22	138.62	140.88	23575094	0	140.88
AAPL	2017-03-28	140.91	144.04	140.62	143.8	33374805	0	143.8
AAPL	2017-03-29	143.68	144.49	143.19	144.12	29189955	0	144.12
AAPL	2017-03-30	144.19	144.5	143.5	143.93	21207252	0	143.93
AAPL	2017-03-31	143.72	144.27	143.01	143.66	19661651	0	143.66
AAPL	2017-04-03	143.71	144.12	143.05	143.7	19985714	0	143.7
AAPL	2017-04-04	143.25	144.89	143.17	144.77	19891354	0	144.77
AAPL	2017-04-05	144.22	145.46	143.81	144.02	27717854	0	144.02
AAPL	2017-04-06	144.29	144.52	143.45	143.66	21149034	0	143.66
AAPL	2017-04-07	143.73	144.18	143.27	143.34	16658543	0	143.34
AAPL	2017-04-10	143.6	143.88	142.9	143.17	18933397	0	143.17
AAPL	2017-04-11	142.94	143.35	140.06	141.63	30379376	0	141.63
AAPL	2017-04-12	141.6	142.15	141.01	141.8	20350000	0	141.8
AAPL	2017-04-13	141.91	142.38	141.05	141.05	17822880	0	141.05
AAPL	2017-04-17	141.48	141.88	140.87	141.83	16582094	0	141.83
AAPL	2017-04-18	141.41	142.04	141.11	141.2	14697544	0	141.2
AAPL	2017-04-19	141.88	142	140.45	140.68	17328375	0	140.68
AAPL	2017-04-20	141.22	142.92	141.16	142.44	23319562	0	142.44
AAPL	2017-04-21	142.44	142.68	141.85	142.27	17320928	0	142.27
AAPL	2017-04-24	143.5	143.95	143.18	143.64	17116599	0	143.64
AAPL	2017-04-25	143.91	144.9	143.87	144.53	18871501	0	144.53
AAPL	2017-04-26	144.47	144.6	143.38	143.68	20041241	0	143.68
AAPL	2017-04-27	143.92	144.16	143.31	143.79	14246347	0	143.79
AAPL	2017-04-28	144.09	144.3	143.27	143.65	20860358	0	143.65
AAPL	2017-05-01	145.1	147.2	144.96	146.58	33602943	0	146.58
AAPL	2017-05-02	147.54	148.09	146.84	147.51	45352194	0	147.51
AAPL	2017-05-03	145.59	147.49	144.27	147.06	45697034	0	147.06
AAPL	2017-05-04	146.52	147.14	145.81	146.53	23371872	0	146.53
AAPL	2017-05-05	146.76	148.98	146.76	148.96	27327725	0	148.96
AAPL	2017-05-08	149.03	153.7	149.03	153.01	48752413	0	153.01
AAPL	2017-05-09	153.87	154.88	153.45	153.99	39130363	0	153.99
AAPL	2017-05-10	153.63	153.94	152.11	153.26	25805692	0	153.26
AAPL	2017-05-11	152.45	154.07	152.31	153.95	27255058	0.63	153.95
AAPL	2017-05-12	154.7	156.42	154.67	156.1	32527017	0	156.1
AAPL	2017-05-15	156.01	156.65	155.05	155.7	26009719	0	155.7
AAPL	2017-05-16	155.94	156.06	154.72	155.47	20048478	0	155.47
AAPL	2017-05-17	153.6	154.57	149.71	150.25	50767678	0	150.25
AAPL	2017-05-18	151.27	153.34	151.13	152.54	33568215	0	152.54
AAPL	2017-05-19	153.38	153.98	152.63	153.06	26960788	0	153.06
AAPL	2017-05-22	154	154.58	152.91	153.99	22966437	0	153.99
AAPL	2017-05-23	154.9	154.9	153.31	153.8	19918871	0	153.8
AAPL	2017-05-24	153.84	154.17	152.67	153.34	19219154	0	153.34
AAPL	2017-05-25	153.73	154.35	153.03	153.87	19235598	0	153.87
AAPL	2017-05-26	154	154.24	153.31	153.61	21927637	0	153.61
AAPL	2017-05-30	153.42	154.43	153.33	153.67	20126851	0	153.67
AAPL	2017-05-31	153.97	154.17	152.38	152.76	24451164	0	152.76
AAPL	2017-06-01	153.17	153.33	152.22	153.18	16404088	0	153.18
AAPL	2017-06-02	153.58	155.45	152.89	155.45	27770715	0	155.45
AAPL	2017-06-05	154.34	154.45	153.46	153.93	25331662	0	153.93
AAPL	2017-06-06	153.9	155.81	153.78	154.45	26624926	0	154.45
AAPL	2017-06-07	155.02	155.98	154.48	155.37	21069647	0	155.37
AAPL	2017-06-08	155.25	155.54	154.4	154.99	21250798	0	154.99
AAPL	2017-06-09	155.19	155.19	146.02	148.98	64882657	0	148.98
AAPL	2017-06-12	145.74	146.09	142.51	145.42	72307330	0	145.42
AAPL	2017-06-13	147.16	147.45	145.15	146.59	34165445	0	146.59
AAPL	2017-06-14	147.5	147.5	143.84	145.16	31531232	0	145.16
AAPL	2017-06-15	143.32	144.48	142.21	144.29	32165373	0	144.29
AAPL	2017-06-16	143.78	144.5	142.2	142.27	50361093	0	142.27
AAPL	2017-06-19	143.66	146.74	143.66	146.34	32541404	0	146.34
AAPL	2017-06-20	146.87	146.87	144.94	145.01	24900073	0	145.01
AAPL	2017-06-21	145.52	146.07	144.61	145.87	21265751	0	145.87
AAPL	2017-06-22	145.77	146.7	145.12	145.63	19106294	0	145.63
AAPL	2017-06-23	145.13	147.16	145.11	146.28	35439389	0	146.28
AAPL	2017-06-26	147.17	148.28	145.38	145.82	25692361	0	145.82
AAPL	2017-06-27	145.01	146.16	143.62	143.73	24761891	0	143.73
AAPL	2017-06-28	144.49	146.11	143.16	145.83	22082432	0	145.83
AAPL	2017-06-29	144.71	145.13	142.28	143.68	31499368	0	143.68
AAPL	2017-06-30	144.45	144.96	143.78	144.02	23024107	0	144.02
AAPL	2017-07-03	144.88	145.3	143.1	143.5	14258300	0	143.5
AAPL	2017-07-05	143.69	144.79	142.72	144.09	21569557	0	144.09
AAPL	2017-07-06	143.02	143.5	142.41	142.73	24128782	0	142.73
AAPL	2017-07-07	142.9	144.75	142.9	144.18	19201712	0	144.18
AAPL	2017-07-10	144.11	145.95	143.37	145.06	21090636	0	145.06
AAPL	2017-07-11	144.73	145.85	144.38	145.53	19781836	0	145.53
AAPL	2017-07-12	145.87	146.18	144.82	145.74	24884478	0	145.74
AAPL	2017-07-13	145.5	148.49	145.44	147.77	25199373	0	147.77
AAPL	2017-07-14	147.97	149.33	147.33	149.04	20132061	0	149.04
AAPL	2017-07-17	148.82	150.9	148.57	149.56	23793456	0	149.56
AAPL	2017-07-18	149.2	150.13	148.67	150.08	17868792	0	150.08
AAPL	2017-07-19	150.48	151.42	149.95	151.02	20922969	0	151.02
AAPL	2017-07-20	151.5	151.74	150.19	150.34	17243748	0	150.34
AAPL	2017-07-21	149.99	150.44	148.88	150.27	26252630	0	150.27
AAPL	2017-07-24	150.58	152.44	149.9	152.09	21493160	0	152.09
AAPL	2017-07-25	151.8	153.84	151.8	152.74	18853932	0	152.74
AAPL	2017-07-26	153.35	153.93	153.06	153.46	15780951	0	153.46
AAPL	2017-07-27	153.75	153.99	147.3	150.56	32476337	0	150.56
AAPL	2017-07-28	149.89	150.23	149.19	149.5	17213653	0	149.5
AAPL	2017-07-31	149.9	150.33	148.13	148.73	19845920	0	148.73
AAPL	2017-08-01	149.1	150.22	148.41	150.05	35368645	0	150.05
AAPL	2017-08-02	159.28	159.75	156.16	157.14	69936800	0	157.14
AAPL	2017-08-03	157.05	157.21	155.02	155.57	27097296	0	155.57
AAPL	2017-08-04	156.07	157.4	155.69	156.39	20559852	0	156.39
AAPL	2017-08-07	157.06	158.92	156.67	158.81	21870321	0	158.81
AAPL	2017-08-08	158.6	161.83	158.27	160.08	36205896	0	160.08
AAPL	2017-08-09	159.26	161.27	159.11	161.06	26131530	0	161.06
AAPL	2017-08-10	159.9	160	154.63	155.32	40804273	0.63	155.32
AAPL	2017-08-11	156.6	158.57	156.07	157.48	26257096	0	157.48
AAPL	2017-08-14	159.32	160.21	158.75	159.85	22122734	0	159.85
AAPL	2017-08-15	160.66	162.19	160.14	161.6	29465487	0	161.6
AAPL	2017-08-16	161.94	162.51	160.15	160.95	27671612	0	160.95


"""