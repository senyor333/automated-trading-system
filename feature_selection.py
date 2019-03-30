selected_sf1_features = [
    "roaq", 
    "chtx",
    "rsup",
    "sue",
    "cinvest",
    "nincr",
    "roavol",
    "cashpr", 
    "cash", 
    "bm",
    "currat",
    "depr",
    "ep",
    "lev",
    "quick",
    "rd_sale", 
    "roic",
    "salecash",
    "saleinv",
    "salerec",
    "sp",
    "tb",
    "sin",
    "tang",
    "debtc_sale",
    "eqt_marketcap",
    "dep_ppne",
    "tangibles_marketcap",
    "agr",
    "cashdebt",
    "chcsho",
    "chinv",
    "egr",
    "gma",
    "invest",
    "lgr",
    "operprof",
    "pchcurrat",
    "pchdepr",
    "pchgm_pchsale",
    "pchquick",
    "pchsale_pchinvt",
    "pchsale_pchrect",
    "pchsale_pchxsga",
    "pchsaleinv",
    "rd",
    "roeq",
    "sgr",
    "grcapx",
    "chtl_lagat",
    "chlt_laginvcap",
    "chlct_lagat",
    "chint_lagat",
    "chinvt_lagsale",
    "chint_lagsgna",
    "chltc_laginvcap",
    "chint_laglt",
    "chdebtnc_lagat",
    "chinvt_lagcor",
    "chppne_laglt", 
    "chpay_lagact",
    "chint_laginvcap",
    "chinvt_lagact",
    "pchppne", "pchlt",
    "pchint",
    "chdebtnc_ppne",
    "chdebtc_sale",
    "age",
    "ipo",
    # "profitmargin",
    # "chprofitmargin",
    # "industry",
    # "change_sales",
    "ps"
]


selected_industry_sf1_features = [
    "bm_ia",
    "cfp_ia",
    "chatoia",
    "mve_ia",
    "pchcapex_ia",
    "chpmia",
    "herf",
    "ms"
]

selected_sep_features = [
    "industry",
    # "sector",
    # "siccode",
    # Need for industry calculation
    # "mom12m_actual",
    "indmom",
    # Needed for beta calculation
    # "mom1w",
    # "mom1w_ewa_market", # This is used for idiovol
    # Calculated using forward filling and matrix multiplication
    "mom1m",
    "mom6m",
    "mom12m",
    "mom24m",
    # "mom12m_to_7m",
    "chmom",
    # Calculated only for samples
    "mve",
    "beta",
    "betasq",
    "idiovol",
    "ill",
    "dy",
    "turn",
    "dolvol",
    "maxret",
    "retvol",
    "std_dolvol",
    "std_turn",
    "zerotrade",
    # Labels
    "return_1m",
    "return_2m",
    "return_3m",
]