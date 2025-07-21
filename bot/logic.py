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
