"""
reference.py - static facts for the DES (description) screens, like Bloomberg's DES.

These are stable facts that rarely change (who issues a currency, where an index trades,
contract sizes). Live numbers (rates, prices, volatility) are calculated from the data.
"""

# ---------------------------------------------------------------- currencies
CURRENCIES = {
    "USD": dict(name="US dollar", country="United States", bank="Federal Reserve (Fed)",
                regime="Free floating (market-determined)", policy_id="us_fedfunds", bis="US"),
    "GBP": dict(name="Pound sterling", country="United Kingdom", bank="Bank of England",
                regime="Free floating (market-determined)", policy_id="uk_bankrate", bis="GB"),
    "EUR": dict(name="Euro", country="Euro area (20 countries)", bank="European Central Bank",
                regime="Free floating (market-determined)", policy_id="ecb_dfr", bis="XM"),
    "JPY": dict(name="Japanese yen", country="Japan", bank="Bank of Japan",
                regime="Free floating (with occasional intervention)", policy_id=None, bis="JP"),
    "CHF": dict(name="Swiss franc", country="Switzerland", bank="Swiss National Bank",
                regime="Floating (the SNB intervenes at times)", policy_id=None, bis="CH"),
    "CAD": dict(name="Canadian dollar", country="Canada", bank="Bank of Canada",
                regime="Free floating (market-determined)", policy_id=None, bis="CA"),
    "AUD": dict(name="Australian dollar", country="Australia", bank="Reserve Bank of Australia",
                regime="Free floating (market-determined)", policy_id=None, bis="AU"),
    "NZD": dict(name="New Zealand dollar", country="New Zealand", bank="Reserve Bank of New Zealand",
                regime="Free floating (market-determined)", policy_id=None, bis="NZ"),
    "NOK": dict(name="Norwegian krone", country="Norway", bank="Norges Bank",
                regime="Free floating (market-determined)", policy_id=None, bis="NO"),
    "CNY": dict(name="Chinese yuan (renminbi)", country="China", bank="People's Bank of China",
                regime="Managed: trades within a band around a daily official fixing",
                policy_id=None, bis="CN"),
    "INR": dict(name="Indian rupee", country="India", bank="Reserve Bank of India",
                regime="Managed float (the RBI intervenes to smooth moves)", policy_id=None, bis="IN"),
    "MXN": dict(name="Mexican peso", country="Mexico", bank="Banco de México",
                regime="Free floating (market-determined)", policy_id=None, bis="MX"),
    "BRL": dict(name="Brazilian real", country="Brazil", bank="Banco Central do Brasil",
                regime="Floating (with occasional intervention)", policy_id=None, bis="BR"),
    "KRW": dict(name="South Korean won", country="South Korea", bank="Bank of Korea",
                regime="Floating (with occasional intervention)", policy_id=None, bis="KR"),
    "ZAR": dict(name="South African rand", country="South Africa", bank="South African Reserve Bank",
                regime="Floating (market-determined)", policy_id=None, bis="ZA"),
}

# indicator id -> (base currency, quote currency, nickname). A rate = units of quote per 1 base.
FX_PAIRS = {
    "gbpusd": ("GBP", "USD", "Cable"), "gbpeur": ("GBP", "EUR", ""), "gbpjpy": ("GBP", "JPY", "Guppy"),
    "eurusd": ("EUR", "USD", "Fiber"), "usdjpy": ("USD", "JPY", "Gopher"), "usdcny": ("USD", "CNY", ""),
    "usdchf": ("USD", "CHF", "Swissie"), "usdcad": ("USD", "CAD", "Loonie"), "audusd": ("AUD", "USD", "Aussie"),
    "nzdusd": ("NZD", "USD", "Kiwi"), "usdnok": ("USD", "NOK", ""), "usdinr": ("USD", "INR", ""),
    "usdmxn": ("USD", "MXN", ""), "usdbrl": ("USD", "BRL", ""), "usdkrw": ("USD", "KRW", ""),
    "usdzar": ("USD", "ZAR", ""),
}
FX_COMMON = {
    "Type": "Spot exchange rate",
    "Trading hours": "24 hours, Sunday evening to Friday evening (UK time)",
    "Settlement": "T+2 (two business days); USD/CAD settles T+1",
    "Market": "Over-the-counter: traded between banks and brokers, not on one exchange",
}

