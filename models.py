from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class FileLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    corrections = db.Column(db.Integer)
    municipio = db.Column(db.String(100))
    mes = db.Column(db.String(20))