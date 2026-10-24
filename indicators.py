"""
indicators.py - THE SETTINGS FILE.

Every indicator on the dashboard is one entry in the INDICATORS list below.
To add a new one, copy an existing entry, paste it underneath and change the details.

What each field means
---------------------
id         : a short unique name used to link indicators together (no spaces)
ticker     : the code you type in the command bar, e.g. UKCPI (capitals, no spaces)
region     : "US", "UK", "Markets" or "FX" (decides which page it appears on)
group      : a heading to group related indicators, e.g. "Inflation"
name       : the label shown on the dashboard
source     : where the data comes from
               "fred"    - St. Louis Fed (US data, needs your free API key)
               "ons"     - Office for National Statistics (UK data, no key)
               "boe"     - Bank of England (UK rates, no key)
               "yahoo"   - Yahoo Finance (market prices, no key, unofficial)
               "derived" - calculated from two other indicators, e.g. "uk_bankrate - uk_cpi"
code       : the series ID at that source (e.g. "UNRATE" on FRED)
dataset    : ONS only - the dataset the series lives in (e.g. "mm23")
topic      : ONS only - the part of the ONS website address before /timeseries/
transform  : "level" (as published), "change" (vs previous period) or "yoy" (% vs a year ago)
scale      : optional - multiply the numbers, e.g. 0.001 to turn millions into billions
unit       : shown after the number, e.g. "%" or "k"
decimals   : how many decimal places to show
good_when  : "up", "down" or "neutral" - colours the change green/red
chart      : "line" or "bar"
forecast   : True to show a forecast (only works if it also has SIGNALS below)
"""

