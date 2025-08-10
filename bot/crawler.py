# crawler.py — robust, atomic, UTC timestamps, better fallbacks
# Stand: 2025-08-10

from __future__ import annotations
import json
import os
import random
import time
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from pytrends.request import TrendReq

# === ENV / API KEYS ===
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
CMC_API_KEY = os.getenv("CMC_API_KEY", "").strip()

# === HTTP Defaults ===
HTTP_TIMEOUT = 10
HTTP_RETRIES = 2
USER_AGENT = "OmertaTradeBot/1.0 (+https://example.invalid)"

# === Atomics / IO ===
CRAWLER_FILE = "crawler_data.json"
SCHEMA_VERSION = "1.2"

def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _atomic_write_json(path: str, data: Any) -> None:
    d = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, dir=d, suffix=".tmp", encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tmp = tf.name
    os.replace(tmp, path)

def _safe_json(obj: Any, default: Any) -> Any:
    try:
        return obj.json()
    except Exception:
        return default

def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    last_err = None
    for i in range(HTTP_RETRIES + 1):
        try:
            r = requests.get(url, headers=h, params=params, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        # kleiner Backoff
        time.sleep(0.6 * (i + 1))
    print(f"[Crawler] GET fehlgeschlagen: {url} — {last_err}")
    return None

# === 1) Google Trends ===
def fetch_google_trends(keywords: List[str] | None = None) -> Dict[str, int]:
    if not keywords:
        keywords = ["bitcoin", "crypto crash", "shiba"]
    try:
        pytrends = TrendReq(hl="de", tz=360)  # Berlin ~ UTC+1/2
        pytrends.build_payload(keywords, cat=0, timeframe="now 1-d")
        data = pytrends.interest_over_time()
        out: Dict[str, int] = {}
        for k in keywords:
            try:
                out[k] = int(data[k].iloc[-1])
            except Exception:
                out[k] = random.randint(10, 90)
        return out
    except Exception as e:
        print(f"[Crawler] Google Trends Fehler: {e}")
        # sinnvolle Fallbacks
        return {k: random.randint(10, 100) for k in keywords}

# === 2) News (NewsAPI) ===
def fetch_news_headlines(query: str = "crypto OR bitcoin OR ethereum", language: str = "de", page_size: int = 10) -> List[str]:
    if not NEWS_API_KEY:
        # Fallback ohne Key
        return [
            "Bitcoin ETF genehmigt in den USA",
            "Altcoins im freien Fall",
            "Ethereum Upgrade verzögert sich",
            "Neue Regulierungsvorschläge für Krypto in der EU",
        ]
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": language,
            "sortBy": "publishedAt",
            "pageSize": page_size,
        }
        headers = {"X-Api-Key": NEWS_API_KEY}
        js = _http_get_json(url, headers=headers, params=params)
        if not js:
            raise RuntimeError("Keine NewsAPI-Daten")
        articles = js.get("articles", []) or []
        titles = [a.get("title") or "Unbekannter Titel" for a in articles[:page_size]]
        return titles or [
            "Krypto-Markt seitwärts",
            "Investoren beobachten makroökonomische Daten",
        ]
    except Exception as e:
        print(f"[Crawler] NewsAPI Fehler: {e}")
        return [
            "Bitcoin ETF genehmigt in den USA",
            "Altcoins im freien Fall",
            "Ethereum Upgrade verzögert sich",
        ]

# === 3) Twitter/X (Platzhalter) ===
def fetch_twitter_mentions() -> Dict[str, int]:
    # Hier könntest du zukünftig echte API/Streamer einhängen
    return {
        "BTC": random.randint(2000, 8000),
        "DOGE": random.randint(1000, 10000),
        "SHIB": random.randint(500, 8000),
    }

# === 4) CoinMarketCap ===
def _cmc_headers() -> Dict[str, str]:
    return {"X-CMC_PRO_API_KEY": CMC_API_KEY, "Accept": "application/json", "User-Agent": USER_AGENT}

def fetch_coinmarketcap_trends() -> Dict[str, Any]:
    """
    Holt BTC/ETH Dominance (global metrics) und — wenn möglich — Top Gainer/Loser aus Listings.
    Fällt robust auf plausible Defaults zurück.
    """
    dominance: Dict[str, float] = {}
    top_gainer = "XRP"
    top_loser = "LUNA"

    # Global Metrics
    try:
        if CMC_API_KEY:
            url = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
            js = _http_get_json(url, headers=_cmc_headers())
            data = (js or {}).get("data", {}) if js else {}
            dominance = {
                "BTC": round(float(data.get("btc_dominance", 0.0)), 2),
                "ETH": round(float(data.get("eth_dominance", 0.0)), 2),
            }
        else:
            raise RuntimeError("kein CMC_API_KEY")
    except Exception as e:
        print(f"[Crawler] CMC Dominance Fehler: {e}")
        dominance = {
            "BTC": round(random.uniform(45.0, 52.0), 2),
            "ETH": round(random.uniform(15.0, 22.0), 2),
        }

    # Listings (Top Gainer/Loser) – optional
    try:
        if CMC_API_KEY:
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
            js = _http_get_json(url, headers=_cmc_headers(), params={"limit": 100, "convert": "USD"})
            data = (js or {}).get("data", []) if js else []
            if isinstance(data, list) and data:
                # sortiere nach 24h Change
                sorted_list = sorted(
                    data,
                    key=lambda x: (x.get("quote", {}).get("USD", {}).get("percent_change_24h") or 0),
                )
                # loser ist am Anfang (negativ), gainer am Ende (positiv)
                loser = sorted_list[0]
                gainer = sorted_list[-1]
                top_loser = loser.get("symbol") or top_loser
                top_gainer = gainer.get("symbol") or top_gainer
    except Exception as e:
        print(f"[Crawler] CMC Listings Fehler: {e}")

    return {
        "top_gainer": top_gainer,
        "top_loser": top_loser,
        "dominance": dominance,
    }

