from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///conquistas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'segredo123'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ------------------ MODELOS ------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), default="https://via.placeholder.com/150")
    bio = db.Column(db.String(200), default="")

class Conquista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    jogo = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Integer, default=1)
    descricao = db.Column(db.String(200), nullable=False)
    foto = db.Column(db.String(200), nullable=False)  # novo campo obrigatório
    data = db.Column(db.DateTime, default=datetime.utcnow)

class Desafio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    criador_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    data_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    data_fim = db.Column(db.DateTime)

class ParticipacaoDesafio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    desafio_id = db.Column(db.Integer, db.ForeignKey('desafio.id'))
    pontos = db.Column(db.Integer, default=0)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ FUNÇÕES ------------------
def calcular_pontos(conquista):
    if conquista.tipo == "zerar":
        return 50 + (conquista.quantidade - 1) * 20
    elif conquista.tipo == "inimigos":
        return (conquista.quantidade // 100) * 1
    elif conquista.tipo == "especial":
        return 100
    else:
        return 10

def medalha(pontos):
    if pontos <= 100:
        return ("🥉 Bronze", "bronze")
    elif pontos <= 300:
        return ("🥈 Prata", "prata")
    elif pontos <= 600:
        return ("🥇 Ouro", "ouro")
    elif pontos >= 1000:
        return ("🏆 Platina", "platina")
    else:
        return ("⭐ Intermediário", "intermediario")

def calcular_ranking():
    ranking = {}
    conquistas = Conquista.query.all()
    for c in conquistas:
        usuario = User.query.get(c.usuario_id).username
        pontos = calcular_pontos(c)
        ranking[usuario] = ranking.get(usuario, 0) + pontos
    return [(usuario, pontos, *medalha(pontos)) for usuario, pontos in sorted(ranking.items(), key=lambda x: x[1], reverse=True)]

# ------------------ ROTAS ------------------
@app.route("/")
@login_required
def dashboard():
    conquistas = Conquista.query.filter_by(usuario_id=current_user.id).all()
    pontos = sum([calcular_pontos(c) for c in conquistas])
    nivel = medalha(pontos)
    return render_template("dashboard.html", conquistas=conquistas, pontos=pontos, nivel=nivel)


class FotoConquista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conquista_id = db.Column(db.Integer, db.ForeignKey('conquista.id'))
    caminho = db.Column(db.String(200), nullable=False)


@app.route("/add", methods=["POST"])
@login_required
def add():
    jogo = request.form.get("jogo")
    tipo = request.form.get("tipo")
    quantidade = int(request.form.get("quantidade"))
    descricao = request.form.get("descricao")
    fotos = request.files.getlist("fotos")  # lista de arquivos

    nova = Conquista(usuario_id=current_user.id, jogo=jogo, tipo=tipo,
                     quantidade=quantidade, descricao=descricao)
    db.session.add(nova)
    db.session.commit()

    # salvar cada foto
    for foto in fotos:
        caminho = f"static/uploads/{foto.filename}"
        foto.save(caminho)
        registro = FotoConquista(conquista_id=nova.id, caminho=caminho)
        db.session.add(registro)

    db.session.commit()

    return redirect(url_for("dashboard"))
@app.route("/ranking")
@login_required
def ranking():
    return render_template("ranking.html", ranking=calcular_ranking())

@app.route("/perfil/<username>")
@login_required
def perfil(username):
    usuario = User.query.filter_by(username=username).first_or_404()
    conquistas = Conquista.query.filter_by(usuario_id=usuario.id).all()
    pontos = sum([calcular_pontos(c) for c in conquistas])
    nivel = medalha(pontos)

    jogos_zerados = sum([c.quantidade for c in conquistas if c.tipo == "zerar"])
    inimigos_mortos = sum([c.quantidade for c in conquistas if c.tipo == "inimigos"])
    especiais = sum([1 for c in conquistas if c.tipo == "especial"])

    return render_template("perfil.html",
                           usuario=usuario.username,
                           avatar=usuario.avatar,
                           bio=usuario.bio,
                           conquistas=conquistas,
                           pontos=pontos,
                           nivel=nivel,
                           jogos_zerados=jogos_zerados,
                           inimigos_mortos=inimigos_mortos,
                           especiais=especiais)

# ------------------ DESAFIOS ------------------
@app.route("/desafios")
@login_required
def desafios():
    lista = Desafio.query.order_by(Desafio.data_fim.asc()).all()
    return render_template("desafios.html", desafios=lista)

@app.route("/desafios/criar", methods=["GET", "POST"])
@login_required
def criar_desafio():
    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        data_fim = request.form.get("data_fim")
        novo = Desafio(
            titulo=titulo,
            descricao=descricao,
            criador_id=current_user.id,
            data_fim=datetime.strptime(data_fim, "%Y-%m-%d")
        )
        db.session.add(novo)
        db.session.commit()
        flash("Desafio criado com sucesso!")
        return redirect(url_for("desafios"))
    return render_template("criar_desafio.html")

@app.route("/desafios/entrar/<int:desafio_id>")
@login_required
def entrar_desafio(desafio_id):
    desafio = Desafio.query.get_or_404(desafio_id)
    existente = ParticipacaoDesafio.query.filter_by(usuario_id=current_user.id, desafio_id=desafio.id).first()
    if not existente:
        novo = ParticipacaoDesafio(usuario_id=current_user.id, desafio_id=desafio.id)
        db.session.add(novo)
        db.session.commit()
        flash("Você entrou no desafio!")
    else:
        flash("Você já está participando deste desafio.")
    return redirect(url_for("desafios"))

@app.route("/desafios/<int:desafio_id>/ranking")
@login_required
def ranking_desafio(desafio_id):
    desafio = Desafio.query.get_or_404(desafio_id)
    participacoes = ParticipacaoDesafio.query.filter_by(desafio_id=desafio.id).all()
    ranking = sorted(participacoes, key=lambda p: p.pontos, reverse=True)
    ranking_view = [(User.query.get(p.usuario_id).username, p.pontos) for p in ranking]
    return render_template("ranking_desafio.html", desafio=desafio, ranking=ranking_view)

# ------------------ LOGIN / CADASTRO ------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Usuário ou senha inválidos")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        avatar = request.form.get("avatar") or "https://via.placeholder.com/150"
        bio = request.form.get("bio") or ""
        if User.query.filter_by(username=username).first():
            flash("Usuário já existe")
        else:
            hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")
            novo = User(username=username, password=hashed_pw, avatar=avatar, bio=bio)
            db.session.add(novo)
            db.session.commit()
            flash("Cadastro realizado! Faça login.")
            return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))
@app.route("/desafios/<int:desafio_id>/encerrar")
@login_required
def encerrar_desafio(desafio_id):
    desafio = Desafio.query.get_or_404(desafio_id)

    # pega ranking dos participantes
    participacoes = ParticipacaoDesafio.query.filter_by(desafio_id=desafio.id).all()
    if not participacoes:
        flash("Nenhum participante neste desafio.")
        return redirect(url_for("desafios"))

    # ordena pelo maior número de pontos
    vencedor = max(participacoes, key=lambda p: p.pontos)

    # marca troféu para o vencedor
    vencedor.trofeu = True
    db.session.commit()

    flash(f"Desafio '{desafio.titulo}' encerrado! 🏆 Vencedor: {User.query.get(vencedor.usuario_id).username}")
    return redirect(url_for("ranking_desafio", desafio_id=desafio.id))
if __name__ == "__main__":
    app.run(debug=True)