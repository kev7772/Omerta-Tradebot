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
