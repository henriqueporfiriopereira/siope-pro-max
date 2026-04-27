from flask import Flask, render_template, request, redirect, send_file, url_for, flash
from models import db, User, FileLog
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import pandas as pd
import os
import zipfile
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from collections import defaultdict

app = Flask(__name__)
app.config["SECRET_KEY"] = "siope_super_seguro_123"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/"

UPLOAD = "uploads"
os.makedirs(UPLOAD, exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================= LOGIN =================

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["user"]).first()

        if not user:
            flash("Usuário não encontrado", "error")
            return redirect("/")

        if not check_password_hash(user.password, request.form["pass"]):
            flash("Senha incorreta", "error")
            return redirect("/")

        lembrar = True if request.form.get("lembrar") else False

        login_user(user, remember=lembrar)
        flash("Login realizado com sucesso", "success")
        return redirect("/home")

    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        senha = generate_password_hash(request.form["pass"])
        user = User(username=request.form["user"], password=senha)
        db.session.add(user)
        db.session.commit()
        flash("Usuário criado com sucesso", "success")
        return redirect("/")
    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema", "info")
    return redirect("/")

# ================= FUNÇÕES =================

def detectar_municipio(texto):
    texto = texto.upper()
    if "CANAPI" in texto:
        return "CANAPI"
    elif "OURO BRANCO" in texto:
        return "OURO_BRANCO"
    else:
        return "OUTROS"

def gerar_pdf(total_arquivos, total_erros):
    buffer = BytesIO()
    c = canvas.Canvas(buffer)

    c.setFont("Helvetica", 14)
    c.drawString(100, 800, "RELATÓRIO SIOPE PRO MAX")

    c.setFont("Helvetica", 12)
    c.drawString(100, 750, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawString(100, 720, f"Arquivos: {total_arquivos}")
    c.drawString(100, 690, f"Correções: {total_erros}")

    c.save()
    buffer.seek(0)

    return buffer

# ================= DASHBOARD =================

@app.route("/home")
@login_required
def home():
    logs = FileLog.query.all()

    meses = defaultdict(int)
    for l in logs:
        mes = datetime.now().strftime("%m/%Y")
        meses[mes] += l.corrections

    return render_template(
        "home.html",
        logs=logs,
        meses=list(meses.keys()),
        valores=list(meses.values())
    )

# ================= PROCESSAMENTO =================

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    files = request.files.getlist("file")

    zip_buffer = BytesIO()
    total_erros = 0

    with zipfile.ZipFile(zip_buffer, "w") as zip_file:

        for file in files:
            df = pd.read_excel(file, header=None)

            linhas = []
            erros = 0
            municipio = "OUTROS"

            for _, row in df.iterrows():
                if pd.isna(row[0]): continue

                texto = str(row[0])
                municipio = detectar_municipio(texto)

                partes = texto.split(';')

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

            nome_saida = f"{municipio}/{file.filename.replace('.xlsx','_CORRIGIDO.xlsx')}"
            zip_file.writestr(nome_saida, excel_buffer.read())

            log = FileLog(filename=file.filename, corrections=erros)
            db.session.add(log)

            total_erros += erros

        pdf = gerar_pdf(len(files), total_erros)
        zip_file.writestr("RELATORIO.pdf", pdf.read())

    db.session.commit()

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name="SIOPE_RESULTADO.zip",
        mimetype="application/zip"
    )

# ================= START =================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()