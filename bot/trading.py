import os
import json
from datetime import datetime
from binance.client import Client

# === API-Setup ===
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

HISTORY_FILE = "history.json"

# === Live-Preisumrechnung: USDT → EUR ===
def get_eur_rate(price_map):
    try:
        return float(price_map.get("EURUSDT", 1))
    except:
        return 1

# === Portfolio abrufen ===
def get_portfolio():
    try:
        account = client.get_account()
        prices = client.get_all_tickers()
    except Exception as e:
        print(f"Fehler beim Abrufen der Binance-Daten: {e}")
        return []

    holdings = []
    price_map = {p['symbol']: float(p.get('price', 0)) for p in prices}
    eur_rate = get_eur_rate(price_map)

    for asset in account['balances']:
        try:
            coin = asset.get('asset')
            free = float(asset.get('free', 0))
            locked = float(asset.get('locked', 0))
            total = free + locked

            if coin and total > 0 and coin != 'USDT':
                symbol = coin + 'USDT'
                current_price = price_map.get(symbol, 0)
                value_eur = round((current_price / eur_rate) * total, 2)
                holdings.append({
                    'coin': coin,
                    'amount': total,
                    'price': round(current_price / eur_rate, 4),
                    'value': value_eur
                })
        except Exception as e:
            print(f"Fehler beim Verarbeiten von Asset {asset}: {e}")
            continue

    return holdings

# === Historie schreiben ===
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

# === Profit-Schätzung ===
def get_profit_estimates():
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden der history.json: {e}")
        return []

    if not history:
        return []

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
            "percent": round(percent, 2),
            "profit": round(coin['value'] * (percent / 100), 2)
        })

    return results

# === Aktuelle Preise ziehen (EUR-Umrechnung optional nutzbar) ===
def get_current_prices():
    try:
        prices = client.get_all_tickers()
        return {p['symbol']: float(p.get('price', 0)) for p in prices}
    except Exception as e:
        print(f"Fehler beim Abrufen aktueller Preise: {e}")
        return {}

# === Simulierte Trades durchführen ===
def simulate_trade(decision, balance, portfolio, prices):
    eur_rate = prices.get("EURUSDT", 1)
    for coin, action in decision.items():
        symbol = coin + "USDT"
        price = prices.get(symbol, 0)
        if price == 0:
            continue
        price_eur = price / eur_rate

        if action == "BUY" and balance > 10:
            qty = round((balance * 0.3) / price_eur, 4)
            portfolio[coin] = portfolio.get(coin, 0) + qty
            balance -= qty * price_eur
        elif action == "SELL" and coin in portfolio:
            balance += portfolio[coin] * price_eur
            portfolio[coin] = 0
    return 
    {"balance": round(balance, 2),
        "portfolio": portfolio}