INDICATORS = [
    # ================================================================== US
    dict(id="us_payrolls", ticker="USNFP", region="US", group="Labour market",
         name="Non-farm payrolls (monthly change)", source="fred", code="PAYEMS",
         transform="change", unit="k", decimals=0, good_when="up", chart="bar", forecast=True),
    dict(id="us_unemp", ticker="USUR", region="US", group="Labour market",
         name="Unemployment rate", source="fred", code="UNRATE",
         transform="level", unit="%", decimals=1, good_when="down", chart="line", forecast=True),
    dict(id="us_claims", ticker="USCLAIMS", region="US", group="Labour market",
         name="Initial jobless claims (weekly)", source="fred", code="ICSA",
         transform="level", scale=0.001, unit="k", decimals=0, good_when="down", chart="line",
         forecast=True),
    dict(id="us_cpi", ticker="USCPI", region="US", group="Inflation",
         name="CPI inflation", source="fred", code="CPIAUCSL",
         transform="yoy", unit="%", decimals=1, good_when="neutral", chart="line", forecast=True),
    dict(id="us_core_cpi", ticker="USCORE", region="US", group="Inflation",
         name="Core CPI inflation", source="fred", code="CPILFESL",
         transform="yoy", unit="%", decimals=1, good_when="neutral", chart="line", forecast=True),
    dict(id="us_gdp", ticker="USGDP", region="US", group="Growth",
         name="Real GDP growth (annualised, q/q)", source="fred", code="A191RL1Q225SBEA",
         transform="level", unit="%", decimals=1, good_when="up", chart="bar", forecast=True),
    dict(id="us_indpro", ticker="USIP", region="US", group="Growth",
         name="Industrial production (y/y)", source="fred", code="INDPRO",
         transform="yoy", unit="%", decimals=1, good_when="up", chart="line", forecast=True),
    dict(id="us_retail", ticker="USRETAIL", region="US", group="Consumer",
         name="Retail sales (y/y)", source="fred", code="RSAFS",
         transform="yoy", unit="%", decimals=1, good_when="up", chart="line", forecast=True),
    dict(id="us_sentiment", ticker="USSENT", region="US", group="Consumer",
         name="Consumer sentiment (UMich)", source="fred", code="UMCSENT",
         transform="level", unit="", decimals=1, good_when="up", chart="line", forecast=True),
    dict(id="us_housing", ticker="USHOUSE", region="US", group="Housing",
         name="Housing starts (annualised)", source="fred", code="HOUST",
         transform="level", unit="k", decimals=0, good_when="up", chart="line", forecast=True),
    dict(id="us_mortgage", ticker="USMORT", region="US", group="Housing",
         name="30-year mortgage rate", source="fred", code="MORTGAGE30US",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="us_trade", ticker="USTRADE", region="US", group="Trade",
         name="Trade balance ($bn)", source="fred", code="BOPGSTB",
         transform="level", scale=0.001, unit="bn", decimals=1, good_when="up", chart="bar",
         forecast=False),
    dict(id="us_m2", ticker="USM2", region="US", group="Money & credit",
         name="M2 money supply (y/y)", source="fred", code="M2SL",
         transform="yoy", unit="%", decimals=1, good_when="neutral", chart="line", forecast=False),
    dict(id="us_hy", ticker="USHY", region="US", group="Money & credit",
         name="High-yield credit spread", source="fred", code="BAMLH0A0HYM2",
         transform="level", unit="%", decimals=2, good_when="down", chart="line", forecast=False),
    dict(id="us_fedfunds", ticker="FEDF", region="US", group="Rates",
         name="Fed funds rate (effective)", source="fred", code="FEDFUNDS",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="us_real_ff", ticker="USREAL", region="US", group="Rates",
         name="Real Fed funds rate (minus CPI)", source="derived", code="us_fedfunds - us_cpi",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="us_10y", ticker="UST10", region="US", group="Rates",
         name="10-year Treasury yield", source="fred", code="DGS10",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="us_2s10s", ticker="US2S10S", region="US", group="Rates",
         name="2s10s spread (10y minus 2y)", source="fred", code="T10Y2Y",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="us_3m10y", ticker="US3M10Y", region="US", group="Rates",
         name="3m10y spread (10y minus 3m)", source="fred", code="T10Y3M",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),

    # ================================================================== UK
    dict(id="uk_gdp", ticker="UKGDP", region="UK", group="Growth", name="GDP growth (q/q)",
         source="ons", code="IHYQ", dataset="qna", topic="economy/grossdomesticproductgdp",
         transform="level", unit="%", decimals=1, good_when="up", chart="bar", forecast=True),
    dict(id="uk_iop", ticker="UKIP", region="UK", group="Growth",
         name="Index of production (y/y)", source="ons", code="K222", dataset="diop",
         topic="economy/economicoutputandproductivity/output",
         transform="yoy", unit="%", decimals=1, good_when="up", chart="line", forecast=True),
    dict(id="uk_cpi", ticker="UKCPI", region="UK", group="Inflation", name="CPI inflation",
         source="ons", code="D7G7", dataset="mm23", topic="economy/inflationandpriceindices",
         transform="level", unit="%", decimals=1, good_when="neutral", chart="line", forecast=True),
    dict(id="uk_unemp", ticker="UKUR", region="UK", group="Labour market",
         name="Unemployment rate (16+)", source="ons", code="MGSX", dataset="lms",
         topic="employmentandlabourmarket/peoplenotinwork/unemployment",
         transform="level", unit="%", decimals=1, good_when="down", chart="line", forecast=True),
    dict(id="uk_emp", ticker="UKEMP", region="UK", group="Labour market",
         name="Employment rate (16-64)", source="ons", code="LF24", dataset="lms",
         topic="employmentandlabourmarket/peopleinwork/employmentandemployeetypes",
         transform="level", unit="%", decimals=1, good_when="up", chart="line", forecast=True),
    dict(id="uk_pay", ticker="UKPAY", region="UK", group="Labour market",
         name="Regular pay growth (3m avg, y/y)", source="ons", code="KAI9", dataset="lms",
         topic="employmentandlabourmarket/peopleinwork/earningsandworkinghours",
         transform="level", unit="%", decimals=1, good_when="neutral", chart="line", forecast=True),
    dict(id="uk_retail", ticker="UKRETAIL", region="UK", group="Consumer",
         name="Retail sales volume (y/y)", source="ons", code="J5EK", dataset="drsi",
         topic="businessindustryandtrade/retailindustry",
         transform="yoy", unit="%", decimals=1, good_when="up", chart="line", forecast=True),
    dict(id="uk_trade", ticker="UKTRADE", region="UK", group="Trade",
         name="Trade balance (£bn)", source="ons", code="IKBJ", dataset="mret",
         topic="economy/nationalaccounts/balanceofpayments",
         transform="level", scale=0.001, unit="bn", decimals=1, good_when="up", chart="bar",
         forecast=False),
    dict(id="uk_bankrate", ticker="UKBR", region="UK", group="Rates", name="Bank Rate",
         source="boe", code="IUDBEDR",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="uk_real_rate", ticker="UKREAL", region="UK", group="Rates",
         name="Real Bank Rate (minus CPI)", source="derived", code="uk_bankrate - uk_cpi",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="uk_10y", ticker="GILT10", region="UK", group="Rates", name="10-year gilt yield",
         source="boe", code="IUDMNZC",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="uk_us_spread", ticker="GILTUST", region="UK", group="Rates",
         name="Gilt minus Treasury (10y)", source="derived", code="uk_10y - us_10y",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),

    # ================================================================== Euro area
    # "ecb" = European Central Bank Data Portal (no key). code = "<dataset>/<series key>"
    dict(id="ea_hicp", ticker="EAHICP", region="EA", group="Inflation",
         name="HICP inflation", source="ecb", code="ICP/M.U2.N.000000.4.ANR",
         transform="level", unit="%", decimals=1, good_when="neutral", chart="line", forecast=True),
    dict(id="ea_core", ticker="EACORE", region="EA", group="Inflation",
         name="Core HICP (ex energy & food)", source="ecb", code="ICP/M.U2.N.XEF000.4.ANR",
         transform="level", unit="%", decimals=1, good_when="neutral", chart="line", forecast=False),
    dict(id="ea_unemp", ticker="EAUR", region="EA", group="Labour market",
         name="Unemployment rate", source="ecb", code="LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T",
         transform="level", unit="%", decimals=1, good_when="down", chart="line", forecast=False),
    dict(id="ecb_dfr", ticker="ECBDFR", region="EA", group="Rates",
         name="ECB deposit facility rate", source="fred", code="ECBDFR",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="ea_real_rate", ticker="EAREAL", region="EA", group="Rates",
         name="Real ECB rate (minus HICP)", source="derived", code="ecb_dfr - ea_hicp",
         transform="level", unit="%", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="stoxx50", ticker="SX5E", region="EA", group="Markets",
         name="Euro Stoxx 50", source="yahoo", code="^STOXX50E", transform="level", unit="",
         decimals=0, good_when="up", chart="line", forecast=False),

    # ================================================================== Markets
    dict(id="ftse100", ticker="UKX", region="Markets", group="Equities", name="FTSE 100",
         source="yahoo", code="^FTSE", transform="level", unit="", decimals=0,
         good_when="up", chart="line", forecast=False),
    dict(id="ftse250", ticker="MCX", region="Markets", group="Equities", name="FTSE 250",
         source="yahoo", code="^FTMC", transform="level", unit="", decimals=0,
         good_when="up", chart="line", forecast=False),
    dict(id="sp500", ticker="SPX", region="Markets", group="Equities", name="S&P 500",
         source="fred", code="SP500", transform="level", unit="", decimals=0,
         good_when="up", chart="line", forecast=False),
    dict(id="nasdaq", ticker="CCMP", region="Markets", group="Equities", name="Nasdaq Composite",
         source="fred", code="NASDAQCOM", transform="level", unit="", decimals=0,
         good_when="up", chart="line", forecast=False),
    dict(id="dax", ticker="DAX", region="Markets", group="Equities", name="DAX (Germany)",
         source="yahoo", code="^GDAXI", transform="level", unit="", decimals=0,
         good_when="up", chart="line", forecast=False),
    dict(id="nikkei", ticker="NKY", region="Markets", group="Equities", name="Nikkei 225 (Japan)",
         source="yahoo", code="^N225", transform="level", unit="", decimals=0,
         good_when="up", chart="line", forecast=False),
    dict(id="vix", ticker="VIX", region="Markets", group="Equities", name="VIX (volatility)",
         source="fred", code="VIXCLS", transform="level", unit="", decimals=1,
         good_when="down", chart="line", forecast=False),
    dict(id="brent", ticker="BRENT", region="Markets", group="Commodities",
         name="Brent crude ($/barrel)", source="fred", code="DCOILBRENTEU",
         transform="level", unit="", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="wti", ticker="WTI", region="Markets", group="Commodities",
         name="WTI crude ($/barrel)", source="fred", code="DCOILWTICO",
         transform="level", unit="", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="natgas", ticker="NATGAS", region="Markets", group="Commodities",
         name="US natural gas ($/MMBtu)", source="fred", code="DHHNGSP",
         transform="level", unit="", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="gold", ticker="GOLD", region="Markets", group="Commodities",
         name="Gold ($/oz, futures)", source="yahoo", code="GC=F",
         transform="level", unit="", decimals=0, good_when="neutral", chart="line", forecast=False),
    dict(id="copper", ticker="COPPER", region="Markets", group="Commodities",
         name="Copper ($/lb, futures)", source="yahoo", code="HG=F",
         transform="level", unit="", decimals=2, good_when="neutral", chart="line", forecast=False),
    dict(id="cu_au", ticker="CUAU", region="Markets", group="Commodities",
         name="Copper/gold ratio (x1000, growth signal)", source="derived", code="copper / gold",
         scale=1000, transform="level", unit="", decimals=3, good_when="up", chart="line",
         forecast=False),

    # ================================================================== FX
    dict(id="gbpusd", ticker="GBPUSD", region="FX", group="Sterling", name="GBP/USD",
         source="fred", code="DEXUSUK", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="gbpeur", ticker="GBPEUR", region="FX", group="Sterling", name="GBP/EUR",
         source="fred_ratio", code="DEXUSUK/DEXUSEU", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="eurusd", ticker="EURUSD", region="FX", group="Majors", name="EUR/USD",
         source="fred", code="DEXUSEU", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdjpy", ticker="USDJPY", region="FX", group="Majors", name="USD/JPY",
         source="fred", code="DEXJPUS", transform="level", unit="", decimals=2,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdcny", ticker="USDCNY", region="FX", group="Majors", name="USD/CNY",
         source="fred", code="DEXCHUS", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="dxy", ticker="DXY", region="FX", group="Majors",
         name="US dollar index (broad, trade-weighted)", source="fred", code="DTWEXBGS",
         transform="level", unit="", decimals=2, good_when="neutral", chart="line",
         forecast=False),
    dict(id="gbpjpy", ticker="GBPJPY", region="FX", group="Sterling", name="GBP/JPY",
         source="derived", code="gbpusd * usdjpy", transform="level", unit="", decimals=2,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdchf", ticker="USDCHF", region="FX", group="Majors", name="USD/CHF",
         source="fred", code="DEXSZUS", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdcad", ticker="USDCAD", region="FX", group="Commodity currencies", name="USD/CAD",
         source="fred", code="DEXCAUS", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="audusd", ticker="AUDUSD", region="FX", group="Commodity currencies", name="AUD/USD",
         source="fred", code="DEXUSAL", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="nzdusd", ticker="NZDUSD", region="FX", group="Commodity currencies", name="NZD/USD",
         source="fred", code="DEXUSNZ", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdnok", ticker="USDNOK", region="FX", group="Commodity currencies", name="USD/NOK",
         source="fred", code="DEXNOUS", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdinr", ticker="USDINR", region="FX", group="Emerging markets", name="USD/INR",
         source="fred", code="DEXINUS", transform="level", unit="", decimals=2,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdmxn", ticker="USDMXN", region="FX", group="Emerging markets", name="USD/MXN",
         source="fred", code="DEXMXUS", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdbrl", ticker="USDBRL", region="FX", group="Emerging markets", name="USD/BRL",
         source="fred", code="DEXBZUS", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdkrw", ticker="USDKRW", region="FX", group="Emerging markets", name="USD/KRW",
         source="fred", code="DEXKOUS", transform="level", unit="", decimals=1,
         good_when="neutral", chart="line", forecast=False),
    dict(id="usdzar", ticker="USDZAR", region="FX", group="Emerging markets", name="USD/ZAR",
         source="fred", code="DEXSFUS", transform="level", unit="", decimals=4,
         good_when="neutral", chart="line", forecast=False),
]

