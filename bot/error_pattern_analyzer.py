import json
import os
from collections import defaultdict

LOGFILE = "simulation_log.json"

def analyze_errors():
    if not os.path.exists(LOGFILE):
        return "⚠️ Noch keine Simulationsdaten vorhanden."

    try:
        with open(LOGFILE, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return "⚠️ Fehler beim Lesen der Simulationsdaten."

    fehler_map = defaultdict(lambda: {"count": 0, "fails": 0})

    for entry in data:
        coin = entry.get("coin", "???")
        decision = entry.get("entscheidung", "").lower()
        erfolg = float(entry.get("success", 0))

        fehler_map[coin]["count"] += 1
        if decision == "gekauft" and erfolg < 0:
            fehler_map[coin]["fails"] += 1
        elif decision == "verkauft" and erfolg < 0:
            fehler_map[coin]["fails"] += 1
        elif decision == "gehalten" and erfolg < 0:
            fehler_map[coin]["fails"] += 1

    output = "🧠 *Fehlermuster-Analyse:*\n"
    gefunden = False

    for coin, stats in fehler_map.items():
        if stats["fails"] >= 2:  # Schwelle: ab 2 Fehlern wird's interessant
            rate = round((stats["fails"] / stats["count"]) * 100, 1)
            output += f"🔻 {coin}: {stats['fails']} Fehler bei {stats['count']} Versuchen ({rate}%)\n"
            gefunden = True

    if not gefunden:
        output += "✅ Keine auffälligen Fehlermuster erkannt."

    return output
