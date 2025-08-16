# main.py — OmertaTradeBot (clean + live_logger integriert)
# Stand: 2025-08-10  (EUR- & Prozent-Formatierung integriert)

import os
import json
import threading
import telebot
from flask import Flask, request
from datetime import datetime

# === Imports aus deinem Projekt ===
from train_ki_model import train_model
from analyze_learning import generate_learning_stats, export_learning_report
from scheduler import run_scheduler, get_scheduler_status
from live_logger import write_history, load_history_safe
from simulator import run_simulation, run_live_simulation
from logic import (
    recommend_trades,
    should_trigger_panic,
    make_trade_decision,
    get_learning_log
)
from bootstrap_learning import bootstrap_learning_if_empty
from sentiment_parser import get_sentiment_data
from indicators import calculate_indicators
from binance.client import Client
from trading import get_portfolio, get_profit_estimates
from decision_logger import log_trade_decisions
from feedback_loop import run_feedback_loop
from visualize_learning import generate_heatmap
from ghost_mode import (
    run_ghost_mode,
    run_ghost_analysis,
    check_ghost_exit,
    get_ghost_performance_ranking
)
from crawler import run_crawler, get_crawler_data   # <— wichtig: nur hier importieren

# === Bot Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
if not BOT_TOKEN or not ADMIN_ID.isdigit():
    raise RuntimeError("❌ BOT_TOKEN oder ADMIN_ID nicht korrekt gesetzt!")
ADMIN_ID = int(ADMIN_ID)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === Format-Helper (NEU) ===
def _to_float(x) -> float:
    try:
        # Strings wie "12.34" oder Decimal etc. robust in float wandeln
        return float(x)
    except Exception:
        return 0.0

def fmt_eur(x) -> str:
    """Immer 2 Nachkommastellen + Euro-Symbol."""
    return f"{_to_float(x):.2f} €"

def fmt_pct(x) -> str:
    """Immer 2 Nachkommastellen + Prozentzeichen."""
    return f"{_to_float(x):.2f}%"

def fmt_amt(x, max_decimals: int = 8) -> str:
    """
    Für Coin-Mengen: bis zu 8 Nachkommastellen, ohne überflüssige Nullen.
    Beispiel: 135.2441175 -> '135.2441175', 0.22000000 -> '0.22'
    """
    s = f"{_to_float(x):.{max_decimals}f}"
    s = s.rstrip("0").rstrip(".")
    return s if s else "0"

# === Flask Webhook (wie in deiner alten Main) ===
@app.route('/')
def index():
    return 'OmertaTradeBot Webhook aktiv'

# Webhook-Endpunkt bleibt /{BOT_TOKEN}
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# === Helper ===
def is_admin(message):
    try:
        return message.chat and message.chat.id == ADMIN_ID
    except Exception:
        return False

def safe_send(chat_id, text, **kwargs):
    try:
        bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        print(f"[Telegram] Fehler: {e}")

# ========= Live-Logger Helpers (neu) =========
def log_market_snapshot_from_estimates():
    """
    Baut prices_input aus get_profit_estimates().
    Erwartet Einträge wie {"coin":"BTC","price":...}. Falls kein 'price' vorhanden,
    wird der Coin ignoriert (wir loggen nur echte Preise).
    """
    estimates = get_profit_estimates() or []
    prices_input = []
    for e in estimates:
        coin = e.get("coin")
        price = e.get("price")
        if coin and isinstance(price, (int, float)):
            prices_input.append({"coin": str(coin), "price": float(price)})

    if not prices_input:
        print("[Logger] Keine validen Preise in get_profit_estimates() gefunden.")
        return 0

    return write_history(prices_input)

def log_market_snapshot_from_binance(symbols=("BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT")):
    """
    Holt Spot-Preise direkt von Binance und schreibt sie in die history.json.
    """
    try:
        client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))
        prices_input = []
        for sym in symbols:
            t = client.get_symbol_ticker(symbol=sym)
            coin = sym.replace("USDT", "")
            price = float(t["price"])
            prices_input.append({"coin": coin, "price": price})
        return write_history(prices_input)
    except Exception as e:
        print(f"[Logger] Binance Snapshot Fehler: {e}")
        return 0

