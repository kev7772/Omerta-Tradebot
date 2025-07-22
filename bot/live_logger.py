from trading import get_current_prices
import json
from datetime import datetime
import os

HISTORY_FILE = "history.json"

def write_history():
    prices = get_current_prices()
    if not prices:
        print("⚠️ Keine aktuellen Preise gefunden.")
        return

    now = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {}

        # Speichere nur relevante USDT-Paare
        filtered = {symbol: price for symbol, price in prices.items() if symbol.endswith("USDT")}

        data[now] = filtered

        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ [{now}] Live-Preise gespeichert ({len(filtered)} Einträge)")
    except Exception as e:
        print(f"Fehler beim Speichern der Preise: {e}")
