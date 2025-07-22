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

# Beispiel-Simulation (vereinfacht)
for coin in simulated_coins:
    decision = "buy"  # oder aus Logik berechnet
    actual_result = 8.5  # Ergebnis der Simulation

    # Lernen auf Basis der simulierten Entscheidung
    learn_from_decision(coin, decision, actual_result)

from autolearn import learn_from_decision

def run_simulation():
    # Test-Daten – später dynamisch aus Portfolio o. Kurslog generieren
    simulated_data = [
        {"coin": "BTC", "decision": "buy", "result": 12.3},
        {"coin": "ETH", "decision": "sell", "result": -3.1},
        {"coin": "DOGE", "decision": "hold", "result": 1.2},
        {"coin": "SOL", "decision": "buy", "result": -8.5}]

    for entry in simulated_data:
        learn_from_decision(entry["coin"], entry["decision"], entry["result"])
