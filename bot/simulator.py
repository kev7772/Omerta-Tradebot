from autolearn import learn_from_decision
import trading
from logic import get_trading_decision
from datetime import datetime
import random
import json
import os

# Dummy-Funktion zum simulieren prozentualer Kursentwicklung
def simulate_coin_change():
    return round(random.uniform(-15, 15), 2)  # -15 % bis +15 %

# Entscheidungs-Logik zur späteren Bewertung
DECISION_LOG = "decision_log.json"

def log_future_evaluation(coin, decision):
    entry = {
        "coin": coin,
        "decision": decision,
        "timestamp": datetime.utcnow().isoformat()
    }

    if os.path.exists(DECISION_LOG):
        with open(DECISION_LOG, "r") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(entry)

    with open(DECISION_LOG, "w") as f:
        json.dump(logs, f, indent=2)

def run_simulation():
    portfolio = trading.get_portfolio()
    decisions = get_trading_decision()  # z. B. ['BTC: 🔼 Hätte verkauft', 'ETH: 🤔 Hätte gehalten']

    for entry in decisions:
        if ":" not in entry:
            continue
        coin, raw_decision = entry.split(":", 1)
        coin = coin.strip()

        if "🔼" in raw_decision:
            decision = "sell"
        elif "🔽" in raw_decision:
            decision = "buy"
        elif "🤔" in raw_decision:
            decision = "hold"
        else:
            continue

        # Simulation
        simulated_change = simulate_coin_change()
        learn_from_decision(coin, decision, simulated_change)

        # Zukünftige Bewertung vormerken
        log_future_evaluation(coin, decision)

def save_simulation_log(entry):
    try:
        with open("learninglog.json", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"Fehler beim Loggen der Simulation: {e}")
