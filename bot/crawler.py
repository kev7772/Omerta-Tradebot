import os
import json
from datetime import datetime

def run_crawler():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dummy_data = {
        "timestamp": timestamp,
        "google_trends": {
            "bitcoin": 78,
            "ethereum": 64,
            "crypto crash": 32
        },
        "news": [
            "Bitcoin ETF approved by SEC",
            "Massive liquidation hits altcoins",
            "Binance resumes withdrawals after outage"
        ],
        "twitter_hype": {
            "DOGE": 15400,
            "SHIB": 9800,
            "BTC": 27600
        },
        "coinmarketcap": {
            "top_gainers": ["RUNE", "INJ", "FTM"],
            "top_losers": ["SUI", "JASMY"]
        },
        "warnings": [
            "⚠️ Verdacht auf Pump & Dump bei DOGE",
            "📉 Panik-Sentiment für SHIB erkannt"
        ]
    }

    try:
        with open("crawler_data.json", "w") as f:
            json.dump(dummy_data, f, indent=2)
        print("✅ crawler_data.json wurde erfolgreich aktualisiert.")
    except Exception as e:
        print(f"❌ Fehler beim Schreiben: {e}")
