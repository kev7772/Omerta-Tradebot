# simulator.py
import json
import datetime
from logic import make_trade_decision
from trading import simulate_trade

# Lädt die gespeicherten Kursdaten aus der history.json
def load_history(file='history.json'):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ Keine history.json gefunden.")
        return []

# Führt die Simulation für alle gespeicherten Tage durch
def simulate_market(history):
    balance = 100.0  # Virtuelles Startkapital in €
    portfolio = {}
    log = []

    for day in history:
        date = day['date']
        prices = day['prices']  # z.B. {"BTC": 26700.5, "ETH": 1620.2}

        decision = make_trade_decision(prices, date, mode="simulation")
        result = simulate_trade(decision, balance, portfolio, prices)
        balance, portfolio = result['balance'], result['portfolio']

        log.append({
            "date": date,
            "decision": decision,
            "balance": balance,
            "portfolio": portfolio
        })

    with open("simulation_log.json", "w") as f:
        json.dump(log, f, indent=4)

    print("✅ Simulation abgeschlossen. Ergebnisse in 'simulation_log.json'.")

# Diese Funktion kann aus main.py oder Telegram-Befehl aufgerufen werden
def run_simulation():
    history = load_history()
    if not history:
        print("❌ Keine historischen Daten gefunden. Bitte erst 'live_logger.py' ausführen.")
        return
    simulate_market(history)
