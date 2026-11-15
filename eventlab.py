"""
eventlab.py - EVENT LAB (PC version only).

Big batch tests of ideas copied from research and company events, all judged the same honest way:
build years, then years the rules never saw, after costs, against the S&P 500 AND a small-company index.
RESULTS = finished tests. WAITING = built and ready, waiting for data (EODHD prices that include bought-out companies).
Not financial advice.
"""

HEADLINE = ("Nothing tested so far beats your 50/50 commodity model + S&P on the years it never saw. Famous strategies "
            "mostly faded once they were published (returns roughly halved). The survivors point to momentum, profitable "
            "companies and shrinking share counts - the next stock model is built from those.")

RESULTS = [  # light, group, idea, build years, held-out years, why
    ("🔴", "Copied models", "Dual Momentum (Antonacci), as published", "+11.0%/yr (S&P +8.2%) 2003-14",
     "+7.6%/yr (S&P +13.9%) 2015-26, p 0.01", "Beat the S&P until it was published in 2014, then lagged."),
    ("🔴", "Copied models", "Faber 10-month rule (5 assets)", "+3.4%/yr 2007-14", "+5.8%/yr 2015-26",
     "Worst drop only -8%, but far behind in a long bull market."),
    ("🔴", "Copied models", "AQR trend, ISA version (long or cash)", "+6.6%/yr", "+4.2%/yr",
     "Too much time in cash; the CFD version already failed on fees."),
    ("🔴", "Copied models", "Six improved versions and mixes", "Best: +12.2%/yr", "Best: +12.3%/yr (2.0%/yr behind S&P)",
     "None beat the current 50/50 model + S&P (+14.4%/yr on the same years)."),
    ("🔴", "Carry", "Commodity carry: long backwardated, short contango", "+3.6%/yr 2010-17 (p 0.21)", "-3.4%/yr 2018-26",
     "Predicted winners slightly until 2017 (p 0.02), zero since (p 0.86)."),
    ("🔴", "Carry", "Commodity carry, long-only best third", "+3.4%/yr", "+7.8%/yr",
     "No better than holding every commodity (+7.7%/yr)."),
    ("🟠", "Carry", "FX carry (central-bank rates)", "+1.0%/yr 2001-14 (p 0.74)", "+4.1%/yr 2015-26 (p 0.14)",
     "Small, unproven, with -13% months."),
    ("🔴", "Takeovers", "Short activist targets, buy the S&P", "Lost at every holding period 2005-15",
     "+3.4% over 6 months 2016-24", "The gain was small companies lagging big ones; vs a small-company index it vanished."),
]

WAITING = [  # idea, trade, needs
    ("New stock model: momentum + profitability + shrinking share count", "Top 20 US companies over $2bn, monthly, long-only ISA", "EODHD"),
    ("Spin-offs", "Buy the new company after its first week, hold 1-2 years", "EODHD"),
    ("IPO lock-up expiry (all, and PE-backed)", "Short 1 week before insiders can sell, hold 2 weeks", "EODHD"),
    ("Short IPOs", "Short 1 month after listing, hold 12 months", "EODHD"),
    ("Short the buyer", "Short companies paying for takeovers in their own shares, 12 months", "EODHD"),
    ("Buybacks", "Buy after the announcement, hold 3 or 12 months", "EODHD"),
    ("Narrow merger arbitrage", "Buy all-cash PE deal targets until the deal closes", "EODHD"),
    ("Activist targets, redone", "With bought-out winners included", "EODHD"),
    ("Politicians' buys and sells", "Copy after disclosure, 3 months", "Quiver + EODHD"),
    ("Big government contracts", "Buy after the award, 1 month", "Quiver + EODHD"),
]

PUBLISHED = dict(total=208, after=56, since2015=28, before_avg=7.2, after_avg=3.8,
                 themes=[("Shrinking share count beats issuing shares", 6, "Backs up 'short the buyer' and 'buybacks'"),
                         ("Momentum", 5, "Same idea as your commodity model"),
                         ("Profitable companies", 3, "New - in the stock model"),
                         ("Heavily shorted stocks keep falling", 2, "Needs short-interest data"),
                         ("Options-market signals", 4, "Needs options data")])

CRASH_SWITCH = ("Tested insurance, not a strategy: hold the S&P, but move to bonds when the S&P is below its 10-month "
                "average AND its 12-month return is below cash. 2008's worst drop: -18% instead of -53%. Cost: about 4% a "
                "year in normal times (2015-26). Worth considering only if Bubble Watch reaches High alert.")
