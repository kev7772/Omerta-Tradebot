# visualize_learning.py
# — OmertaTradeBot: Lern-Erfolg visualisieren (Heatmap) —
# Matplotlib-only (kein seaborn), robustes JSON-Parsing, Value-Labels, Zusammenfassungstext.

import os
import json
from typing import List, Dict, Tuple, Optional
import math

import pandas as pd
import matplotlib.pyplot as plt


LEARNING_LOG_FILE = os.path.join(os.path.dirname(__file__), "learning_log.json")
HEATMAP_FILE = os.path.join(os.path.dirname(__file__), "heatmap.png")


def _load_learning_log(path: str) -> List[dict]:
    if not os.path.exists(path):
        print("❌ Lernlog-Datei fehlt.")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            print("⚠️ Lernlog-Format unerwartet (kein Array).")
            return []
        return data
    except json.JSONDecodeError:
        print("⚠️ Fehler beim Lesen der JSON-Datei.")
        return []
    except Exception as e:
        print(f"⚠️ Unerwarteter Fehler beim Laden: {e}")
        return []


def _coerce_success(x) -> Optional[float]:
    try:
        # Akzeptiere 0/1, 0..100, Strings mit Prozent etc.
        if isinstance(x, str):
            x = x.strip().replace("%", "")
        val = float(x)
        return val
    except Exception:
        return None


def _prepare_dataframe(rows: List[dict]) -> Optional[pd.DataFrame]:
    """
    Erwartet pro Eintrag min.:
      - coin (str)
      - indicator (str)
      - success (float 0..100)
    """
    if not rows:
        return None

    cleaned = []
    for r in rows:
        coin = r.get("coin")
        ind = r.get("indicator") or r.get("indicator_name") or r.get("metric")
        suc = _coerce_success(r.get("success") or r.get("success_rate"))
        if not coin or not ind or suc is None:
            continue
        cleaned.append({"coin": str(coin), "indicator": str(ind), "success": float(suc)})

    if not cleaned:
        return None

    df = pd.DataFrame(cleaned)
    return df if set(["coin", "indicator", "success"]).issubset(df.columns) else None


def _make_pivot(df: pd.DataFrame) -> pd.DataFrame:
    # Mittelwert je Coin x Indikator
    pivot = df.pivot_table(index="coin", columns="indicator", values="success", aggfunc="mean")
    # Sortierung: Coins nach Gesamt-Mean, Indikatoren nach Gesamt-Mean
    pivot = pivot.reindex(pivot.mean(axis=1).sort_values(ascending=False).index)
    pivot = pivot.loc[:, pivot.mean(axis=0).sort_values(ascending=False).index]
    return pivot


def _annotate_cells(ax, data_2d):
    n_rows, n_cols = data_2d.shape
    for i in range(n_rows):
        for j in range(n_cols):
            val = data_2d[i, j]
            if math.isnan(val):
                txt = "—"
                color = "black"
            else:
                txt = f"{val:.1f}"
                # Kontrast grob wählen
                color = "white" if val >= (data_2d[~pd.isna(data_2d)].mean() if (~pd.isna(data_2d)).any() else 50) else "black"
            ax.text(j, i, txt, ha="center", va="center", fontsize=9, color=color)


def generate_heatmap(save_path: str = HEATMAP_FILE) -> Optional[str]:
    """
    Erzeugt eine Heatmap 'Coin vs Indikator' mit durchschnittlicher Erfolgsrate (0..100 %).
    Speichert PNG und gibt Pfad zurück, oder None bei Fehler.
    """
    rows = _load_learning_log(LEARNING_LOG_FILE)
    if not rows:
        return None

    df = _prepare_dataframe(rows)
    if df is None or df.empty:
        print("⚠️ Keine verwertbaren Einträge im Lernlog.")
        return None

    pivot = _make_pivot(df)
    if pivot.empty:
        print("⚠️ Pivot leer (evtl. nur ein Coin oder ein Indikator vorhanden).")
        return None

    # Plot
    fig, ax = plt.subplots(figsize=(max(8, 0.7 * pivot.shape[1] + 3), max(6, 0.5 * pivot.shape[0] + 2)))
    # Standard-Cmap von Matplotlib (keine externen Styles nötig)
    im = ax.imshow(pivot.values, aspect="auto")

    # Achsen-Beschriftungen
    ax.set_xticks(range(pivot.shape[1]))
    ax.set_yticks(range(pivot.shape[0]))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticklabels(pivot.index)

    ax.set_xlabel("Indikator")
    ax.set_ylabel("Coin")
    ax.set_title("📊 Erfolgs-Heatmap: Coin vs. Indikator (Ø Erfolgsrate)")

    # Farbskala
    cbar = plt.colorbar(im, ax=ax)
    cbar.ax.set_ylabel("Erfolg (%)", rotation=270, labelpad=15)

    # Werte in Zellen annotieren
    _annotate_cells(ax, pivot.values)

    plt.tight_layout()
    try:
        plt.savefig(save_path, dpi=150)
        plt.close(fig)
        print(f"✅ Heatmap gespeichert unter: {save_path}")
        return save_path
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Heatmap: {e}")
        plt.close(fig)
        return None


def generate_heatmap_summary_text(top_n: int = 5) -> str:
    """
    Liefert einen kurzen Text für Telegram:
      - Top-Coins nach Ø Erfolg
      - Top-Indikatoren nach Ø Erfolg
    """
    rows = _load_learning_log(LEARNING_LOG_FILE)
    if not rows:
        return "❌ Kein Lernlog vorhanden."

    df = _prepare_dataframe(rows)
    if df is None or df.empty:
        return "⚠️ Kein auswertbarer Lernlog."

    coin_rank = df.groupby("coin")["success"].mean().sort_values(ascending=False).head(top_n)
    ind_rank = df.groupby("indicator")["success"].mean().sort_values(ascending=False).head(top_n)

    msg = "📘 Lern-Overview\n"
    if not coin_rank.empty:
        msg += "🥇 Top-Coins (Ø %): " + ", ".join([f"{c}: {v:.1f}" for c, v in coin_rank.items()]) + "\n"
    if not ind_rank.empty:
        msg += "🧭 Top-Indikatoren (Ø %): " + ", ".join([f"{i}: {v:.1f}" for i, v in ind_rank.items()]) + "\n"
    return msg.strip()


if __name__ == "__main__":
    # Für lokalen Testlauf
    generate_heatmap()
    print(generate_heatmap_summary_text())
