from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Vehicolo(db.Model):
    __tablename__ = "veicoli"
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    # potresti voler aggiungere campi extra: 
    # es.: marca, modello, targa, ecc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posizioni = db.relationship("Posizione", backref="vehicolo", lazy=True)

class Posizione(db.Model):
    __tablename__ = "posizioni"
    id = db.Column(db.Integer, primary_key=True)
    vehicolo_id = db.Column(db.Integer, db.ForeignKey("veicoli.id"), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)  # momento in cui la posizione è stata rilevata
