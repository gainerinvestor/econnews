#!/usr/bin/env python3
"""
EconNews Auto-Updater
Fetches economics news from RSS feeds → writes economics_news.json
Runs daily via GitHub Actions
"""

import json, re, time, sys
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

# ── RSS sources ───────────────────────────────────────────────────────────
RSS_FEEDS = [
    # Indian sources
    ("Economic Times - Economy",      "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms"),
    ("Economic Times - Markets",      "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Business Standard - Economy",   "https://www.business-standard.com/rss/economy-policy-102.rss"),
    ("Business Standard - Markets",   "https://www.business-standard.com/rss/markets-106.rss"),
    ("LiveMint - Economy",            "https://www.livemint.com/rss/economy"),
    ("IBEF News",                     "https://ibef.org/news.xml"),
    # Global sources
    ("Reuters - Business",            "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters - India",               "https://feeds.reuters.com/reuters/INbusinessNews"),
]

# ── Keywords for economics relevance ─────────────────────────────────────
ECON_KEYWORDS = [
    "gdp","economy","economic","inflation","deflation","cpi","wpi",
    "trade","export","import","fiscal","monetary","rbi","reserve bank",
    "budget","tax","gst","market","sensex","nifty","bse","nse",
    "currency","rupee","dollar","investment","fdi","fii","manufacturing",
    "industry","growth","recession","employment","jobs","unemployment",
    "wages","income","debt","deficit","surplus","spending","revenue",
    "imf","world bank","oecd","interest rate","repo rate","policy",
    "banking","credit","loan","reform","privatisation","disinvestment",
    "infrastructure","capex","pli","msme","startup","fintech",
]

INDIA_KEYWORDS = [
    "india","indian","delhi","mumbai","chennai","bangalore","kolkata",
    "hyderabad","rupee","sebi","rbi","niti aayog","modi","fm","finance minister",
    "nifty","sensex","bse","nse","asian","south asia","tamil nadu","maharashtra",
]

CATEGORY_MAP = {
    "gdp_growth":       ["gdp","gross domestic product","growth rate","economic growth"],
    "inflation":        ["inflation","cpi","wpi","consumer price","wholesale price","prices"],
    "monetary_policy":  ["rbi","repo rate","interest rate","monetary policy","mpc","rate cut","rate hike"],
    "stock_market":     ["sensex","nifty","bse","nse","stock","equity","market rally","market fall"],
    "trade":            ["export","import","trade deficit","trade surplus","fta","wto","tariff"],
    "fiscal_policy":    ["budget","fiscal","tax","gst","revenue","spending","deficit","surplus"],
    "manufacturing":    ["manufacturing","pli","msme","industry","production","factory","output"],
    "banking":          ["bank","credit","loan","nbfc","npa","bad loan","rbi","banking"],
    "investment":       ["fdi","fii","investment","capex","infrastructure","startup"],
    "employment":       ["job","employment","unemployment","wage","labour","workforce"],
}

# ── Helpers ───────────────────────────────────────────────────────────────
class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset(); self.fed = []
    def handle_data(self, d): self.fed.append(d)
    def get_data(self): return " ".join(self.fed)

def strip_html(html):
    s = HTMLStripper(); s.feed(html or ""); return s.get_data().strip()

def clean(text):
    text = strip_html(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:300] if len(text) > 300 else text

def score_text(title, summary):
    text = f"{title} {summary}".lower()
    score = 5
    high = ["gdp","inflation","rbi","repo rate","budget","trade deficit","recession",
            "imf","world bank","sensex crash","market crash","fdi","economic growth"]
    med  = ["export","import","manufacturing","employment","fiscal","monetary","banking"]
    for w in high:
        if w in text: score = min(10, score + 1)
    for w in med:
        if w in text: score = min(10, score + 0.5)
    return round(min(10, score))

def categorise(title, summary):
    text = f"{title} {summary}".lower()
    for cat, kws in CATEGORY_MAP.items():
        if any(k in text for k in kws):
            return cat
    return "general"

def is_econ(title, summary):
    text = f"{title} {summary}".lower()
    return any(k in text for k in ECON_KEYWORDS)

def is_india(title, summary):
    text = f"{title} {summary}".lower()
    return any(k in text for k in INDIA_KEYWORDS)

def fetch_rss(name, url, timeout=12):
    articles = []
    try:
        req = Request(url, headers={"User-Agent": "EconNews/2.0 (+https://github.com)"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # Handle both RSS and Atom
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)

        for item in items[:20]:
            def get(tag, alt=""):
                el = item.find(tag) or item.find(f"atom:{tag}", ns)
                return (el.text or "").strip() if el is not None else alt

            title   = clean(get("title"))
            summary = clean(get("description") or get("summary") or get("content"))
            link    = get("link") or get("atom:link")
            if not link:
                le = item.find("link")
                link = (le.get("href","") if le is not None else "")
            pub = get("pubDate") or get("published") or get("updated") or datetime.now(timezone.utc).isoformat()

            if not title or not is_econ(title, summary):
                continue

            articles.append({
                "title":          title,
                "summary":        summary or "Tap to read full article.",
                "source":         name,
                "url":            link,
                "published_date": pub,
                "category":       categorise(title, summary),
                "tags":           [k for k in ECON_KEYWORDS if k in f"{title} {summary}".lower()][:6],
                "india_impact":   is_india(title, summary),
                "global_impact":  True,
                "impact_score":   score_text(title, summary),
            })

        print(f"  ✓ {name}: {len(articles)} articles")
    except URLError as e:
        print(f"  ✗ {name}: network error — {e.reason}", file=sys.stderr)
    except ET.ParseError as e:
        print(f"  ✗ {name}: XML parse error — {e}", file=sys.stderr)
    except Exception as e:
        print(f"  ✗ {name}: {e}", file=sys.stderr)
    return articles

def deduplicate(articles):
    seen, out = set(), []
    for a in articles:
        key = re.sub(r'\W+','',a['title'].lower())[:60]
        if key not in seen:
            seen.add(key); out.append(a)
    return out

def run():
    print("EconNews Auto-Updater starting…")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}\n")

    all_articles = []
    for name, url in RSS_FEEDS:
        print(f"Fetching: {name}")
        articles = fetch_rss(name, url)
        all_articles.extend(articles)
        time.sleep(1)   # polite delay

    # Deduplicate + sort by impact
    unique = deduplicate(all_articles)
    unique.sort(key=lambda a: (a['impact_score'], a['india_impact']), reverse=True)
    top = unique[:30]   # keep top 30

    india_count  = sum(1 for a in top if a['india_impact'])
    global_count = sum(1 for a in top if a['global_impact'])

    payload = {
        "metadata": {
            "last_updated":       datetime.now(timezone.utc).isoformat(),
            "total_articles":     len(top),
            "india_impact_count": india_count,
            "global_impact_count":global_count,
            "sources":            [n for n,_ in RSS_FEEDS],
            "auto_updated":       True,
        },
        "articles": top,
    }

    with open("economics_news.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done — {len(top)} articles saved")
    print(f"   India: {india_count}  |  Global: {global_count}")
    print(f"   Top headline: {top[0]['title'][:80] if top else 'N/A'}")

if __name__ == "__main__":
    run()
