# sentiment_parser.py — Echtquellen (RSS/NewsAPI/Trends/Reddit), gewichtetes Scoring, UTC-Timestamps
# Stand: 2025-08-10

from __future__ import annotations
import os
import re
import json
import time
import unicodedata
import tempfile
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import requests
import feedparser
from pytrends.request import TrendReq

# ========= Einstellungen / ENV =========
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()

LOG_PATH = "sentiment_log.jsonl"   # line-delimited JSON
MAX_LOG_LINES = 50_000             # Rotation

# RSS-Quellen (keine Keys nötig)
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.theblock.co/rss",
    "https://decrypt.co/feed",
    "https://www.reddit.com/r/CryptoCurrency/.rss",
    "https://www.reddit.com/r/CryptoMarkets/.rss",
]

# Google Trends Keywords
TRENDS_KEYWORDS = ["bitcoin", "ethereum", "crypto crash", "altcoins", "binance"]

# Gewichte nach Quelle
WEIGHTS = {
    "news": 1.5,     # CoinDesk/CT/TheBlock/Decrypt/NewsAPI
    "reddit": 0.9,   # Reddit RSS
    "google": 1.0,   # Trends
}

# Keywords (de/en + Emojis)
POSITIVE = [
    r"\ballzeithoch\b", r"\bto the moon\b", r"\bparabolic\b", r"\bkaufen\b",
    r"\bbull(ish)?\b", r"\bbuy\b", r"\brug(en)?\b", r"\brally\b",
    r"\bübertrifft\b", r"\bbreak(out)?\b", r"\brise(s|n)?\b",
    r"🚀", r"📈", r"✅", r"\bprofit(e)?\b", r"\bgewinn(e)?\b", r"\bapproval\b",
]
NEGATIVE = [
    r"\babsturz\b", r"\bcrash\b", r"\bverbot\b", r"\bban(ned)?\b", r"\bpanik\b",
    r"\bpanic\b", r"\bdump(ing)?\b", r"\bpleite\b", r"\bskandal\b", r"\bhack\b",
    r"\bbetrug\b", r"\bverkauf(en)?\b", r"\bsell\b", r"\bcharge(s|d)?\b",
    r"📉", r"❌", r"⚠️", r"\bfud\b", r"\bcollapse\b", r"\bliquidation(s)?\b",
]
POS_PAT = [re.compile(p, re.IGNORECASE) for p in POSITIVE]
NEG_PAT = [re.compile(p, re.IGNORECASE) for p in NEGATIVE]