# ========= Commands =========

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if not is_admin(message): return
    safe_send(message.chat.id, "👋 Willkommen beim OmertaTradeBot!\nNutze /commands für die Übersicht.")

@bot.message_handler(commands=['commands'])
def cmd_commands(message):
    if not is_admin(message): return
    text = """📜 *OmertaTradeBot — Befehlsübersicht*:

💼 *Allgemein*
/start — Bot begrüßt dich
/status — Prüft ob der Bot läuft
/autostatus — Tageszusammenfassung
/schedulerstatus — Aktive Tasks anzeigen
/crawlerstatus — Letzte Crawler-Analyse
/crawler — Crawler jetzt starten

📈 *Trading & Analyse*
/portfolio — Zeigt dein Portfolio
/profit — Gewinn- & Verlustübersicht
/indicators — RSI, MACD, EMA, Bollinger (BTCUSDT live)
/recommend — Trading-Empfehlungen
/tradelogic — Entscheidungssimulation
/panic — Notbremsenprüfung

🧠 *Lernen*
/learninglog — Lernstatistik anzeigen
/forcelearn — Feedback-Learning starten
/heatmap — Fehleranalyse als Heatmap

🧪 *Simulation*
/simulate — Backtest starten
/livesim — Live-Simulation

👻 *Ghost Mode*
/ghostmode — Scannt neue Ghost Entries
/ghoststatus — Überwacht Ghost Exits
/ghostranking — Top Coins im Ghost-Modus
/ghostexit — (Alias) Exit-Check

📝 *Logging*
/logsnapshot — Markt-Snapshot aus Estimates loggen
/logbinance — Markt-Snapshot direkt von Binance loggen

🛵 *KI Being*
/kistatus - Aufrufen des KI Status
"""
    safe_send(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if not is_admin(message): return
    safe_send(message.chat.id, "✅ Bot läuft einwandfrei.")

@bot.message_handler(commands=['portfolio'])
def cmd_portfolio(message):
    if not is_admin(message): return
    try:
        holdings = get_portfolio() or []
        if not holdings:
            safe_send(message.chat.id, "📭 Kein Portfolio gefunden.")
            return
        msg = "📊 Dein Portfolio:\n"
        for h in holdings:
            coin = h.get('coin', '?')
            amount = fmt_amt(h.get('amount', 0))
            value_eur = fmt_eur(h.get('value', 0))
            msg += f"{coin}: {amount} → {value_eur}\n"
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /portfolio: {e}")

@bot.message_handler(commands=['profit'])
def cmd_profit(message):
    if not is_admin(message): return
    try:
        profits = get_profit_estimates() or []
        if not profits:
            safe_send(message.chat.id, "📭 Keine Gewinn-/Verlustdaten gefunden.")
            return
        msg = "💰 Buchgewinne:\n"
        for p in profits:
            coin = p.get('coin', '?')
            profit_eur = fmt_eur(p.get('profit', 0))
            percent = fmt_pct(p.get('percent', 0))
            msg += f"{coin}: {profit_eur} ({percent})\n"
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /profit: {e}")

@bot.message_handler(commands=['simulate'])
def cmd_simulate(message):
    if not is_admin(message): return
    try:
        run_simulation()
        safe_send(message.chat.id, "🧪 Simulation abgeschlossen.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /simulate: {e}")

@bot.message_handler(commands=['livesim'])
def cmd_livesim(message):
    if not is_admin(message): return
    try:
        result = run_live_simulation()
        safe_send(message.chat.id, result or "📭 Keine Daten für Live-Simulation.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /livesim: {e}")

@bot.message_handler(commands=['recommend'])
def cmd_recommend(message):
    if not is_admin(message): return
    try:
        trades = recommend_trades() or []
        msg = "📌 Empfehlungen:\n" + "\n".join(trades) if trades else "📭 Keine Empfehlungen."
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /recommend: {e}")

@bot.message_handler(commands=['learningstats'])
def cmd_learningstats(message):
    if not is_admin(message): return
    try:
        lines = generate_learning_stats(days=30)  # z. B. letzte 30 Tage
        safe_send(message.chat.id, "\n".join(lines))
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /learningstats: {e}")

@bot.message_handler(commands=['tradelogic'])
def cmd_tradelogic(message):
    if not is_admin(message): return
    try:
        logic = make_trade_decision() or []
        if isinstance(logic, dict):
            safe_send(message.chat.id, "🧠 Entscheidung:\n" + json.dumps(logic, ensure_ascii=False, indent=2))
        else:
            safe_send(message.chat.id, "🧠 Entscheidung:\n" + "\n".join(logic))
        try:
            log_trade_decisions(logic)
        except Exception:
            pass
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /tradelogic: {e}")

@bot.message_handler(commands=['panic'])
def cmd_panic(message):
    if not is_admin(message): return
    try:
        res = should_trigger_panic()
        if isinstance(res, tuple) and len(res) >= 2:
            panic, coin = res[0], res[1]
        elif isinstance(res, dict):
            panic, coin = res.get("panic", False), res.get("coin", "?")
        else:
            panic, coin = False, "?"
        safe_send(message.chat.id, f"🚨 Notbremse bei {coin} empfohlen (über -25%)!" if panic else "✅ Keine Notbremse notwendig.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /panic: {e}")

@bot.message_handler(commands=['sentiment'])
def cmd_sentiment(message):
    if not is_admin(message): return
    try:
        sentiment = get_sentiment_data() or {}
        text = f"📡 *Marktstimmung:* {str(sentiment.get('sentiment','')).upper()} ({sentiment.get('score',0)})\n"
        sources = sentiment.get("sources", [])
        if sources:
            text += "📚 *Quellen:*\n" + "\n".join([f"- {s}" for s in sources])
        safe_send(message.chat.id, text, parse_mode="Markdown")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /sentiment: {e}")

@bot.message_handler(commands=['indicators'])
def cmd_indicators(message):
    if not is_admin(message): return
    try:
        client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))
        klines = client.get_klines(symbol='BTCUSDT', interval='1h', limit=100)
        import pandas as pd
        df = pd.DataFrame(klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ]).astype(float)
        result = calculate_indicators(df)
        msg = (
            f"📈 Technische Analyse BTCUSDT\n"
            f"RSI: {result.get('rsi',0):.2f}\n"
            f"MACD: {result.get('macd',0):.4f} | Signal: {result.get('macd_signal',0):.4f}\n"
            f"EMA20: {result.get('ema20',0):.2f} | EMA50: {result.get('ema50',0):.2f}\n"
            f"Bollinger%: {result.get('bb_percent',0):.2f}"
        )
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /indicators: {e}")

