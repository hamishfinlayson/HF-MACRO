"""
sources.py - fetches data from each source and tidies it into a simple
pandas Series (dates down the side, values next to them).

You shouldn't need to edit this file to add indicators - use indicators.py.
"""

import io
import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

HEADERS = {"User-Agent": "Mozilla/5.0 (personal macro dashboard project)"}
TIMEOUT = 20
CACHE_SECONDS = 6 * 60 * 60  # re-download data at most every 6 hours


def _get(url, params=None):
    response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def get_fred_key():
    """Reads your FRED key from .streamlit/secrets.toml (or the hosting 'secrets' box)."""
    try:
        key = st.secrets["FRED_API_KEY"]
    except Exception:
        key = os.environ.get("FRED_API_KEY", "")
    key = str(key).strip()
    if not key or key == "paste-your-key-here":
        return None
    return key


# ---------------------------------------------------------------- parsers
# These turn each source's raw reply into a Series. They are kept separate
# from the downloading so they can be tested with sample data.

def parse_fred(payload):
    rows = payload.get("observations", [])
    if not rows:
        raise ValueError("FRED returned no observations")
    df = pd.DataFrame(rows)
    values = pd.to_numeric(df["value"], errors="coerce")  # FRED uses "." for missing
    series = pd.Series(values.values, index=pd.to_datetime(df["date"]))
    return series.dropna().sort_index()


def parse_ons(payload):
    """ONS gives monthly, quarterly and yearly lists - use the most frequent one available."""
    title = payload.get("description", {}).get("title", "")
    for key, fmt in (("months", "month"), ("quarters", "quarter"), ("years", "year")):
        rows = payload.get(key) or []
        if not rows:
            continue
        dates, values = [], []
        for row in rows:
            raw = str(row.get("date", "")).strip()
            if fmt == "month":            # e.g. "2024 JAN"
                when = pd.to_datetime(raw.title(), format="%Y %b")
            elif fmt == "quarter":        # e.g. "2024 Q1" -> first day of the quarter
                when = pd.Period(raw.replace(" ", ""), freq="Q").start_time
            else:                         # e.g. "2024"
                when = pd.Timestamp(int(raw), 1, 1)
            dates.append(when)
            values.append(pd.to_numeric(row.get("value"), errors="coerce"))
        series = pd.Series(values, index=pd.DatetimeIndex(dates)).dropna().sort_index()
        if not series.empty:
            return series, title
    raise ValueError("ONS returned no data points")


def parse_boe(csv_text, code):
    if "<html" in csv_text[:500].lower():
        raise ValueError("Bank of England returned a web page instead of data")
    df = pd.read_csv(io.StringIO(csv_text))
    df.columns = [c.strip().upper() for c in df.columns]
    if "DATE" not in df.columns or code.upper() not in df.columns:
        raise ValueError(f"Bank of England reply missing DATE/{code} columns")
    dates = pd.to_datetime(df["DATE"], format="%d %b %Y")
    values = pd.to_numeric(df[code.upper()], errors="coerce")
    return pd.Series(values.values, index=dates).dropna().sort_index()


def parse_frankfurter(payload, currencies):
    """Builds a table: latest rate, rate ~1 month ago, and % change."""
    rates = payload.get("rates", {})
    if not rates:
        raise ValueError("FX source returned no rates")
    df = pd.DataFrame(rates).T
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    latest, first = df.iloc[-1], df.iloc[0]
    prev = df.iloc[-2] if len(df) > 1 else first
    table = pd.DataFrame({
        "Currency": currencies,
        "1 GBP buys": [latest.get(c) for c in currencies],
        "1 month ago": [first.get(c) for c in currencies],
    })
    table["1 day %"] = [(latest.get(c) / prev.get(c) - 1) * 100 for c in currencies]
    table["1 month %"] = (table["1 GBP buys"] / table["1 month ago"] - 1) * 100
    table["Change %"] = table["1 month %"]
    return table, df.index[-1]


