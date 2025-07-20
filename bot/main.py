import os
import telebot
from flask import Flask, request

# ⚠️ Hinweis: Token & Admin-ID sind hart codiert. Später besser in Environment-Variablen auslagern.
BOT_TOKEN = "7622848441:AAGiKi2Kpe4K-qUvmDzoj1ECgYYmsvjOmyA"
ADMIN_ID = 1269624949

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Telegram WebHook Endpoint
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# --- Commands ---

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Zugriff verweigert.")
        return
    bot.send_message(message.chat.id, "Willkommen beim OmertaTradeBot 🤖 /status für Zustand.")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if str(message.chat.id) != ADMIN_ID:
        bot.send_message(message.chat.id, "Zugriff verweigert.")
        return
    bot.send_message(message.chat.id, "Bot ist aktiv und wartet auf weitere Funktionen ✅")

# Root (Health Check)
@app.route('/')
def index():
    return "OmertaTradeBot läuft (Webhook aktiv)."

if __name__ == "__main__":
    # Railway setzt PORT automatisch
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
