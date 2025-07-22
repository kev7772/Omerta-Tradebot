from logic import make_trade_decision
from trading import simulate_trade, get_current_prices

def run_simulation():
    # Starte mit fiktivem Startguthaben & leerem Portfolio
    balance = 100.0  # EUR
    portfolio = {}

    # Simuliere aktuelle Preise (z. B. BTC/ETH)
    prices = get_current_prices()

    # Logik trifft Entscheidung basierend auf Gewinnen
    decision = make_trade_decision()

    # Führe Trades durch
    result = simulate_trade(decision, balance, portfolio, prices)

    # Optional: speichere Log in Datei
    log = {
        "start_balance": balance,
        "decision": decision,
        "result": result,
        "prices": prices
    }

    with open("simulation_log.json", "w") as f:
        import json
        json.dump(log, f, indent=2)

    print("✅ Simulation abgeschlossen.")

from autolearn import learn_from_decision

# Beispiel:
learn_from_decision("BTC", "buy", actual_percent=8.5)
