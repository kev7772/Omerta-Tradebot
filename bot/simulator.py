# simulator.py
# — OmertaTradeBot: Historische & Live-Simulation —
# EUR-basiert, Berlin-Zeit, robuste JSON-I/O, kompatibel zu /simstatus

import os
import json
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from binance.client import Client
from trading import get_current_prices, get_eur_rate  # nutzt bereits Binance & EURUSDT

# === Binance API ===
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

# === Files ===
SIM_LOG_FILE = "log_simulation.json"
SIM_META_FILE = "log_simulation_meta.json"

BERLIN = ZoneInfo("Europe/Berlin")


# ========== HISTORISCHE SZENARIEN ==========
historical_scenarios = [
    {
        "name": "FTX Collapse",
        "date": "2022-11-09",
        "coin": "FTT",
        "price_before": 22.00,
        "price_after": 1.50,
        "volume_crash": True,
    },
    {
        "name": "Terra Luna Crash",
        "date": "2022-05-10",
        "coin": "LUNA",
        "price_before": 85.00,
        "price_after": 0.0001,
        "volume_crash": True,
    },
    {
        "name": "Elon Doge Pump",
        "date": "2021-04-15",
        "coin": "DOGE",
        "price_before": 0.08,
        "price_after": 0.32,
        "volume_crash": False,
    },
    {
        "name": "Corona Market Crash",
        "date": "2020-03-12",
        "coin": "BTC",
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
    # Simple Heuristik (Demo): sehr günstige Coins → "gekauft", sehr teure → "gehalten", sonst "verkauft"
    if price_eur < 1.0:
        return "gekauft"
    if price_eur > 1000.0:
        return "gehalten"
    return "verkauft"


# ========== Public API ==========
def run_simulation() -> str:
    """Spielt ein zufälliges historisches Szenario durch und loggt in log_simulation.json."""
    print("🔁 Starte historische Simulation...")

    scenario = random.choice(historical_scenarios)
    decision = get_decision_based_on_scenario(scenario)

    percent_change = ((scenario["price_after"] - scenario["price_before"]) / scenario["price_before"]) * 100.0
    log_entry = {
        "timestamp": _now_str(),
        "mode": "historical",
        "scenario": scenario["name"],
        "date_ref": scenario["date"],
        "coin": scenario["coin"],
        "price_before": scenario["price_before"],
        "price_after": scenario["price_after"],
        "percent_change": round(percent_change, 2),
        "decision": decision,
        "assessment": evaluate_decision(decision, percent_change),
        "success_metric": round(abs(percent_change), 2) if decision in {"verkauft", "gekauft"} else 0.0
    }

    _append_json_list(SIM_LOG_FILE, [log_entry])
    _append_json_list(SIM_META_FILE, [{
        "timestamp": _now_str(),
        "type": "historical",
        "items": 1,
        "info": {"scenario": scenario["name"], "coin": scenario["coin"]}
    }])

    return f"📊 Historische Simulation abgeschlossen ({scenario['name']} – {scenario['coin']})"


def run_live_simulation() -> str:
    """Nutzt Live-Preise, rechnet in EUR um und loggt mehrere Coins."""
    print("⚙️ Starte Live-Simulation mit echten Kursdaten...")

    try:
        price_map_usdt = get_current_prices()  # {'BTCUSDT': 63750.0, ...}
        eur_rate = get_eur_rate(price_map_usdt) or 1.0
    except Exception as e:
        return f"❌ Fehler beim Abrufen der Live-Daten: {e}"

    timestamp = _now_str()
    # Auswahl beliebter Paare – kann easy erweitert werden
    watch_symbols = ["BTCUSDT", "ETHUSDT", "DOGEUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT"]
    log_entries = []

    for sym in watch_symbols:
        usdt_price = float(price_map_usdt.get(sym, 0.0))
        if usdt_price <= 0:
            continue

        coin = sym.replace("USDT", "")
        price_eur = usdt_price / eur_rate
        decision = simulate_live_decision(coin, price_eur)

        # simple Success-Schätzung (rein Demo)
        success = (
            round(random.uniform(5, 25), 2) if decision == "gekauft"
            else round(random.uniform(-15, 10), 2)
        )

        log_entries.append({
            "timestamp": timestamp,
            "mode": "live",
            "coin": coin,
            "price_eur": round(price_eur, 6),
            "decision": decision,
            "assessment": "Live-Modus (Heuristik)",
            "success_metric": success
        })

    if not log_entries:
        return "⚠️ Keine passenden Live-Preise gefunden."

    _append_json_list(SIM_LOG_FILE, log_entries)
    _append_json_list(SIM_META_FILE, [{
        "timestamp": timestamp,
        "type": "live",
        "items": len(log_entries),
        "info": {"watchlist": [e['coin'] for e in log_entries]}
    }])

    for entry in log_entries:
        print(f"[*] {entry['coin']} – {entry['price_eur']} € – Entscheidung: {entry['decision']}")

    return f"✅ Live-Simulation abgeschlossen mit {len(log_entries)} Coins."


def get_simulation_status() -> str:
    """
    Liefert eine kompakte Status-Zeile für /simstatus:
    - Anzahl Einträge
    - Letzter Timestamp
    - Letzter Typ (historical/live)
    """
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
