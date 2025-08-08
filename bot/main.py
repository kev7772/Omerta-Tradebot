import os
import json
import threading
import telebot
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
from forecast import forecast_market
from visualize_learning import generate_heatmap
from ghost_mode import run_ghost_mode, run_ghost_analysis, check_ghost_exit, get_ghost_performance_ranking

# === Bot Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

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

@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_message(message.chat.id, "👋 Willkommen beim OmertaTradeBot!")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, "✅ Bot läuft einwandfrei.")

@bot.message_handler(commands=['portfolio'])
def cmd_portfolio(message):
    if message.chat.id != ADMIN_ID:
        return
    holdings = get_portfolio()
    msg = "📊 Dein Portfolio:\n"
    for h in holdings:
        msg += f"{h['coin']}: {h['amount']} → {h['value']} €\n"
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['profit'])
def cmd_profit(message):
    if message.chat.id != ADMIN_ID:
        return
    profits = get_profit_estimates()
    msg = "💰 Buchgewinne:\n"
    for p in profits:
        msg += f"{p['coin']}: {p['profit']} € ({p['percent']}%)\n"
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['simulate'])
def cmd_simulate(message):
    if message.chat.id != ADMIN_ID:
        return
    run_simulation()
    bot.send_message(message.chat.id, "🧪 Simulation abgeschlossen.")

@bot.message_handler(commands=['livesim'])
def cmd_livesim(message):
    if message.chat.id != ADMIN_ID:
        return
    result = run_live_simulation()
    bot.send_message(message.chat.id, result)

@bot.message_handler(commands=['recommend'])
def cmd_recommend(message):
    if message.chat.id != ADMIN_ID:
        return
    trades = recommend_trades()
    msg = "📌 Empfehlungen:\n" + "\n".join(trades)
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['tradelogic'])
def cmd_tradelogic(message):
    if message.chat.id != ADMIN_ID:
        return
    logic = make_trade_decision()
    bot.send_message(message.chat.id, "🧠 Entscheidung:\n" + "\n".join(logic))

@bot.message_handler(commands=['panic'])
def cmd_panic(message):
    if message.chat.id != ADMIN_ID:
        return
    panic, coin = should_trigger_panic()
    if panic:
        bot.send_message(message.chat.id, f"🚨 Notbremse bei {coin} empfohlen (über -25%)!")
    else:
        bot.send_message(message.chat.id, "✅ Keine Notbremse notwendig.")

