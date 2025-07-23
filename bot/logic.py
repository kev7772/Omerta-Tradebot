from trading import get_profit_estimates
from sentiment_parser import get_sentiment_data

def should_trigger_panic():
    profits = get_profit_estimates()
    for p in profits:
        if p['percent'] < -25:
            return True, p['coin']
    return False, None

def get_trading_decision():
    """
    Kombinierte Logik: Einschätzung auf Basis von Sentiment + Gewinnpotenzial
    Für Anzeige im Bot (z. B. bei /tradelogic)
    """
    profits = get_profit_estimates()
    sentiment_info = get_sentiment_data()
    sentiment = sentiment_info['sentiment']

    decisions = []

    # Sentiment-Analyse
    if sentiment == "bullish":
        decisions.append("📈 Marktstimmung bullish – mehr Risiko erlaubt.")
    elif sentiment == "bearish":
        decisions.append("📉 Marktstimmung bearish – defensiv agieren.")
    else:
        decisions.append("😐 Neutrale Stimmung – keine großen Bewegungen.")

    # Einschätzung pro Coin (Erfahrener Trader)
    for p in profits:
        if p['percent'] > 15:
            decisions.append(f"{p['coin']}: 🔼 Hätte verkauft")
        elif p['percent'] < -10:
            decisions.append(f"{p['coin']}: 🔽 Hätte NICHT gekauft")
        else:
            decisions.append(f"{p['coin']}: 🤔 Hätte gehalten")

    return decisions

def recommend_trades():
    """
    Liefert Empfehlungen auf Basis von Gewinn + aktueller Stimmung
    (für Telegram /recommend)
    """
    profits = get_profit_estimates()
    sentiment_info = get_sentiment_data()
    sentiment = sentiment_info['sentiment']
    recommendations = []

    for p in profits:
        coin = p['coin']
        percent = p['percent']

        if sentiment == "bullish":
            if percent > 12:
                recommendations.append(f"{coin}: ✅ Kauf halten oder Gewinn mitnehmen (+{percent}%)")
            elif percent < -18:
                recommendations.append(f"{coin}: ⚠️ Beobachten – trotz bullisher Lage fällt der Kurs ({percent}%)")
            else:
                recommendations.append(f"{coin}: 🤝 Halten")
        
        elif sentiment == "bearish":
            if percent > 8:
                recommendations.append(f"{coin}: 🔼 Gewinn sichern! Markt könnte kippen (+{percent}%)")
            elif percent < -10:
                recommendations.append(f"{coin}: 🚨 Meiden / Risiko ({percent}%)")
            else:
                recommendations.append(f"{coin}: ⛔ Nicht handeln – Markt unsicher")
        
        else:  # neutral
            if percent > 15:
                recommendations.append(f"{coin}: 📈 Verkauf denkbar (+{percent}%)")
            elif percent < -15:
                recommendations.append(f"{coin}: ⚠️ Abwarten oder meiden ({percent}%)")
            else:
                recommendations.append(f"{coin}: 🤝 Halten ({percent}%)")

    return recommendations

def make_trade_decision():
    """
    Interne Simulation mit Sentiment-Faktor
    Gibt dict {coin: "BUY" | "SELL" | "HOLD"} zurück
    """
    profits = get_profit_estimates()
    sentiment_info = get_sentiment_data()
    sentiment = sentiment_info['sentiment']
    decisions = {}

    for p in profits:
        coin = p['coin']
        percent = p['percent']

        if sentiment == "bullish":
            if percent > 20:
                decisions[coin] = "SELL"
            elif percent < -15:
                decisions[coin] = "HOLD"
            else:
                decisions[coin] = "BUY"

        elif sentiment == "bearish":
            if percent > 12:
                decisions[coin] = "SELL"
            else:
                decisions[coin] = "HOLD"

        else:  # neutral
            if percent > 18:
                decisions[coin] = "SELL"
            elif percent < -10:
                decisions[coin] = "HOLD"
            else:
                decisions[coin] = "BUY"

    return decisions

import json

def get_learning_log():
    try:
        with open("learning_log.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return "❌ Noch kein Lernverlauf vorhanden."

    if not data:
        return "📘 Lernlog ist leer."

    output = "📘 Lernverlauf (letzte 5 Einträge):\n"
    for eintrag in data[-5:]:
        datum = eintrag.get("date", "???")
        coin = eintrag.get("coin", "???")
        erfolg = eintrag.get("success", "?")
        output += f"📅 {datum} | {coin} | Erfolg: {erfolg}%\n"
    return output
