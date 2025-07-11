import os
import logging
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timezone
import telegram
from telegram import Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

# --- Configurazione Iniziale ---
# Imposta il logging per debug
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Carica le variabili d'ambiente (per Render) o usa valori di default per test locali
TOKEN = os.environ.get("TOKEN_BOT_TELEGRAM", "IL_TUO_TOKEN_QUI")
SERVER_URL = os.environ.get("SERVER_URL", "https://la-tua-app.onrender.com")

# Inizializzazione Flask e SQLAlchemy
app = Flask(__name__)
# Usa una variabile d'ambiente per il DB, con fallback a un file locale sqlite
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fleet.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Modello Database ---
# Definisce la struttura della tabella che conterrà le posizioni
class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "username": self.username,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": self.timestamp.isoformat()
        }

# --- Logica del Bot Telegram ---
# Questo dizionario in memoria è semplice ma si resetta se il server riparte.
# Per un progetto più robusto, si potrebbe salvare lo stato dell'utente nel database.
user_states = {} # { chat_id: "awaiting_username" }

def start(update: Update, context: CallbackContext):
    """Gestisce il comando /start, chiedendo l'username."""
    chat_id = update.effective_chat.id
    logger.info(f"Comando /start ricevuto da {chat_id}")
    user_states[chat_id] = "awaiting_username"
    update.message.reply_text(
        "Benvenuto nel sistema di monitoraggio della flotta!\n\n"
        "Per favore, inviami il nome identificativo del tuo veicolo (es. 'Veicolo-01')."
    )

def handle_text(update: Update, context: CallbackContext):
    """Gestisce i messaggi di testo, principalmente per registrare l'username."""
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if user_states.get(chat_id) == "awaiting_username":
        username = text
        # Salva l'username nel contesto del bot per questa conversazione
        context.user_data['username'] = username
        # Rimuovi lo stato di attesa
        del user_states[chat_id]

        # Crea un pulsante per richiedere la posizione
        location_button = telegram.KeyboardButton(
            text="Condividi la tua posizione 📍",
            request_location=True
        )
        custom_keyboard = [[location_button]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True, one_time_keyboard=False)

        update.message.reply_text(
            f"✅ Username '{username}' registrato con successo!\n\n"
            "Ora puoi condividere la tua posizione usando il pulsante qui sotto. "
            "Per una traccia continua, usa la funzione 'Posizione in tempo reale' di Telegram.",
            reply_markup=reply_markup
        )
        logger.info(f"Username '{username}' registrato per {chat_id}")
    else:
        update.message.reply_text("Per iniziare, invia il comando /start.")

def handle_location(update: Update, context: CallbackContext):
    """Gestisce l'invio della posizione e la salva nel database."""
    chat_id = update.effective_chat.id
    username = context.user_data.get('username')

    if not username:
        update.message.reply_text("Per favore, registrati prima con /start e invia il tuo username.")
        logger.warning(f"Posizione ricevuta da {chat_id} senza username registrato.")
        return

    location = update.message.location
    lat = location.latitude
    lon = location.longitude

    # Crea un nuovo oggetto Position e salvalo nel DB
    new_position = Position(username=username, latitude=lat, longitude=lon)
    db.session.add(new_position)
    db.session.commit()

    update.message.reply_text(f"Posizione ricevuta e salvata per '{username}'. Grazie!")
    logger.info(f"Posizione salvata per {username}: ({lat}, {lon})")


# --- Endpoint Web (API e Frontend) ---

@app.route("/")
def index():
    """Mostra la pagina principale con la mappa."""
    return render_template("index.html")

@app.route("/api/data", methods=["GET"])
def get_data():
    """Fornisce tutti i dati di posizione in formato JSON."""
    positions = Position.query.order_by(Position.username, Position.timestamp).all()
    return jsonify([p.to_dict() for p in positions])

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Fornisce statistiche sulla raccolta dati."""
    # Numero di dati per ogni veicolo
    count_by_user = db.session.query(
        Position.username, func.count(Position.id)
    ).group_by(Position.username).all()

    # Data di inizio e fine delle rilevazioni
    first_entry = db.session.query(func.min(Position.timestamp)).scalar()
    last_entry = db.session.query(func.max(Position.timestamp)).scalar()

    stats = {
        "count_by_user": dict(count_by_user),
        "start_date": first_entry.isoformat() if first_entry else None,
        "end_date": last_entry.isoformat() if last_entry else None,
    }
    return jsonify(stats)


# --- Endpoint per il Webhook di Telegram ---

@app.route(f"/{TOKEN}", methods=["POST"])
def respond():
    """Endpoint che riceve gli aggiornamenti da Telegram."""
    update = Update.de_json(request.get_json(force=True), bot)
    dp.process_update(update)
    return "ok"

# --- Inizializzazione del Bot e Webhook ---
bot = telegram.Bot(TOKEN)
dp = Dispatcher(bot, None, use_context=True)

# Aggiungi i gestori dei comandi e messaggi
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
dp.add_handler(MessageHandler(Filters.location, handle_location))


if __name__ == "__main__":
    # Crea le tabelle del database se non esistono
    with app.app_context():
        db.create_all()
    # Esegui l'app in modalità debug (solo per test locali)
    app.run(debug=True, port=5000)