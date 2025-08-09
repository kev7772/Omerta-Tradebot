import json
import os
from datetime import datetime
import random
import requests
from pytrends.request import TrendReq

# === API KEYS ===
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
CMC_API_KEY = os.getenv("CMC_API_KEY")

# === 1) Google Trends ===
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

# === 2) News ===
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

# === 3) Twitter/X (Platzhalter) ===
def fetch_twitter_mentions():
    return {
        "BTC": random.randint(2000, 8000),
        "DOGE": random.randint(1000, 10000),
        "SHIB": random.randint(500, 8000),
    }

# === 4) CoinMarketCap ===
def fetch_coinmarketcap_trends():
    try:
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        url = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json().get("data", {})
        return {
            "top_gainer": "XRP",  # TODO: dynamisch
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

# === 5) Pump Signals (Dummy) ===
def fetch_pump_signals():
    return [
        {"coin": "PEPE", "suspicion": "Ungewöhnlicher Anstieg auf Telegram"},
        {"coin": "LUNA", "suspicion": "Social Hype trotz Kursverlust"}
    ]

# === Analyse / Sentiment ===
def analyze_data(trends, twitter, news, cmc, suspicious):
    sentiment_score = 0
    detected = []

    if trends.get("bitcoin", 0) > 70:
        sentiment_score += 1
        detected.append("🔼 Hohes Bitcoin-Suchvolumen")

    if trends.get("crypto crash", 0) > 60:
        sentiment_score -= 2
        detected.append("⚠️ Crash-Themen im Trend")

    if any("Altcoins im freien Fall" in h for h in news):
        sentiment_score -= 1
        detected.append("📉 Schlechte Altcoin-News")

    if twitter.get("DOGE", 0) > 9000:
        sentiment_score += 1
        detected.append("🐶 DOGE könnte gehypt werden")

    if cmc.get("dominance", {}).get("BTC", 0) > 50:
        detected.append(f"🔗 BTC-Dominanz steigt auf {cmc['dominance']['BTC']}%")

    for s in suspicious:
        detected.append(f"🚨 Pump-Verdacht bei {s['coin']}: {s['suspicion']}")

    overall = "bullish" if sentiment_score >= 2 else "bearish" if sentiment_score <= -2 else "neutral"
    return {"sentiment": overall, "score": sentiment_score, "signals": detected}

# === Coin-Liste für Ghost-Mode ===
def build_coin_list(twitter, trends):
    coins = []
    mapping = {"BTC": "bitcoin", "DOGE": "doge", "SHIB": "shiba"}
    for symbol, trend_key in mapping.items():
        mentions = int(twitter.get(symbol, 0) or 0)
        trend_val = int(trends.get(trend_key, 0) or 0)
        coins.append({
            "coin": symbol,
            "mentions": mentions,
            "trend_score": round(trend_val / 100, 3)  # 0..1
        })
    return coins

# === Hauptfunktion (vom Scheduler genutzt) ===
def run_crawler():
    print("📡 Starte Daten-Crawler...")
    trends = fetch_google_trends()
    news = fetch_news_headlines()
    twitter = fetch_twitter_mentions()
    cmc = fetch_coinmarketcap_trends()
    suspicious = fetch_pump_signals()
    analysis = analyze_data(trends, twitter, news, cmc, suspicious)
    coins_list = build_coin_list(twitter, trends)

    full_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw": {
            "trends": trends,
            "news": news,
            "twitter": twitter,
            "coinmarketcap": cmc,
            "pump_signals": suspicious,
            "analysis": analysis
        },
        "coins": coins_list
    }

    try:
        with open("crawler_data.json", "w", encoding="utf-8") as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
        print("✅ Crawler-Daten erfolgreich gespeichert.")
    except Exception as e:
        print(f"❌ Fehler beim Speichern: {e}")

# === Daten lesen (von main/scheduler/ghost_mode genutzt) ===
def get_crawler_data():
    try:
        with open("crawler_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Crawler] Fehler beim Laden: {e}")
        return {}
