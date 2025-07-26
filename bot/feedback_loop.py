import json
from datetime import datetime, timedelta
from pathlib import Path

DECISION_LOG_FILE = "decision_log.json"
HISTORY_FILE = "history.json"
LEARNING_LOG_FILE = "learning_log.json"

def run_feedback_loop():
    if not Path(DECISION_LOG_FILE).exists() or not Path(HISTORY_FILE).exists():
        return []

    with open(DECISION_LOG_FILE, "r") as f:
        decisions = json.load(f)

    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)

    if Path(LEARNING_LOG_FILE).exists():
        with open(LEARNING_LOG_FILE, "r") as f:
            learning_log = json.load(f)
    else:
        learning_log = []

    today = datetime.today()
    evaluated_entries = []

    for decision in decisions:
        if decision.get("status") != "open":
            continue

        decision_date = datetime.strptime(decision["date"], "%Y-%m-%d")
        coin = decision["coin"]
        eval_date = decision_date + timedelta(days=3)
        eval_date_str = eval_date.strftime("%Y-%m-%d")

        if eval_date > today:
            continue

        if eval_date_str not in history or coin not in history[eval_date_str]:
            continue

        old_price = decision["price"]
        new_price = history[eval_date_str][coin]
        success = round(((new_price - old_price) / old_price) * 100, 2)

        decision["current_price"] = new_price
        decision["success"] = success
        decision["status"] = "evaluated"

        learning_log.append({
            "date": decision["date"],
            "coin": coin,
            "success": success
        })

        evaluated_entries.append({
            "coin": coin,
            "date": decision["date"],
            "success": success
        })

    with open(DECISION_LOG_FILE, "w") as f:
        json.dump(decisions, f, indent=4)

    with open(LEARNING_LOG_FILE, "w") as f:
        json.dump(learning_log, f, indent=4)

    return evaluated_entries
