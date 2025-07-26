import json
import os
from datetime import datetime
from logic import make_trade_decision

DECISION_LOG_FILE = "decision_log.json"

def log_trade_decisions(decisions):
    timestamp = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(DECISION_LOG_FILE):
        with open(DECISION_LOG_FILE, "w") as f:
            json.dump([], f)

    with open(DECISION_LOG_FILE, "r") as f:
        try:
            log = json.load(f)
        except json.JSONDecodeError:
            log = []

    for coin, action in decisions.items():
        entry = {
            "date": timestamp,
            "coin": coin,
            "action": action
        }
        log.append(entry)

    with open(DECISION_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    print(f"📥 Trade-Entscheidungen geloggt ({timestamp}): {decisions}")
