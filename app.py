# from flask import Flask, request, jsonify, render_template
# from flask_sqlalchemy import SQLAlchemy
# from flask_migrate import Migrate
# from models import db, Vehicolo, Posizione
# from datetime import datetime
# import os

# app = Flask(__name__)

# # Configurazione DB: esempio con SQLite per sviluppo, 
# # in produzione potresti usare PostgreSQL (URL su env variable)
# DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///fleet.db")
# app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# db.init_app(app)
# migrate = Migrate(app, db)

# # Se serve consentire richieste CORS dal bot (se bot e server su domini diversi)
# # from flask_cors import CORS
# # CORS(app)

# @app.route("/api/posizione", methods=["POST"])
# def ricevi_posizione():
#     """
#     Endpoint che riceve in POST JSON contenente:
#     {
#       "telegram_user_id": 123456789,
#       "username": "Alfa123",
#       "latitude": 45.1234,
#       "longitude": 7.5678,
#       "timestamp": "2025-06-04T12:34:56"
#     }
#     """
#     data = request.get_json()
#     required = ["telegram_user_id", "username", "latitude", "longitude", "timestamp"]
#     if not data or any(k not in data for k in required):
#         return jsonify({"error": "Payload mancante o incompleto"}), 400

#     try:
#         user_id = int(data["telegram_user_id"])
#         username = data["username"]
#         lat = float(data["latitude"])
#         lon = float(data["longitude"])
#         # Parse ISO8601: in questo esempio usiamo datetime.fromisoformat()
#         ts = datetime.fromisoformat(data["timestamp"])
#     except Exception as e:
#         return jsonify({"error": f"Valori non validi: {e}"}), 400

#     # Cerco se esiste il veicolo, altrimenti lo creo
#     veh = Vehicolo.query.filter_by(telegram_user_id=user_id).first()
#     if not veh:
#         veh = Vehicolo(telegram_user_id=user_id, username=username)
#         db.session.add(veh)
#         db.session.commit()
#     else:
#         # Se lo username inviato dal bot è cambiato, eventualmente aggiorno:
#         if veh.username != username:
#             veh.username = username
#             db.session.commit()

#     # Creo e salvo la posizione
#     pos = Posizione(
#         vehicolo_id=veh.id,
#         latitude=lat,
#         longitude=lon,
#         timestamp=ts
#     )
#     db.session.add(pos)
#     db.session.commit()

#     return jsonify({"ok": True}), 200

# @app.route("/")
# def index():
#     """
#     Pagina principale: mostra mappa, dropdown di selezione username, statistiche.
#     """
#     # Recupero tutti i veicoli esistenti
#     veicoli = Vehicolo.query.order_by(Vehicolo.username).all()
#     # Passo alla template la lista di tuple (id, username)
#     return render_template("index.html", veicoli=veicoli)

# @app.route("/api/traiettoria/<int:veh_id>")
# def get_traiettoria(veh_id):
#     """
#     Restituisce JSON con tutte le posizioni (ordinato per timestamp) 
#     di un dato veicolo (veh_id).
#     Formato di risposta:
#     {
#       "username": "...",
#       "posizioni": [
#          {"lat": ..., "lon": ..., "timestamp": "..."},
#          ...
#       ]
#     }
#     """
#     veh = Vehicolo.query.get_or_404(veh_id)
#     posizioni = (
#         Posizione.query
#         .filter_by(vehicolo_id=veh_id)
#         .order_by(Posizione.timestamp)
#         .all()
#     )
#     dati = [
#         {"lat": p.latitude, "lon": p.longitude, "timestamp": p.timestamp.isoformat()}
#         for p in posizioni
#     ]
#     return jsonify({"username": veh.username, "posizioni": dati})

# @app.route("/api/statistiche")
# def get_statistiche():
#     """
#     Restituisce per ogni veicolo: numero di punti, data prima rilevazione, data ultima rilevazione.
#     [
#       {
#         "veh_id": ...,
#         "username": "...",
#         "num_punti": ...,
#         "prima_rilevazione": "...",
#         "ultima_rilevazione": "..."
#       },
#       ...
#     ]
#     """
#     # Esempio con singola query: 
#     risultati = []
#     veicoli = Vehicolo.query.all()
#     for v in veicoli:
#         q = (
#             db.session.query(
#                 db.func.count(Posizione.id).label("cnt"),
#                 db.func.min(Posizione.timestamp).label("primo"),
#                 db.func.max(Posizione.timestamp).label("ultimo")
#             )
#             .filter(Posizione.vehicolo_id == v.id)
#             .one()
#         )
#         risultati.append({
#             "veh_id": v.id,
#             "username": v.username,
#             "num_punti": q.cnt,
#             "prima_rilevazione": q.primo.isoformat() if q.primo else None,
#             "ultima_rilevazione": q.ultimo.isoformat() if q.ultimo else None
#         })
#     return jsonify(risultati)

# if __name__ == "__main__":
#     # Per eseguire in locale: FLASK_APP=app.py flask run
#     app.run(host="0.0.0.0", port=5000, debug=True)
from flask import Flask, request, jsonify, render_template
from google.cloud import bigquery
from datetime import datetime, timezone
import os

app = Flask(__name__)

# # Inizializza il client BigQuery
# client = bigquery.Client()

# # ID della tabella BigQuery (formato: progetto.dataset.tabella)
# TABLE_ID = "tuo-progetto.fleet_monitoring.vehicle_positions"

@app.route("/position", methods=["POST"])
def receive_position():
    data = request.get_json()

    # Validazione base
    if not all(k in data for k in ("username", "latitude", "longitude")):
        return jsonify({"error": "Missing required fields"}), 400

    # Crea il timestamp UTC ISO 8601
    timestamp = datetime.now(timezone.utc).isoformat()

    row = {
        "username": data["username"],
        "latitude": float(data["latitude"]),
        "longitude": float(data["longitude"]),
        "timestamp": timestamp
    }

    # Inserisce una riga in BigQuery
    errors = client.insert_rows_json(TABLE_ID, [row])

    if errors:
        return jsonify({"status": "error", "details": errors}), 500
    else:
        return jsonify({"status": "success"}), 200

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html"), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)

