import os
import json
import threading
import telebot
from flask import Flask, request
from live_logger import write_history
from simulator import run_simulation, run_live_simulation
from logic import recommend_trades, should_trigger_panic, make_trade_decision, get_learning_log
from sentiment_parser import get_sentiment_data
from indicators import calculate_indicators
from binance.client import Client
from trading import get_portfolio, get_profit_estimates
from scheduler import run_scheduler
from decision_logger import log_trade_decisions
from feedback_loop import run_feedback_loop
from forecast import forecast_market
from visualize_learning import generate_heatmap
from feedback_loop import run_feedback_loop
from ghost_mode import run_ghost_mode

# === Bot Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === Flask Webhook ===
@app.route('/')
def index():
    return 'OmertaTradeBot Webhook aktiv'

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# === Telegram Commands ===
@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_message(message.chat.id, "👋 Willkommen beim OmertaTradeBot!")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Bot läuft ✅")

@bot.message_handler(commands=['enable_trading'])
def enable_trading(message):
    global ALLOW_TRADING
    if message.chat.id != ADMIN_ID:
        return
    ALLOW_TRADING = True
    bot.send_message(message.chat.id, "✅ Trading-Funktion aktiviert!")

@bot.message_handler(commands=['disable_trading'])
def disable_trading(message):
    global ALLOW_TRADING
    if message.chat.id != ADMIN_ID:
        return
    ALLOW_TRADING = False
    bot.send_message(message.chat.id, "🔒 Trading-Funktion deaktiviert!")

@bot.message_handler(commands=['portfolio'])
def cmd_portfolio(message):
    if message.chat.id != ADMIN_ID:
        return
    holdings = get_portfolio()
    text = "📊 Dein Portfolio:\n"
    for h in holdings:
        text += f"{h['coin']}: {h['amount']} → {h['value']} €\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['profit'])
def cmd_profit(message):
    if message.chat.id != ADMIN_ID:
        return
    profits = get_profit_estimates()
    text = "💰 Buchgewinne:\n"
    for p in profits:
        text += f"{p['coin']}: {p['profit']} € ({p['percent']}%)\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['panic'])
def cmd_panic(message):
    if message.chat.id != ADMIN_ID:
        return
    trigger, coin = should_trigger_panic()
    if trigger:
        bot.send_message(message.chat.id, f"⚠️ Notbremse empfohlen bei {coin} (über -25%)!")
    else:
        bot.send_message(message.chat.id, "✅ Keine Notbremse nötig.")

@bot.message_handler(commands=['tradelogic'])
def cmd_tradelogic(message):
    if message.chat.id != ADMIN_ID:
        return
    actions = make_trade_decision()
    text = "🤖 Simulation:\n" + "\n".join(actions)
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['loghistory'])
def cmd_loghistory(message):
    if message.chat.id != ADMIN_ID:
        return
    write_history()
    bot.send_message(message.chat.id, "📊 History gespeichert.")

@bot.message_handler(commands=['simulate'])
def cmd_simulate(message):
    if message.chat.id != ADMIN_ID:
        return
    run_simulation()
    bot.send_message(message.chat.id, "🧪 Simulation abgeschlossen.")

@bot.message_handler(commands=['livesimulate'])
def handle_livesim(message):
    if message.chat.id != ADMIN_ID:
        return
    response = run_live_simulation()
    bot.reply_to(message, response)

