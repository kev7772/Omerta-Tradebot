# analyze_learning.py — Auswertung Lernlog
# Stand: 2025-08-10 (mit PDF-Export & Heatmap-Integration)

from __future__ import annotations
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple, Optional

PRIMARY_FILE = "learning_log.json"
LEGACY_FILE = "learn_log.json"

def _parse_iso(ts: str) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def _to_bool_or_percent(entry: Dict[str, Any]) -> Tuple[Optional[bool], Optional[float]]:
    if "correct" in entry:
        try:
            cb = bool(entry["correct"])
            return cb, 100.0 if cb else 0.0
        except Exception:
            pass
    if "success" in entry:
        try:
            s = entry["success"]
            if isinstance(s, bool):
                return s, 100.0 if s else 0.0
            val = float(s)
            if 0.0 <= val <= 1.0:
                return val >= 0.5, val * 100.0
            val = max(0.0, min(100.0, val))
            return val >= 50.0, val
        except Exception:
            pass
    return None, None

def _load_logs() -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    for path in (PRIMARY_FILE, LEGACY_FILE):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, list):
                data.extend(obj)
        except Exception as e:
            print(f"[Learning] Warnung: {path} konnte nicht gelesen werden: {e}")
    cleaned: List[Dict[str, Any]] = []
    for e in data:
        coin = str(e.get("coin", "")).upper().strip()
        if not coin:
            continue
        ts = e.get("timestamp") or e.get("time") or e.get("date")
        dt = _parse_iso(ts) if ts else None
        corr, succ = _to_bool_or_percent(e)
        if corr is None and succ is None:
            res = str(e.get("result", "")).lower()
            if res in ("win", "success", "correct", "true"):
                corr, succ = True, 100.0
            elif res in ("loss", "fail", "false", "wrong"):
                corr, succ = False, 0.0
        cleaned.append({
            "coin": coin,
            "timestamp": dt,
            "correct": corr if corr is not None else False,
            "success_pct": succ if succ is not None else (100.0 if corr else 0.0),
            "raw": e,
        })
    cleaned.sort(key=lambda x: x["timestamp"] or datetime.min.replace(tzinfo=timezone.utc))
    return cleaned

def _filter_timeframe(rows: List[Dict[str, Any]], days: Optional[int]) -> List[Dict[str, Any]]:
    if not days or days <= 0:
        return rows
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    return [r for r in rows if isinstance(r["timestamp"], datetime) and r["timestamp"] >= cutoff]

def compute_stats(days: Optional[int] = None) -> Dict[str, Any]:
    rows = _filter_timeframe(_load_logs(), days)
    if not rows:
        return {
            "overall": {"total": 0, "correct": 0, "wrong": 0, "accuracy_pct": 0.0},
            "by_coin": {},
            "latest": [],
        }
    total = len(rows)
    correct = sum(1 for r in rows if r["correct"])
    wrong = total - correct
    overall_acc = round(100.0 * correct / total, 2) if total else 0.0
    by_coin = defaultdict(lambda: {"total": 0, "correct": 0, "wrong": 0})
    for r in rows:
        c = r["coin"]
        by_coin[c]["total"] += 1
        if r["correct"]:
            by_coin[c]["correct"] += 1
        else:
            by_coin[c]["wrong"] += 1
    by_coin_final: Dict[str, Dict[str, Any]] = {}
    for coin, s in by_coin.items():
        acc = round(100.0 * s["correct"] / s["total"], 2) if s["total"] else 0.0
        by_coin_final[coin] = {**s, "accuracy_pct": acc}
    latest = rows[-10:]
    latest_fmt = [
        f"{i+1}. {r['coin']} — {'✅' if r['correct'] else '❌'} "
        f"{(r['timestamp'].isoformat() if r['timestamp'] else 'n/a')}"
        for i, r in enumerate(latest)
    ]
    return {
        "overall": {"total": total, "correct": correct, "wrong": wrong, "accuracy_pct": overall_acc},
        "by_coin": by_coin_final,
        "latest": latest_fmt,
    }

