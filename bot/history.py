import os
import json
from datetime import datetime
from trading import get_portfolio

HISTORY_FILE = "history.json"

def save_daily_snapshot():
    snapshot = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "data": get_portfolio()
    }

    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    else:
        history = []

    history.append(snapshot)

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

    print(f"[LOGGED] Snapshot saved at {snapshot['timestamp']}")