# ========= Utils =========
def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _normalize(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return unicodedata.normalize("NFKC", text).strip()

def _score_text(text: str) -> int:
    t = _normalize(text)
    pos = sum(1 for p in POS_PAT if p.search(t))
    neg = sum(1 for n in NEG_PAT if n.search(t))
    if pos == neg == 0:
        return 0
    return pos - neg

def _atomic_append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    # einfache Rotation: wenn zu groß, halbiere
    try:
        if os.path.exists(path):
            # grob: Zeilen zählen (ohne riesige RAM-Last)
            with open(path, "r", encoding="utf-8") as f:
                count = sum(1 for _ in f)
            if count >= MAX_LOG_LINES:
                # halbiere Datei
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                keep = lines[len(lines)//2:]
                with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
                    tf.writelines(keep)
                    tmp = tf.name
                os.replace(tmp, path)
    except Exception as e:
        print(f"[Sentiment] Rotation-Warnung: {e}")

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

# ========= Fetchers =========
def fetch_rss_titles(url: str, limit: int = 10) -> List[str]:
    try:
        feed = feedparser.parse(url)
        titles = []
        for entry in feed.entries[:limit]:
            title = entry.get("title") or ""
            titles.append(_normalize(title))
        return titles
    except Exception as e:
        print(f"[RSS] Fehler {url}: {e}")
        return []

def fetch_all_rss(feeds: List[str], limit_per_feed: int = 6) -> List[str]:
    titles: List[str] = []
    for u in feeds:
        titles.extend(fetch_rss_titles(u, limit_per_feed))
        # kleines Delay gegen Rate Limits
        time.sleep(0.1)
    # deduplicate
    seen = set()
    out = []
    for t in titles:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out

def fetch_newsapi_titles(query="(crypto OR bitcoin OR ethereum) AND -price", language="de", page_size=10) -> List[str]:
    if not NEWS_API_KEY:
        return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": language,
            "sortBy": "publishedAt",
            "pageSize": page_size,
        }
        headers = {"X-Api-Key": NEWS_API_KEY}
        r = requests.get(url, headers=headers, params=params, timeout=12)
        if r.status_code != 200:
            print(f"[NewsAPI] HTTP {r.status_code}: {r.text[:200]}")
            return []
        js = r.json()
        arts = js.get("articles", []) or []
        return [_normalize(a.get("title") or "") for a in arts[:page_size] if (a.get("title") or "").strip()]
    except Exception as e:
        print(f"[NewsAPI] Fehler: {e}")
        return []

def fetch_google_trends(keywords: List[str] = None) -> Dict[str, int]:
    try:
        kw = keywords or TRENDS_KEYWORDS
        pytrends = TrendReq(hl='de', tz=360)  # Berlin
        pytrends.build_payload(kw, cat=0, timeframe='now 1-d')
        df = pytrends.interest_over_time()
        out: Dict[str, int] = {}
        for k in kw:
            try:
                out[k] = int(df[k].iloc[-1])
            except Exception:
                out[k] = 0
        return out
    except Exception as e:
        print(f"[Trends] Fehler: {e}")
        return {}

# ========= Haupt-API =========
def get_sentiment_data() -> Dict[str, Any]:
    """
    Aggregiert echte Headlines (RSS + NewsAPI) + Google Trends.
    Liefert:
    {
      "timestamp": ISO-UTC,
      "score": float,
      "sentiment": "bullish|neutral|bearish",
      "sources": [... Titel ...],
      "breakdown": {
          "news": {"count": n, "score": x, "examples": [...]},
          "reddit": {...},
          "google": {"score": x, "details": {...}}
      }
    }
    """
    # 1) RSS (News & Reddit)
    rss_titles = fetch_all_rss(RSS_FEEDS, limit_per_feed=6)
    news_like = [t for t in rss_titles if not t.lower().startswith("[removed]")]
    reddit_like = [t for t in rss_titles if "reddit" in t.lower()]  # Heuristik (optional)

    # 2) NewsAPI (optional, DE)
    newsapi_titles = fetch_newsapi_titles()

    # 3) Google Trends
    trends = fetch_google_trends()

    # Scoring
    def score_list(titles: List[str]) -> int:
        return sum(_score_text(t) for t in titles)

    news_titles = news_like + newsapi_titles
    reddit_titles = [t for t in rss_titles if t not in news_titles]  # Rest grob als reddit einordnen

    news_score = score_list(news_titles)
    reddit_score = score_list(reddit_titles)

    # Trends: positiv, wenn bitcoin/ethereum hoch & "crypto crash" niedrig
    trends_score = 0
    if trends:
        btc = trends.get("bitcoin", 0)
        eth = trends.get("ethereum", 0)
        crash = trends.get("crypto crash", 0)
        alt = trends.get("altcoins", 0)
        trends_score = (btc + eth + alt) // 30 - (crash // 30)  # grobe Normalisierung

    # Gewichtung
    weighted = news_score * WEIGHTS["news"] + reddit_score * WEIGHTS["reddit"] + trends_score * WEIGHTS["google"]

    # Klassifikation
    sentiment = "neutral"
    if weighted >= 3:
        sentiment = "bullish"
    elif weighted <= -3:
        sentiment = "bearish"

    result = {
        "timestamp": _utc_iso(),
        "score": round(float(weighted), 2),
        "sentiment": sentiment,
        "sources": (news_titles + reddit_titles)[:40],  # kompakt
        "breakdown": {
            "news": {"count": len(news_titles), "score": news_score, "examples": news_titles[:8]},
            "reddit": {"count": len(reddit_titles), "score": reddit_score, "examples": reddit_titles[:8]},
            "google": {"score": trends_score, "details": trends},
        },
    }

    # Loggen (jsonl, atomar rotierend)
    try:
        _atomic_append_jsonl(LOG_PATH, result)
    except Exception as e:
        print(f"[Sentiment] Log-Fehler: {e}")

    return result

# Optional: CLI-Test
if __name__ == "__main__":
    data = get_sentiment_data()
    print(json.dumps(data, ensure_ascii=False, indent=2))
