# live_logger.py
import json
from datetime import datetime
from trading import get_current_prices  # muss existieren

def write_history(filename="history.json"):
    try:
        prices = get_current_prices()  # z.B. {'BTC': 26100.5, 'ETH': 1580.2}
        date_str = datetime.now().strftime("%Y-%m-%d")

        new_entry = {
            "date": date_str,
            "prices": prices
        }

        try:
            with open(filename, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []

        data.append(new_entry)

        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

        print(f"✅ Kursdaten für {date_str} gespeichert.")
    except Exception as e:
        print(f"❌ Fehler beim Schreiben der History: {e}")

if __name__ == "__main__":
    write_history()
