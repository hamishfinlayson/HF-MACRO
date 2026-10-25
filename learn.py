"""
learn.py - the LEARN section: short lessons built around HF Macro's live charts,
case studies from the last 20 years, quizzes, and "how to read this page" guides.

Each lesson is a dict:
  key, title, minutes, summary
  parts:  list of ("text", markdown) | ("chart", [indicator ids], years, caption) | ("now", key)
  quiz:   list of (question, [options], index of correct option, explanation)
"now" parts are filled in by app.py with a sentence about what the data shows today.
"""

LESSONS = [
    dict(
        key="indicators", title="1. Reading economic indicators", minutes=6,
        summary="Leading vs lagging indicators, why surprises move markets, and why first figures get revised.",
        parts=[
            ("text", """
An **economic indicator** is a regularly published number that tells you how part of the economy is
doing: how many jobs were created, how fast prices are rising, how much people are spending.

**Three types, depending on timing**
- **Leading** indicators tend to turn *before* the economy does: the yield curve, business surveys
  (PMIs), building permits, stock prices.
- **Coincident** indicators move *with* the economy: employment, industrial production, retail sales.
- **Lagging** indicators turn *after*: unemployment (firms are slow to fire and slow to hire), and
  inflation, which often keeps rising after growth has slowed.

**Markets trade the surprise, not the number.** Before each release, economists publish a forecast
(the *consensus*). If US payrolls rise by 150,000 but 250,000 was expected, that's a big negative
surprise, even though jobs grew. Prices move on the gap between the figure and what was expected.

**First estimates get revised.** GDP and jobs figures are estimated from incomplete data and revised
later, sometimes a lot. Professionals treat the first print with care. Open US GDP's INFO screen to see
how much the first estimates have changed.
"""),
            ("chart", ["us_payrolls", "us_unemp"], 10,
             "Payrolls (coincident) and unemployment (lagging). Notice unemployment keeps rising for a while "
             "after job growth has already turned."),
            ("now", "payrolls"),
        ],
        quiz=[
            ("Which of these is usually a LEADING indicator?",
             ["The unemployment rate", "The yield curve", "Core inflation"], 1,
             "The yield curve tends to invert well before recessions. Unemployment and inflation usually lag."),
            ("US payrolls rise by 180,000 but the consensus expected 300,000. How would markets most likely "
             "read it?", ["As strong news, because jobs grew", "As weak news, because it missed expectations",
                         "Markets ignore jobs data"], 1,
             "Markets react to the surprise versus expectations, not to whether the number is positive."),
            ("Why should you be careful with a first GDP estimate?",
             ["It's often revised as more data arrives", "It's always too high", "It ignores services"], 0,
             "First estimates use incomplete data. Revisions can change the picture, occasionally from growth "
             "to contraction."),
        ]),

    dict(
        key="inflation", title="2. Inflation and interest rates", minutes=7,
        summary="How inflation is measured, why central banks target 2%, and how they use interest rates.",
        parts=[
            ("text", """
**Inflation** is the rate at which prices rise, usually measured by the **Consumer Price Index (CPI)**:
the cost of a typical basket of goods and services compared with a year earlier.
**Core inflation** strips out food and energy, which jump around, to show the underlying trend.

**Why 2%?** The Bank of England, the Fed and the ECB all aim for about 2% a year. That's low enough
that people don't worry about prices, but above zero, which avoids *deflation* (falling prices that
make people delay spending).

**The main tool is the interest rate.** When inflation is too high, the central bank raises its rate
(Bank Rate in the UK, the Fed funds rate in the US). Borrowing gets more expensive, so households and
firms spend less, demand cools and inflation slows. This takes time, often 18 months to 2 years, so
central banks have to act on where they think inflation is *going*.

**Real interest rate** = interest rate minus inflation. A 5% rate with 6% inflation is still a
*negative* real rate, so it's loose policy. HF Macro shows real rates for the UK, US and euro area.

**Watch for second-round effects:** if high inflation pushes up wages, and wages push up prices, inflation
can become stuck. That's why the Bank of England watches pay growth closely.
"""),
            ("chart", ["uk_cpi", "uk_bankrate"], 10,
             "UK CPI inflation against Bank Rate. In 2021-22 inflation rose first and rates followed."),
            ("now", "uk_inflation"),
            ("chart", ["uk_real_rate"], 20,
             "UK real Bank Rate (Bank Rate minus CPI). Below zero means policy is still stimulating the economy."),
        ],
        quiz=[
            ("Inflation is 7% and Bank Rate is 5%. The real interest rate is:",
             ["+12%", "+2%", "-2%"], 2,
             "Real rate = 5% - 7% = -2%. Borrowing is still cheap in real terms."),
            ("Why do central banks raise rates when inflation is high?",
             ["To make borrowing dearer and cool demand", "To raise more tax", "To weaken the currency"], 0,
             "Higher rates reduce borrowing and spending, which slows price rises (and usually strengthens the "
             "currency, not weakens it)."),
            ("What does core inflation leave out?",
             ["Rent and mortgages", "Food and energy", "Imported goods"], 1,
             "Core inflation excludes the most volatile items, food and energy, to show the underlying trend."),
        ]),

    dict(
        key="curve", title="3. The yield curve and recessions", minutes=6,
        summary="What the yield curve is, why an inversion is a warning sign, and the NY Fed's model.",
        parts=[
            ("text", """
The **yield curve** plots the interest rate (yield) on government bonds of different lengths, from 3
months to 30 years. Normally it slopes **upwards**: lenders want more to tie money up for longer.

**An inverted curve** (short-term yields above long-term) means markets expect the central bank to
*cut* rates in future, usually because they expect the economy to weaken. In the US, an inversion of
the 10-year minus 3-month spread has come before every recession since the late 1960s, typically
6 to 18 months ahead. There has been at least one false alarm.

**The New York Fed turns this into a probability.** Its model links the spread to the chance of a US
recession 12 months later. HF Macro's Home page gauge uses the published formula.

**Careful:** the curve inverted in 2022-23 and the US avoided a recession, at least at first. Signals
like this are probabilities, not certainties. Unusual things (huge bond buying by central banks,
post-pandemic distortions) can weaken old relationships.
"""),
            ("chart", ["us_3m10y"], 40,
             "US 10-year minus 3-month spread with US recessions shaded. Most recessions start after the "
             "line dips below zero."),
            ("now", "curve"),
        ],
        quiz=[
            ("A yield curve is 'inverted' when:",
             ["Long-term yields are above short-term yields", "Short-term yields are above long-term yields",
              "All yields are negative"], 1,
             "Inversion means short-term rates are higher than long-term rates."),
            ("Why might an inverted curve predict a recession?",
             ["Markets expect rate cuts because growth will weaken", "Banks lend more when it's inverted",
              "It makes the currency fall"], 0,
             "Long yields fall when investors expect future rate cuts, which usually happen in downturns. "
             "Inversion also squeezes banks' lending margins."),
        ]),

    dict(
        key="fx", title="4. What moves currencies", minutes=6,
        summary="Interest rate differentials, risk sentiment, and why the dollar is a safe haven.",
        parts=[
            ("text", """
An exchange rate is the price of one currency in another. **GBP/USD 1.30** means £1 buys $1.30.
If it rises, the pound has strengthened.

**1. Interest rate differentials (the biggest driver).** Investors move money to where it earns more.
If UK rates rise relative to US rates, holding pounds becomes more attractive and GBP/USD tends to rise.
Markets trade *expected* rate moves, so a surprise in UK inflation can move the pound within seconds.

**2. Risk sentiment.** In a crisis, investors buy safe havens: the **US dollar**, the **Swiss franc**
and the **Japanese yen**. "Risk" currencies like the Australian dollar or emerging-market currencies
tend to fall.

**3. Growth and trade.** A country exporting more than it imports has foreign buyers needing its
currency. Commodity exporters' currencies (AUD, CAD, NOK) often track commodity prices.

**4. Confidence in policy.** In September 2022 the pound fell to a record low against the dollar after
the UK mini-budget, as investors questioned how unfunded tax cuts would be paid for. See the case study.
"""),
            ("chart", ["gbpusd", "uk_us_rates"], 10,
             "GBP/USD against the UK-US interest rate gap. They often move together, but not always."),
            ("now", "fx"),
        ],
        quiz=[
            ("The Bank of England unexpectedly raises rates. The most likely immediate effect on GBP/USD is:",
             ["It rises", "It falls", "No effect"], 0,
             "Higher UK rates make sterling more attractive to hold, so the pound usually strengthens."),
            ("Which of these is generally seen as a safe-haven currency?",
             ["Australian dollar", "Swiss franc", "Mexican peso"], 1,
             "The Swiss franc, US dollar and Japanese yen tend to strengthen when markets are stressed."),
        ]),

    dict(
        key="bonds", title="5. Bond yields and market expectations", minutes=7,
        summary="How bond prices and yields work, forward rates, and reading inflation expectations.",
        parts=[
            ("text", """
A government bond pays fixed interest. **When bond prices fall, yields rise** (and vice versa),
because a fixed payment on a cheaper bond is a bigger return. That's why the TradingView page shows
gilt and Bund *prices* falling when yields go up.

**The 2-year yield is the market's view of rates.** It closely tracks where traders think the central
bank will set rates over the next two years. If the 2-year yield is well below today's Fed funds rate,
markets are betting on cuts.

**Forward rates** pull that apart: from the 1-year and 2-year yields you can work out the 1-year rate
markets expect *in one year's time*. HF Macro calculates these on the Fed funds and 2-year
screens (the *What others expect* panel on INFO and DRIVERS).

**Breakeven inflation** = normal Treasury yield minus inflation-protected (TIPS) yield. It's the
inflation rate investors expect. The **5y5y forward** (expected inflation for the five years starting
five years from now) is what the Fed watches to check expectations stay anchored near 2%.

**Market expectations aren't perfect forecasts.** They include a *term premium* and they change fast.
But they're what professionals start from, alongside central banks' own projections.
"""),
            ("chart", ["us_2y", "us_fedfunds"], 10,
             "The 2-year Treasury yield usually moves ahead of the Fed funds rate."),
            ("now", "bonds"),
            ("chart", ["us_be5", "us_5y5y"], 10,
             "Market inflation expectations. They jumped in 2021-22 but long-term expectations stayed far below "
             "actual inflation."),
        ],
        quiz=[
            ("A bond's price falls. What happens to its yield?", ["It rises", "It falls", "It stays the same"], 0,
             "Price and yield move in opposite directions."),
            ("The 2-year yield is 3.2% and the Fed funds rate is 4.0%. Markets are probably expecting:",
             ["Rate rises", "Rate cuts", "No change"], 1,
             "A 2-year yield well below the policy rate means markets expect the average rate over two years to "
             "be lower, i.e. cuts."),
            ("Breakeven inflation is calculated as:",
             ["Normal Treasury yield minus TIPS yield", "CPI minus core CPI", "Fed funds minus inflation"], 0,
             "The gap between normal and inflation-protected yields is the inflation investors need to break even."),
        ]),

    dict(
        key="commodities", title="6. Commodities and oil", minutes=5,
        summary="What drives oil prices, why inventories matter, and the link to inflation.",
        parts=[
            ("text", """
**Oil** is priced mainly through two benchmarks: **Brent** (North Sea, the global benchmark) and
**WTI** (US). Prices are set by supply and demand, but the *expected* balance matters most.

**Supply:** OPEC+ production decisions, US shale output, wars and sanctions.
**Demand:** global growth, especially China, plus seasonal driving and heating.
**Inventories:** the weekly US crude stock figures show whether the market is over- or under-supplied.
Falling stocks usually support prices.
**The dollar:** oil is priced in dollars, so a stronger dollar tends to weigh on prices.

**Why it matters for macro:** energy feeds straight into inflation, through petrol, heating and
transport costs. The 2022 energy shock after Russia's invasion of Ukraine was a major reason UK
inflation hit 11.1%.

**Copper** is nicknamed "Dr Copper" because demand tracks construction and manufacturing, so its price
is read as a signal for global growth. **Gold** tends to rise when real interest rates fall and in times
of fear.
"""),
            ("chart", ["brent", "us_crude_stocks"], 5,
             "Brent crude against US crude inventories. Large stock builds often come with weaker prices."),
            ("now", "oil"),
        ],
        quiz=[
            ("US crude inventories fall much more than expected. All else equal, oil prices tend to:",
             ["Rise", "Fall", "Not change"], 0,
             "A bigger-than-expected draw suggests tighter supply relative to demand."),
            ("Why is copper called 'Dr Copper'?",
             ["Its price is read as a signal of global growth", "It's used in medicine", "It never falls"], 0,
             "Copper demand follows construction and industry, so its price is watched as a growth indicator."),
        ]),

    dict(
        key="forecasting", title="7. How to judge a forecast", minutes=5,
        summary="Benchmarks, backtesting and why most forecasts of market prices fail.",
        parts=[
            ("text", """
Anyone can draw a line into the future. The question is whether it's any good.

**Start with a benchmark.** The simplest forecast is *no change*: "in a year it'll be where it is
today". For many market prices that's very hard to beat, because new information gets priced in
straight away (the *efficient markets* idea).

**Backtest it.** Go back in time, run the model using only the data available then, and compare its
forecast with what actually happened. Repeat for every month over 10 years and measure the average miss.
HF Macro does this for every forecast: see **LAB → Forecast scorecard** and the *Model comparison*
panel on each DRIVERS screen.

**Combine models.** Different models make different mistakes, so an average of several is often more
accurate than any single one. That's why central banks look at many models, not one.

**Beware overfitting.** A model with lots of moving parts can fit the past perfectly and still forecast
badly, because it has learned the noise. Simple models often win.

**A confidence score isn't a probability.** HF Macro's 1-5 score counts how many related indicators
point the same way as the forecast. It's a sense check, not a guarantee.
"""),
            ("now", "scorecard"),
        ],
        quiz=[
            ("A model's average 12-month miss is 0.9pp and 'no change' misses by 1.0pp. The model is:",
             ["10% better than no change", "Worse than no change", "Perfect"], 0,
             "1 - 0.9/1.0 = 10% improvement over the benchmark."),
            ("Why do backtests only use data available at each past date?",
             ["To avoid using information the model couldn't have known", "To make it run faster",
              "Because older data is more accurate"], 0,
             "Using future information would make the model look far better than it really is (look-ahead bias)."),
        ]),
]

