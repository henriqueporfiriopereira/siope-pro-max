from flask import Flask, render_template, request, redirect, send_file
from models import db, User, FileLog
from flask_login import LoginManager, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "siope_secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

UPLOAD = "uploads"
os.makedirs(UPLOAD, exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["user"]).first()
        if user and check_password_hash(user.password, request.form["pass"]):
            login_user(user)
            return redirect("/home")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        senha = generate_password_hash(request.form["pass"])
        user = User(username=request.form["user"], password=senha)
        db.session.add(user)
        db.session.commit()
        return redirect("/")
    return render_template("register.html")

@app.route("/home")
@login_required
def home():
    logs = FileLog.query.all()

    nomes = [l.filename for l in logs]
    correcoes = [l.corrections for l in logs]

    total_arquivos = len(logs)
    total_correcoes = sum(correcoes)

    return render_template(
        "home.html",
        logs=logs,
        nomes=nomes,
        correcoes=correcoes,
        total_arquivos=total_arquivos,
        total_correcoes=total_correcoes
    )

from flask import redirect, url_for

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    files = request.files.getlist("file")

    for file in files:
        path = os.path.join(UPLOAD, file.filename)
        file.save(path)

        df = pd.read_excel(path, header=None)
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

        out = path.replace(".xlsx","_CORRIGIDO.xlsx")
        pd.DataFrame(linhas).to_excel(out, index=False, header=False)

        log = FileLog(filename=file.filename, corrections=erros)
        db.session.add(log)

    db.session.commit()

    # 🔥 VOLTA PRO DASHBOARD
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
if __name__ == "__main__":
    app.run()