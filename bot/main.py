import os
import json
import threading
import telebot
from crawler import run_crawler, get_crawler_data
from flask import Flask, request
from datetime import datetime
from scheduler import run_scheduler, get_scheduler_status
from live_logger import write_history
from simulator import run_simulation, run_live_simulation
from logic import recommend_trades, should_trigger_panic, make_trade_decision, get_learning_log
from sentiment_parser import get_sentiment_data
from indicators import calculate_indicators
from binance.client import Client
from trading import get_portfolio, get_profit_estimates
from decision_logger import log_trade_decisions
from feedback_loop import run_feedback_loop
from visualize_learning import generate_heatmap
from ghost_mode import run_ghost_mode, run_ghost_analysis, check_ghost_exit, get_ghost_performance_ranking

# === Bot Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()

if not BOT_TOKEN or not ADMIN_ID.isdigit():
    raise RuntimeError("❌ BOT_TOKEN oder ADMIN_ID nicht korrekt gesetzt!")

ADMIN_ID = int(ADMIN_ID)
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === Flask Webhook ===
@app.route('/')
def index():
    return 'OmertaTradeBot Webhook aktiv'

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# === Helper ===
def is_admin(message):
    return message.chat.id == ADMIN_ID

def safe_send(chat_id, text, **kwargs):
    try:
        bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        print(f"[Telegram] Fehler: {e}")

# === Commands ===
@bot.message_handler(commands=['start'])
def cmd_start(message):
    safe_send(message.chat.id, "👋 Willkommen beim OmertaTradeBot!")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if not is_admin(message):
        return
    safe_send(message.chat.id, "✅ Bot läuft einwandfrei.")

@bot.message_handler(commands=['portfolio'])
def cmd_portfolio(message):
    if not is_admin(message):
        return
    holdings = get_portfolio() or []
    if not holdings:
        safe_send(message.chat.id, "📭 Kein Portfolio gefunden.")
        return
    msg = "📊 Dein Portfolio:\n"
    for h in holdings:
        msg += f"{h.get('coin','?')}: {h.get('amount',0)} → {h.get('value',0)} €\n"
    safe_send(message.chat.id, msg)

@bot.message_handler(commands=['profit'])
def cmd_profit(message):
    if not is_admin(message):
        return
    profits = get_profit_estimates() or []
    if not profits:
        safe_send(message.chat.id, "📭 Keine Gewinn-/Verlustdaten gefunden.")
        return
    msg = "💰 Buchgewinne:\n"
    for p in profits:
        msg += f"{p.get('coin','?')}: {p.get('profit',0)} € ({p.get('percent',0)}%)\n"
    safe_send(message.chat.id, msg)

@bot.message_handler(commands=['simulate'])
def cmd_simulate(message):
    if not is_admin(message):
        return
    run_simulation()
    safe_send(message.chat.id, "🧪 Simulation abgeschlossen.")

@bot.message_handler(commands=['livesim'])
def cmd_livesim(message):
    if not is_admin(message):
        return
    result = run_live_simulation()
    safe_send(message.chat.id, result or "📭 Keine Daten für Live-Simulation.")

@bot.message_handler(commands=['recommend'])
def cmd_recommend(message):
    if not is_admin(message):
        return
    trades = recommend_trades() or []
    msg = "📌 Empfehlungen:\n" + "\n".join(trades) if trades else "📭 Keine Empfehlungen."
    safe_send(message.chat.id, msg)

@bot.message_handler(commands=['tradelogic'])
def cmd_tradelogic(message):
    if not is_admin(message):
        return
    logic = make_trade_decision() or []
    safe_send(message.chat.id, "🧠 Entscheidung:\n" + "\n".join(logic))

@bot.message_handler(commands=['panic'])
def cmd_panic(message):
    if not is_admin(message):
        return
    panic, coin = should_trigger_panic()
    if panic:
        safe_send(message.chat.id, f"🚨 Notbremse bei {coin} empfohlen (über -25%)!")
    else:
        safe_send(message.chat.id, "✅ Keine Notbremse notwendig.")

@bot.message_handler(commands=['sentiment'])
def cmd_sentiment(message):
    if not is_admin(message):
        return
    sentiment = get_sentiment_data() or {}
    text = f"📊 Marktstimmung: {str(sentiment.get('sentiment','')).upper()} ({sentiment.get('score',0)})\n"
    sources = sentiment.get("sources", [])
    if sources:
        text += "📚 Quellen:\n" + "\n".join([f"- {s}" for s in sources])
    safe_send(message.chat.id, text)

@bot.message_handler(commands=['crawlerstatus'])
def cmd_crawlerstatus(message):
    if not is_admin(message):
        return
    data = get_crawler_data()
    if not data:
        safe_send(message.chat.id, "📭 Keine Crawler-Daten vorhanden.")
        return

    ts = data.get("timestamp", "unbekannt")
    coins = data.get("coins", [])
    analysis = data.get("raw", {}).get("analysis", {})

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