@bot.message_handler(commands=['recommend'])
def cmd_recommend(message):
    if message.chat.id != ADMIN_ID:
        return
    recs = recommend_trades()
    text = "📌 Empfehlungen:\n" + "\n".join(recs)
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['sentiment'])
def cmd_sentiment(message):
    if message.chat.id != ADMIN_ID:
        return
    data = get_sentiment_data()
    text = f"📊 Marktstimmung: {data['sentiment'].upper()}\n"
    text += f"🔥 Stimmungsscore: {data['score']}\n\n"
    text += "📡 Quellen:\n" + "\n".join([f"- {s}" for s in data["sources"]])
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['indicators'])
def cmd_indicators(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        API_KEY = os.getenv("BINANCE_API_KEY")
        API_SECRET = os.getenv("BINANCE_API_SECRET")
        client = Client(API_KEY, API_SECRET)

        klines = client.get_klines(symbol='BTCUSDT', interval='1h', limit=100)
        import pandas as pd
        df = pd.DataFrame(klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df = df.astype(float)

        result = calculate_indicators(df)

        text = f"🧠 Technische Analyse BTCUSDT\n"
        text += f"RSI: {result['rsi']:.2f}\n"
        text += f"MACD: {result['macd']:.4f} | Signal: {result['macd_signal']:.4f}\n"
        text += f"EMA20: {result['ema20']:.2f} | EMA50: {result['ema50']:.2f}\n"
        text += f"Bollinger%: {result['bb_percent']:.2f}"

        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Fehler bei /indicators:\n{str(e)}")

@bot.message_handler(commands=['forecast'])
def cmd_forecast(message):
    if message.chat.id != ADMIN_ID:
        return
    lines = forecast_market()
    bot.send_message(message.chat.id, "🔮 Marktprognose:\n" + "\n".join(lines))

@bot.message_handler(commands=['heatmap'])
def cmd_heatmap(message):
    if message.chat.id != ADMIN_ID:
        return
    path = generate_heatmap()
    with open(path, "rb") as f:
        bot.send_photo(message.chat.id, f, caption="Lern-Heatmap (Coin-Erfolgsquote)")

@bot.message_handler(commands=['learninglog'])
def handle_learninglog(message):
    if message.chat.id != ADMIN_ID:
        return
    log = get_learning_log()
    bot.reply_to(message, log)

@bot.message_handler(commands=['ghost'])
def send_ghost_trades(message):
    ghost_trades = run_ghost_analysis()
    if ghost_trades:
        response = "👻 *Ghost Entries gefunden:*\n\n"
        for t in ghost_trades:
            response += f"🔍 {t['coin']}: {t['reason']}\n"
    else:
        response = "Kein Ghost Entry aktuell. Markt ist laut."

    bot.send_message(message.chat.id, response, parse_mode="Markdown")

@bot.message_handler(commands=["simstatus"])
def simstatus_handler(message):
    filepath = "simulation_log.json"

    if not os.path.exists(filepath):
        bot.reply_to(message, "❌ Noch keine Simulationen durchgeführt.")
        return

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        bot.reply_to(message, "⚠️ simulation_log.json ist beschädigt.")
        return

    if not data:
        bot.reply_to(message, "ℹ️ simulation_log.json ist leer.")
        return

    # Anzahl & letzter Eintrag
    total = len(data)
    last = data[-1]
    last_date = last.get("date", "???")
    last_coin = last.get("coin", "???")
    last_type = last.get("verhalten", "???")

    msg = (
        f"📊 *Simulationsstatus:*\n"
        f"🧮 Anzahl Einträge: *{total}*\n"
        f"🕒 Letzte Simulation: *{last_date}*\n"
        f"🪙 Coin: *{last_coin}*\n"
        f"🧠 Verhalten: *{last_type}*"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['forcelearn'])
def handle_forcelearn(message):
    if message.chat.id != ADMIN_ID:
        return
    results = run_feedback_loop()
    if not results:
        bot.send_message(message.chat.id, "📉 Keine offenen Entscheidungen oder Kursdaten fehlen.")
    else:
        response = "📈 Lernbewertung abgeschlossen:\n"
        for r in results:
            emoji = "✅" if r["success"] > 0 else "❌"
            response += f"{emoji} {r['coin']} ({r['date']}) → {r['success']} %\n"
        bot.send_message(message.chat.id, response)

@bot.message_handler(commands=["crawlerstatus"])
def handle_crawlerstatus(message):
    try:
        with open("crawler_data.json", "r") as f:
            data = json.load(f)
        last_entry = data[-1]
        response = f"📊 Letzte Crawler-Analyse:\n"
        response += f"🪙 Coin: {last_entry.get('coin')}\n"
        response += f"🔥 Score: {last_entry.get('trend_score')}\n"
        response += f"📡 Quellen: {', '.join(last_entry.get('sources', []))}\n"
        response += f"🕒 Zeitpunkt: {last_entry.get('timestamp')}"
    except Exception as e:
        response = f"❌ Fehler beim Abruf: {e}"
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['ghostmode'])
def toggle_ghost_mode(message):
    bot.send_message(message.chat.id, "👻 Ghost-Modus ist *aktiviert*. Scanne still den Markt...", parse_mode="Markdown")
    trades = run_ghost_mode()
    if trades:
        msg = "⚔️ Neue Ghost Entries:\n\n"
        for t in trades:
            msg += f"• {t['coin']}: {t['reason']}\n"
        bot.send_message(message.chat.id, msg)
    else:
        bot.send_message(message.chat.id, "Keine Ghost Entries im aktuellen Durchlauf.")

@bot.message_handler(commands=['ghostlog'])
def send_ghost_log(message):
    try:
        with open("ghost_log.json", "r") as f:
            entries = json.load(f)
        if not entries:
            bot.send_message(message.chat.id, "Ghost Log ist leer.")
            return
        response = "📜 Ghost Log Einträge:\n\n"
        for e in entries[-5:]:  # nur die letzten 5 zeigen
            response += f"🕓 {e['time']}\n💀 {e['coin']}: {e['reason']}\n\n"
        bot.send_message(message.chat.id, response)
    except:
        bot.send_message(message.chat.id, "⚠️ Kein Ghost Log gefunden.")

@bot.message_handler(func=lambda m: True)
def debug_echo(message):
    print(f"📥 Nachricht empfangen von {message.chat.id}: {message.text}")
    bot.send_message(message.chat.id, "✅ Nachricht empfangen.")

# === Startup-Scheduler & Lernlogik aktivieren ===
def startup_tasks():
    if not os.path.exists("history.json"):
        with open("history.json", "w") as f:
            json.dump({}, f)

    print("📈 Starte Initial-Simulation...")
    run_simulation()
    print("🤖 Logge Entscheidungen...")
    decisions = make_trade_decision()
    log_trade_decisions(decisions)
    print("🧠 Starte Feedback-Learning...")
    run_feedback_loop()

# === Bot starten ===
if __name__ == '__main__':
    threading.Thread(target=run_scheduler).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

if not os.path.exists("ghost_log.json"):
    with open("ghost_log.json", "w") as f:
        json.dump([], f)
