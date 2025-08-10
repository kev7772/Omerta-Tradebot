# live_logger.py — History-Logger (EUR) im Format { "YYYY-MM-DD": {COIN: price_eur, ...}, ... }

from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any

HISTORY_FILE = "history.json"
STREAM_FILE  = "history_stream.jsonl"  # optionaler Roh-Stream je Snapshot (append)

# Optional: Binance für EUR-Umrechnung, wenn Preise in USDT geliefert werden
try:
    from binance.client import Client
except Exception:
    Client = None


def _ensure_history_file() -> None:
    """Legt ein leeres {} an, falls history.json fehlt oder kaputt ist."""
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        return
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("wrong type")
    except Exception:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def load_history_safe() -> Any:
    try:
        _ensure_history_file()
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_eurusdt() -> float:
    """EURUSDT (USDT pro EUR). Preis(EUR) = Preis(USDT) / EURUSDT. Fallback 1.0."""
    try:
        if Client is None:
            return 1.0
        api = os.getenv("BINANCE_API_KEY")
        sec = os.getenv("BINANCE_API_SECRET")
        if not api or not sec:
            return 1.0
        client = Client(api, sec)
        t = client.get_symbol_ticker(symbol="EURUSDT")
        v = float(t["price"])
        return v if v > 0 else 1.0
    except Exception:
        return 1.0


def _to_eur_prices(prices_input: List[Dict[str, float]], currency_hint: str | None) -> Dict[str, float]:
    """
    Konvertiert zu EUR.
    prices_input: [{coin:'BTC', price:12345.6}, ...]
    currency_hint: 'EUR' oder 'USDT' (None => USDT)
    """
    if not prices_input:
        return {}

    if (currency_hint or "USDT").upper() != "USDT":
        return {str(p["coin"]).upper(): float(p["price"]) for p in prices_input if "coin" in p and "price" in p}

    eurusdt = _get_eurusdt() or 1.0
    out: Dict[str, float] = {}
    for p in prices_input:
        try:
            coin = str(p["coin"]).upper()
            usdt = float(p["price"])
            eur = usdt / eurusdt if eurusdt > 0 else usdt
            out[coin] = round(eur, 6)
        except Exception:
            continue
    return out


def write_history(prices_input: List[Dict[str, float]], currency: str | None = "USDT") -> int:
    """
    Speichert ins von trading.py erwartete Format:
      { 'YYYY-MM-DD': {'BTC': 25123.45, 'ETH': 1590.22, ...}, ... }
    - Preise als EUR (USDT -> EUR via EURUSDT).
    - Merge: gleicher Tag wird erweitert/aktualisiert.
    - Zusätzlich Roh-Snapshot in history_stream.jsonl (optional).

    Rückgabe: Anzahl verarbeiteter Coins.
    """
    try:
        prices_eur = _to_eur_prices(prices_input, currency_hint=currency)
        if not prices_eur:
            print("[Logger] Keine validen Preise erhalten.")
            return 0

        _ensure_history_file()
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            hist = json.load(f)
        if not isinstance(hist, dict):
            hist = {}

        today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
        day_map = hist.get(today, {})
        if not isinstance(day_map, dict):
            day_map = {}

        day_map.update(prices_eur)
        hist[today] = day_map

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)

        # Optionaler Stream
        try:
            ts = datetime.now(timezone.utc).isoformat()
            snap = {"time": ts, "prices_eur": prices_eur}
            with open(STREAM_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(snap, ensure_ascii=False) + "\n")
        except Exception:
            pass

        print(f"[Logger] {len(prices_eur)} Preise gespeichert für {today} (EUR).")
        return len(prices_eur)
    except Exception as e:
        print(f"[Logger] write_history Fehler: {e}")
        return 0