@bot.message_handler(commands=['heatmap'])
def cmd_heatmap(message):
    if not is_admin(message): return
    try:
        path = generate_heatmap()
        if path and os.path.isfile(path):
            with open(path, "rb") as f:
                bot.send_photo(message.chat.id, f, caption="📊 Heatmap der Lernbewertung")
        else:
            safe_send(message.chat.id, "📭 Keine Heatmap erzeugt.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /heatmap: {e}")

@bot.message_handler(commands=['learninglog'])
def cmd_learninglog(message):
    if not is_admin(message): return
    try:
        log = get_learning_log()
        if isinstance(log, (dict, list)):
            safe_send(message.chat.id, json.dumps(log, ensure_ascii=False, indent=2))
        else:
            safe_send(message.chat.id, log or "📭 Kein Lernlog gefunden.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /learninglog: {e}")

@bot.message_handler(commands=['forcelearn'])
def cmd_forcelearn(message):
    if not is_admin(message): return
    try:
        results = run_feedback_loop() or []
        if isinstance(results, list) and results:
            msg = "📈 Lernbewertung:\n"
            for r in results:
                emoji = "✅" if r.get('success',0) > 0 else "❌"
                msg += f"{emoji} {r.get('coin')} ({r.get('date')}) → {r.get('success')} %\n"
            safe_send(message.chat.id, msg)
        else:
            safe_send(message.chat.id, "Keine offenen Lernbewertungen gefunden.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /forcelearn: {e}")

