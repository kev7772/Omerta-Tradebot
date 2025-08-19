# simulator.py
# — OmertaTradeBot: Historische & Live-Simulation —
# EUR-basiert, Berlin-Zeit, robuste JSON-I/O, kompatibel zu /simstatus
# Neu:
#  - Liefert für historisch & live eine LISTE von Entries (ALLE Coins) zurück
#  - Jeder Entry kompatibel zu decision_logger (coin, action, percent, price, signal, reason, source)
#  - Prozent-Berechnung vs. letztem EUR-Preis aus history.json (falls vorhanden)
#  - Helpers zum direkten Loggen in log_simulation.json + decision_log.json

from __future__ import annotations
import os
import json
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

from binance.client import Client
from trading import get_current_prices, get_eur_rate, list_all_tradeable_coins  # All-Coins
from decision_logger import log_trade_decisions

# === Binance API ===
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

# === Files ===
SIM_LOG_FILE = "log_simulation.json"
SIM_META_FILE = "log_simulation_meta.json"
HISTORY_FILE = "history.json"  # erwartet Struktur {"BTC": [{"time": "...", "eur": 123.45}, ...], ...}

BERLIN = ZoneInfo("Europe/Berlin")


# ========== HISTORISCHE SZENARIEN (Multi-Coin) ==========
historical_scenarios = [
    {
        "name": "FTX Collapse",
        "date": "2022-11-09",
        "coins": ["FTT", "BTC", "ETH", "SOL", "BNB"],
        "price_before": 22.00,
        "price_after": 1.50,
        "volume_crash": True,
    },
    {
        "name": "Terra Luna Crash",
        "date": "2022-05-10",
        "coins": ["LUNA", "UST", "BTC", "ETH"],
        "price_before": 85.00,
        "price_after": 0.0001,
        "volume_crash": True,
    },
    {
        "name": "Elon Doge Pump",
        "date": "2021-04-15",
        "coins": ["DOGE", "SHIB", "BTC"],
        "price_before": 0.08,
        "price_after": 0.32,
        "volume_crash": False,
    },
    {
        "name": "Corona Market Crash",
        "date": "2020-03-12",
        "coins": ["BTC", "ETH", "XRP", "LTC", "ADA"],
        "price_before": 9200,
        "price_after": 4800,
        "volume_crash": True,
    }
]


# ========== Helpers ==========
def _now_str() -> str:
    return datetime.now(BERLIN).strftime("%Y-%m-%d %H:%M:%S")


def _load_json_list(path: str) -> list:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        pass
    return []


def _save_json_list(path: str, data: list) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[simulator] Fehler beim Schreiben {path}: {e}")


def _append_json_list(path: str, entries: list) -> None:
    data = _load_json_list(path)
    data.extend(entries)
    _save_json_list(path, data)


def _load_history() -> Dict[str, List[Dict[str, Any]]]:
    """Lädt history.json falls vorhanden. Erwartet pro Coin eine Liste von Records mit 'eur'."""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _last_eur_price(history: Dict[str, List[Dict[str, Any]]], coin: str) -> Optional[float]:
    arr = history.get(coin.upper())
    if not arr or not isinstance(arr, list):
        return None
    # letztes Element mit 'eur' nehmen
    for rec in reversed(arr):
        eur = rec.get("eur")
        try:
            if eur is not None:
                return float(eur)
        except Exception:
            continue
    return None


def _pct_change(now_val: Optional[float], prev_val: Optional[float]) -> Optional[float]:
    if now_val is None or prev_val is None:
        return None
    if prev_val == 0:
        return None
    return ((now_val - prev_val) / prev_val) * 100.0


def _to_action(decision: str) -> str:
    """Mappt freie Entscheidungen ('gekauft', 'verkauft', 'gehalten') auf action (buy/sell/hold)."""
    d = str(decision).lower()
    if d.startswith("gekauf"):
        return "buy"
    if d.startswith("verkauf"):
        return "sell"
    if d.startswith("gehalten"):
        return "hold"
    # Fallback
    if d in {"buy", "sell", "hold"}:
        return d
    return "hold"