# --------------------------------------------------------------------------
# STAR RATINGS - five related indicators checked for each forecast.
# (indicator id, relationship): +1 = moves the same way, -1 = moves the opposite way.
# Stars = how many of the five point the same way as the forecast.
# --------------------------------------------------------------------------
SIGNALS = {
    "us_gdp":       [("us_payrolls", +1), ("us_unemp", -1), ("us_retail", +1),
                     ("us_2s10s", +1), ("sp500", +1)],
    "us_unemp":     [("us_payrolls", -1), ("us_claims", +1), ("us_retail", -1),
                     ("sp500", -1), ("vix", +1)],
    "us_payrolls":  [("us_unemp", -1), ("us_claims", -1), ("us_retail", +1),
                     ("sp500", +1), ("us_2s10s", +1)],
    "us_claims":    [("us_payrolls", -1), ("us_indpro", -1), ("sp500", -1),
                     ("us_hy", +1), ("us_sentiment", -1)],
    "us_cpi":       [("us_core_cpi", +1), ("brent", +1), ("us_unemp", -1),
                     ("us_retail", +1), ("us_fedfunds", -1)],
    "us_core_cpi":  [("us_cpi", +1), ("us_unemp", -1), ("us_retail", +1),
                     ("us_fedfunds", -1), ("us_payrolls", +1)],
    "us_indpro":    [("us_payrolls", +1), ("us_claims", -1), ("us_sentiment", +1),
                     ("us_2s10s", +1), ("copper", +1)],
    "us_retail":    [("us_payrolls", +1), ("us_unemp", -1), ("sp500", +1),
                     ("us_fedfunds", -1), ("us_cpi", -1)],
    "us_sentiment": [("sp500", +1), ("us_cpi", -1), ("us_unemp", -1),
                     ("us_mortgage", -1), ("us_payrolls", +1)],
    "us_housing":   [("us_mortgage", -1), ("us_sentiment", +1), ("us_payrolls", +1),
                     ("us_fedfunds", -1), ("sp500", +1)],
    "uk_gdp":       [("uk_retail", +1), ("uk_unemp", -1), ("uk_emp", +1),
                     ("ftse250", +1), ("uk_bankrate", -1)],
    "uk_iop":       [("uk_gdp", +1), ("copper", +1), ("gbpusd", -1),
                     ("uk_bankrate", -1), ("ftse250", +1)],
    "uk_unemp":     [("uk_emp", -1), ("uk_gdp", -1), ("uk_retail", -1),
                     ("ftse250", -1), ("uk_pay", -1)],
    "uk_emp":       [("uk_unemp", -1), ("uk_gdp", +1), ("uk_retail", +1),
                     ("ftse250", +1), ("uk_pay", +1)],
    "uk_pay":       [("uk_unemp", -1), ("uk_emp", +1), ("uk_cpi", +1),
                     ("uk_gdp", +1), ("uk_bankrate", +1)],
    "uk_cpi":       [("uk_pay", +1), ("brent", +1), ("gbpusd", -1),
                     ("uk_unemp", -1), ("uk_retail", +1)],
    "uk_retail":    [("uk_pay", +1), ("uk_unemp", -1), ("uk_bankrate", -1),
                     ("ftse250", +1), ("uk_cpi", -1)],
    "ea_hicp":      [("ea_core", +1), ("brent", +1), ("ea_unemp", -1),
                     ("ecb_dfr", -1), ("eurusd", -1)],
}