@bot.message_handler(commands=['ghostmode'])
def cmd_ghostmode(message):
    if not is_admin(message): return
    try:
        entries = run_ghost_mode() or []
        if entries and isinstance(entries, list):
            msg = "⚔️ Neue Ghost Entries:\n\n" + "\n".join([f"• {e.get('coin')}: {e.get('reason')}" for e in entries])
        else:
            msg = "Keine Ghost Entries gefunden."
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /ghostmode: {e}")

@bot.message_handler(commands=['ghoststatus'])
def cmd_ghoststatus(message):
    if not is_admin(message): return
    try:
        exits = check_ghost_exit() or []
        if exits and isinstance(exits, list):
            msg = "🚪 Ghost Exits erkannt:\n\n" + "\n".join([f"• {e.get('coin')}: {e.get('success')} % (Exit: {e.get('exit_time')})" for e in exits])
        else:
            msg = "🧘 Keine aktiven Ghost Exits."
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /ghoststatus: {e}")

@bot.message_handler(commands=['ghostranking'])
def cmd_ghostranking(message):
    if not is_admin(message): return
    try:
        ranking = get_ghost_performance_ranking() or []
        if ranking:
            # Prozent hübsch formatieren
            lines = []
            for r in ranking[:10]:
                coin = r.get('coin')
                avg = fmt_pct(r.get('durchschnitt', 0))
                n = r.get('anzahl')
                lines.append(f"• {coin}: {avg} über {n} Trades")
            msg = "👑 *Top Ghost-Träger:*\n\n" + "\n".join(lines)
            safe_send(message.chat.id, msg, parse_mode="Markdown")
        else:
            safe_send(message.chat.id, "Keine abgeschlossenen Ghost-Trades.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /ghostranking: {e}")

@bot.message_handler(commands=['ghostexit'])
def cmd_ghostexit(message):
    if not is_admin(message): return
    try:
        exits = check_ghost_exit() or []
        if exits:
            msg = "🚪 Ghost Exit-Check:\n\n" + "\n".join([f"• {e.get('coin')}: {e.get('success')} % (Exit: {e.get('exit_time')})" for e in exits])
        else:
            msg = "Keine Exits."
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /ghostexit: {e}")

