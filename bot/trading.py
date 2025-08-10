# trading.py
import os
import json
from datetime import datetime, timezone
from binance.client import Client

# === API-Setup ===
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

HISTORY_FILE = "history.json"


# === Live-Preisumrechnung: USDT → EUR ===
def get_eur_rate(price_map: dict) -> float:
    """
    EURUSDT = wie viele USDT ist 1 EUR wert.
    Um von USDT-Preis auf EUR zu kommen: euro_price = usdt_price / EURUSDT
    """
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


# === Portfolio abrufen (Werte in EUR) ===
def get_portfolio() -> list:
    """
    Gibt Liste zurück:
    [
      { 'coin': 'BTC', 'amount': 0.1234, 'price': 25123.45 (EUR), 'value': 3090.12 (EUR) },
      ...
    ]
    """
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

            try:
                free = float(asset.get("free", 0.0))
                locked = float(asset.get("locked", 0.0))
                total = free + locked
            except Exception:
                total = 0.0

            if total <= 0:
                continue

            symbol = f"{coin}USDT"
            usdt_price = float(price_map.get(symbol, 0.0))
            if usdt_price <= 0:
                # Kein USDT-Paar → skippen
                continue

            price_eur = round(usdt_price / eur_rate, 6)
            value_eur = round(price_eur * total, 2)

            holdings.append({
                "coin": coin,
                "amount": total,
                "price": price_eur,  # EUR/Einheit
                "value": value_eur    # EUR Gesamt
            })
    except Exception as e:
        print(f"[trading] Fehler bei Portfolio-Verarbeitung: {e}")

    return holdings


# === Historie schreiben (Preise in EUR) ===
def log_history() -> None:
    """
    Speichert tagesaktuelle EUR-Preise pro Coin in history.json.
    Format: { 'YYYY-MM-DD': {'BTC': 25123.45, 'ETH': 1590.22, ...}, ... }
    """
    holdings = get_portfolio()
    if not holdings:
        print("[trading] Kein Portfolio gefunden – History nicht aktualisiert.")
        return

    # Map {coin: eur_price}
    log_entry = {item["coin"]: float(item["price"]) for item in holdings}

    # Datum in UTC (nur Datumsteil). Wenn du Berlin-Zone willst, kann ich umstellen.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        else:
            data = {}

        data[today] = log_entry

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[{today}] Historie erfolgreich gespeichert.")
    except Exception as e:
        print(f"[trading] Fehler beim Speichern der {HISTORY_FILE}: {e}")


# === Profit-Schätzung (gegen letzten History-Tag) ===
def get_profit_estimates() -> list:
    """
    Vergleicht aktuelle EUR-Preise mit dem letzten gespeicherten Tag in history.json.
    Rückgabe-Liste pro Coin:
    {
      "coin": "BTC",
      "old": 25000.0,
      "current": 26250.0,
      "percent": 5.0,
      "profit": 123.45,     # grob auf Basis aktueller Bestände (value * Prozent)
      "amount": 0.1234,
      "value": 3234.56      # aktueller EUR-Gesamtwert der Position
    }
    Mindestens gebraucht von deiner logic.py: "coin", "percent".
    """
    try:
        # History laden
        if not os.path.exists(HISTORY_FILE):
            print(f"[trading] {HISTORY_FILE} nicht gefunden.")
            return []

        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

        if not isinstance(history, dict) or not history:
            print("[trading] History leer oder falsches Format.")
            return []

        # Letzten verfügbaren Tag ermitteln
        last_day = sorted(history.keys())[-1]
        old_prices = history.get(last_day, {})
        if not isinstance(old_prices, dict) or not old_prices:
            print("[trading] Letzter History-Tag hat keine Daten.")
            return []

        # Aktuelles Portfolio & aktuelle EUR-Preise
        current_holdings = get_portfolio()
        if not current_holdings:
            return []

        results = []
        for pos in current_holdings:
            coin = pos.get("coin")
            amount = float(pos.get("amount", 0.0))
            current_price = float(pos.get("price", 0.0))  # EUR/Einheit

            if not coin or amount <= 0 or current_price <= 0:
                continue

            old_price = old_prices.get(coin)
            if old_price is None or old_price == 0:
                # Kein alter Preis → für Prozentrechnung überspringen (oder 0 setzen)
                print(f"[trading] ⚠️ Kein alter Preis für {coin} am {last_day} – überspringe")
                continue

            try:
                old_price = float(old_price)
            except Exception:
                continue

            percent = ((current_price - old_price) / old_price) * 100.0
            value_now = round(current_price * amount, 2)
            profit_abs = round(value_now * (percent / 100.0), 2)

            results.append({
                "coin": coin,
                "old": round(old_price, 6),
                "current": round(current_price, 6),
                "percent": round(percent, 2),
                "profit": profit_abs,
                "amount": amount,
                "value": value_now
            })

        return results

    except Exception as e:
        print(f"[ProfitEstimate] Fehler: {e}")
        return []


# === Aktuelle Preise ziehen (USDT-Map; optional nützlich) ===
def get_current_prices() -> dict:
    """
    Gibt {SYMBOL: USDT-Preis} zurück (z. B. 'BTCUSDT': 63750.0).
    Für EUR-Preis -> teile durch EURUSDT.
    """
    try:
        return _get_price_map_usdt()
    except Exception as e:
        print(f"[trading] Fehler beim Abrufen aktueller Preise: {e}")
        return {}


# === Simulierte Trades durchführen (einfaches Demo) ===
def simulate_trade(decision: dict, balance: float, portfolio: dict, prices: dict) -> dict:
    """
    decision: {'BTC': 'BUY'/'SELL'/...}
    balance: EUR-Guthaben (float)
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

    return {
        "balance": round(balance, 2),
        "portfolio": portfolio
    }
