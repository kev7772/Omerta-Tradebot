import json
import os
from datetime import datetime
import random

# Platzhalter für echte APIs (können später ersetzt werden)
def fetch_google_trends():
    return {
        "bitcoin": random.randint(30, 100),
        "crypto crash": random.randint(10, 90),
        "shiba": random.randint(0, 80)
    }

def fetch_news_headlines():
    return [
        "Bitcoin ETF genehmigt in den USA",
        "Altcoins im freien Fall",
        "Ethereum Upgrade verzögert sich"
    ]

def fetch_twitter_mentions():
    return {
        "BTC": random.randint(2000, 8000),
        "DOGE": random.randint(1000, 10000),
        "SHIB": random.randint(500, 8000),
    }

def fetch_coinmarketcap_trends():
    return {
        "top_gainer": "XRP",
        "top_loser": "LUNA",
        "dominance": {
            "BTC": 48.3,
            "ETH": 18.2
        }
    }

def fetch_pump_signals():
    return [
        {"coin": "PEPE", "suspicion": "Ungewöhnlicher Anstieg auf Telegram"},
        {"coin": "LUNA", "suspicion": "Social Hype trotz Kursverlust"}
    ]

# Auswertung / Analyse
def analyze_data(trends, twitter, news):
    sentiment_score = 0
    detected_signals = []

    if trends["bitcoin"] > 70:
        sentiment_score += 1
        detected_signals.append("🔼 Hohes Bitcoin-Suchvolumen")

    if trends["crypto crash"] > 60:
        sentiment_score -= 2
        detected_signals.append("⚠️ Crash-Themen im Trend")

    if "Altcoins im freien Fall" in news:
        sentiment_score -= 1
        detected_signals.append("📉 Schlechte Altcoin-News")

    if twitter.get("DOGE", 0) > 9000:
        detected_signals.append("🐶 DOGE könnte gehypt werden")

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

# Hauptfunktion
def run_crawler():
    print("📡 Starte Daten-Crawler...")

    trends = fetch_google_trends()
    news = fetch_news_headlines()
    twitter = fetch_twitter_mentions()
    cmc = fetch_coinmarketcap_trends()
    suspicious = fetch_pump_signals()

    analysis = analyze_data(trends, twitter, news)

    full_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trends": trends,
        "news": news,
        "twitter": twitter,
        "coinmarketcap": cmc,
        "pump_signals": suspicious,
        "analysis": analysis
    }

    try:
        with open("crawler_data.json", "w") as f:
            json.dump(full_data, f, indent=2)
        print("✅ Daten erfolgreich gespeichert.")
    except Exception as e:
        print(f"❌ Fehler beim Speichern: {e}")

def get_crawler_data():
    try:
        with open("crawler_data.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[GhostMode] Fehler beim Laden der crawler_data.json: {e}")
        return {}