@bot.message_handler(commands=['sentiment'])
def cmd_sentiment(message):
    if message.chat.id != ADMIN_ID:
        return
    sentiment = get_sentiment_data()
    text = f"📊 Marktstimmung: {sentiment['sentiment'].upper()} ({sentiment['score']})\n"
    text += "📚 Quellen:\n" + "\n".join([f"- {s}" for s in sentiment["sources"]])
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['indicators'])
def cmd_indicators(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))
        klines = client.get_klines(symbol='BTCUSDT', interval='1h', limit=100)
        import pandas as pd
        df = pd.DataFrame(klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df = df.astype(float)
        result = calculate_indicators(df)
        msg = f"📈 Technische Analyse BTCUSDT\n"
        msg += f"RSI: {result['rsi']:.2f}\n"
        msg += f"MACD: {result['macd']:.4f} | Signal: {result['macd_signal']:.4f}\n"
        msg += f"EMA20: {result['ema20']:.2f} | EMA50: {result['ema50']:.2f}\n"
        msg += f"Bollinger%: {result['bb_percent']:.2f}"
        bot.send_message(message.chat.id, msg)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Fehler bei /indicators: {e}")

@bot.message_handler(commands=['heatmap'])
def cmd_heatmap(message):
    if message.chat.id != ADMIN_ID:
        return
    path = generate_heatmap()
    with open(path, "rb") as f:
        bot.send_photo(message.chat.id, f, caption="📊 Heatmap der Lernbewertung")

@bot.message_handler(commands=['learninglog'])
def cmd_learninglog(message):
    if message.chat.id != ADMIN_ID:
        return
    log = get_learning_log()
    bot.send_message(message.chat.id, log)

@bot.message_handler(commands=['forcelearn'])
def cmd_forcelearn(message):
    if message.chat.id != ADMIN_ID:
        return
    results = run_feedback_loop()
    if results:
        msg = "📈 Lernbewertung:\n"
        for r in results:
            emoji = "✅" if r['success'] > 0 else "❌"
            msg += f"{emoji} {r['coin']} ({r['date']}) → {r['success']} %\n"
        bot.send_message(message.chat.id, msg)
    else:
        bot.send_message(message.chat.id, "Keine offenen Lernbewertungen gefunden.")

@bot.message_handler(commands=['ghostmode'])
def cmd_ghostmode(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "🧙 Ghost-Modus aktiviert.")
    entries = run_ghost_mode()
    if entries:
        msg = "⚔️ Neue Ghost Entries:\n\n"
        for e in entries:
            msg += f"• {e['coin']}: {e['reason']}\n"
        bot.send_message(message.chat.id, msg)
    else:
        bot.send_message(message.chat.id, "Keine Ghost Entries gefunden.")

@bot.message_handler(commands=['ghoststatus'])
def cmd_ghoststatus(message):
    if message.chat.id != ADMIN_ID:
        return
    exits = check_ghost_exit()
    if exits:
        msg = "🚪 Ghost Exits erkannt:\n\n"
        for e in exits:
            msg += f"• {e['coin']}: {e['success']} % (Exit: {e['exit_time']})\n"
        bot.send_message(message.chat.id, msg)
    else:
        bot.send_message(message.chat.id, "🧘 Keine aktiven Ghost Exits.")

@bot.message_handler(commands=['ghostranking'])
def cmd_ghostranking(message):
    if message.chat.id != ADMIN_ID:
        return
    ranking = get_ghost_performance_ranking()
    if ranking:
        msg = "👑 *Top Ghost-Träger:*\n\n"
        for r in ranking[:10]:
            msg += f"• {r['coin']}: {r['durchschnitt']} % über {r['anzahl']} Trades\n"
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Keine abgeschlossenen Ghost-Trades.")

@bot.message_handler(commands=['schedulerstatus'])
def cmd_schedulerstatus(message):
    if message.chat.id != ADMIN_ID:
        return
    status = get_scheduler_status()
    bot.send_message(message.chat.id, status, parse_mode="Markdown")

@bot.message_handler(commands=['autostatus'])
def cmd_autostatus(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        portfolio = get_portfolio()
        profits = get_profit_estimates()
        sentiment = get_sentiment_data()

        msg = "📊 Portfolio:\n"
        for h in portfolio:
            msg += f"• {h['coin']}: {h['amount']} → {h['value']} €\n"

        msg += "\n💰 Gewinne:\n"
        for p in profits:
            msg += f"{p['coin']}: {p['profit']} € ({p['percent']}%)\n"

        msg += f"\n📡 Sentiment: {sentiment['sentiment'].upper()} ({sentiment['score']})"
        bot.send_message(message.chat.id, msg)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Fehler bei /autostatus: {e}")

@bot.message_handler(commands=['commands'])
def cmd_commands(message):
    if message.chat.id != ADMIN_ID:
        return
    text = """
📜 *OmertaTradeBot — Befehlsübersicht*:

💼 *Allgemein*
/start — Bot begrüßt dich
/status — Prüft ob der Bot läuft
/autostatus — Tageszusammenfassung
/schedulerstatus — Aktive Tasks anzeigen

📈 *Trading & Analyse*
/portfolio — Zeigt dein Portfolio
/profit — Gewinn- & Verlustübersicht
/indicators — RSI, MACD, EMA, Bollinger
/forecast — Marktprognose
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

💬 *Sentiment & Crawler*
/sentiment — Marktstimmung analysieren

"""
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# === Startup Tasks ===
def startup_tasks():
    for file in ["history.json", "ghost_log.json", "learning_log.json"]:
        if not os.path.exists(file):
            with open(file, "w") as f:
                json.dump([], f)

    print("🕒 Preise loggen...")
    write_history()
    print("🧠 Simulation starten...")
    run_simulation()
    print("📋 Entscheidungen loggen...")
    log_trade_decisions(make_trade_decision())
    print("🔁 Feedback-Learning starten...")
    run_feedback_loop()

# === Bot starten ===
if __name__ == '__main__':
    threading.Thread(target=run_scheduler).start()
    startup_tasks()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
