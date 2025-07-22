from trading import get_profit_estimates
from sentiment_parser import fetch_mock_sentiment, interpret_sentiment

# === 1. Notbremse (für /panic)
def should_trigger_panic():
    profits = get_profit_estimates()
    for p in profits:
        if p['percent'] < -25:
            return True, p['coin']
    return False, None

# === 2. Handelslogik-Auswertung (für /tradelogic)
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

# === 3. Empfehlungen (für /recommend)
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

# === 4. Entscheidungslogik für Simulator
def make_trade_decision(prices, date=None, mode="live"):
    decisions = {}

    for coin, price in prices.items():
        trend = price / 10000  # Dummy-Trendanalyse (vereinfachter Score)
        sentiment = interpret_sentiment(fetch_mock_sentiment())  # Simuliertes Sentiment

        score = trend + sentiment

        if score > 1.5:
            decisions[coin] = "BUY"
        elif score < -1:
            decisions[coin] = "SELL"
        else:
            decisions[coin] = "HOLD"

    return decisions