# ========== Kernlogik ==========
def get_decision_based_on_scenario(scenario: dict) -> str:
    drop = scenario["price_after"] < (0.3 * scenario["price_before"])
    if scenario.get("volume_crash") or drop:
        return "verkauft"
    elif scenario["price_after"] > scenario["price_before"]:
        return "gekauft"
    return "gehalten"


def evaluate_decision(decision: str, percent_change: float) -> str:
    if decision == "verkauft" and percent_change <= -50:
        return "Top – Verlust vermieden"
    if decision == "gehalten" and percent_change <= -50:
        return "Fehler – Hätte verkaufen sollen"
    if decision == "gekauft" and percent_change > 0:
        return "Guter Einstieg"
    return "Neutral / kein klarer Vorteil"


def simulate_live_decision(coin: str, price_eur: float) -> str:
    # Simple Heuristik (Demo) – hier kannst du später deine echte Signal-Logik einsetzen
    if price_eur < 1.0:
        return "gekauft"
    if price_eur > 1000.0:
        return "gehalten"
    return "verkauft"


# ========== Multi-Coin Historische Simulation ==========
def run_simulation() -> List[Dict[str, Any]]:
    """
    Spielt ein zufälliges historisches Szenario für ALLE betroffenen Coins durch.
    Rückgabe: Liste von Einträgen, kompatibel zu decision_logger.log_trade_decisions()
    """
    print("🔁 Starte historische Multi-Coin-Simulation...")

    scenario = random.choice(historical_scenarios)
    log_entries: List[Dict[str, Any]] = []

    percent_change = ((scenario["price_after"] - scenario["price_before"]) / scenario["price_before"]) * 100.0
    timestamp = _now_str()

    for coin in scenario["coins"]:
        decision = get_decision_based_on_scenario({
            "price_before": scenario["price_before"],
            "price_after": scenario["price_after"],
            "volume_crash": scenario.get("volume_crash", False)
        })

        entry = {
            # --- Felder fürs Simulation-Log (frei) ---
            "timestamp": timestamp,
            "mode": "historical",
            "scenario": scenario["name"],
            "date_ref": scenario["date"],
            "coin": coin,
            "price_before": scenario["price_before"],
            "price_after": scenario["price_after"],
            "percent_change": round(percent_change, 2),
            "decision": decision,
            "assessment": evaluate_decision(decision, percent_change),
            "success_metric": round(abs(percent_change), 2) if decision in {"verkauft", "gekauft"} else 0.0,

            # --- Felder kompatibel zu decision_logger ---
            "action": _to_action(decision),                  # buy/sell/hold
            "signal": decision,                              # freier Text
            "percent": round(percent_change, 2),             # % ggü. before/after (Szenario)
            "price": scenario["price_after"],                # aktueller Referenzpreis
            "reason": f"Szenario: {scenario['name']}",
            "source": "historical-sim",
        }
        log_entries.append(entry)

    return log_entries


