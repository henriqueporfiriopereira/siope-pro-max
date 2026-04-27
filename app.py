import matplotlib
matplotlib.use('Agg')

from flask import Flask, render_template, request, redirect, send_file, flash
from models import db, User, FileLog
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import pandas as pd
import zipfile
from io import BytesIO
import re
from collections import defaultdict
import os

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import matplotlib.pyplot as plt

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "siope_enterprise")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db_final_v3.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================= LOGIN =================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["user"]).first()

        if not user or not check_password_hash(user.password, request.form["pass"]):
            flash("Login inválido")
            return redirect("/")

        login_user(user, remember=True)
        return redirect("/home")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if User.query.filter_by(username=request.form["user"]).first():
            flash("Usuário já existe")
            return redirect("/register")

        user = User(
            username=request.form["user"],
            password=generate_password_hash(request.form["pass"])
        )

        db.session.add(user)
        db.session.commit()

        return redirect("/")

    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")

# ================= FUNÇÕES =================

def detectar_municipio(nome):
    nome = nome.upper()
    if "CANAPI" in nome:
        return "CANAPI"
    elif "OURO" in nome:
        return "OURO_BRANCO"
    return "OUTROS"

def extrair_mes(nome):
    meses = {
        "JANEIRO":"01","FEVEREIRO":"02","MARCO":"03","ABRIL":"04",
        "MAIO":"05","JUNHO":"06","JULHO":"07","AGOSTO":"08",
        "SETEMBRO":"09","OUTUBRO":"10","NOVEMBRO":"11","DEZEMBRO":"12"
    }

    nome = nome.upper()

    for m in meses:
        if m in nome:
            ano = re.findall(r"\d{4}", nome)
            if ano:
                return f"{meses[m]}/{ano[0]}"

    return "00/0000"

# ================= DASHBOARD =================

@app.route("/home")
@login_required
def home():
    logs = FileLog.query.all()

    meses_dict = defaultdict(int)
    for l in logs:
        meses_dict[l.mes] += l.corrections

    crescimento = 0
    if len(meses_dict) >= 2:
        valores = list(meses_dict.values())
        crescimento = valores[-1] - valores[-2]

    municipios = [m[0] for m in db.session.query(FileLog.municipio).distinct()]
    meses_lista = [m[0] for m in db.session.query(FileLog.mes).distinct()]

    return render_template(
        "home.html",
        logs=logs,
        correcoes=[l.corrections for l in logs],
        meses=list(meses_dict.keys()),
        valores=list(meses_dict.values()),
        municipios=municipios,
        meses_lista=meses_lista,
        crescimento=crescimento
    )

# ================= UPLOAD =================

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    files = request.files.getlist("file")
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for file in files:

            df = pd.read_excel(file, header=None)

            linhas = []
            erros = 0

            for _, row in df.iterrows():
                if pd.isna(row[0]):
                    continue

                partes = str(row[0]).split(';')

                if len(partes) > 21:
                    try:
                        base = float(partes[17].replace('.', '').replace(',', '.'))
                        rem = float(partes[21].replace('.', '').replace(',', '.'))

                        if base > rem:
                            partes[17] = partes[21]
                            erros += 1
                    except:
                        pass

                linhas.append(';'.join(partes))

            excel_buffer = BytesIO()
            pd.DataFrame(linhas).to_excel(excel_buffer, index=False, header=False)
            excel_buffer.seek(0)

            nome_saida = file.filename.replace(".xlsx","_CORRIGIDO.xlsx")
            zip_file.writestr(nome_saida, excel_buffer.read())

            db.session.add(FileLog(
                filename=file.filename,
                corrections=erros,
                municipio=detectar_municipio(file.filename),
                mes=extrair_mes(file.filename)
            ))

    db.session.commit()

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name="resultado.zip")

# ================= PDF =================

@app.route("/relatorio_pdf")
@login_required
def relatorio_pdf():

    logs = FileLog.query.all()

    meses = {}
    for l in logs:
        meses[l.mes] = meses.get(l.mes, 0) + l.corrections

    plt.figure()
    plt.bar(meses.keys(), meses.values())
    plt.title("Correções por mês")

    img = "grafico.png"
    plt.savefig(img)
    plt.close()

    pdf = "relatorio.pdf"

    doc = SimpleDocTemplate(pdf)
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("Relatório SIOPE PRO MAX", styles["Title"]))
    elements.append(Spacer(1, 20))

    for l in logs:
        elements.append(Paragraph(f"{l.filename} - {l.corrections}", styles["Normal"]))

    elements.append(Spacer(1, 20))
    elements.append(Image(img, width=400, height=200))

    doc.build(elements)

    return send_file(pdf, as_attachment=True)

# ================= START =================

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)