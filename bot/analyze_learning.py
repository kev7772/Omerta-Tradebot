import json
from collections import defaultdict

def generate_learning_stats():
    with open("learn_log.json", "r") as f:
        data = json.load(f)

    stats = defaultdict(lambda: {"correct": 0, "wrong": 0})

    for entry in data:
        coin = entry["coin"]
        if entry["correct"]:
            stats[coin]["correct"] += 1
        else:
            stats[coin]["wrong"] += 1

    summary = []
    for coin, s in stats.items():
        total = s["correct"] + s["wrong"]
        accuracy = round(100 * s["correct"] / total, 2)
        summary.append(f"{coin}: ✅ {s['correct']} / ❌ {s['wrong']} → {accuracy}% richtig")

    return summary

def generate_learning_stats():
    try:
        with open("learn_log.json", "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ["⚠️ Kein Lernlog gefunden oder Datei fehlerhaft."]

    if not data:
        return ["ℹ️ Noch keine Lern-Daten vorhanden."]

    stats = defaultdict(lambda: {"correct": 0, "wrong": 0})
    ...
