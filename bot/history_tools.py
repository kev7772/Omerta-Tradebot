# history_tools.py
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

try:
    # Python 3.9+: eingebaute ZoneInfo
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Berlin")
except Exception:
    TZ = None  # Fallback auf naive datetime

HISTORY_FILE = "history.json"


# ---------------------------
# Helpers
# ---------------------------

def _today_str() -> str:
    if TZ:
        return datetime.now(TZ).strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def _load_history() -> Optional[Dict[str, Dict[str, float]]]:
    if not os.path.exists(HISTORY_FILE):
        return None
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Erwartet: { "YYYY-MM-DD": {"BTC": 65000.0, ...}, ... }
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def get_available_dates() -> List[str]:
    """Gibt alle Datumsschlüssel sortiert (alt -> neu) zurück."""
    data = _load_history()
    if not data:
        return []
    try:
        return sorted(data.keys())
    except Exception:
        return []


def get_latest_date() -> Optional[str]:
    dates = get_available_dates()
    return dates[-1] if dates else None


def _safe_pct_change(old: Any, new: Any) -> Optional[float]:
    """Sichere Prozentänderung in %. Gibt None bei Fehlern/0-Div zurück."""
    try:
        old_f = float(old)
        new_f = float(new)
        if old_f == 0:
            return None
        return round(((new_f - old_f) / old_f) * 100.0, 2)
    except Exception:
        return None


def _format_line(coin: str, pct: float) -> str:
    symbol = "📈" if pct > 0 else "📉" if pct < 0 else "⚖️"
    return f"{coin}: {symbol} {pct} %"


# ---------------------------
# Public API
# ---------------------------

def get_all_changes_since(
    since_date: str,
    to_date: Optional[str] = None,
    *,
    sort_by_abs: bool = False,
    top_n: Optional[int] = None
) -> List[str]:
    """
    Kursveränderungen ALLER verfügbaren Coins zwischen since_date und to_date (Standard: heute bzw. letztes Datum).
    Rückgabe: Liste formatierter Strings pro Coin.
    Optionen:
      - sort_by_abs=True -> nach absoluter Veränderung (absteigend) sortieren
      - top_n=N -> nur Top N Einträge zurückgeben
    """
    data = _load_history()
    if not data:
        return ["⚠️ Keine history.json vorhanden."]

    if since_date not in data:
        return [f"⚠️ Kein Preislog für {since_date} gefunden."]

    if not to_date:
        # Bevorzugt „heute“ in Berlin; falls nicht vorhanden -> letztes verfügbares Datum
        today = _today_str()
        to_date = today if today in data else get_latest_date()

    if not to_date or to_date not in data:
        return [f"⚠️ Kein Preislog für Ziel-Datum gefunden. (angefragt: {to_date})"]

    old = data[since_date]
    cur = data[to_date]

    lines: List[Tuple[str, float]] = []
    for coin, new_price in cur.items():
        if coin in old:
            pct = _safe_pct_change(old.get(coin), new_price)
            if pct is not None:
                lines.append((coin, pct))

    if not lines:
        return ["⚠️ Keine gemeinsamen Coins zwischen beiden Tagen."]

    if sort_by_abs:
        lines.sort(key=lambda x: abs(x[1]), reverse=True)
    else:
        # Alphabetisch, damit deterministisch
        lines.sort(key=lambda x: x[0])

    if top_n is not None and top_n > 0:
        lines = lines[:top_n]

    return [_format_line(c, p) for c, p in lines]


def get_change_since(
    coin: str,
    since_date: str,
    to_date: Optional[str] = None
) -> Optional[float]:
    """
    Prozentuale Veränderung eines Coins zwischen since_date und to_date.
    Rückgabe: float in Prozent (z. B. 12.34) oder None, wenn nicht berechenbar.
    """
    data = _load_history()
    if not data:
        return None

    if since_date not in data:
        return None

    if not to_date:
        today = _today_str()
        to_date = today if today in data else get_latest_date()

    if not to_date or to_date not in data:
        return None

    old_price = data[since_date].get(coin)
    new_price = data[to_date].get(coin)
    return _safe_pct_change(old_price, new_price)


def get_changes_between(
    from_date: str,
    to_date: str,
    *,
    sort_by_abs: bool = False
) -> List[str]:
    """
    Wie get_all_changes_since, aber explizit zwischen zwei festen Daten.
    Praktisch für Telegram-Befehl /change 2025-08-01 2025-08-10
    """
    return get_all_changes_since(from_date, to_date, sort_by_abs=sort_by_abs)