# --------------------------------------------------------------------------
# RECESSION SHADING
# US: official NBER dates. UK: "technical recession" = 2+ quarters of falling GDP.
# --------------------------------------------------------------------------
RECESSIONS = {
    "US": dict(source="fred", code="USREC", label="US recessions (NBER)"),
    "UK": dict(source="derived", from_id="uk_gdp",
               label="UK recessions (2+ quarters of falling GDP)"),
}

# Market and economic events that can be marked on charts
EVENTS = [
    ("1973-10-17", "Oil embargo"),
    ("1979-10-06", "Volcker shock"),
    ("1987-10-19", "Black Monday"),
    ("1992-09-16", "Black Wednesday"),
    ("2000-03-10", "Dot-com peak"),
    ("2001-09-11", "9/11"),
    ("2008-09-15", "Lehman collapse"),
    ("2016-06-23", "Brexit vote"),
    ("2020-03-11", "COVID pandemic"),
    ("2022-02-24", "Russia invades Ukraine"),
    ("2022-09-23", "UK mini-budget"),
]

# Yield curves: (maturity label, series code) from short to long.
YIELD_CURVES = {
    "US Treasuries": dict(source="fred", points=[
        ("1M", "DGS1MO"), ("3M", "DGS3MO"), ("6M", "DGS6MO"), ("1Y", "DGS1"),
        ("2Y", "DGS2"), ("5Y", "DGS5"), ("10Y", "DGS10"), ("30Y", "DGS30"),
    ]),
    "UK gilts (nominal zero coupon)": dict(source="boe", points=[
        ("5Y", "IUDSNZC"), ("10Y", "IUDMNZC"), ("20Y", "IUDLNZC"),
    ]),
}

