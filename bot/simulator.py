from autolearn import learn_from_decision
from trading import get_portfolio
from logic import get_trading_decision
import random

# Dummy-Funktion zum simulieren prozentualer Kursentwicklung
def simulate_coin_change():
    return round(random.uniform(-15, 15), 2)  # -15 % bis +15 %

def run_simulation():
    portfolio = get_portfolio()
    decisions = get_trading_decision()  # z. B. ['BTC: 🔼 Hätte verkauft', 'ETH: 🤔 Hätte gehalten', ...]

    for entry in decisions:
        if ":" not in entry:
            continue
        coin, raw_decision = entry.split(":", 1)
        coin = coin.strip()

        # Entscheidung aus Symbol erkennen
        if "🔼" in raw_decision:
            decision = "sell"
        elif "🔽" in raw_decision:
            decision = "buy"
        elif "🤔" in raw_decision:
            decision = "hold"
        else:
            continue

        simulated_change = simulate_coin_change()
        learn_from_decision(coin, decision, simulated_change)
