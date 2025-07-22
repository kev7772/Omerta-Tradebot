from trading import get_profit_estimates

def should_trigger_panic():
    profits = get_profit_estimates()
    for p in profits:
        if p['percent'] < -25:
            return True, p['coin']
    return False, None

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

# logic.py (Erweiterung)
from sentiment_parser import fetch_mock_sentiment, interpret_sentiment

def make_trade_decision(prices, date=None, mode="live"):
    decisions = {}

    for coin, price in prices.items():
        trend = price / 10000  # Dummylogik (wird noch erweitert)
        sentiment = interpret_sentiment(fetch_mock_sentiment())

        score = trend + sentiment  # Kombiniert technisches & soziales Signal

        if score > 1.5:
            decisions[coin] = "BUY"
        elif score < -1:
            decisions[coin] = "SELL"
        else:
            decisions[coin] = "HOLD"

    return decisions
