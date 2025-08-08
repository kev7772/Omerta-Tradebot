from datetime import datetime
from binance.client import Client
import os
import json

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

HISTORY_FILE = "history.json"

def write_history():
    try:
        prices = client.get_all_tickers()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history_entry = {"timestamp": timestamp, "prices": {}}

        for p in prices:
            symbol = p["symbol"]
            price = p["price"]
            history_entry["prices"][symbol] = price

        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
        else:
            data = []

        data.append(history_entry)

        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)

        print(f"[Logger] Preise gespeichert um {timestamp}")

    except Exception as e:
        print(f"[Logger] Fehler beim Speichern der Preise: {e}")

        # Speichere nur relevante USDT-Paare
        filtered = {symbol: price for symbol, price in prices.items() if symbol.endswith("USDT")}

        data[now] = filtered

        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ [{now}] Live-Preise gespeichert ({len(filtered)} Einträge)")
    except Exception as e:
        print(f"Fehler beim Speichern der Preise: {e}")
