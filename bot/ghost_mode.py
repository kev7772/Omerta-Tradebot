import json
from datetime import datetime
from sentiment_parser import get_sentiment_data
from trading import get_profit_estimates
from crawler import get_crawler_data

GHOST_LOG_PATH = "ghost_log.json"

def detect_stealth_entry(profit_data, sentiment_data, crawler_data):
    entries = []
    for p in profit_data:
        coin = p["coin"]
        percent = p["percent"]
        sentiment = sentiment_data.get(coin, {})
        mentions = crawler_data.get(coin, {}).get("mentions", 0)
        trend_score = crawler_data.get(coin, {}).get("trend_score", 0)

        if (
            percent < 2 and
            mentions < 50 and
            sentiment.get("score", 0) > 0.6 and
            trend_score > 0.4
        ):
            entries.append({
                "coin": coin,
                "reason": "Ghost Entry: Ruhiger Markt, frühes Sentiment, kein Social-Hype",
                "time": datetime.now().isoformat()
            })
    return entries

def run_ghost_mode():
    profits = get_profit_estimates()
    sentiment = get_sentiment_data()
    crawler_data = get_crawler_data()
    new_entries = detect_stealth_entry(profits, sentiment, crawler_data)

    if new_entries:
        try:
            with open(GHOST_LOG_PATH, "r") as f:
                log = json.load(f)
        except:
            log = []

        log.extend(new_entries)

        with open(GHOST_LOG_PATH, "w") as f:
            json.dump(log, f, indent=2)

    return new_entries

from datetime import datetime
import json
import os

def check_ghost_exit():
    if not os.path.exists("ghost_log.json"):
        return []

    with open("ghost_log.json", "r") as f:
        entries = json.load(f)

    updated = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for entry in entries:
        if "exit_time" in entry:
            continue  # Schon abgeschlossen

        # Beispiel: Exit-Bedingung → starker Kursanstieg oder Sentiment-Hype
        if simulate_exit_trigger(entry["coin"]):
            entry["exit_time"] = now
            entry["exit_reason"] = "Hype erkannt"
            entry["success"] = simulate_trade_success(entry)
            updated.append(entry)

    # Log aktualisieren
    with open("ghost_log.json", "w") as f:
        json.dump(entries, f, indent=2)

    return updated

def get_ghost_performance_ranking():
    if not os.path.exists("ghost_log.json"):
        return []

    with open("ghost_log.json", "r") as f:
        entries = json.load(f)

    stats = {}
    for e in entries:
        coin = e["coin"]
        if "success" not in e:
            continue
        if coin not in stats:
            stats[coin] = {"count": 0, "sum": 0.0}
        stats[coin]["count"] += 1
        stats[coin]["sum"] += float(e["success"])

    ranking = []
    for coin, data in stats.items():
        avg = data["sum"] / data["count"]
        ranking.append({"coin": coin, "durchschnitt": round(avg, 2), "anzahl": data["count"]})

    ranking.sort(key=lambda x: x["durchschnitt"], reverse=True)
    return ranking

def run_ghost_analysis():
    """
    Führt eine Analyse über vergangene Ghost-Trades aus.
    Optional kannst du hier Heatmaps, Erfolgsquoten oder Fehlermuster analysieren lassen.
    """
    try:
        with open("ghost_log.json", "r") as f:
            entries = json.load(f)

        if not entries:
            return "📭 Keine Einträge im Ghost-Log gefunden."

        stats = {}
        for entry in entries:
            coin = entry.get("coin")
            stats.setdefault(coin, 0)
            stats[coin] += 1

        result = "🧠 Ghost-Analyse abgeschlossen:\n\n"
        for coin, count in stats.items():
            result += f"• {coin}: {count} Trades\n"

        return result

    except FileNotFoundError:
        return "⚠️ ghost_log.json nicht gefunden."
    except Exception as e:
        return f"❌ Fehler bei run_ghost_analysis: {str(e)}"
