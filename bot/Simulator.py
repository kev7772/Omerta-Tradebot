import json
import os

HISTORY_FILE = "history.json"

def run_simulation():
    if not os.path.exists(HISTORY_FILE):
        return ["Keine historischen Daten gefunden."]

    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)

    results = []
    for entry in history:
        date = entry["timestamp"]
        for coin in entry["data"]:
            profit = coin["value"] - (coin["value"] * 0.85)
            percent = (profit / (coin["value"] * 0.85)) * 100
            if percent >= 10:
                results.append(f"{coin['coin']} am {date}: +{round(percent,2)} % (hätte verkauft)")
            elif percent <= -10:
                results.append(f"{coin['coin']} am {date}: {round(percent,2)} % (wäre Verlust geworden)")
            else:
                results.append(f"{coin['coin']} am {date}: {round(percent,2)} % (neutral)")
    return results[-20:]  # letzte 20 Einträge zeigen
