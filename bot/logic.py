from trading import get_profit_estimates
from sentiment_parser import fetch_mock_sentiment, interpret_sentiment
import json

# === 1. Notbremse bei -25% Verlust
def should_trigger_panic():
    profits = get_profit_estimates()
    for p in profits:
        if p['percent'] < -25:
            return True, p['coin']
    return False, None

# === 2. Entscheidung basierend auf Gewinnen (für /tradelogic)
def get_trading_decision():
    profits = get_profit_estimates()
    simulated_actions = []
    for p in profits:
        if p['percent'] > 15:
            simulated_actions.append(f"{p['coin']}: 🔼 Hätte verkauft")
        elif p['percent'] < -10:
            simulated_actions.append(f"{p['coin']}: 🔽 Hätte NICHT gekauft")
        else:
            simulated_actions.append(f"{p['coin']}: 🤔 Hätte gehalten")
    return simulated_actions

# === 3. Empfehlungen geben (für /recommend)
def recommend_trades():
    profits = get_profit_estimates()
    recommendations = []
    for p in profits:
        if p['percent'] > 10:
            recommendations.append(f"{p['coin']}: ✅ gute Performance – beobachten")
        elif p['percent'] < -20:
            recommendations.append(f"{p['coin']}: ⚠️ instabil – nicht anfassen")
        else:
            recommendations.append(f"{p['coin']}: ⏳ abwarten")
    return recommendations

# === 4. Preisänderung ermitteln (für realistische Analyse)
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

# === 5. Kombinierte Entscheidungslogik (für simulator.py)
def make_trade_decision(prices, date=None, mode="live"):
    decisions = {}

    for coin, price in prices.items():
        price_change = get_price_change(coin, price)
        sentiment = interpret_sentiment(fetch_mock_sentiment())

        score = (price_change * 10) + sentiment  # Mischung aus Kursverlauf + Social-Mood

        if score > 1.5:
            decisions[coin] = "BUY"
        elif score < -1:
            decisions[coin] = "SELL"
        else:
            decisions[coin] = "HOLD"

    return decisions
