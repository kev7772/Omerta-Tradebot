import json
import random
from datetime import datetime

# Platzhalter-Datenquellen
FAKE_NEWS = [
    "Bitcoin stürzt wegen SEC-Verbot", 
    "Ethereum erreicht Allzeithoch", 
    "Massive Abverkäufe bei Altcoins erwartet", 
    "DOGE wird Zahlungsmittel bei Tesla", 
    "Krypto-Regulierung in Europa beschlossen"
]

FAKE_SOCIAL = [
    "🔥 $ETH is going parabolic!!", 
    "Panic sell $SOL now!!", 
    "Buy the dip or cry later 😭", 
    "Rumors of Binance trouble again", 
    "Whales are dumping $ADA"
]

FAKE_GOOGLE = [
    "Krypto Absturz", 
    "Bitcoin kaufen", 
    "Beste Coins 2025", 
    "FTX Pleite", 
    "USDT Skandal"
]

def mock_sentiment_score(text):
    # Sehr simple Bewertung: +1 bei Bullish, -1 bei Bearish
    positive_keywords = ["hoch", "parabolic", "Allzeithoch", "kaufen", "Buy", "Tesla", "Zahlungsmittel"]
    negative_keywords = ["Absturz", "Verbot", "Panik", "dump", "Pleite", "Skandal", "sell"]

    score = 0
    for word in positive_keywords:
        if word.lower() in text.lower():
            score += 1
    for word in negative_keywords:
        if word.lower() in text.lower():
            score -= 1
    return score

def get_sentiment_data():
    # Simuliert, dass der Bot gerade Daten analysiert
    news = random.sample(FAKE_NEWS, 3)
    social = random.sample(FAKE_SOCIAL, 3)
    google = random.sample(FAKE_GOOGLE, 3)

    combined = news + social + google
    scores = [mock_sentiment_score(t) for t in combined]
    overall_score = sum(scores)

    sentiment = "neutral"
    if overall_score >= 3:
        sentiment = "bullish"
    elif overall_score <= -3:
        sentiment = "bearish"

    return {
        "timestamp": datetime.now().isoformat(),
        "score": overall_score,
        "sentiment": sentiment,
        "sources": combined
    }

def log_sentiment():
    data = get_sentiment_data()
    with open("sentiment_log.json", "a") as f:
        f.write(json.dumps(data) + "\n")
    return data
