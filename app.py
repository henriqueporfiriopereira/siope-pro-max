from flask import Flask, render_template, request, redirect, send_file, flash
from models import db, User, FileLog
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import pandas as pd
import zipfile
from io import BytesIO
import re
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
app.config["SECRET_KEY"] = "siope_enterprise"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================= LOGIN =================

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["user"]).first()
        if not user or not check_password_hash(user.password, request.form["pass"]):
            flash("Login inválido")
            return redirect("/")

        login_user(user, remember=True)
        return redirect("/home")

    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
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

# ================= EXTRAIR DADOS REAIS =================

def detectar_municipio(nome):
    nome = nome.upper()
    if "CANAPI" in nome:
        return "CANAPI"
    elif "OURO" in nome:
        return "OURO_BRANCO"
    return "OUTROS"

def extrair_mes(nome):
    meses = {
        "JANEIRO":"01", "FEVEREIRO":"02", "MARCO":"03", "ABRIL":"04",
        "MAIO":"05", "JUNHO":"06", "JULHO":"07", "AGOSTO":"08",
        "SETEMBRO":"09", "OUTUBRO":"10", "NOVEMBRO":"11", "DEZEMBRO":"12"
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
    municipio = request.args.get("municipio")
    mes = request.args.get("mes")

    query = FileLog.query

    if municipio:
        query = query.filter_by(municipio=municipio)

    if mes:
        query = query.filter_by(mes=mes)

    logs = query.all()

    nomes = [l.filename for l in logs]
    correcoes = [l.corrections for l in logs]

    # gráfico mensal
    meses = defaultdict(int)
    for l in logs:
        meses[l.mes] += l.corrections

    # comparação entre meses
    crescimento = 0
    if len(meses) >= 2:
        valores = list(meses.values())
        crescimento = valores[-1] - valores[-2]

    # selects
    municipios = [m[0] for m in db.session.query(FileLog.municipio).distinct()]
    meses_lista = [m[0] for m in db.session.query(FileLog.mes).distinct()]

    return render_template(
        "home.html",
        nomes=nomes,
        correcoes=correcoes,
        meses=list(meses.keys()),
        valores=list(meses.values()),
        logs=logs,
        municipios=municipios,
        meses_lista=meses_lista,
        crescimento=crescimento
    )

# ================= PROCESSAMENTO =================

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
                if pd.isna(row[0]): continue

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

            # 🔥 SALVANDO DADOS REAIS
            db.session.add(FileLog(
                filename=file.filename,
                corrections=erros,
                municipio=detectar_municipio(file.filename),
                mes=extrair_mes(file.filename)
            ))

    db.session.commit()

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name="resultado.zip")

# ================= EXPORTAR FILTRADO =================

@app.route("/exportar")
@login_required
def exportar():
    municipio = request.args.get("municipio")
    mes = request.args.get("mes")

    query = FileLog.query

    if municipio:
        query = query.filter_by(municipio=municipio)

    if mes:
        query = query.filter_by(mes=mes)

    logs = query.all()

    buffer = BytesIO()
    df = pd.DataFrame([{
        "arquivo": l.filename,
        "correcoes": l.corrections,
        "municipio": l.municipio,
        "mes": l.mes
    } for l in logs])

    df.to_excel(buffer, index=False)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="relatorio.xlsx")

# ================= START =================

if __name__ == "__main__":
    with app.app_context():
    db.drop_all()
    db.create_all()
    app.run()