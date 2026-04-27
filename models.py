from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class FileLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    filename = db.Column(db.String(200))
    corrections = db.Column(db.Integer)

    municipio = db.Column(db.String(100))
    mes = db.Column(db.String(10))