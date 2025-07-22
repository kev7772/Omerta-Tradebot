import os
import threading
import telebot
from flask import Flask, request

BOT_TOKEN = "7622848441:AAGiKi2Kpe4K-qUvmDzoj1ECgYYmsvjOmyA"
ADMIN_ID = 1269624949

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Root Check
@app.route('/')
def index():
    return 'OmertaTradeBot Webhook aktiv'

# Telegram Webhook Endpoint
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# Telegram Commands
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
@bot.message_handler(commands=['start'])
def cmd_start(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Zugriff verweigert.")
        return
    bot.send_message(message.chat.id, "Willkommen beim OmertaTradeBot 🤖")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Zugriff verweigert.")
        return
    bot.send_message(message.chat.id, "Bot läuft ✅")

# Flask in Thread starten (damit Bot auch aktiv bleibt)
def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()

from trading import get_portfolio, get_profit_estimates
from logic import should_trigger_panic, get_trading_decision

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

import schedule
import time
from live_logger import write_history
from simulator import run_simulation
from logic import recommend_trades

# Telegram-Befehle

@bot.message_handler(commands=['loghistory'])
def cmd_loghistory(message):
    if message.chat.id != ADMIN_ID:
        return
    save_daily_snapshot()
    bot.send_message(message.chat.id, "📊 History gespeichert.")

@bot.message_handler(commands=['simulate'])
def cmd_simulate(message):
    if message.chat.id != ADMIN_ID:
        return
    results = run_simulation()
    text = "🧪 Simulationsergebnisse:\n" + "\n".join(results)
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['recommend'])
def cmd_recommend(message):
    if message.chat.id != ADMIN_ID:
        return
    recs = recommend_trades()
    text = "📌 Empfehlungen:\n" + "\n".join(recs)
    bot.send_message(message.chat.id, text)

# Tägliches Logging um 00:01 Uhr
def run_scheduler():
    schedule.every().day.at("00:01").do(write_history)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Threads starten (damit alles wach bleibt)
threading.Thread(target=run_flask).start()
threading.Thread(target=run_scheduler).start()