CASES = [
    dict(
        key="gfc", title="2008: the Global Financial Crisis", start="2007-01-01", end="2010-12-31",
        ids=["us_unemp", "us_fedfunds", "us_payrolls", "uk_bankrate"],
        events=[("2007-08-09", "Credit markets freeze"), ("2008-09-15", "Lehman Brothers collapses"),
                ("2008-12-16", "Fed cuts to 0-0.25%"), ("2009-03-05", "BoE cuts to 0.5%")],
        story="""
Problems in US subprime mortgages spread through a banking system that had borrowed heavily against
them. In **August 2007** credit markets froze. When **Lehman Brothers** collapsed on **15 September 2008**,
panic spread worldwide.

**What the indicators did:** US payrolls fell by hundreds of thousands a month and unemployment rose
from about 5% to 10%. The Fed cut rates to almost zero by **December 2008**, and the Bank of England
cut Bank Rate to **0.5% in March 2009**, then its lowest in over 300 years. Both started buying bonds
(quantitative easing) when they couldn't cut further.

**Lesson:** unemployment kept rising well after the worst of the panic. It's a lagging indicator.
"""),
    dict(
        key="covid", title="2020: the Covid shock", start="2019-06-01", end="2021-12-31",
        ids=["us_unemp", "us_payrolls", "uk_gdp", "us_fedfunds"],
        events=[("2020-03-11", "WHO declares pandemic"), ("2020-03-15", "Fed cuts to 0-0.25%"),
                ("2020-03-23", "UK lockdown begins")],
        story="""
Lockdowns in **March 2020** caused the fastest collapse in activity on record. US payrolls fell by more
than 20 million in April 2020 and US unemployment jumped to nearly 15%. UK GDP fell by around a fifth
in the second quarter of 2020.

Central banks cut rates to near zero and governments paid wages and supported businesses on a huge
scale, so the rebound was also extremely fast.

**Lesson:** this is why HF Macro's forecasts leave out February 2020 to December 2021. Moves this extreme
would distort any model trained on them.
"""),
    dict(
        key="inflation2022", title="2021-23: the inflation surge", start="2020-06-01", end="2024-06-30",
        ids=["uk_cpi", "us_cpi", "uk_bankrate", "us_fedfunds"],
        events=[("2021-12-16", "BoE starts raising rates"), ("2022-02-24", "Russia invades Ukraine"),
                ("2022-03-16", "Fed starts raising rates")],
        story="""
Reopening after Covid, supply-chain bottlenecks and then the energy shock after Russia's invasion of
Ukraine pushed inflation to 40-year highs: **US CPI peaked at 9.1% in June 2022** and **UK CPI at
11.1% in October 2022**.

Central banks had first called the rise "transitory", then raised rates at the fastest pace in decades:
Bank Rate went from 0.1% to **5.25%** and the Fed funds rate to **5.25-5.5%** by summer 2023.

**Lesson:** inflation can rise much faster than models built on calm years expect, and policy works with
a lag. Compare the inflation peaks with when rates stopped rising.
"""),
    dict(
        key="minibudget", title="2022: the UK mini-budget", start="2022-06-01", end="2023-03-31",
        ids=["uk_10y", "gbpusd", "uk_bankrate"],
        events=[("2022-09-23", "Mini-budget"), ("2022-09-28", "BoE emergency gilt buying"),
                ("2022-10-20", "PM announces resignation")],
        story="""
On **23 September 2022** the UK government announced large unfunded tax cuts. Investors worried about
how they would be paid for at a time of high inflation. Gilt yields jumped by the most in decades and
the pound fell to a **record low of about $1.03** against the dollar.

The sell-off hit pension funds using *liability-driven investment* (LDI) strategies, forcing them to sell
gilts and pushing yields up further. The Bank of England stepped in on **28 September** with emergency
gilt purchases. Most of the measures were reversed and the Prime Minister announced her resignation on
**20 October**.

**Lesson:** markets judge the credibility of fiscal policy. A loss of confidence shows up in bond yields
and the currency at the same time.
"""),
]