# Currencies in the FX snapshot (all quoted as 1 GBP = x)
FX_TABLE_CURRENCIES = ["USD", "EUR", "JPY", "CHF", "CAD", "AUD", "CNY", "INR"]

# --------------------------------------------------------------------------
# NEWS - RSS feeds (headlines and links only). Add or remove feeds freely.
# --------------------------------------------------------------------------
NEWS_FEEDS = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Guardian Economics", "https://www.theguardian.com/business/economics/rss"),
    ("Guardian Business", "https://www.theguardian.com/uk/business/rss"),
    ("CNBC Economy", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("Bank of England", "https://www.bankofengland.co.uk/rss/news"),
    ("ECB", "https://www.ecb.europa.eu/rss/press.html"),
    ("IMF", "https://www.imf.org/en/News/rss?language=eng"),
    ("WTO", "https://www.wto.org/library/rss/latest_news_e.xml"),
]

# Words used to sort headlines into topics
NEWS_TOPICS = {
    "FX": ["pound", "sterling", "dollar", "euro", "yen", "yuan", "currency", "currencies",
           "exchange rate", "forex", " fx"],
    "Growth": ["gdp", "growth", "recession", "economy", "economic", "output", "forecast",
               "slowdown", "jobs", "unemployment", "productivity"],
    "Trade": ["trade", "tariff", "export", "import", "wto", "supply chain", "shipping",
              "customs", "sanction"],
    "Central banks": ["interest rate", "rates", "fed ", "federal reserve", "bank of england",
                      "ecb", "inflation", "mpc", "fomc", "monetary", "rate cut", "rate rise",
                      "hike"],
    "Markets": ["stocks", "shares", "ftse", "s&p", "nasdaq", "bond", "gilt", "treasury",
                "oil", "gold", "market"],
}

