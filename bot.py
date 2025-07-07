from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import requests
import os

TOKEN = os.environ.get("TOKEN_BOT_TELEGRAM")  # recuperato da BotFather
FLASK_SERVER_URL = "https://tuo_server_flask.com/api/posizione"  # endpoint per ricevere coordinate

# In memoria (o usare un DB più avanti): mappa telegram_user_id → username
registrati = {}  # es.: { 123456789: "Alfa123", ... }

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    # Chiedo username
    context.bot.send_message(
        chat_id=user_id,
        text=(
            "Benvenuto! Per favore, inviami il tuo username (codice veicolo). "
            "Scrivi qualcosa come: username: Alfa123"
        ),
        reply_markup=ReplyKeyboardRemove()
    )

def handle_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Cerco se l'utente ha già registrato username
    if user_id not in registrati:
        # Mi aspetto "username: Qualcosa"
        if text.lower().startswith("username:"):
            username = text.split(":", 1)[1].strip()
            if username:
                registrati[user_id] = username
                # Conferma all'utente e chiedo di inviare posizione
                btn = KeyboardButton(text="Invia posizione ora", request_location=True)
                markup = ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=False)
                context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"Username impostato a '{username}'.\n"
                        "Ora puoi condividere la posizione toccando il pulsante qui sotto. "
                        "Puoi ripetere questa operazione ogni volta che vuoi o impostare la ‘posizione live’."
                    ),
                    reply_markup=markup
                )
            else:
                context.bot.send_message(chat_id=user_id, text="Non hai inserito uno username valido. Riprovare.")
        else:
            context.bot.send_message(chat_id=user_id, text="Per favore, inviami lo username nel formato: username: Alfa123")
    else:
        # Se l'utente è già registrato ma scrive testo libero, chiedo di usare il pulsante posizione
        context.bot.send_message(
            chat_id=user_id,
            text="Per favore, usa il pulsante per inviare la posizione."
        )

def handle_location(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in registrati:
        context.bot.send_message(chat_id=user_id, text="Prima registrati con /start e fornisci lo username.")
        return

    username = registrati[user_id]
    loc = update.message.location
    lat = loc.latitude
    lon = loc.longitude
    timestamp = update.message.date.isoformat()  # ISO8601

    # Preparo payload da inviare al server Flask
    payload = {
        "telegram_user_id": user_id,
        "username": username,
        "latitude": lat,
        "longitude": lon,
        "timestamp": timestamp
    }
    try:
        r = requests.post(FLASK_SERVER_URL, json=payload, timeout=5)
        if r.status_code == 200:
            context.bot.send_message(chat_id=user_id, text="Posizione inviata correttamente ✅")
        else:
            context.bot.send_message(
                chat_id=user_id,
                text=f"Errore nell’invio dei dati al server (status={r.status_code})."
            )
    except Exception as e:
        context.bot.send_message(chat_id=user_id, text=f"Impossibile connettersi al server: {e}")

def main():
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))
    dp.add_handler(MessageHandler(Filters.location, handle_location))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
