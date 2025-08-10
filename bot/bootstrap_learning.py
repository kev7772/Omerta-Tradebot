# bootstrap_learning.py — füttert automatisch das Lernlog, wenn noch leer

from __future__ import annotations
import os, json, time
from typing import Optional

from simulator import run_simulation, run_live_simulation
from logic import make_trade_decision
from decision_logger import log_trade_decisions
from feedback_loop import run_feedback_loop

LEARNING_FILE = "learning_log.json"
DECISION_FILE = "decision_log.json"

def _count_json_items(path: str) -> int:
    try:
        if not os.path.exists(path): 
            return 0
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data)
        return 0
    except Exception:
        return 0

def bootstrap_learning_if_empty(target_min_entries: int = 30, max_cycles: int = 5) -> str:
    """
    Wenn learning_log.json (fast) leer ist:
      - Starte mehrere historische Simulationen
      - Starte Live-Simulation
      - Logge aktuelle Entscheidungen
      - Triggere Feedback-Lernen
    Läuft maximal `max_cycles` Runden, bis `target_min_entries` Einträge existieren.
    """
    created = 0
    cycles = 0

    while cycles < max_cycles:
        cycles += 1
        learn_cnt = _count_json_items(LEARNING_FILE)
        if learn_cnt >= target_min_entries:
            break

        # 1) Historische Simulationen (füttern das Simulation-Log, evtl. Inputs für Learning)
        for _ in range(3):
            try:
                run_simulation()
            except Exception:
                pass

        # 2) Live-Simulation (echte Preise → Variation)
        try:
            run_live_simulation()
        except Exception:
            pass

        # 3) Entscheidungen generieren & loggen
        try:
            decisions = make_trade_decision()
            log_trade_decisions(decisions)
        except Exception:
            pass

        # 4) Feedback-Lernen (schreibt ins learning_log.json)
        try:
            res = run_feedback_loop() or []
            created += len(res) if isinstance(res, list) else 0
        except Exception:
            pass

        # kurze Pause, falls irgendwas asynchron schreibt
        time.sleep(1)

    final_cnt = _count_json_items(LEARNING_FILE)
    return f"Bootstrap: {final_cnt} Lern-Einträge vorhanden (neu erzeugt: ~{created}, Zyklen: {cycles})."

def ensure_min_learning_entries(min_entries: int = 100, max_cycles: int = 10) -> str:
    """
    Regelmäßig aufrufen (z. B. im Scheduler). Füllt nach, falls unter Schwellwert.
    """
    learn_cnt = _count_json_items(LEARNING_FILE)
    if learn_cnt >= min_entries:
        return f"Lernlog OK: {learn_cnt} Einträge (>= {min_entries})."

    # sonst nachfüttern
    return bootstrap_learning_if_empty(target_min_entries=min_entries, max_cycles=max_cycles)