# --------------------------------------------------------------------------
# GLOBAL - IMF World Economic Outlook data (actuals and IMF forecasts)
# --------------------------------------------------------------------------
IMF_INDICATORS = {
    "NGDP_RPCH": ("Real GDP growth", "%"),
    "PCPIPCH": ("Inflation", "%"),
    "LUR": ("Unemployment rate", "%"),
    "BCA_NGDPD": ("Current account balance (% of GDP)", "%"),
    "GGXWDG_NGDP": ("Government debt (% of GDP)", "%"),
}
MAJOR_ECONOMIES = ["USA", "CHN", "DEU", "JPN", "IND", "GBR", "FRA", "ITA", "CAN", "BRA",
                   "RUS", "KOR", "AUS", "MEX", "ESP", "IDN", "NLD", "SAU", "TUR", "CHE"]

# --------------------------------------------------------------------------
# CALENDAR - key US releases picked out of FRED's release calendar
# --------------------------------------------------------------------------
CALENDAR_RELEASES = [
    "Employment Situation", "Consumer Price Index", "Gross Domestic Product",
    "Advance Monthly Sales for Retail", "Industrial Production", "Personal Income and Outlays",
    "Job Openings and Labor Turnover", "Unemployment Insurance Weekly Claims",
    "New Residential Construction", "Producer Price Index", "International Trade",
    "FOMC", "University of Michigan", "Existing Home Sales",
]

# --------------------------------------------------------------------------
# SHADING options for charts. Each finds periods from an indicator using a rule:
#   ("recession", "US"/"UK")       official / technical recessions
#   ("rising"/"falling", id, step) rate up/down by at least `step` over 6 months
#   ("below"/"above", id, level)   indicator under / over a level
#   ("drawdown", id, pct)          market at least pct% below its previous peak
# --------------------------------------------------------------------------
SHADES = {
    "US recessions":           (("recession", "US"), "rgba(139,148,158,0.20)"),
    "UK recessions":           (("recession", "UK"), "rgba(139,148,158,0.20)"),
    "Fed hiking cycles":       (("rising", "us_fedfunds", 0.5), "rgba(242,84,91,0.14)"),
    "Fed cutting cycles":      (("falling", "us_fedfunds", 0.5), "rgba(47,191,113,0.14)"),
    "BoE hiking cycles":       (("rising", "uk_bankrate", 0.5), "rgba(242,84,91,0.14)"),
    "BoE cutting cycles":      (("falling", "uk_bankrate", 0.5), "rgba(47,191,113,0.14)"),
    "US yield curve inverted": (("below", "us_2s10s", 0.0), "rgba(180,140,255,0.16)"),
    "S&P 500 bear markets":    (("drawdown", "sp500", 20), "rgba(242,84,91,0.16)"),
    "VIX above 30 (stress)":   (("above", "vix", 30), "rgba(255,159,26,0.16)"),
    "US inflation above 4%":   (("above", "us_cpi", 4), "rgba(255,159,26,0.12)"),
    "UK inflation above 4%":   (("above", "uk_cpi", 4), "rgba(255,159,26,0.12)"),
}