@bot.message_handler(commands=['kistatus'])
def cmd_kistatus(msg):
    import json, os
    from pathlib import Path
    METRICS_PATH = Path("models/ki_metrics.json")
    if not METRICS_PATH.exists():
        # Auto-Placeholder erzeugen
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        placeholder = {
            "n_samples": 0,
            "auc": None,
            "accuracy": 0.0,
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "Auto-Placeholder – bitte /kitrain ausführen."
        }
        with open(METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(placeholder, f, ensure_ascii=False, indent=2)

    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        m = json.load(f)
    bot.reply_to(
        msg,
        "🤖 KI-Status\n"
        f"Samples: {m.get('n_samples')}\n"
        f"AUC: {m.get('auc')}\n"
        f"Accuracy: {m.get('accuracy')}\n"
        f"Train: {m.get('trained_at')}"
        + (f"\nHinweis: {m.get('note')}" if m.get('note') else "")

@bot.message_handler(commands=['crawler'])
def cmd_crawler(message):
    if not is_admin(message): return
    try:
        res = run_crawler()
        safe_send(message.chat.id, f"🕷 Crawler gestartet:\n{json.dumps(res, ensure_ascii=False, indent=2)}")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /crawler: {e}")

@bot.message_handler(commands=['crawlerstatus'])
def cmd_crawlerstatus(message):
    if not is_admin(message): return
    try:
        data = get_crawler_data()
        if not data:
            safe_send(message.chat.id, "📭 Keine Crawler-Daten vorhanden.")
            return
        ts = data.get("timestamp", "unbekannt")
        coins = data.get("coins", [])
        analysis = (data.get("raw") or {}).get("analysis", {})
        msg = f"📡 *Crawler Status*\n⏱ Letzter Lauf: {ts}\n"
        msg += f"📊 Sentiment: {analysis.get('sentiment','?')} (Score: {analysis.get('score',0)})\n\n"
        if coins:
            msg += "💠 Top Coins nach Trend:\n"
            for c in coins:
                msg += f"• {c.get('coin')} — Mentions: {c.get('mentions')} | Trend: {c.get('trend_score')}\n"
        else:
            msg += "Keine Coin-Trends gefunden."
        signals = analysis.get("signals", [])
        if signals:
            msg += "\n🚨 Signale:\n" + "\n".join(signals)
        safe_send(message.chat.id, msg, parse_mode="Markdown")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /crawlerstatus: {e}")

@bot.message_handler(commands=['schedulerstatus'])
def cmd_schedulerstatus(message):
    if not is_admin(message): return
    try:
        status = get_scheduler_status()
        if isinstance(status, dict):
            safe_send(message.chat.id, json.dumps(status, ensure_ascii=False, indent=2))
        else:
            safe_send(message.chat.id, str(status))
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /schedulerstatus: {e}")

@bot.message_handler(commands=['autostatus'])
def cmd_autostatus(message):
    if not is_admin(message): return
    try:
        portfolio = get_portfolio() or []
        profits = get_profit_estimates() or []
        sentiment = get_sentiment_data() or {}

        msg = "📊 Autostatus — Portfolio:\n"
        for h in portfolio:
            coin = h.get('coin', '?')
            amount = fmt_amt(h.get('amount', 0))
            value_eur = fmt_eur(h.get('value', 0))
            msg += f"{coin}: {amount} → {value_eur}\n"

        msg += "\n💰 Gewinne:\n"
        for p in profits:
            coin = p.get('coin', '?')
            profit_eur = fmt_eur(p.get('profit', 0))
            percent = fmt_pct(p.get('percent', 0))
            msg += f"{coin}: {profit_eur} ({percent})\n"

        msg += f"\n📡 Sentiment: {str(sentiment.get('sentiment','')).upper()} ({sentiment.get('score',0)})"
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /autostatus: {e}")

# === Logging Commands (neu) ===
@bot.message_handler(commands=['logsnapshot'])
def cmd_logsnap(message):
    if not is_admin(message): return
    try:
        n = log_market_snapshot_from_estimates()
        safe_send(message.chat.id, f"📝 Snapshot geloggt: {n} Einträge.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /logsnapshot: {e}")

@bot.message_handler(commands=['logbinance'])
def cmd_logbinance(message):
    if not is_admin(message): return
    try:
        n = log_market_snapshot_from_binance()
        safe_send(message.chat.id, f"📝 Binance-Snapshot geloggt: {n} Einträge.")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /logbinance: {e}")

@bot.message_handler(commands=['kitrain'])
def cmd_kitrain(message):
    if not is_admin(message): return
    try:
        metrics = train_model()
        txt = "🤖 KI neu trainiert:\n"
        txt += f"• Samples: {metrics.get('n_samples')}\n"
        txt += f"• Accuracy: {metrics.get('accuracy')}\n"
        auc = metrics.get('auc')
        txt += f"• AUC: {auc if auc is not None else 'n/a'}\n"
        if metrics.get("note"):
            txt += f"• Hinweis: {metrics['note']}\n"
        txt += f"• Stand: {metrics.get('trained_at')}"
        safe_send(message.chat.id, txt)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /kitrain: {e}")

@bot.message_handler(commands=['selftest'])
def cmd_selftest(message):
    if not is_admin(message): return
    try:
        checks = []

        # Env & Bot
        checks.append(f"BOT_TOKEN gesetzt: {'✅' if os.getenv('BOT_TOKEN') else '❌'}")
        checks.append(f"ADMIN_ID gesetzt: {'✅' if os.getenv('ADMIN_ID') else '❌'}")

        # Dateien
        files = ["history.json", "learning_log.json", "ghost_log.json", "crawler_data.json"]
        for f in files:
            exists = os.path.exists(f)
            size = os.path.getsize(f) if exists else 0
            checks.append(f"{f}: {'✅' if exists else '❌'} ({size} B)")

        # Kernfunktionen (sanft)
        ok_portfolio = False
        try:
            p = get_portfolio() or []
            ok_portfolio = isinstance(p, list)
        except Exception:
            pass
        checks.append(f"get_portfolio(): {'✅' if ok_portfolio else '❌'}")

        ok_profit = False
        try:
            pe = get_profit_estimates() or []
            ok_profit = isinstance(pe, list)
        except Exception:
            pass
        checks.append(f"get_profit_estimates(): {'✅' if ok_profit else '❌'}")

        ok_sent = False
        try:
            s = get_sentiment_data()
            ok_sent = s is not None
        except Exception:
            pass
        checks.append(f"get_sentiment_data(): {'✅' if ok_sent else '❌'}")

        # Scheduler Status
        try:
            status = get_scheduler_status()
            checks.append("Scheduler: ✅" if status else "Scheduler: ❌")
        except Exception:
            checks.append("Scheduler: ❌")

        # Ergebnis senden
        safe_send(message.chat.id, "🧪 *Selftest*\n" + "\n".join("• " + c for c in checks), parse_mode="Markdown")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /selftest: {e}")

# === Startup Tasks (asynchron) ===
def startup_tasks():
    # Dateien anlegen, falls nicht vorhanden
    try:
        ensure_files = {
            "history.json": [],
            "ghost_log.json": [],
            "learning_log.json": [],
            "crawler_data.json": {}   # für Crawler strukturierter
        }
        for path, default in ensure_files.items():
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Startup] Datei-Init Fehler: {e}")

    # Initiale Logs/Analysen
    wrote = 0
    try:
        wrote = log_market_snapshot_from_estimates() or 0
    except Exception as e:
        print(f"[Startup] Estimates Snapshot Fehler: {e}")

    if wrote == 0:
        try:
            log_market_snapshot_from_binance()
        except Exception as e:
            print(f"[Startup] Binance Snapshot Fehler: {e}")

    # Restliche Startprozesse
    try:
        run_simulation()
    except Exception as e:
        print(f"[Startup] run_simulation Fehler: {e}")

    try:
        log_trade_decisions(make_trade_decision())
    except Exception as e:
        print(f"[Startup] decision_log Fehler: {e}")

    try:
        run_feedback_loop()
    except Exception as e:
        print(f"[Startup] feedback_loop Fehler: {e}")

    try:
        run_crawler()  # einmal initial
    except Exception as e:
        print(f"[Startup] run_crawler Fehler: {e}")

# === Start ===
if __name__ == '__main__':
    # Scheduler im Hintergrund starten
    try:
        threading.Thread(target=run_scheduler, daemon=True).start()
        print("[OK] Scheduler gestartet.")
    except Exception as e:
        print(f"[ERR] Scheduler-Start: {e}")

    # Startup-Jobs im Hintergrund
    threading.Thread(target=startup_tasks, daemon=True).start()

    # Flask starten (Webhook-Modus)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

    # --- Lernlog automatisch füttern, falls leer ---
    try:
        msg = bootstrap_learning_if_empty(target_min_entries=30, max_cycles=5)
        print("[Startup]", msg)
    except Exception as e:
        print(f"[Startup] Bootstrap Learning Fehler: {e}")
