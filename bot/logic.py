from trading import get_profit_estimates
from sentiment_parser import get_sentiment_data
import json
import os

def should_trigger_panic():
    profits = get_profit_estimates()
    for p in profits:
        if p['percent'] < -25:
            return True, p['coin']
    return False, None

def get_trading_decision():
    profits = get_profit_estimates()
    if not profits:
        return ["⚠️ Keine Kursdaten verfügbar"]

    sentiment_info = get_sentiment_data()
    sentiment = sentiment_info['sentiment']
    decisions = []

    if sentiment == "bullish":
        decisions.append("📈 Marktstimmung bullish – mehr Risiko erlaubt.")
    elif sentiment == "bearish":
        decisions.append("📉 Marktstimmung bearish – defensiv agieren.")
    else:
        decisions.append("😐 Neutrale Stimmung – keine großen Bewegungen.")

    for p in profits:
        if p['percent'] > 15:
            decisions.append(f"{p['coin']}: 🔼 Hätte verkauft")
        elif p['percent'] < -10:
            decisions.append(f"{p['coin']}: 🔽 Hätte NICHT gekauft")
        else:
            decisions.append(f"{p['coin']}: 🤔 Hätte gehalten")

    return decisions

def recommend_trades():
    profits = get_profit_estimates()
    if not profits:
        return ["⚠️ Keine Kursdaten verfügbar"]

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
        else:
            if percent > 15:
                recommendations.append(f"{coin}: 📈 Verkauf denkbar (+{percent}%)")
            elif percent < -15:
                recommendations.append(f"{coin}: ⚠️ Abwarten oder meiden ({percent}%)")
            else:
                recommendations.append(f"{coin}: 🤝 Halten ({percent}%)")

    return recommendations

def make_trade_decision():
    profits = get_profit_estimates()
    if not profits:
        return {"info": "⚠️ Keine Kursdaten verfügbar"}

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
        else:
            if percent > 18:
                decisions[coin] = "SELL"
            elif percent < -10:
                decisions[coin] = "HOLD"
            else:
                decisions[coin] = "BUY"

    return decisions

def get_learning_log():
    filepath = os.path.join(os.path.dirname(__file__), "learning_log.json")

    print("🔎 Absoluter Pfad zur Datei:", filepath)
    if not os.path.exists(filepath):
        print("❌ Datei nicht gefunden!")
        return "❌ Noch kein Lernverlauf vorhanden (Datei fehlt)."

    try:
        with open(filepath, "r") as f:
            content = f.read()
            print("📄 Inhalt der Datei:", content)
            data = json.loads(content)
    except json.JSONDecodeError:
        print("⚠️ JSON-Fehler!")
        return "⚠️ Lernlog-Datei beschädigt oder leer."

    if not data:
        print("ℹ️ Datei ist leer.")
        return "📘 Lernlog ist leer."

    output = "📘 Lernverlauf (letzte 5 Einträge):\n"
    for eintrag in data[-5:]:
        datum = eintrag.get("date", "???")
        coin = eintrag.get("coin", "???")
        erfolg = eintrag.get("success", "?")
        output += f"📅 {datum} | {coin} | Erfolg: {erfolg}%\n"

    print("✅ Ausgabe an Telegram:", output)
    return output

from ghost_mode import detect_stealth_entry

def run_ghost_analysis():
    profits = get_profit_estimates()
    sentiment = get_sentiment_data()
    crawler_data = get_crawler_data()

    return detect_stealth_entry(profits, sentiment, crawler_data)