# Level lines offered automatically on some charts (id: [(value, label)])
REFERENCE_LINES = {
    "us_cpi": [(2.0, "Fed 2% target")], "us_core_cpi": [(2.0, "Fed 2% target")],
    "uk_cpi": [(2.0, "BoE 2% target")], "ea_hicp": [(2.0, "ECB 2% target")],
    "ea_core": [(2.0, "ECB 2% target")], "vix": [(20, "long-run average ~20"), (30, "stress")],
    "us_2s10s": [(0.0, "inversion")], "us_3m10y": [(0.0, "inversion")],
}

# --------------------------------------------------------------------------
# NEWS SEARCH - what to search Google News for on each full-screen chart.
# Anything not listed searches for the indicator's name.
# --------------------------------------------------------------------------
NEWS_QUERIES = {
    "gbpusd": "sterling dollar OR GBP/USD OR pound dollar",
    "gbpeur": "sterling euro OR GBP/EUR OR pound euro",
    "gbpjpy": "pound yen OR GBP/JPY",
    "eurusd": "euro dollar OR EUR/USD",
    "usdjpy": "yen dollar OR USD/JPY OR Bank of Japan",
    "usdcny": "yuan dollar OR renminbi OR USD/CNY",
    "usdchf": "Swiss franc OR USD/CHF OR SNB",
    "usdcad": "Canadian dollar OR loonie OR USD/CAD",
    "audusd": "Australian dollar OR AUD/USD OR RBA",
    "nzdusd": "New Zealand dollar OR kiwi dollar OR RBNZ",
    "usdnok": "Norwegian krone OR Norges Bank",
    "usdinr": "Indian rupee OR RBI rupee",
    "usdmxn": "Mexican peso OR Banxico",
    "usdbrl": "Brazilian real OR Brazil central bank",
    "usdkrw": "Korean won OR Bank of Korea",
    "usdzar": "South African rand OR SARB",
    "dxy": "dollar index OR US dollar strength",
    "uk_cpi": "UK inflation CPI", "us_cpi": "US inflation CPI", "us_core_cpi": "US core inflation",
    "uk_bankrate": "Bank of England interest rate", "us_fedfunds": "Federal Reserve interest rate",
    "ecb_dfr": "ECB interest rate", "ea_hicp": "eurozone inflation",
    "uk_gdp": "UK GDP economy", "us_gdp": "US GDP economy", "us_payrolls": "US jobs report payrolls",
    "uk_unemp": "UK unemployment labour market", "us_unemp": "US unemployment rate",
    "brent": "oil prices Brent", "wti": "oil prices WTI", "gold": "gold price",
    "copper": "copper price", "natgas": "natural gas prices",
    "ftse100": "FTSE 100", "ftse250": "FTSE 250", "sp500": "S&P 500 stocks",
    "nasdaq": "Nasdaq stocks", "vix": "VIX volatility stocks", "uk_10y": "gilt yields",
    "us_10y": "Treasury yields", "uk_trade": "UK trade deficit", "us_trade": "US trade deficit tariffs",
}

# --------------------------------------------------------------------------
# COUNTRY PROFILES - free sources for each country.
#   bis: country code for BIS central bank rates (XM = euro area)
#   fx: (FRED code, "per_usd" or "usd_per") - how the FRED rate is quoted
#   equity: Yahoo Finance index ticker
# --------------------------------------------------------------------------
COUNTRIES = {
    "USA": dict(name="United States", bis="US", fx=None, equity="^GSPC", ccy="USD"),
    "GBR": dict(name="United Kingdom", bis="GB", fx=("DEXUSUK", "usd_per"), equity="^FTSE", ccy="GBP"),
    "DEU": dict(name="Germany", bis="XM", fx=("DEXUSEU", "usd_per"), equity="^GDAXI", ccy="EUR"),
    "FRA": dict(name="France", bis="XM", fx=("DEXUSEU", "usd_per"), equity="^FCHI", ccy="EUR"),
    "ITA": dict(name="Italy", bis="XM", fx=("DEXUSEU", "usd_per"), equity="FTSEMIB.MI", ccy="EUR"),
    "ESP": dict(name="Spain", bis="XM", fx=("DEXUSEU", "usd_per"), equity="^IBEX", ccy="EUR"),
    "NLD": dict(name="Netherlands", bis="XM", fx=("DEXUSEU", "usd_per"), equity="^AEX", ccy="EUR"),
    "CHE": dict(name="Switzerland", bis="CH", fx=("DEXSZUS", "per_usd"), equity="^SSMI", ccy="CHF"),
    "SWE": dict(name="Sweden", bis="SE", fx=("DEXSDUS", "per_usd"), equity="^OMX", ccy="SEK"),
    "NOR": dict(name="Norway", bis="NO", fx=("DEXNOUS", "per_usd"), equity=None, ccy="NOK"),
    "JPN": dict(name="Japan", bis="JP", fx=("DEXJPUS", "per_usd"), equity="^N225", ccy="JPY"),
    "CHN": dict(name="China", bis="CN", fx=("DEXCHUS", "per_usd"), equity="000001.SS", ccy="CNY"),
    "IND": dict(name="India", bis="IN", fx=("DEXINUS", "per_usd"), equity="^BSESN", ccy="INR"),
    "KOR": dict(name="South Korea", bis="KR", fx=("DEXKOUS", "per_usd"), equity="^KS11", ccy="KRW"),
    "AUS": dict(name="Australia", bis="AU", fx=("DEXUSAL", "usd_per"), equity="^AXJO", ccy="AUD"),
    "NZL": dict(name="New Zealand", bis="NZ", fx=("DEXUSNZ", "usd_per"), equity="^NZ50", ccy="NZD"),
    "CAN": dict(name="Canada", bis="CA", fx=("DEXCAUS", "per_usd"), equity="^GSPTSE", ccy="CAD"),
    "BRA": dict(name="Brazil", bis="BR", fx=("DEXBZUS", "per_usd"), equity="^BVSP", ccy="BRL"),
    "MEX": dict(name="Mexico", bis="MX", fx=("DEXMXUS", "per_usd"), equity="^MXX", ccy="MXN"),
    "ZAF": dict(name="South Africa", bis="ZA", fx=("DEXSFUS", "per_usd"), equity=None, ccy="ZAR"),
}

