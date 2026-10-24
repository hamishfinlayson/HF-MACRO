"""
glossary.py - plain-English explanations shown when someone clicks an (i) icon.

TERMS  : abbreviations and concepts used around the dashboard
ABOUT  : what each indicator is and why it matters (keyed by indicator id)
To add one, just add a line. Keep it short: what it is, then why it matters.
"""

TERMS = {
    # ---- units and maths
    "pp": "Percentage points. The plain difference between two percentages: inflation going from 3% "
          "to 4% is +1pp (not +33%).",
    "y/y": "Year on year: compared with the same month or quarter a year earlier. Removes seasonal effects.",
    "q/q": "Quarter on quarter: compared with the previous three months.",
    "annualised": "A quarterly change scaled up to show what it would be over a full year if it kept "
                  "going at that pace (roughly x4). The US reports GDP this way; the UK doesn't.",
    "percentile": "Where today's reading sits in its own last 20 years. 0 = the lowest it has been, "
                  "100 = the highest, 50 = middle of the range.",
    "change": "How much the indicator has moved over the period shown (e.g. 3 or 12 months). Green = a "
              "move in the 'good' direction, red = 'bad', grey = neither.",
    "rebase": "Rebase to 100: every line starts at 100 so you can compare growth of things with very "
              "different sizes (e.g. the FTSE at 8,000 vs the S&P at 5,000).",
    "log scale": "A log scale shows equal percentage moves as equal distances, so a doubling from 100 "
                 "to 200 looks the same as from 1,000 to 2,000. Best for long histories of prices.",
    "correlation": "How closely two things move together, from -1 (always opposite) through 0 (no link) "
                   "to +1 (always together). It shows association, not cause and effect.",
    "lead/lag": "Shifts one indicator back and forward in time to see if it tends to move first. If "
                "correlation peaks when X is shifted 6 months, X 'leads' Y by about 6 months.",
    "bps": "Basis points: one hundredth of a percentage point. 25bps = 0.25pp, the usual size of a "
           "central bank rate move.",

    # ---- dashboard features
    "forecast": "A simple statistical projection (an autoregressive model) of where the indicator may go "
                "over the next 12 months, based only on its own past behaviour. The shaded band is "
                "where 80% of 2,000 simulated futures ended up. Educational only, not advice.",
    "confidence": "Confidence blocks (0-5): five related indicators are checked over the last 6 months. "
                  "Each filled block is one that points the same way as the forecast. 5 = everything "
                  "agrees, 0 = nothing backs it up.",
    "recession probability": "The chance of a US recession within 12 months, from the New York Fed's "
                             "published model using the yield curve (10-year minus 3-month Treasury "
                             "yield). An inverted curve pushes the probability up. Above ~30% has "
                             "historically been a warning sign.",
    "risk appetite": "A 0-100 gauge of how willing investors are to take risk. It combines the VIX, "
                     "high-yield credit spreads, the copper/gold ratio, the dollar and the S&P 500 vs "
                     "its 200-day average, each compared with its last 3 years. Low = fear (risk-off), "
                     "high = greed (risk-on).",
    "macro momentum": "A 0-100 gauge of the economy's direction: the share of US, UK and euro area "
                      "indicators that have moved in a good direction over the last 3 months. Above 50 "
                      "= more improving than worsening.",
    "scorecard": "Every indicator's latest value, its change over 3 and 12 months, and where it sits in "
                 "its 20-year range (the marker on the bar).",
    "watchlist": "Your pinned indicators. Open any chart full screen and press PIN TO HOME to add or "
                 "remove it.",
    "shading": "Shaded periods help you see how indicators behave in different regimes: recessions, "
               "rate hiking/cutting cycles, yield curve inversions, bear markets, market stress and "
               "high inflation.",
    "events": "Vertical markers for big moments such as Black Wednesday, Lehman Brothers' collapse, the "
              "Brexit vote, COVID and the 2022 UK mini-budget.",
    "news markers": "Diamonds on the chart show recent headlines about this indicator at the date they "
                    "were published. Hover to read them.",
    "biggest moves": "The largest recent changes in the indicator, with any headline published around "
                     "the same day that may explain the move.",
    "level lines": "Horizontal reference lines, e.g. a 2% inflation target. Type your own values "
                   "separated by commas.",
    "views": "Change how the data is shown: as published, change vs the previous reading, % change on a "
             "year earlier, or a 3/12-month average to smooth out noise.",
    "drawing": "Choose Line, Draw, Box or Circle under Mouse, then drag on the chart to annotate it. "
               "The eraser (top right of the chart) removes a shape; the camera saves a picture.",
    "currency strength": "How much each currency has gained (green) or lost (red) against the chosen "
                         "base currency over each period.",
    "public mode": "The online version hides a few series owned by private companies (some stock "
                   "indices, volatility and credit data) because they can't be republished freely. "
                   "Live market charts come from TradingView instead.",

    # ---- economics
    "GDP": "Gross Domestic Product: the total value of goods and services an economy produces. Its "
           "growth rate is the headline measure of how fast the economy is expanding or shrinking.",
    "recession": "A significant, broad fall in economic activity. The US uses official dates from the "
                 "NBER; in the UK the common rule is two quarters in a row of falling GDP (a 'technical "
                 "recession').",
    "NBER": "National Bureau of Economic Research: the US body that officially dates when recessions "
            "start and end.",
    "technical recession": "Two or more consecutive quarters of falling GDP. The usual UK definition.",
    "CPI": "Consumer Prices Index: the change in prices of a typical basket of goods and services "
           "households buy. The main measure of inflation.",
    "core inflation": "Inflation excluding volatile food and energy prices. Central banks watch it to "
                      "see the underlying trend.",
    "HICP": "Harmonised Index of Consumer Prices: the euro area's inflation measure, built the same way "
            "in every country so they can be compared. The ECB targets 2%.",
    "inflation target": "The inflation rate a central bank aims for. The Bank of England, Fed and ECB "
                        "all target 2%.",
    "NFP": "Non-farm payrolls: the number of US jobs added each month, excluding farm workers. Released "
           "on the first Friday of the month and one of the most market-moving data releases.",
    "jobless claims": "The number of people filing for US unemployment benefit for the first time each "
                      "week. A fast, early signal of layoffs.",
    "unemployment rate": "The share of people who want a job and are looking, but don't have one.",
    "employment rate": "The share of 16-64 year olds who are in work.",
    "industrial production": "Output of factories, mines and utilities. Sensitive to the business "
                             "cycle, so it often turns before the wider economy.",
    "trade balance": "Exports minus imports. Negative = a trade deficit (the country buys more from "
                     "abroad than it sells).",
    "current account": "The trade balance plus income and transfers with the rest of the world, as a % "
                       "of GDP. A persistent deficit means the country relies on foreign money.",
    "government debt": "Total government borrowing as a % of GDP. High debt can limit room to respond "
                       "to crises and push up borrowing costs.",
    "M2": "A broad measure of money in the economy: cash, current accounts, savings and small deposits. "
          "Fast growth can feed inflation; shrinking M2 is rare and a sign of tight money.",
    "PMI": "Purchasing Managers' Index: a monthly survey of businesses. Above 50 = activity expanding, "
           "below 50 = contracting. One of the earliest signals of where the economy is heading.",
    "Taylor rule": "A simple formula for where interest rates 'should' be given inflation and how tight "
                   "the jobs market is. Comparing it with the actual rate shows whether policy looks "
                   "loose or tight.",
    "neutral rate": "The interest rate that neither speeds up nor slows down the economy (r*). Nobody "
                    "knows it exactly; estimates are around 0-1% after inflation.",
    "IMF": "International Monetary Fund. Publishes the World Economic Outlook with data and forecasts "
           "for almost every country.",
    "WEO": "World Economic Outlook: the IMF's twice-yearly forecasts for the global economy.",

    # ---- rates and central banks
    "policy rate": "The interest rate set by a central bank (Bank Rate in the UK, the Fed funds rate in "
                   "the US, the deposit rate for the ECB). It drives borrowing costs across the economy.",
    "Bank Rate": "The Bank of England's main interest rate, set by its Monetary Policy Committee (MPC).",
    "Fed funds rate": "The rate US banks charge each other overnight, steered by the Federal Reserve. "
                      "The main US policy rate.",
    "ECB deposit rate": "The rate the European Central Bank pays banks on overnight deposits. The ECB's "
                        "main policy rate.",
    "real rate": "An interest rate minus inflation. Positive = borrowing is genuinely costly (tight "
                 "policy); negative = inflation is eating away at the cost of borrowing (loose policy).",
    "hiking cycle": "A period when a central bank keeps raising interest rates, usually to fight "
                    "inflation. A cutting cycle is the opposite, usually to support a slowing economy.",
    "MPC": "Monetary Policy Committee: the Bank of England group that votes on Bank Rate eight times a "
           "year.",
    "FOMC": "Federal Open Market Committee: the US Federal Reserve group that sets interest rates.",
    "BIS": "Bank for International Settlements: the 'central bank for central banks', which publishes "
           "policy rates for dozens of countries.",
    "ECB": "European Central Bank: sets interest rates for the 20 countries using the euro.",
    "yield": "The annual return you get from holding a bond at today's price. When bond prices fall, "
             "yields rise.",
    "gilt": "A UK government bond.",
    "Treasury": "A US government bond (or bill, for short maturities).",
    "yield curve": "A chart of government bond yields from short (e.g. 3 months) to long maturities "
                   "(e.g. 30 years). Normally slopes upwards, because lenders want more for lending "
                   "longer.",
    "inversion": "When short-term yields are higher than long-term ones (the curve slopes down). It has "
                 "come before almost every US recession since the 1960s.",
    "2s10s": "The 10-year Treasury yield minus the 2-year. Below zero = inverted curve.",
    "3m10y": "The 10-year Treasury yield minus the 3-month bill. The New York Fed's preferred recession "
             "signal.",
    "zero coupon": "A yield calculated as if the bond paid everything at the end, with no interest "
                   "payments along the way. Used by the Bank of England to build clean yield curves.",
    "credit spread": "The extra yield investors demand to lend to companies rather than the government. "
                     "Widening spreads = rising fear of defaults.",
    "high yield": "Bonds from riskier companies (below investment grade, sometimes called junk bonds). "
                  "Their spread is a good gauge of stress.",

    # ---- markets and FX
    "VIX": "The 'fear index': expected volatility of the S&P 500 over the next 30 days, based on option "
           "prices. Around 12-20 is calm; above 30 means stress.",
    "bear market": "A fall of 20% or more from a market's previous peak.",
    "200-day average": "The average price over the last 200 trading days. Prices above it are usually "
                       "seen as an uptrend.",
    "copper/gold ratio": "Copper (used in industry) divided by gold (a safe haven). Rising = markets "
                         "expect stronger growth; falling = caution. Often tracks bond yields.",
    "futures": "Contracts to buy or sell something at a set price on a future date. Commodity prices "
               "usually quote the nearest ('front-month') contract.",
    "DXY": "The US dollar against a basket of trading partners' currencies (here the Fed's broad, "
           "trade-weighted index). Rising = a stronger dollar.",
    "FX": "Foreign exchange: currencies and exchange rates.",
    "GBP/USD": "How many US dollars one pound buys (nicknamed 'cable'). Rising = a stronger pound.",
    "currency pair": "Quoted as BASE/QUOTE: how many units of the second currency one unit of the first "
                     "buys. USD/JPY at 150 = one dollar buys 150 yen.",
    "commodity currencies": "Currencies of countries that export a lot of raw materials (Canada, "
                            "Australia, New Zealand, Norway). They often move with commodity prices.",
    "emerging markets": "Faster-growing, less developed economies such as India, Brazil, Mexico and "
                        "South Africa. Their currencies tend to be more volatile.",
    "ECB reference rates": "Official daily exchange rates published by the European Central Bank "
                           "around 4pm CET.",
    "inventories": "How much crude oil (or gasoline) is sitting in storage. Builds (rising stocks) "
                   "usually mean supply is outpacing demand and weigh on prices; draws support prices. "
                   "The US EIA publishes the figures every Wednesday.",
    "real yield": "A bond yield after inflation. The 10-year TIPS yield is the market's real interest "
                  "rate. Rising real yields make non-interest-paying assets like gold and growth "
                  "stocks less attractive.",
    "breakeven inflation": "The inflation rate bond markets expect over the next 10 years: the normal "
                           "Treasury yield minus the inflation-protected (TIPS) yield.",
    "Brent-WTI spread": "The gap between the global (Brent) and US (WTI) oil price. It widens when US "
                        "supply is plentiful or export routes are tight.",
    "rate differential": "One country's interest rate minus another's. Money tends to flow towards "
                         "higher rates, so a widening gap in the UK's favour usually supports the pound.",
    "market forecast": "Market prices react to news instantly, so they're very hard to forecast: the "
                       "model mostly gives a range with a slight lean. Treat the confidence score "
                       "(what the drivers say) as the more useful part. Educational only, not advice.",
    "outlook board": "Every forecast on the dashboard in one table: direction, 12-month projection, "
                     "range and how many related indicators back it up.",
    "drivers": "The five related indicators each forecast is checked against, with the direction each "
               "one is pointing. Click a driver to open its chart.",
    "crypto": "Cryptocurrencies: digital assets recorded on a blockchain rather than issued by a "
              "central bank. Prices are very volatile and trade 24/7.",
    "market cap": "Market capitalisation: price x number of coins (or shares) in circulation. The "
                  "usual way to rank how big a coin or company is.",
    "bitcoin dominance": "Bitcoin's share of the total crypto market cap. Rising dominance often means "
                         "money is retreating to the largest, most established coin (more cautious); "
                         "falling dominance often means appetite for smaller, riskier coins.",
    "fear and greed": "The Crypto Fear & Greed Index (0-100) from alternative.me, built from "
                      "volatility, momentum, social media, dominance and search trends. Extreme fear "
                      "can mean investors are too worried; extreme greed, too excited.",
    "stablecoin": "A crypto token designed to hold a fixed value, usually $1 (e.g. USDT, USDC), backed "
                  "by cash or short-term bonds. Their total size shows how much money is parked in "
                  "crypto markets.",
    "volume": "The value of a coin traded over the last 24 hours. High volume means a move is "
              "backed by lots of trading.",
    "TradingView": "A market data and charting platform whose free widgets can be embedded on websites. "
                   "Its charts are interactive: drag, zoom and change the time range.",
}

