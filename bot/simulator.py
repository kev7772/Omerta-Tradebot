import json
import random
from datetime import datetime
from binance.client import Client
import os

# Binance API laden
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)


# ========== HISTORISCHE SZENARIEN ==========

historical_scenarios = [
    {
        "name": "FTX Collapse",
        "date": "2022-11-09",
        "coin": "FTT",
        "price_before": 22.00,
        "price_after": 1.50,
        "volume_crash": True,
    },
    {
        "name": "Terra Luna Crash",
        "date": "2022-05-10",
        "coin": "LUNA",
        "price_before": 85.00,
        "price_after": 0.0001,
        "volume_crash": True,
    },
    {
        "name": "Elon Doge Pump",
        "date": "2021-04-15",
        "coin": "DOGE",
        "price_before": 0.08,
        "price_after": 0.32,
        "volume_crash": False,
    },
    {
        "name": "Corona Market Crash",
        "date": "2020-03-12",
        "coin": "BTC",
        "price_before": 9200,
        "price_after": 4800,
        "volume_crash": True,
    }
]


def run_simulation():
    print("🔁 Starte historische Simulation...")

    scenario = random.choice(historical_scenarios)

    decision = get_decision_based_on_scenario(scenario)

    percent_change = ((scenario["price_after"] - scenario["price_before"]) / scenario["price_before"]) * 100

    log_entry = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "szenario": scenario["name"],
        "coin": scenario["coin"],
        "preis_vorher": scenario["price_before"],
        "preis_nachher": scenario["price_after"],
        "änderung": f"{percent_change:.2f}%",
        "entscheidung": decision,
        "verhalten": evaluate_decision(decision, percent_change),
        "success": round(abs(percent_change), 2) if decision in ["verkauft", "gekauft"] else 0.0
    }

    save_simulation_log(log_entry)

    return (
        f"📊 *Simulation abgeschlossen:*\n"
        f"🧠 Szenario: {log_entry['szenario']}\n"
        f"💰 Coin: {log_entry['coin']}\n"
        f"📉 Preis vorher: {log_entry['preis_vorher']} €\n"
        f"📈 Preis nachher: {log_entry['preis_nachher']} €\n"
        f"📉 Änderung: {log_entry['änderung']}\n"
        f"📌 Entscheidung: {log_entry['entscheidung']}\n"
        f"🧠 Verhalten: {log_entry['verhalten']}"
    )


# ========== LIVE-SIMULATION ==========

def run_live_simulation():
    print("🔄 Starte Live-Simulation mit echten Kursdaten...")

    try:
        prices = client.get_all_tickers()
    except Exception as e:
        return f"❌ Fehler beim Abrufen der Live-Daten: {e}"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    selected_coins = ["BTCUSDT", "ETHUSDT", "DOGEUSDT", "LTCUSDT"]

    log_entries = []

    for p in prices:
        if p["symbol"] in selected_coins:
            price = float(p["price"])
            coin = p["symbol"].replace("USDT", "")
            decision = simulate_live_decision(coin, price)

            log_entries.append({
                "date": timestamp,
                "coin": coin,
                "preis_live": price,
                "entscheidung": decision,
                "verhalten": "Live-Modus",
                "success": random.uniform(5, 25) if decision == "gekauft" else random.uniform(-15, 10)
            })

    save_simulation_log(log_entries, batch=True)

    return f"✅ Live-Simulation abgeschlossen mit {len(log_entries)} Coins."

for entry in log_entries:
    print(f"🪙 {entry['coin']} – Preis: {entry['preis_live']} €, Entscheidung: {entry['entscheidung']}")

# ========== LOGIK & SPEICHERN ==========

def get_decision_based_on_scenario(scenario):
    if scenario["volume_crash"] or scenario["price_after"] < (0.3 * scenario["price_before"]):
        return "verkauft"
    elif scenario["price_after"] > scenario["price_before"]:
        return "gekauft"
    else:
        return "gehalten"

def simulate_live_decision(coin, price):
    if "DOGE" in coin or price < 0.5:
        return "gekauft"
    elif price > 1000:
        return "gehalten"
    else:
        return "verkauft"

def evaluate_decision(decision, percent_change):
    if decision == "verkauft" and percent_change < -50:
        return "Top – Verlust vermieden"
    elif decision == "gehalten" and percent_change < -50:
        return "Fehler – Hätte verkaufen sollen"
    elif decision == "gekauft" and percent_change > 0:
        return "Guter Einstieg"
    else:
        return "Neutral / kein klarer Vorteil"

def save_simulation_log(entries, batch=False):
    filepath = "simulation_log.json"

    try:
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = []

        if batch:
            data.extend(entries)
        else:
            data.append(entries)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        print(f"❌ Fehler beim Schreiben: {e}")
