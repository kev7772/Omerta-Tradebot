# sentiment_parser.py
import random

# Simulation echter Social/News-Sentiments (API-Einbindung optional)
def fetch_mock_sentiment():
    topics = ["Bitcoin", "Elon", "Regulation", "ETF", "Crash", "Pump", "Shitcoin"]
    return [
        {"keyword": random.choice(topics), "score": random.uniform(-1, 1)}
        for _ in range(5)
    ]

def interpret_sentiment(sentiments):
    impact = 0
    for s in sentiments:
        if s["keyword"] in ["Crash", "Regulation", "Shitcoin"]:
            impact += s["score"] * 1.5
        else:
            impact += s["score"]
    return round(impact, 2)

if __name__ == "__main__":
    sentiments = fetch_mock_sentiment()
    impact = interpret_sentiment(sentiments)
    print(f"Sentiment Impact Score: {impact}")
