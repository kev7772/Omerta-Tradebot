import json
import os
from datetime import datetime, timedelta
from autolearn import learn_from_decision
from history_tools import get_change_since

DECISION_LOG = "decision_log.json"

def evaluate_pending_learnings():
    if not os.path.exists(DECISION_LOG):
        return

    with open(DECISION_LOG, "r") as f:
        logs = json.load(f)

    new_logs = []
    for entry in logs:
        try:
            timestamp = datetime.fromisoformat(entry["timestamp"])
            age_days = (datetime.utcnow() - timestamp).days

            if age_days >= 3:
                coin = entry["coin"]
                decision = entry["decision"]
                date_str = timestamp.strftime("%Y-%m-%d")
                change = get_change_since(coin, date_str)

                if change is not None:
                    learn_from_decision(coin, decision, change)
                    print(f"📘 Gelernt: {coin} → {decision} → {round(change, 2)}%")
                else:
                    new_logs.append(entry)  # Kein Vergleich möglich → nochmal versuchen
            else:
                new_logs.append(entry)
        except Exception as e:
            print(f"⚠️ Fehler bei Bewertung: {e}")

    with open(DECISION_LOG, "w") as f:
        json.dump(new_logs, f, indent=2)