# World Equity Monitor (Yahoo Finance tickers)
EQUITY_MONITOR = {
    "Americas": [("^GSPC", "S&P 500"), ("^DJI", "Dow Jones"), ("^IXIC", "Nasdaq Composite"),
                 ("^RUT", "Russell 2000"), ("^GSPTSE", "S&P/TSX (Canada)"),
                 ("^BVSP", "Ibovespa (Brazil)"), ("^MXX", "IPC (Mexico)")],
    "Europe": [("^FTSE", "FTSE 100"), ("^FTMC", "FTSE 250"), ("^GDAXI", "DAX"),
               ("^FCHI", "CAC 40"), ("^STOXX50E", "Euro Stoxx 50"), ("FTSEMIB.MI", "FTSE MIB (Italy)"),
               ("^IBEX", "IBEX 35 (Spain)"), ("^AEX", "AEX (Netherlands)"), ("^SSMI", "SMI (Switzerland)")],
    "Asia-Pacific": [("^N225", "Nikkei 225"), ("^HSI", "Hang Seng"), ("000001.SS", "Shanghai Composite"),
                     ("^KS11", "KOSPI (Korea)"), ("^TWII", "Taiwan Weighted"), ("^BSESN", "Sensex (India)"),
                     ("^AXJO", "ASX 200 (Australia)")],
}

# Commodities Monitor (Yahoo Finance front-month futures)
COMMODITY_MONITOR = {
    "Energy": [("BZ=F", "Brent crude"), ("CL=F", "WTI crude"), ("NG=F", "US natural gas"),
               ("RB=F", "Gasoline (RBOB)"), ("HO=F", "Heating oil")],
    "Metals": [("GC=F", "Gold"), ("SI=F", "Silver"), ("PL=F", "Platinum"), ("HG=F", "Copper")],
    "Agriculture": [("ZW=F", "Wheat"), ("ZC=F", "Corn"), ("ZS=F", "Soybeans"), ("KC=F", "Coffee"),
                    ("SB=F", "Sugar"), ("CC=F", "Cocoa"), ("CT=F", "Cotton"), ("LE=F", "Live cattle")],
}

# Currencies in the currency strength heatmap (ECB reference rates)
HEATMAP_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK",
                      "CNY", "INR", "KRW", "SGD", "HKD", "MXN", "BRL", "ZAR", "TRY", "PLN"]

# Risk-on / risk-off meter: (indicator id, +1 if a rise means more risk appetite, -1 if less)
RISK_COMPONENTS = [("vix", -1), ("us_hy", -1), ("cu_au", +1), ("dxy", -1), ("sp500", +1)]

# Indicators pinned to the Home page the first time you open the dashboard
DEFAULT_WATCHLIST = ["uk_cpi", "uk_bankrate", "us_cpi", "us_unemp",
                     "ftse100", "sp500", "gbpusd", "brent"]
