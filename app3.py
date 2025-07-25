import os
import logging
import threading # For running the Telegram Application in a separate thread
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timezone
import telegram
from telegram import Update
# Import specific components from telegram.ext, including filters
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

# --- Initial Configuration ---
# Set up logging for debugging purposes
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables (for deployment like Render) or use default values for local testing
# IMPORTANT: Replace "IL_TUO_TOKEN_QUI" and "https://la-tua-app.onrender.com"
# with your actual bot token and deployment URL.
TOKEN = os.environ.get("TOKEN_BOT_TELEGRAM", "IL_TUO_TOKEN_QUI")
SERVER_URL = os.environ.get("SERVER_URL", "https://la-tua-app.onrender.com") # e.g., "https://your-app-name.onrender.com"

# Initialize Flask app
app = Flask(__name__)

# Configure SQLAlchemy for database connection
# Uses an environment variable for the DB URI, falls back to a local sqlite file
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fleet.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable SQLAlchemy event system to save memory
db = SQLAlchemy(app)

# --- Database Model ---
# Defines the structure of the table to store position data
class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    # Use timezone.utc for consistent timestamps, especially important for global applications
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Converts a Position object to a dictionary for JSON serialization."""
        return {
            "username": self.username,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": self.timestamp.isoformat() # ISO format for easy parsing in web clients
        }

# --- Telegram Bot Logic ---
# This in-memory dictionary is simple but resets if the server restarts.
# For a more robust project, user state could be saved in the database.
user_states = {} # Stores user conversation states, e.g., { chat_id: "awaiting_username" }

async def start(update: Update, context: CallbackContext):
    """Handles the /start command, asking for the vehicle's username."""
    chat_id = update.effective_chat.id
    logger.info(f"Command /start received from {chat_id}")
    user_states[chat_id] = "awaiting_username" # Set user state to await username
    await update.message.reply_text(
        "Benvenuto nel sistema di monitoraggio della flotta!\n\n"
        "Per favore, inviami il nome identificativo del tuo veicolo (es. 'Veicolo-01')."
    )

async def handle_text(update: Update, context: CallbackContext):
    """Handles text messages, primarily for registering the username."""
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if user_states.get(chat_id) == "awaiting_username":
        username = text
        # Save the username in the bot's context for this conversation
        context.user_data['username'] = username
        # Remove the waiting state
        del user_states[chat_id]

        # Create a button to request location, which is more user-friendly
        location_button = telegram.KeyboardButton(
            text="Condividi la tua posizione 📍",
            request_location=True
        )
        custom_keyboard = [[location_button]]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            f"✅ Username '{username}' registrato con successo!\n\n"
            "Ora puoi condividere la tua posizione usando il pulsante qui sotto. "
            "Per una traccia continua, usa la funzione 'Posizione in tempo reale' di Telegram.",
            reply_markup=reply_markup
        )
        logger.info(f"Username '{username}' registered for {chat_id}")
    else:
        await update.message.reply_text("Per iniziare, invia il comando /start.")

async def handle_location(update: Update, context: CallbackContext):
    """Handles incoming location data and saves it to the database."""
    chat_id = update.effective_chat.id
    username = context.user_data.get('username')

    if not username:
        await update.message.reply_text("Per favore, registrati prima con /start e invia il tuo username.")
        logger.warning(f"Location received from {chat_id} without registered username.")
        return

    location = update.message.location
    lat = location.latitude
    lon = location.longitude

    # Create a new Position object and save it to the database
    # Ensure database operations are handled within a Flask application context
    with app.app_context():
        new_position = Position(username=username, latitude=lat, longitude=lon)
        db.session.add(new_position)
        db.session.commit()

    await update.message.reply_text(f"Posizione ricevuta e salvata per '{username}'. Grazie!")
    logger.info(f"Location saved for {username}: ({lat}, {lon})")

# --- Initialize the Bot with Application (python-telegram-bot v20+ approach) ---
# This creates and configures the bot application instance.
application = Application.builder().token(TOKEN).build()

