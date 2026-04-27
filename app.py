
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Organization, FileLog
import random
import io
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config['SECRET_KEY'] = 'empresa_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect('/dashboard')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        try:
            org_name = request.form.get('org')
            email = request.form.get('email')
            password = request.form.get('password')

            if not org_name or not email or not password:
                return "Preencha todos os campos"

            org = Organization(name=org_name)
            db.session.add(org)
            db.session.commit()

            user = User(
                email=email,
                password=generate_password_hash(password),
                org_id=org.id
            )
            db.session.add(user)
            db.session.commit()

            return redirect('/')

        except Exception as e:
            return f"Erro ao cadastrar: {str(e)}"

    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    files = FileLog.query.filter_by(org_id=current_user.org_id).all()
    return render_template('dashboard.html', files=files)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    files = request.files.getlist("files")
    for f in files:
        log = FileLog(
            filename=f.filename,
            org_id=current_user.org_id,
            corrections=random.randint(50,300)
        )
        db.session.add(log)
    db.session.commit()
    return jsonify({"status":"ok"})

@app.route('/api/chart')
@login_required
def chart():
    data = FileLog.query.filter_by(org_id=current_user.org_id).all()
    return jsonify({
        "labels":[f.filename for f in data],
        "values":[f.corrections for f in data]
    })

@app.route('/pdf')
@login_required
def pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    y = 800
    p.drawString(50, y, "Relatório SIOPE")
    y -= 30

    files = FileLog.query.filter_by(org_id=current_user.org_id).all()

    for f in files:
        p.drawString(50, y, f"{f.filename} - {f.corrections}")
        y -= 20

    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="relatorio.pdf", mimetype='application/pdf')

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')

if __name__ == "__main__":
    with app.app_context():
    db.drop_all()
    db.create_all()
