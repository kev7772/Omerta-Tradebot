import os
import json
import threading
import telebot
from flask import Flask, request
import time
from live_logger import write_history
from simulator import run_simulation
from logic import recommend_trades, should_trigger_panic, get_trading_decision
from sentiment_parser import get_sentiment_data
from indicators import calculate_indicators
from binance.client import Client
from trading import get_portfolio, get_profit_estimates
from scheduler import run_scheduler
from simulator import run_simulation

# === Bot & Server Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === Flask Endpunkte ===
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

# === Telegram-Befehle ===
@bot.message_handler(commands=['start'])
def cmd_start(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Zugriff verweigert.")
        return
    bot.send_message(message.chat.id, "Willkommen beim OmertaTradeBot 🤖")

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
    actions = get_trading_decision()
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
    bot.send_message(message.chat.id, "🧪 Simulation abgeschlossen. Ergebnisse in 'simulation_log.json'.")

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
    from forecast import forecast_market
    lines = forecast_market()
    bot.send_message(message.chat.id, "🔮 Marktprognose:\n" + "\n".join(lines))

@bot.message_handler(commands=['heatmap'])
def cmd_heatmap(message):
    if message.chat.id != ADMIN_ID:
        return
    from visualize_learning import generate_heatmap
    path = generate_heatmap()
    with open(path, "rb") as f:
        bot.send_photo(message.chat.id, f, caption="Lern-Heatmap (Coin-Erfolgsquote)")

@bot.message_handler(commands=['simlog'])
def send_simulation_log(message):
    try:
        with open("learninglog.json", "r") as f:
            logs = f.readlines()[-5:]  # letzte 5 Logs
        response = "\n".join([json.loads(l).get("szenario", "") + " – " + json.loads(l).get("aktion", "") for l in logs])
        bot.reply_to(message, f"Letzte Simulationen:\n{response}")
    except:
        bot.reply_to(message, "Keine Simulationen gefunden.")

import os
import telebot
from logic import get_learning_log

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['learninglog'])
def handle_learninglog(message):
    print("📥 /learninglog empfangen")
    log = get_learning_log()
    print("📤 Antwort an Telegram:", log)
    bot.reply_to(message, log)

from simulator import run_simulation  # Importieren

@bot.message_handler(commands=['simulate'])
def handle_simulate(message):
    result_text = run_simulation()
    bot.reply_to(message, result_text)

from simulator import run_simulation

@bot.message_handler(commands=['simulate'])
def handle_simulate(message):
    result = run_simulation()
    bot.reply_to(message, result)
    
# === Flask & Scheduler starten ===
if __name__ == '__main__':
    threading.Thread(target=run_scheduler).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# history.json anlegen, falls nicht vorhanden
if not os.path.exists("history.json"):
    with open("history.json", "w") as f:
        json.dump({}, f)

# Direkt beim Start:
run_simulation()