GUIDES = {
    "HOME": ["Start top left: the recession gauge and the momentum gauge give the big picture.",
             "The scorecard shows where each economy's key numbers sit versus the last 20 years.",
             "Check the calendar for this week's data releases, which are when markets move most."],
    "US": ["Read top to bottom: jobs, then inflation, then growth, then rates.",
           "Ask: is the Fed's rate high enough to bring inflation back to 2% without hurting jobs?",
           "Click any card for the full chart, INFO for facts, and DRIVERS for the forecast logic."],
    "UK": ["Inflation and pay growth decide what the Bank of England does next.",
           "Compare CPI with Bank Rate: the gap is the real rate (UKREAL).",
           "Gilt yields (GILT10) show what markets think of UK rates and government borrowing."],
    "EA": ["The ECB targets 2% HICP inflation. Compare it with the deposit rate.",
           "Unemployment in the euro area is structurally higher than in the UK or US."],
    "MKT": ["Equities, volatility and commodities together show risk appetite.",
            "Rising VIX and falling stocks usually go with a stronger dollar and lower yields."],
    "FX": ["Use the winners and losers lists to see which currencies are moving most.",
           "Compare each move with the interest rate gap between the two countries.",
           "Click a currency code for its profile: central bank, rate and performance."],
    "CMDTY": ["Start with the oil dashboard: prices, inventories and production.",
              "Commodity moves feed into inflation a few months later."],
    "CRV": ["A normal curve slopes up. Inversion (short above long) is a classic recession warning."],
    "LAB": ["The Forecast scorecard shows how accurate each forecast would have been over 10 years.",
            "Use lead/lag to test whether one indicator moves before another."],
}
GUIDE_LESSON = {"HOME": "indicators", "US": "inflation", "UK": "inflation", "EA": "inflation", "MKT": "commodities",
                "FX": "fx", "CMDTY": "commodities", "CRV": "curve", "LAB": "forecasting"}
