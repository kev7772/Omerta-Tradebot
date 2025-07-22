from trading import get_profit_estimates

def should_trigger_panic():
    profits = get_profit_estimates()
    for p in profits:
        if p['percent'] < -25:
            return True, p['coin']
    return False, None

def get_trading_decision():
    """
    Liefert eine erklärende Liste an: Was hätte ein erfahrener Trader wohl getan?
    (Nur zur Anzeige im Bot)
    """
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
    """
    Liefert echte Empfehlungen basierend auf den Profiten
    (z. B. bei /recommend Befehl)
    """
    profits = get_profit_estimates()
    recommendations = []
    for p in profits:
        if p['percent'] > 10:
            recommendations.append(f"{p['coin']}: 📈 Verkauf möglich (+{p['percent']}%)")
        elif p['percent'] < -15:
            recommendations.append(f"{p['coin']}: ⚠️ Beobachten / meiden ({p['percent']}%)")
        else:
            recommendations.append(f"{p['coin']}: 🤝 Halten ({p['percent']}%)")
    return recommendations

def make_trade_decision():
    """
    Wird intern für echte Simulationen genutzt:
    Liefert klares dict {coin: "BUY" | "SELL" | "HOLD"}
    """
    profits = get_profit_estimates()
    decision = {}
    for p in profits:
        if p['percent'] > 20:
            decision[p['coin']] = "SELL"
        elif p['percent'] < -12:
            decision[p['coin']] = "HOLD"
        else:
            decision[p['coin']] = "BUY"
    return decision