@bot.message_handler(commands=['indicators'])
def cmd_indicators(message):
    if not is_admin(message):
        return
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
    if not is_admin(message):
        return
    try:
        path = generate_heatmap()
        with open(path, "rb") as f:
            bot.send_photo(message.chat.id, f, caption="📊 Heatmap der Lernbewertung")
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /heatmap: {e}")

@bot.message_handler(commands=['learninglog'])
def cmd_learninglog(message):
    if not is_admin(message):
        return
    log = get_learning_log()
    safe_send(message.chat.id, log or "📭 Kein Lernlog gefunden.")

@bot.message_handler(commands=['forcelearn'])
def cmd_forcelearn(message):
    if not is_admin(message):
        return
    results = run_feedback_loop() or []
    if results:
        msg = "📈 Lernbewertung:\n"
        for r in results:
            emoji = "✅" if r.get('success',0) > 0 else "❌"
            msg += f"{emoji} {r.get('coin')} ({r.get('date')}) → {r.get('success')} %\n"
        safe_send(message.chat.id, msg)
    else:
        safe_send(message.chat.id, "Keine offenen Lernbewertungen gefunden.")

@bot.message_handler(commands=['ghostmode'])
def cmd_ghostmode(message):
    if not is_admin(message):
        return
    entries = run_ghost_mode() or []
    if entries:
        msg = "⚔️ Neue Ghost Entries:\n\n" + "\n".join([f"• {e.get('coin')}: {e.get('reason')}" for e in entries])
    else:
        msg = "Keine Ghost Entries gefunden."
    safe_send(message.chat.id, msg)

@bot.message_handler(commands=['ghoststatus'])
def cmd_ghoststatus(message):
    if not is_admin(message):
        return
    exits = check_ghost_exit() or []
    if exits:
        msg = "🚪 Ghost Exits erkannt:\n\n" + "\n".join([f"• {e.get('coin')}: {e.get('success')} % (Exit: {e.get('exit_time')})" for e in exits])
    else:
        msg = "🧘 Keine aktiven Ghost Exits."
    safe_send(message.chat.id, msg)

@bot.message_handler(commands=['ghostranking'])
def cmd_ghostranking(message):
    if not is_admin(message):
        return
    ranking = get_ghost_performance_ranking() or []
    if ranking:
        msg = "👑 *Top Ghost-Träger:*\n\n" + "\n".join([f"• {r.get('coin')}: {r.get('durchschnitt')} % über {r.get('anzahl')} Trades" for r in ranking[:10]])
        safe_send(message.chat.id, msg, parse_mode="Markdown")
    else:
        safe_send(message.chat.id, "Keine abgeschlossenen Ghost-Trades.")

@bot.message_handler(commands=['schedulerstatus'])
def cmd_schedulerstatus(message):
    if not is_admin(message):
        return
    status = get_scheduler_status()
    safe_send(message.chat.id, status, parse_mode="Markdown")

@bot.message_handler(commands=['autostatus'])
def cmd_autostatus(message):
    if not is_admin(message):
        return
    try:
        portfolio = get_portfolio() or []
        profits = get_profit_estimates() or []
        sentiment = get_sentiment_data() or {}
        msg = "📊 Portfolio:\n"
        for h in portfolio:
            msg += f"• {h.get('coin')}: {h.get('amount')} → {h.get('value')} €\n"
        msg += "\n💰 Gewinne:\n"
        for p in profits:
            msg += f"{p.get('coin')}: {p.get('profit')} € ({p.get('percent')}%)\n"
        msg += f"\n📡 Sentiment: {sentiment.get('sentiment','').upper()} ({sentiment.get('score',0)})"
        safe_send(message.chat.id, msg)
    except Exception as e:
        safe_send(message.chat.id, f"❌ Fehler bei /autostatus: {e}")

@bot.message_handler(commands=['commands'])
def cmd_commands(message):
    if not is_admin(message):
        return
    text = """📜 *OmertaTradeBot — Befehlsübersicht*:

💼 *Allgemein*
/start — Bot begrüßt dich
/status — Prüft ob der Bot läuft
/autostatus — Tageszusammenfassung
/schedulerstatus — Aktive Tasks anzeigen

📈 *Trading & Analyse*
/portfolio — Zeigt dein Portfolio
/profit — Gewinn- & Verlustübersicht
/indicators — RSI, MACD, EMA, Bollinger
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

💬 *Sentiment*
/sentiment — Marktstimmung analysieren
"""
    safe_send(message.chat.id, text, parse_mode="Markdown")

# === Startup Tasks ===
def startup_tasks():
    for file in ["history.json", "ghost_log.json", "learning_log.json"]:
        if not os.path.exists(file):
            with open(file, "w") as f:
                json.dump([], f)
    write_history()
    run_simulation()
    log_trade_decisions(make_trade_decision())
    run_feedback_loop()

# === Bot starten ===
if __name__ == '__main__':
    threading.Thread(target=run_scheduler, daemon=True).start()
    threading.Thread(target=startup_tasks, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
