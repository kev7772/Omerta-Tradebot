import json
from sentiment_parser import fetch_mock_sentiment, interpret_sentiment

def get_price_change(coin, current_price):
    try:
        with open("history.json", "r") as f:
            data = json.load(f)
            if len(data) < 2:
                return 0.0
            prev_day = data[-2]["prices"].get(coin)
            if not prev_day:
                return 0.0
            return round((current_price - prev_day) / prev_day, 4)
    except:
        return 0.0

def make_trade_decision(prices, date=None, mode="live"):
    decisions = {}

    for coin, price in prices.items():
        price_change = get_price_change(coin, price)
        sentiment = interpret_sentiment(fetch_mock_sentiment())

        score = (price_change * 10) + sentiment  # Kombiniert realen Kursverlauf mit Social-Effekt

        if score > 1.5:
            decisions[coin] = "BUY"
        elif score < -1:
            decisions[coin] = "SELL"
        else:
            decisions[coin] = "HOLD"

    return decisions
