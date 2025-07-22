import json
import os
from datetime import datetime

LEARN_LOG = "learn_log.json"

def learn_from_decision(coin, decision, actual_percent):
    """
    Vergleicht die Entscheidung mit dem echten Verlauf.
    decision: 'buy', 'hold', 'sell'
    actual_percent: tatsächliche Entwicklung nach X Tagen (z. B. +10%)
    """
    correct = False

    if decision == "buy" and actual_percent > 5:
        correct = True
    elif decision == "sell" and actual_percent < -5:
        correct = True
    elif decision == "hold" and -5 <= actual_percent <= 5:
        correct = True

    result = {
        "coin": coin,
        "decision": decision,
        "actual": actual_percent,
        "correct": correct,
        "timestamp": datetime.now().isoformat()
    }

    if os.path.exists(LEARN_LOG):
        with open(LEARN_LOG, "r") as f:
            data = json.load(f)
    else:
        data = []

    data.append(result)

    with open(LEARN_LOG, "w") as f:
        json.dump(data, f, indent=2)

    return correct
