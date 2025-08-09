import json
import os
from datetime import datetime, timedelta
from autolearn import learn_from_decision
from history_tools import get_change_since

DECISION_LOG = "decision_log.json"
LEARNING_LOG = "learning_log.json"

def log_learning_result(coin, decision, change):
    """Schreibt das Ergebnis ins learning_log.json."""
    if not os.path.exists(LEARNING_LOG):
        logs = []
    else:
        try:
            with open(LEARNING_LOG, "r") as f:
                logs = json.load(f)
        except json.JSONDecodeError:
            logs = []

    logs.append({
        "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "coin": coin,
        "decision": decision,
        "change": round(change, 2)
    })

    with open(LEARNING_LOG, "w") as f:
        json.dump(logs, f, indent=2)

def parse_timestamp(ts_str):
    """Versucht, verschiedene Zeitformate zu lesen."""
    try:
        return datetime.fromisoformat(ts_str)
    except ValueError:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            raise ValueError(f"Ungültiges Zeitformat: {ts_str}")

def evaluate_pending_learnings():
    """Prüft offene Entscheidungen und lernt nach 3 Tagen automatisch."""
    if not os.path.exists(DECISION_LOG):
        print("ℹ️ Keine decision_log.json gefunden.")
        return

    try:
        with open(DECISION_LOG, "r") as f:
            logs = json.load(f)
    except json.JSONDecodeError:
        print("❌ Fehler: decision_log.json ist beschädigt.")
        return

    new_logs = []
    for entry in logs:
        try:
            timestamp = parse_timestamp(entry["timestamp"])
            age_days = (datetime.utcnow() - timestamp).days

            if age_days >= 3:
                coin = entry["coin"]
                decision = entry["decision"]
                date_str = timestamp.strftime("%Y-%m-%d")
                change = get_change_since(coin, date_str)

                if change is not None:
                    learn_from_decision(coin, decision, change)
                    log_learning_result(coin, decision, change)
                    print(f"📘 Gelernt: {coin} → {decision} → {round(change, 2)}%")
                else:
                    print(f"⚠️ Keine Kursdaten für {coin} seit {date_str} gefunden.")
                    new_logs.append(entry)  # Erneut versuchen
            else:
                new_logs.append(entry)

        except Exception as e:
            print(f"⚠️ Fehler bei Bewertung von {entry.get('coin', 'unbekannt')}: {e}")
            new_logs.append(entry)  # Sicherstellen, dass nichts verloren geht

    with open(DECISION_LOG, "w") as f:
        json.dump(new_logs, f, indent=2)

    print(f"✅ Lernbewertung abgeschlossen. {len(new_logs)} offene Einträge verbleiben.")
