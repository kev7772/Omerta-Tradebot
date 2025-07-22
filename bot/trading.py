import os
import json
from datetime import datetime
from binance.client import Client

# API-Keys aus Environment (Railway / Render Variablen)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

HISTORY_FILE = "history.json"

def get_portfolio():
    try:
        account = client.get_account()
        prices = client.get_all_tickers()
    except Exception as e:
        print(f"Fehler beim Abrufen der Binance-Daten: {e}")
        return []

    holdings = []
    price_map = {p['symbol']: float(p.get('price', 0)) for p in prices}

    for asset in account['balances']:
        try:
            coin = asset.get('asset')
            free = float(asset.get('free', 0))
            locked = float(asset.get('locked', 0))
            total = free + locked

            if coin and total > 0 and coin != 'USDT':
                symbol = coin + 'USDT'
                current_price = price_map.get(symbol, 0)
                holdings.append({
                    'coin': coin,
                    'amount': total,
                    'price': current_price,
                    'value': round(current_price * total, 2)
                })
        except Exception as e:
            print(f"Fehler beim Verarbeiten von Asset {asset}: {e}")
            continue

    return holdings

def log_history():
    holdings = get_portfolio()
    log = {item['coin']: item['price'] for item in holdings}
    now = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {}

        data[now] = log

        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)

        print(f"[{now}] Historie erfolgreich gespeichert.")
    except Exception as e:
        print(f"Fehler beim Speichern der history.json: {e}")

def get_profit_estimates():
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden der history.json: {e}")
        return []

    if not history:
        return []

    # Letzter Tag
    last_day = sorted(history.keys())[-1]
    old_prices = history[last_day]

    current = get_portfolio()
    results = []

    for coin in current:
        symbol = coin['coin']
        current_price = coin['price']
        old_price = float(old_prices.get(symbol, 0))

        if old_price > 0:
            percent = ((current_price - old_price) / old_price) * 100
        else:
            percent = 0

        results.append({
            "coin": symbol,
            "old": old_price,
            "current": current_price,
            "percent": round(percent, 2)
        })

    return results
