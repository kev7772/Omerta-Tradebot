import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json

def generate_heatmap():
    filepath = os.path.join(os.path.dirname(__file__), "learning_log.json")

    if not os.path.exists(filepath):
        print("❌ Lernlog-Datei fehlt.")
        return

    with open(filepath, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Fehler beim Lesen der JSON-Datei.")
            return

    if not data:
        print("⚠️ Keine Einträge im Lernlog.")
        return

    # Umwandeln in DataFrame
    df = pd.DataFrame(data)

    if not all(col in df.columns for col in ["coin", "indicator", "success"]):
        print("⚠️ Fehlende Spalten in der Lernlog-Datei.")
        return

    # Pivot-Tabelle: Coins vs Indikatoren
    pivot = df.pivot_table(index="coin", columns="indicator", values="success", aggfunc="mean")

    # Heatmap erstellen
    plt.figure(figsize=(10, 6))
    sns.heatmap(pivot, annot=True, cmap="coolwarm", fmt=".1f", linewidths=0.5)
    plt.title("📊 Erfolgs-Heatmap: Coin vs Indikator")
    plt.tight_layout()

    # Speichern als PNG
    output_path = os.path.join(os.path.dirname(__file__), "heatmap.png")
    plt.savefig(output_path)
    print(f"✅ Heatmap gespeichert unter: {output_path}")
