import json
from datetime import datetime
from typing import List, Dict, Any, Iterable, Tuple
import os

HISTORY_FILE = "history.json"


def _ensure_history_file():
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w") as f:
            json.dump([], f)


def _iso_now() -> str:
    return datetime.now().isoformat()


def _normalize_prices(prices_input) -> List[Dict[str, Any]]:
    """
    Akzeptiert z.B.:
      - [{"coin":"BTC","price":12345.6}, ...]
      - {"BTC":12345.6,"ETH":2345.7}
      - [("BTC",123), ("ETH",234)]
    Gibt immer: [{"coin":..., "price":...}, ...] zurück.
    """
    out: List[Dict[str, Any]] = []

    if isinstance(prices_input, dict):
        for c, p in prices_input.items():
            out.append({"coin": str(c), "price": float(p)})
        return out

    if isinstance(prices_input, Iterable):
        for item in prices_input:
            if isinstance(item, dict) and "coin" in item and "price" in item:
                out.append({"coin": str(item["coin"]), "price": float(item["price"])})
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                c, p = item
                out.append({"coin": str(c), "price": float(p)})
    return out


def write_history(prices_input) -> int:
    """
    Hängt die aktuellen Preise mit garantiertem ISO-Timestamp an die history.json an.
    Gibt die Anzahl der geschriebenen Einträge zurück.
    """
    _ensure_history_file()

    prices = _normalize_prices(prices_input)
    if not prices:
        print("⚠️ write_history: Keine gültigen Preis-Daten erhalten.")
        return 0

    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
            if not isinstance(history, list):
                history = []
    except Exception:
        history = []

    now_iso = _iso_now()
    for item in prices:
        history.append({
            "coin": item["coin"],
            "price": item["price"],
            "timestamp": now_iso  # ← immer vorhanden
        })

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"[Logger] Preise gespeichert um {now_iso}")
    return len(prices)


def load_history_safe() -> List[Dict[str, Any]]:
    """
    Lädt history.json und filtert alles raus, was keinen oder einen ungültigen Timestamp hat.
    So crasht die Lernbewertung nicht mehr.
    """
    _ensure_history_file()
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
            if not isinstance(history, list):
                return []
    except Exception:
        return []

    cleaned: List[Dict[str, Any]] = []
    for e in history:
        ts = e.get("timestamp")
        coin = e.get("coin")
        price = e.get("price")
        if not coin or price is None:
            continue
        if not isinstance(ts, str):
            continue
        # Prüfen, ob ISO-parsbar
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        cleaned.append({"coin": str(coin), "price": float(price), "timestamp": ts})

    return cleaned
