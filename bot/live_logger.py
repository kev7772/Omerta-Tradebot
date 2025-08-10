# live_logger.py — optimiert
# - Robust gegen kaputte history.json
# - ISO-8601 mit Zeitzone (UTC+Offset), sekundengenau
# - Thread-safe via Lock
# - Akzeptiert Dict, Liste von Dicts, Liste von Tupeln
# - Atomisches Schreiben (Tempfile + Replace)
# - Zusätzliche Helper: load_history_safe(), read_latest(), last_price_map()

from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Iterable, Tuple, Union
import os
import tempfile
import threading

HISTORY_FILE = "history.json"
_LOCK = threading.Lock()

PriceItem = Dict[str, Any]
PricesInput = Union[
    Dict[str, float],               # {"BTC": 12345.6, "ETH": 2345.7}
    List[PriceItem],                # [{"coin":"BTC","price":12345.6}, ...]
    List[Tuple[str, float]],        # [("BTC",123), ("ETH",234)]
]

# ---------- intern ----------

def _ensure_history_file() -> None:
    if not os.path.exists(HISTORY_FILE):
        _atomic_write(HISTORY_FILE, [])

def _iso_now() -> str:
    # Zeitzonen-bewusst, sekundengenau
    return datetime.now().astimezone().isoformat(timespec="seconds")

def _parse_iso(ts: str) -> datetime | None:
    # Akzeptiert "Z" und Offset
    try:
        ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except Exception:
        return None

def _normalize_coin_name(name: Any) -> str:
    if name is None:
        return ""
    s = str(name).strip().upper()
    # kleine Aufräum-Regel: BTCUSDT -> BTC
    if s.endswith("USDT") and len(s) > 4:
        s = s[:-4]
    return s

def _normalize_prices(prices_input: PricesInput) -> List[PriceItem]:
    """
    Unterstützte Eingaben:
      - [{"coin":"BTC","price":12345.6}, ...]
      - {"BTC":12345.6,"ETH":2345.7}
      - [("BTC",123), ("ETH",234)]
    Ausgabe:
      - [{"coin": "...", "price": float}, ...] (ohne Timestamp)
    """
    out: List[PriceItem] = []
    if prices_input is None:
        return out

    if isinstance(prices_input, dict):
        for c, p in prices_input.items():
            try:
                coin = _normalize_coin_name(c)
                price = float(p)
                if coin and price >= 0:
                    out.append({"coin": coin, "price": price})
            except Exception:
                continue
        return out

    if isinstance(prices_input, Iterable):
        for item in prices_input:
            try:
                if isinstance(item, dict):
                    if "coin" in item and "price" in item:
                        coin = _normalize_coin_name(item["coin"])
                        price = float(item["price"])
                        if coin and price >= 0:
                            out.append({"coin": coin, "price": price})
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    coin = _normalize_coin_name(item[0])
                    price = float(item[1])
                    if coin and price >= 0:
                        out.append({"coin": coin, "price": price})
            except Exception:
                continue
    return out

def _safe_load_list(path: str) -> List[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

def _atomic_write(path: str, data: Any) -> None:
    # schreibt atomar, um korrupten Dateien vorzubeugen
    d = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, dir=d, suffix=".tmp", encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tmp_name = tf.name
    os.replace(tmp_name, path)

# ---------- öffentlich ----------

def write_history(prices_input: PricesInput) -> int:
    """
    Hängt die aktuellen Preise (mit garantiertem ISO-Timestamp) an die history.json an.
    Rückgabe: Anzahl geschriebener Einträge.
    """
    prices = _normalize_prices(prices_input)
    if not prices:
        print("⚠️ write_history: Keine gültigen Preis-Daten erhalten.")
        return 0

    entry_ts = _iso_now()

    with _LOCK:
        _ensure_history_file()
        history = _safe_load_list(HISTORY_FILE)

        # Anhängen
        for item in prices:
            history.append({
                "coin": item["coin"],
                "price": float(item["price"]),
                "timestamp": entry_ts  # einheitlicher Timestamp pro Batch
            })

        # Schreiben (atomar)
        _atomic_write(HISTORY_FILE, history)

    print(f"[Logger] {len(prices)} Preise gespeichert um {entry_ts}")
    return len(prices)

def load_history_safe() -> List[Dict[str, Any]]:
    """
    Lädt history.json und filtert:
      - ohne/kaputten Timestamp
      - ohne Coin
      - ohne Price
    Gibt nur saubere Einträge zurück.
    """
    with _LOCK:
        _ensure_history_file()
        raw = _safe_load_list(HISTORY_FILE)

    cleaned: List[Dict[str, Any]] = []
    for e in raw:
        coin = _normalize_coin_name(e.get("coin"))
        price = e.get("price")
        ts = e.get("timestamp")
        if not coin or price is None or not isinstance(ts, str):
            continue
        dt = _parse_iso(ts)
        if dt is None:
            continue
        try:
            cleaned.append({"coin": coin, "price": float(price), "timestamp": ts})
        except Exception:
            continue
    return cleaned

# ---------- praktische Zusatz-Helper (optional, aber nützlich) ----------

def read_latest(n: int = 200) -> List[Dict[str, Any]]:
    """
    Liefert die letzten n Einträge (sauber gefiltert).
    """
    data = load_history_safe()
    return data[-n:] if n > 0 else data

def last_price_map() -> Dict[str, float]:
    """
    Liefert ein Dict {COIN: letzter_price}.
    """
    data = load_history_safe()
    latest: Dict[str, float] = {}
    seen_ts: Dict[str, datetime] = {}

    for e in data:
        coin = e["coin"]
        price = float(e["price"])
        ts = _parse_iso(e["timestamp"])
        if ts is None:
            continue
        if coin not in seen_ts or ts > seen_ts[coin]:
            seen_ts[coin] = ts
            latest[coin] = price
    return latest

def read_range(start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
    """
    Filtert Einträge zwischen start_iso und end_iso (inklusive).
    ISO-Format mit Offset erwartet, 'Z' wird akzeptiert.
    """
    s = _parse_iso(start_iso)
    e = _parse_iso(end_iso)
    if not s or not e:
        return []
    if e < s:
        s, e = e, s
    out: List[Dict[str, Any]] = []
    for item in load_history_safe():
        ts = _parse_iso(item["timestamp"])
        if ts and s <= ts <= e:
            out.append(item)
    return out