# What each indicator is and why it matters (keyed by indicator id in indicators.py)
ABOUT = {
    "us_payrolls": "Jobs added to US payrolls each month (thousands). Strong numbers point to a healthy "
                   "economy and can push the Fed to keep rates higher.",
    "us_unemp": "Share of the US labour force without a job. A rise of 0.5pp from its low has "
                "historically signalled recession (the Sahm rule).",
    "us_claims": "New US unemployment benefit claims each week (thousands). Rising claims are an early "
                 "warning of layoffs.",
    "us_cpi": "US consumer price inflation, % change on a year earlier. The Fed targets 2% (using a "
              "related measure, PCE).",
    "us_core_cpi": "US inflation excluding food and energy, showing the underlying trend.",
    "us_gdp": "US economic growth, quarter on quarter, annualised. Two negative quarters often (not "
              "always) means recession.",
    "us_indpro": "US factory, mining and utility output vs a year earlier. A cyclical, early-moving "
                 "indicator.",
    "us_retail": "US retail sales vs a year earlier. Consumer spending is about two-thirds of the US "
                 "economy.",
    "us_sentiment": "University of Michigan survey of how consumers feel about their finances and the "
                    "economy. Falls often come before spending slows.",
    "us_housing": "New US homes started (annualised, thousands). Housing is very sensitive to interest "
                  "rates and often turns first in a downturn.",
    "us_mortgage": "Average 30-year fixed US mortgage rate. Moves with the 10-year Treasury yield.",
    "us_trade": "US exports minus imports of goods and services ($bn). The US runs a large, persistent "
                "deficit.",
    "us_m2": "Growth in the broad US money supply vs a year earlier.",
    "us_hy": "Extra yield on US high-yield (junk) bonds over Treasuries. Spikes in crises such as 2008 "
             "and 2020.",
    "us_fedfunds": "The US policy rate, set by the Federal Reserve's FOMC.",
    "us_real_ff": "The Fed funds rate minus CPI inflation. Positive = tight policy.",
    "us_10y": "Yield on 10-year US government bonds: the world's benchmark long-term interest rate.",
    "us_2s10s": "10-year minus 2-year Treasury yield. Below zero = inverted curve, a classic recession "
                "warning.",
    "us_3m10y": "10-year minus 3-month Treasury yield. Feeds the recession probability gauge.",
    "uk_gdp": "UK economic growth, quarter on quarter (not annualised). Two negative quarters = technical "
              "recession.",
    "uk_iop": "UK output of manufacturing, mining, energy and water vs a year earlier.",
    "uk_cpi": "UK consumer price inflation vs a year earlier. The Bank of England targets 2%.",
    "uk_unemp": "Share of the UK labour force (16+) without a job, from the Labour Force Survey.",
    "uk_emp": "Share of UK 16-64 year olds in work.",
    "uk_pay": "Growth in regular pay (excluding bonuses), 3-month average vs a year earlier. Fast pay "
              "growth can keep inflation high.",
    "uk_retail": "Volume of UK retail sales vs a year earlier (adjusted for price changes).",
    "uk_trade": "UK exports minus imports (£bn). The UK usually runs a trade deficit.",
    "uk_bankrate": "The Bank of England's policy rate, set by the MPC.",
    "uk_real_rate": "Bank Rate minus CPI inflation. Positive = tight policy.",
    "uk_10y": "Yield on 10-year UK government bonds (gilts), nominal zero coupon.",
    "uk_us_spread": "UK 10-year gilt yield minus the US 10-year Treasury yield. Rising = UK borrowing "
                    "getting relatively more expensive.",
    "ea_hicp": "Euro area inflation (HICP) vs a year earlier. The ECB targets 2%.",
    "ea_core": "Euro area inflation excluding energy, food, alcohol and tobacco.",
    "ea_unemp": "Share of the euro area labour force without a job.",
    "ecb_dfr": "The ECB's deposit facility rate: its main policy rate.",
    "ea_real_rate": "The ECB deposit rate minus HICP inflation.",
    "stoxx50": "The 50 largest companies in the euro area.",
    "ftse100": "The 100 largest companies on the London Stock Exchange. Earns most of its money abroad, "
               "so it often rises when the pound falls.",
    "ftse250": "The next 250 UK companies. More domestically focused than the FTSE 100, so a better "
               "gauge of the UK economy.",
    "sp500": "The 500 largest US companies: the world's most-watched stock index.",
    "nasdaq": "US index dominated by technology companies.",
    "dax": "Germany's 40 largest companies.",
    "nikkei": "Japan's main stock index of 225 companies.",
    "vix": "Expected S&P 500 volatility over 30 days: the 'fear index'.",
    "brent": "The global benchmark oil price (North Sea crude), in dollars per barrel.",
    "wti": "The US benchmark oil price (West Texas Intermediate).",
    "natgas": "US natural gas price at the Henry Hub, in dollars per million British thermal units.",
    "gold": "Gold price (front-month futures). A safe haven that tends to rise in uncertainty and when "
            "real interest rates fall.",
    "copper": "Copper price. Nicknamed 'Dr Copper' because demand tracks global industry and growth.",
    "cu_au": "Copper price divided by gold price (x1000). Rising = growth optimism.",
    "gbpusd": "How many dollars one pound buys.",
    "gbpeur": "How many euros one pound buys.",
    "gbpjpy": "How many yen one pound buys.",
    "eurusd": "How many dollars one euro buys: the world's most traded currency pair.",
    "usdjpy": "How many yen one dollar buys. Very sensitive to US vs Japanese interest rates.",
    "usdcny": "How many Chinese yuan one dollar buys. China manages its currency within a range.",
    "dxy": "The US dollar against a broad, trade-weighted basket of currencies (Federal Reserve index).",
    "usdchf": "How many Swiss francs one dollar buys. The franc is a safe-haven currency.",
    "usdcad": "How many Canadian dollars one US dollar buys. The Canadian dollar often moves with oil.",
    "audusd": "How many US dollars one Australian dollar buys. Sensitive to China and commodities.",
    "nzdusd": "How many US dollars one New Zealand dollar buys.",
    "usdnok": "How many Norwegian kroner one dollar buys. The krone often moves with oil.",
    "usdinr": "How many Indian rupees one dollar buys.",
    "usdmxn": "How many Mexican pesos one dollar buys.",
    "usdbrl": "How many Brazilian reais one dollar buys.",
    "usdkrw": "How many South Korean won one dollar buys.",
    "usdzar": "How many South African rand one dollar buys.",
    "btc": "Bitcoin in US dollars: the largest cryptocurrency. Tends to move with tech stocks and "
           "against real interest rates and the dollar.",
    "eth": "Ethereum in US dollars: the second-largest cryptocurrency, the main platform for "
           "decentralised apps and stablecoins.",
    "us_real10y": "The 10-year US Treasury yield after inflation (TIPS). The key driver of gold and "
                  "tech-stock valuations.",
    "us_breakeven": "Inflation the bond market expects over the next 10 years.",
    "brent_wti": "Brent oil price minus WTI. Shows how global and US oil markets compare.",
    "us_crude_stocks": "Weekly US commercial crude oil stocks (excluding the Strategic Petroleum "
                       "Reserve), in millions of barrels. Rising stocks tend to push prices down.",
    "us_crude_prod": "Weekly US crude oil output in millions of barrels a day. The US is the world's "
                     "largest producer, so this matters for global supply.",
    "us_gas_stocks": "Weekly US gasoline stocks in millions of barrels: a gauge of fuel demand.",
    "us_pump": "Average US regular petrol price per gallon. Feeds straight into consumer inflation "
               "and sentiment.",
    "uk_us_rates": "Bank Rate minus the Fed funds rate. A rising gap tends to support the pound "
                   "against the dollar.",
    "ea_us_rates": "ECB deposit rate minus the Fed funds rate. A rising gap tends to support the euro "
                   "against the dollar.",
}


def lookup(key):
    """Finds an explanation for an indicator id or a term (case-insensitive)."""
    if key in ABOUT:
        return ABOUT[key]
    if key in TERMS:
        return TERMS[key]
    lower = {k.lower(): v for k, v in TERMS.items()}
    return lower.get(str(key).lower(), "")
