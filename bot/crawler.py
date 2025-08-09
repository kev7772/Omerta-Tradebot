import json
import os
from datetime import datetime
import random
import requests
from pytrends.request import TrendReq

# === API KEYS ===
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
CMC_API_KEY = os.getenv("CMC_API_KEY")

# === 1. Google Trends ===
def fetch_google_trends():
    try:
        pytrends = TrendReq(hl='de', tz=360)
        pytrends.build_payload(["bitcoin", "crypto crash", "shiba"], cat=0, timeframe='now 1-d')
        data = pytrends.interest_over_time()
        return {
            "bitcoin": int(data["bitcoin"].iloc[-1]),
            "crypto crash": int(data["crypto crash"].iloc[-1]),
            "shiba": int(data["shiba"].iloc[-1])
        }
    except Exception as e:
        print(f"[Crawler] Fehler bei Google Trends: {e}")
        return {
            "bitcoin": random.randint(30, 100),
            "crypto crash": random.randint(10, 90),
            "shiba": random.randint(0, 80)
        }

# === 2. News Headlines ===
def fetch_news_headlines():
    try:
        url = f"https://newsapi.org/v2/everything?q=crypto&language=de&apiKey={NEWS_API_KEY}"
        response = requests.get(url, timeout=10)
        articles = response.json().get("articles", [])
        return [article.get("title", "Unbekannter Titel") for article in articles[:5]]
    except Exception as e:
        print(f"[Crawler] Fehler bei NewsAPI: {e}")
        return [
            "Bitcoin ETF genehmigt in den USA",
            "Altcoins im freien Fall",
            "Ethereum Upgrade verzögert sich"
        ]

# === 3. Twitter/X Mentions (Platzhalter) ===
def fetch_twitter_mentions():
    # TODO: Echte API-Anbindung
    return {
        "BTC": random.randint(2000, 8000),
        "DOGE": random.randint(1000, 10000),
        "SHIB": random.randint(500, 8000),
    }

# === 4. CoinMarketCap Trends ===
def fetch_coinmarketcap_trends():
    try:
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        url = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json().get("data", {})
        return {
            "top_gainer": "XRP",  # TODO: Später dynamisch ermitteln
            "top_loser": "LUNA",
            "dominance": {
                "BTC": round(data.get("btc_dominance", 0), 2),
                "ETH": round(data.get("eth_dominance", 0), 2)
            }
        }
    except Exception as e:
        print(f"[Crawler] Fehler bei CoinMarketCap: {e}")
        return {
            "top_gainer": "XRP",
            "top_loser": "LUNA",
            "dominance": {
                "BTC": round(random.uniform(45.0, 52.0), 2),
                "ETH": round(random.uniform(15.0, 22.0), 2)
            }
        }

# === 5. Pump Signals ===
def fetch_pump_signals():
    return [
        {"coin": "PEPE", "suspicion": "Ungewöhnlicher Anstieg auf Telegram"},
        {"coin": "LUNA", "suspicion": "Social Hype trotz Kursverlust"}
    ]

# === Analyse ===
def analyze_data(trends, twitter, news, cmc, suspicious):
    sentiment_score = 0
    detected_signals = []

    if trends.get("bitcoin", 0) > 70:
        sentiment_score += 1
        detected_signals.append("🔼 Hohes Bitcoin-Suchvolumen")

    if trends.get("crypto crash", 0) > 60:
        sentiment_score -= 2
        detected_signals.append("⚠️ Crash-Themen im Trend")

    if any("Altcoins im freien Fall" in headline for headline in news):
        sentiment_score -= 1
        detected_signals.append("📉 Schlechte Altcoin-News")

    if twitter.get("DOGE", 0) > 9000:
        sentiment_score += 1
        detected_signals.append("🐶 DOGE könnte gehypt werden")

    if cmc.get("dominance", {}).get("BTC", 0) > 50:
        detected_signals.append(f"🔗 BTC-Dominanz steigt auf {cmc['dominance']['BTC']}%")

    for signal in suspicious:
        detected_signals.append(f"🚨 Pump-Verdacht bei {signal['coin']}: {signal['suspicion']}")

    if sentiment_score >= 2:
        overall_sentiment = "bullish"
    elif sentiment_score <= -2:
        overall_sentiment = "bearish"
    else:
        overall_sentiment = "neutral"

    return {
        "sentiment": overall_sentiment,
        "score": sentiment_score,
        "signals": detected_signals
    }

# === Coin-Format für Ghost-Mode ===
def build_coin_list(twitter, trends):
    coins = []
    mapping = {
        "BTC": "bitcoin",
        "DOGE": "doge",
        "SHIB": "shiba"
    }
    for symbol, trend_key in mapping.items():
        mentions = twitter.get(symbol, 0)
        trend_val = trends.get(trend_key, 0)
        coins.append({
            "coin": symbol,
            "mentions": mentions,
            "trend_score": round(trend_val / 100, 3)  # 0..1 normalisiert
        })
    return coins

# === Hauptfunktion ===
def crawler_job():
    _job("Crawler", run_crawler)
    data = get_crawler_data()
    if not data:
        return
    coins = data.get("coins", [])
    if coins:
        top = sorted(coins, key=lambda x: x.get("mentions",0), reverse=True)[:3]
        msg = f"📡 Crawler Update — Top Trends:\n"
        for c in top:
            msg += f"• {c.get('coin')} — Mentions: {c.get('mentions')} | Trend: {c.get('trend_score')}\n"
        _send(msg)

# === Daten lesen ===
def get_crawler_data():
    try:
        with open("crawler_data.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Crawler] Fehler beim Laden: {e}")
        return {}