# ---------------------------------------------------------------- stock indices
INDICES = {
    "ftse100": dict(Country="United Kingdom", Exchange="London Stock Exchange", Constituents="100",
                    Currency="GBP", Provider="FTSE Russell (LSEG)", Hours="08:00-16:30 UK time",
                    Weighting="Free-float market capitalisation",
                    Note="Most revenue earned abroad, so it often rises when the pound falls."),
    "ftse250": dict(Country="United Kingdom", Exchange="London Stock Exchange", Constituents="250",
                    Currency="GBP", Provider="FTSE Russell (LSEG)", Hours="08:00-16:30 UK time",
                    Weighting="Free-float market capitalisation",
                    Note="Companies ranked 101-350 on the LSE; more UK-focused than the FTSE 100."),
    "sp500": dict(Country="United States", Exchange="NYSE and Nasdaq", Constituents="About 500",
                  Currency="USD", Provider="S&P Dow Jones Indices", Hours="09:30-16:00 New York time",
                  Weighting="Free-float market capitalisation",
                  Note="The benchmark for US large companies; tech is its largest sector."),
    "nasdaq": dict(Country="United States", Exchange="Nasdaq", Constituents="Over 3,000",
                   Currency="USD", Provider="Nasdaq", Hours="09:30-16:00 New York time",
                   Weighting="Market capitalisation",
                   Note="Every stock listed on the Nasdaq; dominated by technology companies."),
    "dax": dict(Country="Germany", Exchange="Xetra (Frankfurt)", Constituents="40",
                Currency="EUR", Provider="STOXX (Deutsche Börse)", Hours="09:00-17:30 Frankfurt time",
                Weighting="Free-float market capitalisation",
                Note="A total-return index: dividends are reinvested in the index level."),
    "stoxx50": dict(Country="Euro area", Exchange="Several euro area exchanges", Constituents="50",
                    Currency="EUR", Provider="STOXX (Deutsche Börse)", Hours="09:00-17:30 Central European time",
                    Weighting="Free-float market capitalisation",
                    Note="The 50 largest companies across the euro area."),
    "nikkei": dict(Country="Japan", Exchange="Tokyo Stock Exchange", Constituents="225",
                   Currency="JPY", Provider="Nikkei Inc.", Hours="09:00-15:30 Tokyo time (lunch break)",
                   Weighting="Price-weighted (like the Dow)",
                   Note="Higher-priced shares carry more weight; sensitive to the yen."),
    "vix": dict(Country="United States", Exchange="Cboe", Constituents="Calculated from S&P 500 options",
                Currency="Index points", Provider="Cboe Global Markets", Hours="US trading hours",
                Weighting="n/a", Note="Measures expected volatility over the next 30 days."),
}

# ---------------------------------------------------------------- commodities
COMMODITIES = {
    "brent": dict(Benchmark="North Sea light, sweet crude", Venue="ICE Futures Europe",
                  Contract="1,000 barrels", Quoted="US dollars per barrel",
                  Note="The global oil benchmark: prices around two-thirds of the world's oil."),
    "wti": dict(Benchmark="West Texas Intermediate light, sweet crude", Venue="NYMEX (CME Group)",
                Contract="1,000 barrels", Quoted="US dollars per barrel",
                Note="Delivered at Cushing, Oklahoma; the US oil benchmark."),
    "natgas": dict(Benchmark="Henry Hub natural gas", Venue="NYMEX (CME Group)",
                   Contract="10,000 MMBtu", Quoted="US dollars per MMBtu",
                   Note="Henry Hub in Louisiana is the US gas pricing point; very weather-sensitive."),
    "gold": dict(Benchmark="Gold futures", Venue="COMEX (CME Group)", Contract="100 troy ounces",
                 Quoted="US dollars per troy ounce",
                 Note="A safe haven; tends to rise when real interest rates and the dollar fall."),
    "copper": dict(Benchmark="High-grade copper futures", Venue="COMEX (CME Group)",
                   Contract="25,000 pounds", Quoted="US dollars per pound",
                   Note="'Dr Copper': demand tracks global construction and manufacturing."),
}

# ---------------------------------------------------------------- crypto
CRYPTO = {
    "btc": dict(Launched="2009", Supply="Capped at 21 million coins", Consensus="Proof of work (mining)",
                Note="New supply halves roughly every four years (the 'halving'). Trades 24/7."),
    "eth": dict(Launched="2015", Supply="No fixed cap", Consensus="Proof of stake (since 2022)",
                Note="Runs smart contracts, decentralised apps and most stablecoins. Trades 24/7."),
}

# ---------------------------------------------------------------- economic releases
RELEASES = {
    "uk_cpi": "Monthly, around the middle of the following month (ONS)",
    "us_cpi": "Monthly, around the middle of the following month (BLS)",
    "us_core_cpi": "Monthly, with headline CPI (BLS)",
    "us_payrolls": "Monthly, usually the first Friday of the following month (BLS)",
    "us_unemp": "Monthly, with the payrolls report (BLS)",
    "us_claims": "Weekly, every Thursday (Department of Labor)",
    "uk_gdp": "Quarterly; first estimate about six weeks after the quarter ends (ONS)",
    "us_gdp": "Quarterly; advance estimate about four weeks after the quarter ends (BEA)",
    "uk_unemp": "Monthly, covering the latest three months (ONS)",
    "uk_pay": "Monthly, with the labour market report (ONS)",
    "uk_bankrate": "Set at eight MPC meetings a year (Bank of England)",
    "us_fedfunds": "Set at eight FOMC meetings a year (Federal Reserve)",
    "ecb_dfr": "Set at eight Governing Council meetings a year (ECB)",
    "ea_hicp": "Monthly; a flash estimate at the start of the following month (Eurostat/ECB)",
}

# Benchmarks for the correlation figure on the DES screen
BENCHMARK = {"FX": "dxy", "Markets": "sp500", "Crypto": "nasdaq", "EA": "stoxx50"}
