from flask import Flask, render_template, request, redirect, send_file, url_for, flash
from models import db, User, FileLog
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import pandas as pd
import zipfile
from io import BytesIO
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret"
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
            flash("Login inválido", "error")
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

# ================= IA SIMPLES =================

def gerar_insights(logs):
    if not logs:
        return ["Sem dados ainda"]

    total = sum(l.corrections for l in logs)
    maior = max(logs, key=lambda x: x.corrections)
    menor = min(logs, key=lambda x: x.corrections)

    insights = []
    insights.append(f"Arquivo com mais erros: {maior.filename}")
    insights.append(f"Arquivo com menos erros: {menor.filename}")
    insights.append(f"Média geral de erros: {round(total/len(logs),2)}")

    if total > 100:
        insights.append("Alto volume de inconsistências detectado")

    return insights

# ================= DASHBOARD =================

@app.route("/home")
@login_required
def home():
    logs = FileLog.query.all()

    nomes = [l.filename for l in logs]
    correcoes = [l.corrections for l in logs]

    meses = defaultdict(int)
    for l in logs:
        mes = datetime.now().strftime("%m/%Y")
        meses[mes] += l.corrections

    insights = gerar_insights(logs)

    return render_template(
        "home.html",
        nomes=nomes,
        correcoes=correcoes,
        meses=list(meses.keys()),
        valores=list(meses.values()),
        insights=insights,
        logs=logs
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

            db.session.add(FileLog(filename=file.filename, corrections=erros))

    db.session.commit()

    zip_buffer.seek(0)

    return send_file(zip_buffer, as_attachment=True, download_name="resultado.zip")

# ================= START =================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()