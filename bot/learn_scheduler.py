import json
import os
from datetime import datetime, timedelta
from autolearn import learn_from_decision
from trading import get_coin_change_percent  # musst du ggf. selbst schreiben

DECISION_LOG = "decision_log.json"

def evaluate_pending_learnings():
    if not os.path.exists(DECISION_LOG):
        return

    with open(DECISION_LOG, "r") as f:
        logs = json.load(f)

    new_logs = []
    for entry in logs:
        time_elapsed = datetime.now() - datetime.fromisoformat(entry["timestamp"])
        if time_elapsed > timedelta(days=3):
            actual = get_coin_change_percent(entry["coin"], since=entry["timestamp"])
            learn_from_decision(entry["coin"], entry["decision"], actual)
        else:
            new_logs.append(entry)

    with open(DECISION_LOG, "w") as f:
        json.dump(new_logs, f, indent=2)
