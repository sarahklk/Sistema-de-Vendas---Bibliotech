import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask_migrate import Migrate
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bibliotech.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "segredo123"

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    senha = db.Column(db.String(200))
    tipo = db.Column(db.String(20), default="Cliente")
    status = db.Column(db.String(20), default="Ativo")

class Livro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    autor = db.Column(db.String(100))
    genero = db.Column(db.String(50))
    preco = db.Column(db.Float)
    capa = db.Column(db.String(200))
    previa = db.Column(db.Text)


class Compra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    livro_id = db.Column(db.Integer, db.ForeignKey("livro.id"))
    status = db.Column(db.String(20), default="Pago")

    usuario = db.relationship("Usuario", backref="compras")
    livro = db.relationship("Livro", backref="compras")


class Historico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer)
    titulo = db.Column(db.String(200))
    preco = db.Column(db.Float)
    data_compra = db.Column(db.DateTime, default=datetime.utcnow)

def enviar_email_com_ebooks(destino_email, anexos):
    servidor = "smtp.gmail.com"
    porta = 587
    email_sistema = os.environ.get("SMTP_EMAIL")
    senha_sistema = os.environ.get("SMTP_PASS")

    if not email_sistema or not senha_sistema:
        return False, "Servidor de e-mail não configurado."

    msg = MIMEMultipart()
    msg["From"] = email_sistema
    msg["To"] = destino_email
    msg["Subject"] = "Seus eBooks - Bibliotech"
    msg.attach(MIMEText("Obrigado pela compra! Seus eBooks estão anexados."))

    for arquivo in anexos:
        with open(arquivo, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=os.path.basename(arquivo))
            msg.attach(part)

    try:
        with smtplib.SMTP(servidor, porta) as smtp:
            smtp.starttls()
            smtp.login(email_sistema, senha_sistema)
            smtp.send_message(msg)
        return True, "E-mail enviado!"
    except:
        return False, "Falha ao enviar e-mail."

@app.route("/")
def index():
    livros = Livro.query.all()
    return render_template("index.html", livros=livros)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        if Usuario.query.filter_by(email=email).first():
            flash("E-mail já cadastrado!", "danger")
            return redirect(url_for("register"))

        novo = Usuario(
            nome=nome,
            email=email,
            senha=generate_password_hash(senha)
        )
        db.session.add(novo)
        db.session.commit()

        flash("Cadastro realizado!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        user = Usuario.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.senha, senha):
            flash("Credenciais inválidas!", "danger")
            return redirect(url_for("login"))

        session["logged_in"] = True
        session["user_id"] = user.id
        session["user_name"] = user.nome
        session["user_email"] = user.email

        return redirect(url_for("minha_biblioteca"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu.", "info")
    return redirect(url_for("index"))

@app.route("/adicionar_carrinho/<int:livro_id>", methods=["POST"])
def adicionar_carrinho(livro_id):
    if "carrinho" not in session:
        session["carrinho"] = []

    if livro_id not in session["carrinho"]:
        session["carrinho"].append(livro_id)

    session.modified = True
    flash("Livro adicionado!", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/remover_carrinho/<int:livro_id>")
def remover_carrinho(livro_id):
    if "carrinho" in session and livro_id in session["carrinho"]:
        session["carrinho"].remove(livro_id)
        session.modified = True
    return redirect(url_for("carrinho"))


@app.route("/carrinho")
def carrinho():
    itens = session.get("carrinho", [])
    livros = Livro.query.filter(Livro.id.in_(itens)).all()
    total = sum(l.preco for l in livros)
    return render_template("carrinho.html", livros=livros, total=total)

@app.route("/checkout")
def checkout():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    itens = session.get("carrinho", [])
    livros = Livro.query.filter(Livro.id.in_(itens)).all()
    total = sum(l.preco for l in livros)

    return render_template("checkout.html", livros=livros, total=total)


@app.route("/finalizar_compra", methods=["POST"])
def finalizar_compra():
    cpf = request.form.get("cpf")
    telefone = request.form.get("telefone")
    pagamento = request.form.get("pagamento")

    carrinho = session.get("carrinho", [])

    livros = Livro.query.filter(Livro.id.in_(carrinho)).all()
    total = sum(l.preco for l in livros)

    session["carrinho"] = []

    return redirect(url_for(
        "comprovante",
        cpf=cpf,
        telefone=telefone,
        pagamento=pagamento,
        total=total,
        livros=carrinho  
    ))
@app.route("/historico")
def historico():
    if "user_id" not in session:
        return redirect(url_for("login"))

    compras = Historico.query.filter_by(usuario_id=session["user_id"]).all()
    return render_template("historico.html", compras=compras)

@app.route("/minha_biblioteca")
def minha_biblioteca():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    compras = Compra.query.filter_by(usuario_id=session["user_id"]).all()
    livros = [Livro.query.get(c.livro_id) for c in compras]

    return render_template("minha_biblioteca.html", livros=livros)

@app.route("/previa/<int:livro_id>")
def previa(livro_id):
    livro = Livro.query.get_or_404(livro_id)
    return render_template("previa.html", livro=livro)


@app.route("/ler/<int:livro_id>")
def ler(livro_id):
    livro = Livro.query.get_or_404(livro_id)
    return render_template("aviso_comprar.html", livro=livro)

@app.route("/pesquisar")
def pesquisar():
    termo = request.args.get("q", "").strip()

    if termo == "":
        flash("Digite algo para pesquisar.", "info")
        return redirect(url_for("index"))

    resultados = Livro.query.filter(
        or_(
            Livro.titulo.ilike(f"%{termo}%"),
            Livro.autor.ilike(f"%{termo}%")
        )
    ).all()

    return render_template("pesquisa.html", livros=resultados, termo=termo)
livros_inseridos = False

@app.before_request
def inserir_livros_iniciais():
    global livros_inseridos

    if not livros_inseridos:
        if Livro.query.count() == 0:
            l1 = Livro(
                titulo="O Essencial de Python",
                autor="João da Silva",
                genero="Tecnologia",
                preco=29.90,
                capa="essencial_python.jpg",
                previa="Um guia essencial para aprender Python de forma prática e objetiva."
            )

            l2 = Livro(
                titulo="O Guia Definitivo de UX",
                autor="Maria Souza",
                genero="Design",
                preco=34.90,
                capa="guia_ux.jpg",
                previa="Domine conceitos fundamentais de UX e construa interfaces incríveis."
            )

            l3 = Livro(
                titulo="Lógica de Programação Moderna",
                autor="Carlos Andrade",
                genero="Tecnologia",
                preco=24.90,
                capa="logica_programacao.jpg",
                previa="Aprenda lógica de programação de forma clara e acessível."
            )

            db.session.add_all([l1, l2, l3])
            db.session.commit()
            print("Livros adicionados ao banco!")
        
        livros_inseridos = True
@app.route("/comprovante")
def comprovante():
    cpf = request.args.get("cpf")
    telefone = request.args.get("telefone")
    pagamento = request.args.get("pagamento")
    total = request.args.get("total")
    livros_ids = request.args.getlist("livros")

    livros = Livro.query.filter(Livro.id.in_(livros_ids)).all()

    return render_template(
        "comprovante.html",
        cpf=cpf,
        telefone=telefone,
        pagamento=pagamento,
        total=total,
        livros=livros
    )

if __name__ == "__main__":
    app.run(debug=True)