# ---------------------------------------------------------------- downloaders

@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def fetch_fred(code, api_key):
    payload = _get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={"series_id": code, "api_key": api_key, "file_type": "json"},
    ).json()
    return parse_fred(payload)


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def fetch_ons(code, dataset, topic):
    url = f"https://www.ons.gov.uk/{topic}/timeseries/{code.lower()}/{dataset.lower()}/data"
    return parse_ons(_get(url).json())


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def fetch_boe(code, years=55):
    start = (date.today() - timedelta(days=365 * years)).strftime("%d/%b/%Y")
    params = {
        "csv.x": "yes", "Datefrom": start, "Dateto": "now",
        "SeriesCodes": code, "CSVF": "TN", "UsingCodes": "Y", "VPD": "Y", "VFD": "N",
    }
    text = _get(
        "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp",
        params=params,
    ).text
    return parse_boe(text, code)


def parse_yahoo(history):
    """Turns a yfinance price table into a Series of daily closing prices."""
    if history is None or history.empty or "Close" not in history.columns:
        raise ValueError("Yahoo Finance returned no prices")
    close = history["Close"].dropna()
    index = pd.DatetimeIndex(close.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    return pd.Series(close.values, index=index.normalize()).sort_index()


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def fetch_yahoo(code):
    import yfinance as yf  # imported here so the rest of the app works without it
    return parse_yahoo(yf.Ticker(code).history(period="max", auto_adjust=False))


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def fetch_fx_table(currencies):
    start = (date.today() - timedelta(days=31)).isoformat()
    payload = _get(
        f"https://api.frankfurter.app/{start}..",
        params={"from": "GBP", "to": ",".join(currencies)},
    ).json()
    return parse_frankfurter(payload, list(currencies))


# ---------------------------------------------------------------- transforms

def apply_transform(series, transform):
    if transform == "change":
        return series.diff().dropna()
    if transform == "yoy":
        year_ago = series.copy()
        year_ago.index = year_ago.index + pd.DateOffset(years=1)
        year_ago = year_ago.reindex(series.index)
        return ((series / year_ago - 1) * 100).dropna()
    return series


def load_indicator(ind):
    """Returns a dict with the cleaned series, latest values, and any error message."""
    result = {"series": None, "latest": None, "previous": None, "first_date": None,
              "latest_date": None, "official_title": "", "error": None}
    try:
        source = ind["source"]
        if source in ("fred", "fred_ratio"):
            key = get_fred_key()
            if not key:
                result["error"] = "Add your FRED API key to .streamlit/secrets.toml"
                return result
            if source == "fred":
                raw = fetch_fred(ind["code"], key)
            else:
                top, bottom = ind["code"].split("/")
                a, b = fetch_fred(top, key), fetch_fred(bottom, key)
                raw = (a / b).dropna()
        elif source == "ons":
            raw, result["official_title"] = fetch_ons(ind["code"], ind["dataset"], ind["topic"])
        elif source == "boe":
            raw = fetch_boe(ind["code"])
        elif source == "yahoo":
            raw = fetch_yahoo(ind["code"])
        elif source == "ecb":
            raw, result["official_title"] = fetch_ecb(ind["code"])
        elif source == "derived":
            result["error"] = "calculated after the other indicators load"
            return result
        else:
            raise ValueError(f"Unknown source '{source}'")

        series = apply_transform(raw, ind.get("transform", "level")) * ind.get("scale", 1)
        _finish(result, series)
    except requests.RequestException as exc:
        result["error"] = f"Couldn't reach the data source ({type(exc).__name__})"
    except Exception as exc:
        result["error"] = f"Data problem: {exc}"
    return result


def _finish(result, series):
    series = series.dropna()
    if series.empty:
        raise ValueError("no data after transform")
    result["series"] = series
    result["first_date"] = series.index[0]
    result["latest"] = float(series.iloc[-1])
    result["latest_date"] = series.index[-1]
    result["previous"] = float(series.iloc[-2]) if len(series) > 1 else None
    result["error"] = None


def to_monthly(series):
    """Puts any series onto month-start dates (last reading of each month)."""
    return series.resample("MS").last().dropna()


def _is_daily(series):
    gap = pd.Series(series.index[-60:]).diff().dt.days.median()
    return gap is not None and gap <= 4


def compute_derived(ind, loaded):
    """
    Works out 'a - b', 'a / b' or 'a * b' indicators from two others,
    e.g. Bank Rate minus CPI, copper / gold, GBP/USD x USD/JPY.
    Two daily series are matched day by day; anything else month by month.
    """
    result = {"series": None, "latest": None, "previous": None, "first_date": None,
              "latest_date": None, "official_title": "", "error": None}
    try:
        op = next(o for o in (" - ", " / ", " * ") if o in ind["code"])
        left, right = [part.strip() for part in ind["code"].split(op)]
        a, b = loaded[left][1]["series"], loaded[right][1]["series"]
        if a is None or b is None:
            raise ValueError(f"needs both {left} and {right} to load first")
        if _is_daily(a) and _is_daily(b):
            joined = pd.concat([a, b], axis=1, sort=True).ffill(limit=3).dropna()
        else:
            # monthly, carrying values forward so months line up (e.g. CPI comes out later)
            joined = pd.concat([to_monthly(a), to_monthly(b)], axis=1,
                               sort=True).ffill(limit=2).dropna()
        x, y = joined.iloc[:, 0], joined.iloc[:, 1]
        value = x - y if op == " - " else x / y if op == " / " else x * y
        _finish(result, value * ind.get("scale", 1))
    except Exception as exc:
        result["error"] = f"Data problem: {exc}"
    return result


# ---------------------------------------------------------------- ECB (euro area)

def parse_ecb(csv_text):
    df = pd.read_csv(io.StringIO(csv_text))
    if "TIME_PERIOD" not in df.columns or "OBS_VALUE" not in df.columns:
        raise ValueError("ECB reply missing TIME_PERIOD/OBS_VALUE")
    periods = df["TIME_PERIOD"].astype(str)
    if periods.str.contains("Q").any():
        dates = [pd.Period(p.replace("-", ""), freq="Q").start_time for p in periods]
    else:
        dates = pd.to_datetime(periods)
    title = str(df["TITLE"].iloc[0]) if "TITLE" in df.columns and len(df) else ""
    s = pd.Series(pd.to_numeric(df["OBS_VALUE"], errors="coerce").values,
                  index=pd.DatetimeIndex(dates))
    return s.dropna().sort_index(), title


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def fetch_ecb(code):
    flow, key = code.split("/", 1)
    text = _get(f"https://data-api.ecb.europa.eu/service/data/{flow}/{key}",
                params={"format": "csvdata"}).text
    return parse_ecb(text)


# ---------------------------------------------------------------- BIS (central bank rates)

def parse_bis(csv_text):
    """BIS SDMX CSV -> table: one column per country (REF_AREA), monthly rows."""
    df = pd.read_csv(io.StringIO(csv_text))
    cols = {c.upper(): c for c in df.columns}
    need = ("REF_AREA", "TIME_PERIOD", "OBS_VALUE")
    if not all(n in cols for n in need):
        raise ValueError("BIS reply missing expected columns")
    df = df[[cols[n] for n in need]]
    df.columns = list(need)
    df["TIME_PERIOD"] = pd.to_datetime(df["TIME_PERIOD"].astype(str))
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    return df.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE").sort_index()


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def fetch_policy_rates(areas, start_year=1990):
    """Monthly central bank policy rates from the BIS for several countries in one request."""
    key = "M." + "+".join(sorted(set(areas)))
    attempts = [
        (f"https://stats.bis.org/api/v1/data/WS_CBPOL/{key}/all",
         {"format": "csv", "startPeriod": str(start_year)}, {}),
        (f"https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/{key}",
         {"startPeriod": str(start_year)}, {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}),
    ]
    last_error = None
    for url, params, extra in attempts:
        try:
            r = requests.get(url, params=params, headers={**HEADERS, **extra}, timeout=TIMEOUT)
            r.raise_for_status()
            return parse_bis(r.text)
        except Exception as exc:
            last_error = exc
    raise last_error


# ---------------------------------------------------------------- Google News search

@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_news_search(query, days=30):
    """Headlines and links from a Google News RSS search over the last `days` days."""
    import feedparser
    text = _get("https://news.google.com/rss/search",
                params={"q": f"{query} when:{days}d", "hl": "en-GB", "gl": "GB",
                        "ceid": "GB:en"}).content
    parsed = feedparser.parse(text)
    rows = []
    for entry in parsed.get("entries", []):
        title = str(entry.get("title", "")).strip()
        source = ""
        src = entry.get("source")
        if isinstance(src, dict):
            source = src.get("title", "")
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        stamp = entry.get("published_parsed")
        rows.append(dict(time=pd.Timestamp(*stamp[:6]) if stamp else pd.NaT,
                         source=source or "Google News", headline=title,
                         link=entry.get("link", ""), topics=[]))
    df = pd.DataFrame(rows, columns=["time", "source", "headline", "link", "topics"])
    return df.sort_values("time", ascending=False) if not df.empty else df


# ---------------------------------------------------------------- Yahoo monitors

def parse_yahoo_batch(frame, tickers):
    """yfinance download (many tickers) -> table of closing prices, one column per ticker."""
    if frame is None or frame.empty:
        raise ValueError("Yahoo Finance returned no prices")
    if isinstance(frame.columns, pd.MultiIndex):
        level = 0 if "Close" in frame.columns.get_level_values(0) else 1
        close = frame.xs("Close", axis=1, level=level)
    else:
        close = frame[["Close"]].rename(columns={"Close": tickers[0]})
    close.index = pd.DatetimeIndex(close.index).tz_localize(None) \
        if pd.DatetimeIndex(close.index).tz is not None else pd.DatetimeIndex(close.index)
    return close.sort_index()


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_yahoo_batch(tickers):
    import yfinance as yf
    frame = yf.download(list(tickers), period="2y", interval="1d", auto_adjust=False,
                        progress=False, threads=True)
    return parse_yahoo_batch(frame, list(tickers))


def performance_table(prices, names):
    """Last price and % change over 1 day, 1 week, 1 month, year to date and 1 year."""
    rows = []
    for ticker, name in names:
        if ticker not in prices.columns:
            continue
        s = prices[ticker].dropna()
        if len(s) < 2:
            continue
        last, end = float(s.iloc[-1]), s.index[-1]

        def chg(when):
            past = s.asof(when)
            return None if pd.isna(past) or not past else (last / float(past) - 1) * 100
        ytd_base = s[s.index < pd.Timestamp(end.year, 1, 1)]
        rows.append({
            "Ticker": ticker, "Name": name, "Last": last,
            "1D %": (last / float(s.iloc[-2]) - 1) * 100,
            "1W %": chg(end - pd.Timedelta(days=7)),
            "1M %": chg(end - pd.DateOffset(months=1)),
            "YTD %": (last / float(ytd_base.iloc[-1]) - 1) * 100 if len(ytd_base) else None,
            "1Y %": chg(end - pd.DateOffset(years=1)),
            "Trend (1Y)": [float(v) for v in s[s.index >= end - pd.DateOffset(years=1)].iloc[::3]],
            "As of": end,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- currency strength

@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_fx_history(base, currencies, days=400):
    start = (date.today() - timedelta(days=days)).isoformat()
    payload = _get(f"https://api.frankfurter.app/{start}..",
                   params={"from": base, "to": ",".join(c for c in currencies if c != base)}).json()
    rates = pd.DataFrame(payload.get("rates", {})).T
    if rates.empty:
        raise ValueError("FX source returned no rates")
    rates.index = pd.to_datetime(rates.index)
    return rates.sort_index()


def currency_strength(rates):
    """
    rates: units of each currency per 1 unit of the base.
    A currency 'strengthens' against the base when fewer units buy 1 base unit,
    so strength % = (old rate / new rate - 1) x 100.
    """
    end = rates.index[-1]
    horizons = {"1D": rates.index[-2] if len(rates) > 1 else end,
                "1W": end - pd.Timedelta(days=7), "1M": end - pd.DateOffset(months=1),
                "3M": end - pd.DateOffset(months=3), "YTD": pd.Timestamp(end.year - 1, 12, 31),
                "1Y": end - pd.DateOffset(years=1)}
    latest = rates.iloc[-1]
    out = {}
    for label, when in horizons.items():
        past = rates[rates.index <= when]
        out[label] = (past.iloc[-1] / latest - 1) * 100 if len(past) else latest * float("nan")
    return pd.DataFrame(out)


# ---------------------------------------------------------------- links and names

SOURCE_NAMES = {
    "fred": "FRED (Federal Reserve Bank of St. Louis)",
    "fred_ratio": "FRED (Federal Reserve Bank of St. Louis), calculated",
    "ons": "Office for National Statistics",
    "boe": "Bank of England Statistical Database",
    "yahoo": "Yahoo Finance (unofficial)",
    "derived": "Calculated from other indicators on this dashboard",
    "ecb": "European Central Bank Data Portal",
}


def source_url(ind):
    """A link to the indicator's page on the source website."""
    src, code = ind["source"], ind["code"]
    if src == "fred":
        return f"https://fred.stlouisfed.org/series/{code}"
    if src == "fred_ratio":
        return f"https://fred.stlouisfed.org/series/{code.split('/')[0]}"
    if src == "ons":
        return f"https://www.ons.gov.uk/{ind['topic']}/timeseries/{code.lower()}/{ind['dataset']}"
    if src == "boe":
        return ("https://www.bankofengland.co.uk/boeapps/database/"
                f"fromshowcolumns.asp?SeriesCodes={code}&UsingCodes=Y")
    if src == "yahoo":
        return f"https://finance.yahoo.com/quote/{code}"
    if src == "ecb":
        flow, key = code.split("/", 1)
        return f"https://data.ecb.europa.eu/data/datasets/{flow}/{flow}.{key}"
    return ""


def load_us_recession_flags():
    """NBER recession indicator (1 = recession month). Returns None if unavailable."""
    key = get_fred_key()
    if not key:
        return None
    try:
        return fetch_fred("USREC", key)
    except Exception:
        return None


# ---------------------------------------------------------------- yield curves

def build_curve(series_by_label):
    """
    Takes {"2Y": Series, "10Y": Series, ...} and returns a table with each
    maturity's latest yield and its yield about one year earlier.
    """
    rows = []
    latest_dates = [s.index[-1] for s in series_by_label.values() if not s.empty]
    if not latest_dates:
        raise ValueError("no curve data")
    today = min(latest_dates)                     # a date every maturity has reached
    year_ago = today - pd.DateOffset(years=1)
    for label, s in series_by_label.items():
        s = s.dropna()
        rows.append({
            "Maturity": label,
            "Latest": s.asof(today) if not s.empty else None,
            "1 year ago": s.asof(year_ago) if not s.empty else None,
        })
    return pd.DataFrame(rows), today, year_ago


def load_curve(curve):
    """Returns (table, latest date, year-ago date, error message)."""
    try:
        series = {}
        if curve["source"] == "fred":
            key = get_fred_key()
            if not key:
                return None, None, None, "Add your FRED API key to .streamlit/secrets.toml"
            for label, code in curve["points"]:
                series[label] = fetch_fred(code, key)
        elif curve["source"] == "boe":
            for label, code in curve["points"]:
                series[label] = fetch_boe(code)
        else:
            raise ValueError(f"Unknown source '{curve['source']}'")
        table, today, year_ago = build_curve(series)
        return table, today, year_ago, None
    except requests.RequestException as exc:
        return None, None, None, f"Couldn't reach the data source ({type(exc).__name__})"
    except Exception as exc:
        return None, None, None, f"Data problem: {exc}"


# ---------------------------------------------------------------- news

def classify_headline(title, topics):
    text = f" {title.lower()} "
    return [topic for topic, words in topics.items() if any(w in text for w in words)]


def parse_feed(parsed, source_name, topics):
    """Turns a feedparser result into rows: time, source, headline, link, topics."""
    rows = []
    for entry in parsed.get("entries", []):
        title = str(entry.get("title", "")).strip()
        link = entry.get("link", "")
        if not title or not link:
            continue
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        when = pd.Timestamp(*stamp[:6]) if stamp else pd.NaT
        rows.append(dict(time=when, source=source_name, headline=title, link=link,
                         topics=classify_headline(title, topics)))
    return rows


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_news(feeds, topics):
    """Downloads every feed. Feeds that fail are listed instead of stopping the page."""
    import feedparser
    rows, failed = [], []
    for name, url in feeds:
        try:
            text = _get(url).content
            rows += parse_feed(feedparser.parse(text), name, dict(topics))
        except Exception:
            failed.append(name)
    df = pd.DataFrame(rows, columns=["time", "source", "headline", "link", "topics"])
    if not df.empty:
        df = df.drop_duplicates("headline").sort_values("time", ascending=False,
                                                        na_position="last")
    return df, failed


# ---------------------------------------------------------------- IMF (global)

def parse_imf(payload, indicator):
    """IMF DataMapper reply -> table with one row per country and one column per year."""
    values = payload.get("values", {}).get(indicator, {})
    if not values:
        raise ValueError("IMF returned no values")
    df = pd.DataFrame(values).T
    df.columns = [int(c) for c in df.columns]
    return df.apply(pd.to_numeric, errors="coerce").sort_index(axis=1)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def fetch_imf(indicator, years):
    url = f"https://www.imf.org/external/datamapper/api/v1/{indicator}"
    payload = _get(url, params={"periods": ",".join(str(y) for y in years)}).json()
    return parse_imf(payload, indicator)


@st.cache_data(ttl=7 * 24 * 60 * 60, show_spinner=False)
def fetch_imf_countries():
    payload = _get("https://www.imf.org/external/datamapper/api/v1/countries").json()
    return {code: info.get("label", code)
            for code, info in payload.get("countries", {}).items()}


# ---------------------------------------------------------------- calendar

def parse_calendar(payload, keep):
    rows = [r for r in payload.get("release_dates", [])
            if any(k.lower() in r.get("release_name", "").lower() for k in keep)]
    df = pd.DataFrame(rows, columns=["release_id", "release_name", "date"])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates(["release_name", "date"]).sort_values("date")


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_calendar(api_key, keep, days=45):
    today = date.today()
    payload = _get("https://api.stlouisfed.org/fred/releases/dates", params={
        "api_key": api_key, "file_type": "json",
        "realtime_start": today.isoformat(),
        "realtime_end": (today + timedelta(days=days)).isoformat(),
        "include_release_dates_with_no_data": "true",
        "sort_order": "asc", "limit": 1000,
    }).json()
    return parse_calendar(payload, list(keep))


# ---------------------------------------------------------------- PMI file

PMI_COLUMNS = ["date", "region", "survey", "value", "source"]


def load_pmi(path):
    """Reads data/pmi.csv. Returns an empty table if the file has no rows yet."""
    try:
        df = pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame(columns=PMI_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=PMI_COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value"]).sort_values("date")