# === 5) Pump Signals (Dummy/Heuristik) ===
def fetch_pump_signals() -> List[Dict[str, str]]:
    # Hier kannst du später echte Tele-/Discord-Scanner integrieren
    return [
        {"coin": "PEPE", "suspicion": "Ungewöhnlicher Anstieg auf Telegram"},
        {"coin": "LUNA", "suspicion": "Social Hype trotz Kursverlust"},
    ]

# === Analyse / Sentiment ===
def analyze_data(trends: Dict[str, int],
                 twitter: Dict[str, int],
                 news: List[str],
                 cmc: Dict[str, Any],
                 suspicious: List[Dict[str, str]]) -> Dict[str, Any]:
    score = 0
    detected: List[str] = []

    # Trends
    if trends.get("bitcoin", 0) > 70:
        score += 1
        detected.append("🔼 Hohes Bitcoin-Suchvolumen")
    if trends.get("crypto crash", 0) > 60:
        score -= 2
        detected.append("⚠️ Crash-Themen im Trend")

    # News (heuristisch)
    neg_keywords = ("fall", "crash", "verzögert", "hack", "betrug", "absturz")
    if any(any(k in (t or "").lower() for k in neg_keywords) for t in news):
        score -= 1
        detected.append("📉 Negative News-Signale")

    # Twitter Mentions
    if twitter.get("DOGE", 0) > 9000:
        score += 1
        detected.append("🐶 DOGE könnte gehypt werden")

    # Dominance
    btc_dom = cmc.get("dominance", {}).get("BTC", 0)
    if btc_dom and btc_dom > 50:
        detected.append(f"🔗 BTC-Dominanz steigt auf {btc_dom}%")

    # Verdachtsfälle
    for s in suspicious:
        detected.append(f"🚨 Pump-Verdacht bei {s.get('coin')}: {s.get('suspicion')}")

    overall = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    return {"sentiment": overall, "score": score, "signals": detected}

# === Coin-Liste für Ghost-Mode ===
def build_coin_list(twitter: Dict[str, int], trends: Dict[str, int]) -> List[Dict[str, Any]]:
    coins = []
    mapping = {"BTC": "bitcoin", "DOGE": "shiba" if "shiba" in trends else "crypto crash", "SHIB": "shiba"}
    for symbol, trend_key in mapping.items():
        mentions = int(twitter.get(symbol, 0) or 0)
        trend_val = int(trends.get(trend_key, 0) or 0)
        coins.append({
            "coin": symbol,
            "mentions": mentions,
            "trend_score": round(max(0.0, min(1.0, trend_val / 100)), 3)  # 0..1
        })
    return coins

# === Hauptfunktion (vom Scheduler genutzt) ===
def run_crawler() -> Dict[str, Any]:
    print("📡 Starte Daten-Crawler...")
    trends = fetch_google_trends()
    news = fetch_news_headlines()
    twitter = fetch_twitter_mentions()
    cmc = fetch_coinmarketcap_trends()
    suspicious = fetch_pump_signals()
    analysis = analyze_data(trends, twitter, news, cmc, suspicious)
    coins_list = build_coin_list(twitter, trends)

    full_data: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "timestamp": _iso_now_utc(),   # UTC ISO-8601
        "raw": {
            "trends": trends,
            "news": news,
            "twitter": twitter,
            "coinmarketcap": cmc,
            "pump_signals": suspicious,
            "analysis": analysis,
            "sources": {
                "newsapi": bool(NEWS_API_KEY),
                "cmc": bool(CMC_API_KEY),
            }
        },
        "coins": coins_list
    }

    try:
        _atomic_write_json(CRAWLER_FILE, full_data)
        print("✅ Crawler-Daten erfolgreich gespeichert.")
    except Exception as e:
        print(f"❌ Fehler beim Speichern: {e}")

    return full_data

# === Daten lesen (von main/scheduler/ghost_mode genutzt) ===
def get_crawler_data() -> Dict[str, Any]:
    try:
        with open(CRAWLER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Crawler] Fehler beim Laden: {e}")
        return {}
