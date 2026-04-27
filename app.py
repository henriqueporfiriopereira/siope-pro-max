from flask import Flask, render_template, request, send_file
from models import db, FileLog
import pandas as pd
import zipfile
import os
import io

import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Criar banco automaticamente
with app.app_context():
    db.create_all()

# ---------------- HOME ----------------
@app.route("/")
@app.route("/home")
def home():
    logs = FileLog.query.all()

    meses = [l.mes for l in logs]
    valores = [l.corrections for l in logs]

    return render_template("home.html", logs=logs, meses=meses, valores=valores)

# ---------------- UPLOAD ----------------
@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zip_file:

        for file in files:
            df = pd.read_excel(file)

            # exemplo de contagem
            corrections = len(df)

            nome = file.filename
            municipio = nome.split(" ")[1] if len(nome.split(" ")) > 1 else "N/A"
            mes = nome.split(" ")[-1].replace(".xlsx","")

            # salvar no banco
            log = FileLog(
                filename=nome,
                corrections=corrections,
                municipio=municipio,
                mes=mes
            )
            db.session.add(log)

            # gerar arquivo corrigido (simples)
            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)

            zip_file.writestr(nome, output.read())

        db.session.commit()

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name="resultado.zip",
        mimetype="application/zip"
    )

# ---------------- RODAR ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)