# ========== Live-Simulation für ALLE Coins ==========
def run_live_simulation() -> List[Dict[str, Any]]:
    """
    Nutzt Live-Preise, rechnet in EUR um und liefert EINTRÄGE FÜR ALLE handelbaren Coins.
    Jeder Eintrag ist ready für decision_logger.log_trade_decisions().
    """
    print("⚙️ Starte Live-Simulation mit echten Kursdaten...")

    try:
        price_map_usdt = get_current_prices()  # z.B. {"BTCUSDT": 59234.12, ...}
        eur_rate = get_eur_rate(price_map_usdt) or 1.0
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Live-Daten: {e}")
        return []

    timestamp = _now_str()
    all_coins = list_all_tradeable_coins()
    history = _load_history()

    entries: List[Dict[str, Any]] = []

    for coin in all_coins:
        symbol = f"{coin}USDT"
        usdt_price = price_map_usdt.get(symbol)
        try:
            usdt_price = float(usdt_price)
        except Exception:
            continue

        if not usdt_price or usdt_price <= 0:
            continue

        price_eur = usdt_price / eur_rate
        decision = simulate_live_decision(coin, price_eur)

        prev_eur = _last_eur_price(history, coin)
        pct = _pct_change(price_eur, prev_eur)

        entry = {
            # --- freie Sim-Felder ---
            "timestamp": timestamp,
            "mode": "live",
            "coin": coin,
            "price_eur": round(price_eur, 6),
            "prev_price_eur": round(prev_eur, 6) if isinstance(prev_eur, (int, float)) else None,
            "decision": decision,
            "assessment": "Live-Modus (Heuristik)",
            "success_metric": (
                round(random.uniform(5, 25), 2) if decision == "gekauft"
                else round(random.uniform(-15, 10), 2)
            ),

            # --- decision_logger-kompatibel ---
            "action": _to_action(decision),
            "signal": decision,
            "percent": round(pct, 4) if isinstance(pct, (int, float)) else None,  # ggü. letztem history-EUR
            "price": round(price_eur, 6),
            "reason": "Live-Simulation (EUR-basiert)",
            "source": "live-sim",
        }
        entries.append(entry)

    return entries


# ========== Logging-Wrapper (bequem) ==========
def log_historical_simulation_and_decisions() -> str:
    """
    Führt run_simulation() aus, hängt ALLE Entries an log_simulation.json & log_simulation_meta.json
    und loggt sie zusätzlich in decision_log.json (über decision_logger).
    """
    entries = run_simulation()
    if not entries:
        return "⚠️ Historische Simulation lieferte keine Einträge."

    timestamp = _now_str()

    # 1) Simulation-Logs (frei)
    _append_json_list(SIM_LOG_FILE, entries)
    scenario_name = entries[0].get("scenario", "unknown")
    coins = [e["coin"] for e in entries]
    _append_json_list(SIM_META_FILE, [{
        "timestamp": timestamp,
        "type": "historical",
        "items": len(entries),
        "info": {"scenario": scenario_name, "coins": coins}
    }])

    # 2) Decision-Log (strukturiert)
    added = log_trade_decisions(entries, source="historical-sim")
    return f"📊 Historische Simulation '{scenario_name}' geloggt: {len(entries)} Coins (Decision-Log +{added})."


def log_live_simulation_and_decisions() -> str:
    """
    Führt run_live_simulation() aus, hängt ALLE Entries an log_simulation.json & log_simulation_meta.json
    und loggt sie zusätzlich in decision_log.json (über decision_logger).
    """
    entries = run_live_simulation()
    if not entries:
        return "⚠️ Keine passenden Live-Preise gefunden."

    timestamp = _now_str()

    # 1) Simulation-Logs (frei)
    _append_json_list(SIM_LOG_FILE, entries)
    _append_json_list(SIM_META_FILE, [{
        "timestamp": timestamp,
        "type": "live",
        "items": len(entries),
        "info": {"watchlist": [e['coin'] for e in entries]}
    }])

    # 2) Decision-Log (strukturiert)
    added = log_trade_decisions(entries, source="live-sim")
    print(f"[*] Live-Simulation: {len(entries)} Coins geloggt, Decision-Log +{added}.")
    return f"✅ Live-Simulation abgeschlossen: {len(entries)} Coins (Decision-Log +{added})."


# ========== Status ==========
def get_simulation_status() -> str:
    logs = _load_json_list(SIM_LOG_FILE)
    meta = _load_json_list(SIM_META_FILE)

    count = len(logs)
    last_time = "—"
    last_type = "—"

    if meta:
        last = meta[-1]
        last_time = last.get("timestamp", "—")
        last_type = last.get("type", "—")

    return f"🧪 Simulationen: {count} | Letzter Lauf: {last_time} | Typ: {last_type}"
