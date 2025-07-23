import json
from datetime import datetime
import trading  # wichtig: keine circular imports!

def run_simulation():
    print("🔁 Simulation gestartet...")

    # Beispiel-Szenario: FTX-Crash
    scenario = {
        "name": "FTX Collapse",
        "date": "2022-11-09",
        "coin": "FTT",
        "price_before": 22.00,
        "price_after": 1.50,
        "volume_crash": True,
    }

    # Simulierte Entscheidung des Bots:
    decision = get_decision_based_on_scenario(scenario)

    # Ergebnis berechnen
    percent_change = ((scenario["price_after"] - scenario["price_before"]) / scenario["price_before"]) * 100

    log_entry = {
        "datum": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "szenario": scenario["name"],
        "coin": scenario["coin"],
        "preis_vorher": scenario["price_before"],
        "preis_nachher": scenario["price_after"],
        "änderung": f"{percent_change:.2f}%",
        "entscheidung": decision,
        "verhalten": evaluate_decision(decision, percent_change)
    }

    # Loggen in learninglog.json
    save_simulation_log(log_entry)
    print("✅ Simulation abgeschlossen:", log_entry)


def get_decision_based_on_scenario(scenario):
    if scenario["volume_crash"] or scenario["price_after"] < (0.3 * scenario["price_before"]):
        return "verkauft"
    elif scenario["price_after"] > scenario["price_before"]:
        return "gekauft"
    else:
        return "gehalten"


def evaluate_decision(decision, percent_change):
    if decision == "verkauft" and percent_change < -50:
        return "Top – Verlust vermieden"
    elif decision == "gehalten" and percent_change < -50:
        return "Fehler – Hätte verkaufen sollen"
    elif decision == "gekauft" and percent_change > 0:
        return "Guter Einstieg"
    else:
        return "Neutral / kein klarer Vorteil"


def save_simulation_log(entry):
    try:
        with open("learninglog.json", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"❌ Fehler beim Schreiben der Log-Datei: {e}")
