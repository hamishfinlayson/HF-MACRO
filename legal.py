"""
legal.py - the site's disclaimer, terms, privacy policy, cookie policy, accessibility
statement and about/contact details. Plain English, written for a free, personal,
non-commercial educational project run from the UK.

To change your contact link, edit CONTACT_URL below.
"""

OWNER = "Hamish Finlayson"
CONTACT_URL = "https://www.linkedin.com/search/results/people/?keywords=Hamish%20Finlayson"
CONTACT_LABEL = "Message Hamish Finlayson on LinkedIn"
LAST_UPDATED = "24 October 2026"
MIN_AGE = 18
CONSENT_COOKIE = "hfm_consent"

DISCLAIMER_SHORT = ("NOT FINANCIAL ADVICE. HF Macro is a free educational project. Data can be delayed, "
                    "incomplete or wrong, and forecasts are simple statistical estimates, not predictions. "
                    "Don't make investment decisions based on this site.")

SECTIONS = {
    "disclaimer": ("Disclaimer", f"""
### Disclaimer: not financial advice

**Nothing on HF Macro is financial, investment, tax, legal or any other professional advice.**
It is not a recommendation to buy, sell or hold anything, and it does not take your personal
circumstances into account.

- **Educational only.** HF Macro is a personal, non-commercial learning project built by {OWNER},
  an accounting student. It is not run by a regulated firm and is not authorised by the
  Financial Conduct Authority (FCA).
- **Data can be wrong.** Figures come from third-party sources (listed under *Data sources*
  below). They can be delayed (some by hours or days), revised, incomplete or wrong. Prices shown
  by TradingView may also be delayed. Nothing here is real-time unless the source says so.
- **Forecasts are not predictions.** The 12-month forecasts are simple statistical models
  (autoregressive models with simulated ranges). The confidence score only counts how many related
  indicators point the same way. It is **not** a probability that the forecast is right, and these
  models are often wrong, especially for market prices.
- **Past performance is not a reliable indicator of future results.** Investments can go down as
  well as up, and you could lose money.
- **Do your own research.** If you need advice, speak to a qualified, FCA-authorised adviser.

HF Macro is not affiliated with, endorsed by or connected to Bloomberg L.P., TradingView, the
Federal Reserve, the Bank of England, the ECB, the ONS, the IMF or any other organisation named on
the site. Their names are used only to say where data comes from.
"""),

    "terms": ("Terms of service", f"""
### Terms of service

*Last updated: {LAST_UPDATED}*

By using HF Macro you agree to these terms. If you don't agree, please don't use the site.

**1. Who runs it.** HF Macro is a free, personal, non-commercial educational project run by
{OWNER} in the United Kingdom. Contact details are under *About & contact*.

**2. Age.** You must be **{MIN_AGE} or over** to use HF Macro. When you first visit, you're asked
to confirm this. There's no ID check, so this relies on you being honest.

**3. Not advice.** Everything on the site is for general education and information only. Please
read the *Disclaimer*, which forms part of these terms.

**4. Free, with no hidden costs.** HF Macro is free. There are no fees, subscriptions, adverts,
affiliate links, paid placements, sponsored content or in-app purchases, and you don't need an
account.

**5. Data belongs to its owners.** Data, charts and headlines come from the third parties listed
under *Data sources* and remain their property, under their own terms. You may view them for
personal use. Don't copy, scrape or republish data from HF Macro. Get it from the original source
under that source's licence instead.

**6. Fair use.** Don't try to break, overload, scrape or reverse-engineer the site, or use it for
anything unlawful.

**7. No guarantee.** The site is provided "as is". I try to keep it working and accurate but don't
promise that it will be available, error-free, complete or up to date, and I may change or remove
features at any time.

**8. Liability.** As far as the law allows, I'm not liable for any loss or damage arising from
your use of the site or reliance on its content, including investment losses. Nothing in these
terms limits liability that can't legally be limited, such as for death or personal injury caused
by negligence, or for fraud. Nothing here affects your statutory rights.

**9. Links to other sites.** News headlines and source links take you to other websites. I'm not
responsible for their content or their privacy practices.

**10. Changes.** I may update these terms. The date at the top shows when they last changed.

**11. Law.** These terms are governed by the laws of the United Kingdom. If you live in Scotland or
Northern Ireland, you can also bring proceedings in your local courts.
"""),

    "privacy": ("Privacy policy", f"""
### Privacy policy

*Last updated: {LAST_UPDATED}*

**The short version:** HF Macro doesn't ask for your name, email or any account details, doesn't
run its own analytics or advertising, and doesn't sell or share data. The only things that can
involve your personal data are the hosting service and, if you agree to them, TradingView's charts
and Google's fonts.

**Who is responsible.** {OWNER} (United Kingdom), who runs HF Macro as a personal project.
Contact: see *About & contact*.

**What HF Macro itself stores**
- **Your choices.** Your age confirmation and cookie choice are stored in a small cookie
  (`{CONSENT_COOKIE}`) and in the page address, so you aren't asked again on every page. They
  contain no personal details.
- **Pinned charts.** On the public site, charts you pin to Home are kept only for your current
  visit and are not saved on the server.
- **Searches.** What you type in the command bar or news search is used to show results and is
  not stored or logged by HF Macro.

**Hosting (always on).** The site runs on **Streamlit Community Cloud**, provided by
Snowflake Inc. To deliver the site, their servers process technical data such as your IP address,
browser type and the pages you request, and they may set cookies needed to run and secure the
service. Streamlit's own usage statistics are switched off in this app's settings. See
[Streamlit's privacy notice](https://streamlit.io/privacy-policy) and
[Snowflake's privacy notice](https://www.snowflake.com/privacy-notice/).

**Optional third parties (only if you choose "Accept all")**
- **TradingView** charts and price boxes load from TradingView's servers. TradingView receives your
  IP address and browser details and may set cookies. See
  [TradingView's privacy policy](https://www.tradingview.com/privacy-policy/).
- **Google Fonts** supplies the IBM Plex typeface. Your browser contacts Google's servers, which
  receive your IP address. See [Google's privacy policy](https://policies.google.com/privacy).

If you choose "Essential only", neither is loaded, and you see your device's standard fonts and a
button to load the charts if you change your mind.

**Data sources (no personal data).** Economic and market data are fetched by the server, not your
browser, from FRED, ONS, the Bank of England, the ECB, the BIS, the IMF, the World Bank, the EIA,
Frankfurter, CoinGecko, alternative.me, Yahoo Finance (PC edition only) and public news feeds. None
of your information is sent to them.

**Legal basis (UK GDPR).** Hosting data is processed on the basis of legitimate interests (running
a secure website). Optional third-party content is loaded only with your consent, which you can
withdraw at any time under *Cookie settings*.

**How long data is kept.** HF Macro keeps no personal data. The consent cookie expires after six
months. Hosting and third-party providers keep data under their own policies.

**Your rights.** Under UK data protection law you can ask for access to, correction of, or deletion
of your personal data, and you can object to processing. As HF Macro holds no personal data itself,
most requests will be for the providers above. You can also complain to the Information
Commissioner's Office: [ico.org.uk](https://ico.org.uk/make-a-complaint/).

**Age.** HF Macro is for people aged {MIN_AGE} and over and is not directed at children.

**Changes.** Any updates will appear here with a new date.
"""),

    "cookies": ("Cookie policy", f"""
### Cookie policy

*Last updated: {LAST_UPDATED}*

Cookies are small files a website stores in your browser. HF Macro asks for your choice on your
first visit. **"Accept all" and "Essential only" are equally easy to pick**, and you can change
your mind at any time under *Cookie settings* (the link at the bottom of every page).

| Cookie / service | Set by | What it's for | Type | How long |
|---|---|---|---|---|
| `{CONSENT_COOKIE}` | HF Macro | Remembers your age confirmation and cookie choice | Strictly necessary | 6 months |
| Hosting cookies | Streamlit Community Cloud (Snowflake) | Run, balance and secure the hosted app | Strictly necessary | Set by the host |
| TradingView cookies | TradingView | Power the embedded charts and price boxes, and may be used for TradingView's own analytics | Optional: only with "Accept all" | Set by TradingView |
| Google Fonts | Google | Load the typeface. No cookies, but your IP address is sent to Google | Optional: only with "Accept all" | n/a |

HF Macro uses **no** advertising cookies and **no** analytics or tracking cookies of its own.

**Strictly necessary** cookies don't need consent under the UK's Privacy and Electronic
Communications Regulations (PECR) because the site can't work, or can't remember your choice,
without them. You can also block or delete cookies in your browser settings. If you block all
cookies, you may be asked for your choice again on each visit.
"""),

    "accessibility": ("Accessibility", """
### Accessibility and keyboard use

HF Macro can be used with a keyboard:

| Key | What it does |
|---|---|
| `Tab` / `Shift + Tab` | Move forwards / backwards through links, buttons, cards and menus (a red outline shows where you are) |
| `Enter` or `Space` | Open the focused card, link, button or (i) explanation |
| `/` | Jump to the command bar from anywhere |
| `Esc` | Close any open (i) explanation |
| Arrow keys | Move through options in a menu or the command bar's results |

**Other features.** Every chart has a matching number display. Rises and falls are shown with
+ and − signs and arrows, not only colour. Every indicator has a text description (the INFO
screen).

**Known limitations.** The interactive charts are visual and are hard to use with a screen reader.
Use the INFO screens and tables instead. TradingView's embedded charts are controlled by
TradingView. If something doesn't work for you, please get in touch (see *About & contact*).
"""),

    "about": ("About & contact", f"""
### About HF Macro

HF Macro is a terminal-style dashboard for UK, US, euro area and global economic data, markets,
currencies and commodities, inspired by professional market terminals. It was designed and built by
**{OWNER}**, a BA (Hons) Accounting student based in the UK, as a personal learning project.

- **Cost:** free. No adverts, no paid features, no affiliate links, no sponsorship.
- **Reviews and testimonials:** none are shown on this site.
- **Commercial status:** non-commercial. It is not a business, and nothing is for sale.
- **Contact:** [{CONTACT_LABEL}]({CONTACT_URL}). Use this for questions, corrections, accessibility
  problems or privacy requests.

**Data sources.** FRED (Federal Reserve Bank of St. Louis; this product uses the FRED® API but is
not endorsed or certified by it; some series are owned by third parties) · Office for National
Statistics (Open Government Licence v3.0) · Bank of England · European Central Bank · Bank for
International Settlements · IMF · World Bank · US Energy Information Administration · ECB reference
rates via Frankfurter · CoinGecko · alternative.me · TradingView (embedded widgets) · headlines and
links from Google News and public RSS feeds.
"""),
}