# --- Add Handlers to the Application ---
# Register your bot's command and message handlers
application.add_handler(CommandHandler("start", start))
# Use uppercase constants for filters (e.g., filters.TEXT, filters.COMMAND)
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
application.add_handler(MessageHandler(filters.LOCATION, handle_location))

# --- Web Endpoints (API and Frontend) ---

@app.route("/")
def index():
    """Renders the main page with the map."""
    # Assumes you have a 'templates/index.html' file
    return render_template("index.html")

@app.route("/api/data", methods=["GET"])
def get_data():
    """Provides all position data in JSON format."""
    with app.app_context():
        positions = Position.query.order_by(Position.username, Position.timestamp).all()
        return jsonify([p.to_dict() for p in positions])

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Provides statistics about data collection."""
    with app.app_context():
        # Number of data points per vehicle
        count_by_user = db.session.query(
            Position.username, func.count(Position.id)
        ).group_by(Position.username).all()

        # Start and end dates of detections
        first_entry = db.session.query(func.min(Position.timestamp)).scalar()
        last_entry = db.session.query(func.max(Position.timestamp)).scalar()

        stats = {
            "count_by_user": dict(count_by_user),
            "start_date": first_entry.isoformat() if first_entry else None,
            "end_date": last_entry.isoformat() if last_entry else None,
        }
        return jsonify(stats)


# --- Endpoint for Telegram Webhook ---
@app.route(f"/{TOKEN}", methods=["POST"])
async def respond():
    """
    This endpoint receives updates from Telegram via webhook.
    It takes the incoming JSON request, converts it into a Telegram Update object,
    and then puts it into the `application`'s internal queue for processing.
    """
    if request.method == "POST":
        # Get the JSON data from the incoming webhook request
        json_data = request.get_json(force=True)
        logger.info(f"Received webhook update: {json_data}")

        # Create a Telegram Update object from the JSON data.
        # The 'application.bot' property holds the Bot instance managed by the Application.
        update = Update.de_json(json_data, application.bot)
        
        # Put the generated Update object into the application's update queue.
        # The application's internal worker will pick this up and process it
        # using the handlers you've added (e.g., CommandHandler, MessageHandler).
        await application.update_queue.put(update) # Use await because update_queue.put is async
        
        return "ok" # Telegram expects a 200 OK response quickly
    
    return "Method Not Allowed", 405 # Respond with 405 for non-POST requests

# --- Webhook Setup Endpoint ---
@app.route("/set_webhook", methods=["GET", "POST"])
async def set_webhook():
    """
    Sets the Telegram bot's webhook to the SERVER_URL.
    This should be called once when deploying your bot.
    """
    webhook_url = f"{SERVER_URL}/{TOKEN}"
    try:
        # Use application.bot directly for webhook operations
        # The drop_pending_updates=True argument ensures that any updates
        # received while the webhook was not set are discarded.
        await application.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        logger.info(f"Webhook set to: {webhook_url}")
        return jsonify({"status": "ok", "message": f"Webhook set to {webhook_url}"})
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Main Execution Block ---
if __name__ == "__main__":
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        logger.info("Database tables checked/created.")

    # When using webhooks, the `application` needs to be running its internal
    # update processing loop in a non-blocking way.
    # We run the python-telegram-bot Application in a separate thread.
    # def run_ptb_application():
    #     """Starts the python-telegram-bot Application's internal processing."""
    #     logger.info("Starting python-telegram-bot Application processing...")
    #     # `run_until_idle()` processes the queue when updates arrive.
    #     # It's suitable for webhook setups where updates are fed manually.
    #     application.run_until_idle() 
    #     logger.info("python-telegram-bot Application stopped.")

    # Start the python-telegram-bot application in a separate daemon thread
    # Daemon threads automatically close when the main program exits.
    # ptb_thread = threading.Thread(target=run_ptb_application, daemon=True)
    # ptb_thread.start()

    # Run the Flask app
    logger.info(f"Flask app starting on port 5000.")
    logger.info(f"Telegram Webhook endpoint: /{TOKEN}")
    logger.info(f"To set webhook, visit: {SERVER_URL}/set_webhook (after deployment)")
    app.run(debug=True, port=5000) # debug=True is for local development only
