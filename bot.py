from flask import Flask, request
import requests

app = Flask(__name__)

# Neuer Bot-Token direkt im Code gesetzt
BOT_TOKEN = "7758825681:AAE6z7kchN2EER40zpe0ph_MZjE0BKfGb60"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route("/")
def home():
    return "OmertaBot läuft über Railway ✅", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "Willkommen Bruder, OmertaBot ist aktiv ✅")
        elif text == "/status":
            send_message(chat_id, "Status: Alles unter Kontrolle 💹")
        elif text == "/panic":
            send_message(chat_id, "⚠️ Panikmodus aktiviert! Alle Trades gestoppt.")
        elif text == "/report":
            send_message(chat_id, "📄 Bericht folgt in Kürze... (PDF-Modul wird vorbereitet)")
        else:
            send_message(chat_id, "Unbekannter Befehl Bruder.")

    return "ok", 200

def send_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    requests.post(API_URL, json=payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
