# trading.py — All-Coins-Version mit EUR-Preisen
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from binance.client import Client

# === API-Setup ===
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

HISTORY_FILE = "history.json"

# === Hilfsfunktionen ===
def get_eur_rate(price_map: dict) -> float:
    """Liefert EURUSDT-Kurs oder 1.0 als Fallback."""
    try:
        eurusdt = float(price_map.get("EURUSDT", 0))
        return eurusdt if eurusdt > 0 else 1.0
    except Exception:
        return 1.0

def _get_price_map_usdt() -> dict:
    """Holt alle Binance-Tickerpreise als {SYMBOL: price(float)} in USDT-Notation."""
    try:
        prices = client.get_all_tickers()
        return {p["symbol"]: float(p.get("price", 0.0)) for p in prices}
    except Exception as e:
        print(f"[trading] Fehler bei get_all_tickers: {e}")
        return {}

# === Alle handelbaren Coins (Spot, USDT-Paare) ===
def list_all_tradeable_coins() -> list:
    """
    Holt alle handelbaren Base-Assets gegen USDT (Spot).
    Stablecoins werden ignoriert.
    """
    try:
        info = client.get_exchange_info()
        coins = set()
        for s in info.get("symbols", []):
            if s.get("status") != "TRADING":
                continue
            if s.get("quoteAsset") != "USDT":
                continue
            base = s.get("baseAsset")
            if not base or base in ["USDT", "BUSD", "USDC", "TUSD"]:
                continue
            coins.add(base)
        return sorted(coins)
    except Exception as e:
        print(f"[trading] Fehler beim Abrufen der handelbaren Coins: {e}")
        return []

# === Portfolio (nur Coins mit USDT-Paar, in EUR) ===
def get_portfolio() -> list:
    try:
        account = client.get_account()
        price_map = _get_price_map_usdt()
    except Exception as e:
        print(f"[trading] Fehler beim Abrufen der Binance-Daten: {e}")
        return []

    eur_rate = get_eur_rate(price_map)
    holdings = []

    try:
        for asset in account.get("balances", []):
            coin = asset.get("asset")
            if not coin or coin == "USDT":
                continue
            free = float(asset.get("free", 0.0))
            locked = float(asset.get("locked", 0.0))
            total = free + locked
            if total <= 0:
                continue

            symbol = f"{coin}USDT"
            usdt_price = float(price_map.get(symbol, 0.0))
            if usdt_price <= 0:
                continue

            price_eur = round(usdt_price / eur_rate, 6)
            value_eur = round(price_eur * total, 2)

            holdings.append({
                "coin": coin,
                "amount": total,
                "price": price_eur,
                "value": value_eur
            })
    except Exception as e:
        print(f"[trading] Fehler bei Portfolio-Verarbeitung: {e}")

    return holdings

# === History schreiben (für ALLE Coins) ===
def log_history() -> None:
    """
    Speichert Tagespreise (EUR) für ALLE handelbaren Coins.
    """
    all_coins = list_all_tradeable_coins()
    price_map = _get_price_map_usdt()
    eur_rate = get_eur_rate(price_map)

    log_entry = {}
    for coin in all_coins:
        symbol = f"{coin}USDT"
        usdt_price = float(price_map.get(symbol, 0.0))
        if usdt_price <= 0:
            continue
        price_eur = round(usdt_price / eur_rate, 6)
        log_entry[coin] = price_eur

    today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()

    try:
        data = {}
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        data = {}
                except Exception:
                    data = {}

        # merge/aktualisieren
        day_map = data.get(today, {})
        if not isinstance(day_map, dict):
            day_map = {}
        day_map.update(log_entry)
        data[today] = day_map

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[trading] History gespeichert für {today} ({len(log_entry)} Coins).")
    except Exception as e:
        print(f"[trading] Fehler beim Speichern der {HISTORY_FILE}: {e}")

# === Profit-Schätzung (für ALLE Coins) ===
def get_profit_estimates():
    """
    Vergleicht aktuelle EUR-Preise aller handelbaren Coins
    mit den zuletzt gespeicherten Tagespreisen.
    """
    try:
        if not os.path.exists(HISTORY_FILE):
            print(f"[trading] {HISTORY_FILE} nicht gefunden.")
            return []

        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

        if not isinstance(history, dict) or not history:
            print("[trading] History leer oder falsches Format.")
            return []

        days = sorted(history.keys())
        last_day = days[-1]
        old_prices_map = history.get(last_day, {})
        if not isinstance(old_prices_map, dict) or not old_prices_map:
            print("[trading] Keine alten Tagespreise gefunden.")
            return []

        price_map = _get_price_map_usdt()
        eur_rate = get_eur_rate(price_map)
        all_coins = list_all_tradeable_coins()

        results = []
        for coin in all_coins:
            symbol = f"{coin}USDT"
            usdt_price = float(price_map.get(symbol, 0.0))
            if usdt_price <= 0:
                continue

            current_price = round(usdt_price / eur_rate, 6)
            old_price = old_prices_map.get(coin)
            if old_price is None or old_price == 0:
                continue

            try:
                old_price = float(old_price)
            except Exception:
                continue

            percent = ((current_price - old_price) / old_price) * 100.0
            profit_abs = round(current_price - old_price, 6)

            results.append({
                "coin": coin,
                "old": round(old_price, 6),
                "current": current_price,
                "percent": round(percent, 2),
                "profit": profit_abs
            })

        return results

    except Exception as e:
        print(f"[ProfitEstimate] Fehler: {e}")
        return []

# === Aktuelle Preise holen ===
def get_current_prices() -> dict:
    """Gibt {SYMBOL: USDT-Preis} zurück."""
    try:
        return _get_price_map_usdt()
    except Exception as e:
        print(f"[trading] Fehler beim Abrufen aktueller Preise: {e}")
        return {}

# === Simulierte Trades (Demo) ===
def simulate_trade(decision: dict, balance: float, portfolio: dict, prices: dict) -> dict:
    """
    decision: {'BTC': 'BUY'/'SELL'/...}
    balance: EUR-Guthaben
    portfolio: {'BTC': menge, ...}
    prices: USDT-Preismap inkl. 'EURUSDT'
    """
    try:
        eur_rate = float(prices.get("EURUSDT", 1)) or 1.0
    except Exception:
        eur_rate = 1.0

    for coin, action in (decision or {}).items():
        symbol = f"{coin}USDT"
        usdt_price = float(prices.get(symbol, 0.0))
        if usdt_price <= 0:
            continue

        price_eur = usdt_price / eur_rate

        if action == "BUY" and balance > 10:
            qty = round((balance * 0.3) / price_eur, 6)
            portfolio[coin] = round(portfolio.get(coin, 0.0) + qty, 6)
            balance = round(balance - qty * price_eur, 2)

        elif action == "SELL" and coin in portfolio and portfolio[coin] > 0:
            balance = round(balance + portfolio[coin] * price_eur, 2)
            portfolio[coin] = 0.0

    return {"balance": round(balance, 2), "portfolio": portfolio}
