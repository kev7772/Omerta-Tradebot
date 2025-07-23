import json
from datetime import datetime

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

    # Simulierte Entscheidung des Bots
    decision = get_decision_based_on_scenario(scenario)

    # Prozentuale Preisänderung berechnen
    percent_change = ((scenario["price_after"] - scenario["price_before"]) / scenario["price_before"]) * 100

    # Zusammenfassung der Simulation
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

    # In learning_log.json speichern
    save_simulation_log(log_entry)

    # Rückgabe für Telegram
    result_text = (
        f"📊 *Simulation abgeschlossen:*\n"
        f"🧠 Szenario: {log_entry['szenario']}\n"
        f"💰 Coin: {log_entry['coin']}\n"
        f"📉 Preis vorher: {log_entry['preis_vorher']} €\n"
        f"📈 Preis nachher: {log_entry['preis_nachher']} €\n"
        f"📉 Änderung: {log_entry['änderung']}\n"
        f"📌 Entscheidung: {log_entry['entscheidung']}\n"
        f"🧠 Verhalten: {log_entry['verhalten']}"
    )

    print(result_text)
    return result_text


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
    filepath = "learning_log.json"

    try:
        # Vorherige Einträge laden
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = []

        # Neuen Eintrag anhängen
        data.append(entry)

        # Zurückspeichern
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        print(f"❌ Fehler beim Schreiben in learning_log.json: {e}")