def generate_learning_stats(days: Optional[int] = None) -> List[str]:
    stats = compute_stats(days=days)
    if stats["overall"]["total"] == 0:
        return ["ℹ️ Noch keine Lern-Daten vorhanden."]
    lines: List[str] = []
    o = stats["overall"]
    lines.append(f"🧠 Lernstatistik (letzte {days} Tage)" if days else "🧠 Lernstatistik (gesamt)")
    lines.append(f"Gesamt: {o['total']} — ✅ {o['correct']} / ❌ {o['wrong']} — Accuracy: {o['accuracy_pct']}%")
    coins = list(stats["by_coin"].items())
    coins.sort(key=lambda kv: (kv[1]["accuracy_pct"], kv[1]["total"]), reverse=True)
    lines.append("\n🏆 Top Coins (Accuracy):")
    for coin, s in coins[:10]:
        lines.append(f"• {coin}: ✅ {s['correct']} / ❌ {s['wrong']} → {s['accuracy_pct']}% (n={s['total']})")
    if stats["latest"]:
        lines.append("\n📅 Letzte 10 Entscheidungen:")
        lines.extend(stats["latest"])
    return lines

# === Neuer Export mit PDF & Heatmap ===
def export_learning_report(days: Optional[int] = 30) -> str:
    stats = compute_stats(days=days)
    total = stats.get("overall", {}).get("total", 0)
    acc   = stats.get("overall", {}).get("accuracy_pct", 0.0)
    heatmap_path = None
    try:
        from visualize_learning import generate_heatmap
        heatmap_path = generate_heatmap()
    except Exception:
        pass
    top_coins_line = "—"
    try:
        coins = stats.get("by_coin", {})
        if coins:
            ranked = sorted(coins.items(), key=lambda kv: (kv[1].get("accuracy_pct", 0.0), kv[1].get("total", 0)), reverse=True)
            top = [f"{c}: {v.get('accuracy_pct',0):.1f}% (n={v.get('total',0)})" for c, v in ranked[:10]]
            top_coins_line = ", ".join(top) if top else "—"
    except Exception:
        pass
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S %Z")
    PDF_PATH = os.path.join(os.path.dirname(__file__), "learning_report.pdf")
    TXT_PATH = os.path.join(os.path.dirname(__file__), "learning_report.txt")
    title = "OmertaTradeBot – Learning Report"
    subtitle = f"Zeitraum: letzte {days} Tage" if days else "Zeitraum: gesamt"
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
        from reportlab.lib.utils import ImageReader
        from reportlab.lib import colors
        c = canvas.Canvas(PDF_PATH, pagesize=A4)
        w, h = A4
        y = h - 2*cm
        c.setFont("Helvetica-Bold", 16); c.drawString(2*cm, y, title); y -= 0.8*cm
        c.setFont("Helvetica", 10)
        c.drawString(2*cm, y, subtitle); y -= 0.55*cm
        c.drawString(2*cm, y, f"Erstellt: {now}"); y -= 0.9*cm
        c.setStrokeColor(colors.black); c.line(2*cm, y, w-2*cm, y); y -= 0.7*cm
        c.setFont("Helvetica", 11)
        c.drawString(2*cm, y, f"Gesamteinträge: {total}"); y -= 0.55*cm
        c.drawString(2*cm, y, f"Accuracy gesamt: {acc:.1f}%"); y -= 0.7*cm
        if heatmap_path and os.path.isfile(heatmap_path):
            try:
                img = ImageReader(heatmap_path)
                iw, ih = img.getSize()
                max_w = w - 4*cm
                scale = min(max_w/iw, 12*cm/ih)
                dw, dh = iw*scale, ih*scale
                c.drawImage(img, (w - dw)/2, y - dh, width=dw, height=dh)
                y -= dh + 0.8*cm
            except Exception:
                pass
        c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Top-Coins (Accuracy)"); y -= 0.6*cm
        c.setFont("Helvetica", 11)
        line = "• " + top_coins_line
        for chunk in [line[i:i+100] for i in range(0, len(line), 100)]:
            if y < 3*cm:
                c.showPage(); y = h - 2*cm; c.setFont("Helvetica", 11)
            c.drawString(2*cm, y, chunk); y -= 0.5*cm
        c.setFont("Helvetica-Oblique", 8)
        c.drawRightString(w-2*cm, 1.5*cm, "OmertaTradeBot – Learning Report")
        c.save()
        return PDF_PATH
    except Exception:
        with open(TXT_PATH, "w", encoding="utf-8") as f:
            f.write(f"{title}\n{subtitle}\nErstellt: {now}\n\n")
            f.write(f"Gesamteinträge: {total}\nAccuracy gesamt: {acc:.1f}%\n")
            f.write("Top-Coins: " + top_coins_line + "\n")
            if heatmap_path:
                f.write(f"(Heatmap: {heatmap_path})\n")
        return TXT_PATH

def export_learning_report_json(path: str = "learning_report.json", days: Optional[int] = 30) -> str:
    stats = compute_stats(days=days)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    return path
