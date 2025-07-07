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
from google.cloud import bigquery
from datetime import datetime, timedelta
import random

def create_dataset(project_id,dataset_id,location):
    # Construct a BigQuery client object.
    client = bigquery.Client.from_service_account_json('test_esame.json')
    dataset_full_id = f'{project_id}.{dataset_id}'
    dataset = bigquery.Dataset(dataset_full_id)
    dataset.location = location
    # Send the dataset to the API for creation, with an explicit timeout.
    # Raises google.api_core.exceptions.Conflict if the Dataset already
    # exists within the project.
    dataset = client.create_dataset(dataset, timeout=30)  # Make an API request.
    print("Created dataset {}.{}".format(client.project, dataset.dataset_id))

def create_table(project_id,dataset_id,table_id):
    client = bigquery.Client.from_service_account_json('test_esame.json')
    table_full_id = f'{project_id}.{dataset_id}.{table_id}'

    schema = [
        bigquery.SchemaField("sensor", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("lat", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("lon", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("value", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("datetime", "DATETIME", mode="REQUIRED"),
    ]

    table = bigquery.Table(table_full_id, schema=schema)
    table = client.create_table(table)  # Make an API request.
    print(f'Created table {table.project}.{table.dataset_id}.{table.table_id}')

def insert(project_id,dataset_id,table_id):
    client = bigquery.Client.from_service_account_json('test_esame.json')
    table_full_id = f'{project_id}.{dataset_id}.{table_id}'

    rows_to_insert = [
    {'sensor':'sensor1','value':3.4,'datetime':'2021-11-17 15:32:00'}, # DATETIME	A string in the form "YYYY-MM-DD [HH:MM:SS]"
    {'sensor':'sensor1','value':3.5,'datetime':'2021-11-17 15:33:00'},
    ]

    errors = client.insert_rows_json(table_full_id, rows_to_insert)  # Make an API request.
    if errors == []:
        print("New rows have been added.")
    else:
        print("Encountered errors while inserting rows: {}".format(errors))

def insert2(project_id,dataset_id,table_id):
    client = bigquery.Client.from_service_account_json('test_esame.json')
    table_full_id = f'{project_id}.{dataset_id}.{table_id}'

    dt = datetime.strptime('2021-11-17 15:33:00', '%Y-%m-%d %H:%M:%S')  # YYYY-MM-DD [HH:MM:SS]
    for i in range(100):
        dt += timedelta(minutes=1)
        #print(dt.strftime('%Y-%m-%d %H:%M:%S'))
        v = 3.4 + i + random.gauss(0,2)
        rows = [{'sensor': 'sensor1', 'value': v, 'datetime': dt.strftime('%Y-%m-%d %H:%M:%S')}]
        errors = client.insert_rows_json(table_full_id, rows)  # Make an API request.
        if errors == []:
            print("New rows have been added.")
        else:
            print("Encountered errors while inserting rows: {}".format(errors))

def insert3(project_id,dataset_id,table_id):
    client = bigquery.Client.from_service_account_json('test_esame.json')
    table_full_id = f'{project_id}.{dataset_id}.{table_id}'

    dt = datetime.strptime('2021-11-17 17:33:00', '%Y-%m-%d %H:%M:%S')  # YYYY-MM-DD [HH:MM:SS]

    sensors = [
        {'id': 'modena','lat':44.64661935128612, 'lon':10.925714194043392},
        {'id': 'reggio emilia', 'lat': 44.69833568636162, 'lon': 10.63119575772369},
        {'id': 'mantova', 'lat': 45.158563488324816, 'lon': 10.793287903622467}
    ]

    for i in range(100):
        dt += timedelta(minutes=1)
        for s in sensors:
            v = 60 -  0.5*i + random.gauss(0,2)
            if i == 50:
                v += 100
            rows = [{'sensor': s['id'], 'lat': s['lat'], 'lon': s['lon'], 'value': v, 'datetime': dt.strftime('%Y-%m-%d %H:%M:%S')}]
            errors = client.insert_rows_json(table_full_id, rows)  # Make an API request.
            if errors == []:
                print("New rows have been added.")
            else:
                print("Encountered errors while inserting rows: {}".format(errors))


def query(project_id,db_id,table):
    query = f'SELECT * FROM {project_id}.{db_id}.{table} LIMIT 100'
    client = bigquery.Client.from_service_account_json('test_esame.json')
    query_job = client.query(query)
    for row in query_job:
        #print(row)
        # Row values can be accessed by field name or index.
        print(f'name={row[0]} datetime={row["datetime"]}')



if __name__ == '__main__':
    project_id = 'plcoud2024'
    region = 'europe-west8'
    db_id = 'test2'
    table = 'table2'
    #create_dataset(project_id,db_id,region)
    #create_table(project_id,db_id,table)
    #insert3(project_id, db_id, table)
    query(project_id,db_id,table)
