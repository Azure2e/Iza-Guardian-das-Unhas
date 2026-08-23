#!/usr/bin/env python3
"""
Encanto Gelato — Sistema completo de sorveteria
Site + pedidos + PDV + estoque + módulo de segurança
"""
from datetime import datetime, timedelta
from functools import wraps
import json
import re
import secrets

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, g, abort, current_app
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from pix_module import build_pix_payload, make_txid

# Config injetada uma vez no start
CFG = Config()

app = Flask(__name__)
app.config["SECRET_KEY"] = CFG.secret_key
app.config["ENCANTO_CFG"] = CFG
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///encanto.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_NAME"] = "encanto_session"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

SESSION_IDLE_MINUTES = 30
MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 8

db = SQLAlchemy(app)

ROLES = {
    "admin": {
        "label": "Administrador",
        "perms": {"dashboard", "pdv", "pedidos", "produtos", "estoque", "relatorios", "seguranca"},
    },
    "gerente": {
        "label": "Gerente",
        "perms": {"dashboard", "pdv", "pedidos", "produtos", "estoque", "relatorios"},
    },
    "caixa": {
        "label": "Caixa",
        "perms": {"dashboard", "pdv", "pedidos"},
    },
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(300), default="")
    category = db.Column(db.String(40), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(400), default="")
    unit = db.Column(db.String(30), default="un")
    active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "price": self.price,
            "stock": self.stock,
            "image": self.image,
            "unit": self.unit,
            "active": self.active,
        }


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default="")
    order_type = db.Column(db.String(20), default="balcao")
    address = db.Column(db.String(250), default="")
    notes = db.Column(db.String(300), default="")
    payment = db.Column(db.String(20), default="pix")
    status = db.Column(db.String(20), default="aguardando_pix")
    total = db.Column(db.Float, default=0)
    pix_txid = db.Column(db.String(32), default="")
    pix_copia_cola = db.Column(db.String(512), default="")
    pix_paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name = db.Column(db.String(120))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0)
    product = db.relationship("Product")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="caixa")
    active = db.Column(db.Boolean, default=True)
    failed_logins = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(60), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw, method="scrypt")

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def is_locked(self):
        return bool(self.locked_until and self.locked_until > datetime.utcnow())

    def has_perm(self, perm):
        return perm in ROLES.get(self.role, {}).get("perms", set())


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(60), default="")
    action = db.Column(db.String(80), nullable=False)
    detail = db.Column(db.String(400), default="")
    ip = db.Column(db.String(60), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
def client_ip():
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:60]


def audit(action, detail=""):
    db.session.add(AuditLog(
        user_id=session.get("user_id"),
        username=session.get("username") or "",
        action=action,
        detail=(detail or "")[:400],
        ip=client_ip(),
    ))
    db.session.commit()


def current_user():
    if getattr(g, "user", None):
        return g.user
    uid = session.get("user_id")
    g.user = db.session.get(User, uid) if uid else None
    return g.user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user.active:
            session.clear()
            flash("Faça login para acessar o painel.", "warning")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


def role_required(*perms):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or not user.active:
                flash("Faça login para acessar o painel.", "warning")
                return redirect(url_for("admin_login"))
            if not any(user.has_perm(p) for p in perms):
                flash("Você não tem permissão para esta área.", "error")
                return redirect(url_for("admin_dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return deco


def valid_password(pw):
    if len(pw or "") < MIN_PASSWORD:
        return "A senha precisa ter pelo menos 8 caracteres."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "A senha precisa ter letras e números."
    return None


def issue_csrf():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def csrf_ok():
    sent = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("_csrf")
        or (request.get_json(silent=True) or {}).get("_csrf")
    )
    return bool(sent) and secrets.compare_digest(str(sent), session.get("_csrf") or "")


@app.before_request
def security_gate():
    g.user = None
    session.permanent = True
    last = session.get("_last_seen")
    if session.get("user_id") and last:
        try:
            seen = datetime.fromisoformat(last)
            if datetime.utcnow() - seen > timedelta(minutes=SESSION_IDLE_MINUTES):
                session.clear()
                if request.path.startswith("/admin") and request.path != "/admin/login":
                    flash("Sessão expirada por inatividade.", "warning")
                    return redirect(url_for("admin_login"))
        except ValueError:
            session["_last_seen"] = datetime.utcnow().isoformat()
    if session.get("user_id"):
        session["_last_seen"] = datetime.utcnow().isoformat()

    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.path.startswith("/admin") and request.path != "/admin/login":
            if not csrf_ok():
                abort(400, description="Token de segurança inválido. Recarregue a página.")


@app.after_request
def security_headers(resp):
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["X-XSS-Protection"] = "0"
    resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return resp


@app.context_processor
def inject_globals():
    user = current_user() if session.get("user_id") else None
    return {
        "csrf_token": issue_csrf(),
        "current_user": user,
        "ROLES": ROLES,
    }


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
SEED = [
    dict(name="Chocolate Belga", description="Cacau belga intenso, cremoso e aveludado.", category="sorvete", price=12.0, stock=80, unit="bola",
         image="https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=800&q=80"),
    dict(name="Morango com Nata", description="Morango fresco com nata bem cremosa.", category="sorvete", price=11.0, stock=70, unit="bola",
         image="https://images.unsplash.com/photo-1488900128323-3681cf4be282?w=800&q=80"),
    dict(name="Flocos", description="Creme clássico com lascas de chocolate.", category="sorvete", price=10.0, stock=90, unit="bola",
         image="https://images.unsplash.com/photo-1501443762994-82bd5dace89a?w=800&q=80"),
    dict(name="Ninho com Nutella", description="Leite Ninho com generoso recheio de Nutella.", category="sorvete", price=14.0, stock=50, unit="bola",
         image="https://images.unsplash.com/photo-1497034825429-c343d7c6a68f?w=800&q=80"),
    dict(name="Doce de Leite", description="Doce de leite argentino, doce na medida.", category="sorvete", price=12.0, stock=60, unit="bola",
         image="https://images.unsplash.com/photo-1551024506-0bccd828d307?w=800&q=80"),
    dict(name="Pistache", description="Pistache siciliano, o queridinho gourmet.", category="sorvete", price=15.0, stock=40, unit="bola",
         image="https://images.unsplash.com/photo-1570197788417-0e02308cbf6e?w=800&q=80"),
    dict(name="Cookies & Cream", description="Baunilha com pedaços crocantes de cookie.", category="sorvete", price=13.0, stock=55, unit="bola",
         image="https://images.unsplash.com/photo-1633933358116-a27b902fad35?w=800&q=80"),
    dict(name="Brigadeiro", description="O clássico brasileiro em versão gelada.", category="sorvete", price=12.0, stock=65, unit="bola",
         image="https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=800&q=80"),
    dict(name="Romeu e Julieta", description="Goiabada com queijo, combinação perfeita.", category="sorvete", price=12.0, stock=45, unit="bola",
         image="https://images.unsplash.com/photo-1516559828984-fb7b7ecbc5f4?w=800&q=80"),
    dict(name="Maracujá", description="Azedinho, refrescante e tropical.", category="sorvete", price=11.0, stock=50, unit="bola",
         image="https://images.unsplash.com/photo-1505394033641-40c6ad1178d7?w=800&q=80"),
    dict(name="Açaí 300 ml", description="Açaí puro batido na hora, cremoso.", category="acai", price=16.0, stock=40, unit="copo",
         image="https://images.unsplash.com/photo-1590301157890-4810ed352733?w=800&q=80"),
    dict(name="Açaí 500 ml", description="Porção média, ideal para uma pessoa.", category="acai", price=22.0, stock=35, unit="copo",
         image="https://images.unsplash.com/photo-1590301157890-4810ed352733?w=800&q=80"),
    dict(name="Açaí 700 ml", description="Para compartilhar. Açaí bem consistente.", category="acai", price=28.0, stock=25, unit="copo",
         image="https://images.unsplash.com/photo-1590301157890-4810ed352733?w=800&q=80"),
    dict(name="Milkshake Chocolate", description="Cremoso, com sorvete de chocolate e calda.", category="milkshake", price=18.0, stock=30, unit="copo",
         image="https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=800&q=80"),
    dict(name="Milkshake Morango", description="Morango natural batido com sorvete.", category="milkshake", price=18.0, stock=30, unit="copo",
         image="https://images.unsplash.com/photo-1579954115545-a95591f28bfc?w=800&q=80"),
    dict(name="Milkshake Ovomaltine", description="Crocante por fora, cremoso por dentro.", category="milkshake", price=20.0, stock=20, unit="copo",
         image="https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=800&q=80"),
    dict(name="Picolé Leite Condensado", description="Cremoso e bem doce.", category="picole", price=8.0, stock=100, unit="un",
         image="https://images.unsplash.com/photo-1633933358116-a27b902fad35?w=800&q=80"),
    dict(name="Picolé Manga", description="Polpa de manga, refrescante.", category="picole", price=7.0, stock=80, unit="un",
         image="https://images.unsplash.com/photo-1501443762994-82bd5dace89a?w=800&q=80"),
    dict(name="Picolé Limão", description="Azedinho que mata a sede.", category="picole", price=7.0, stock=80, unit="un",
         image="https://images.unsplash.com/photo-1505394033641-40c6ad1178d7?w=800&q=80"),
    dict(name="Calda de Chocolate", description="Calda quente artesanal.", category="adicional", price=3.0, stock=200, unit="un", image=""),
    dict(name="Granulado Colorido", description="Crocante e divertido.", category="adicional", price=2.0, stock=200, unit="un", image=""),
    dict(name="Leite em Pó", description="Camada generosa de Ninho.", category="adicional", price=3.0, stock=150, unit="un", image=""),
    dict(name="Paçoca Triturada", description="Amendoim no ponto certo.", category="adicional", price=3.5, stock=120, unit="un", image=""),
    dict(name="Casquinha Crocante", description="Casquinha waffle recém-assada.", category="adicional", price=3.0, stock=80, unit="un", image=""),
    dict(name="Pote 500 ml (1 sabor)", description="Leve seu sabor favorito para casa.", category="pote", price=28.0, stock=40, unit="pote",
         image="https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=800&q=80"),
    dict(name="Pote 1 Litro (2 sabores)", description="Ideal para a família.", category="pote", price=48.0, stock=25, unit="pote",
         image="https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=800&q=80"),
]


def seed_if_empty():
    if Product.query.count() == 0:
        for p in SEED:
            db.session.add(Product(**p))
        db.session.commit()
    if User.query.count() == 0:
        admin = User(name="Administrador", username="admin", role="admin", active=True)
        admin.set_password(CFG.admin_pass)
        caixa = User(name="Caixa da loja", username="caixa", role="caixa", active=True)
        caixa.set_password(CFG.caixa_pass)
        db.session.add_all([admin, caixa])
        db.session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("sorvete", "Sorvetes"),
    ("acai", "Açaí"),
    ("milkshake", "Milkshakes"),
    ("picole", "Picolés"),
    ("pote", "Potes"),
    ("adicional", "Adicionais"),
]
STATUS_LABEL = {
    "novo": "Novo",
    "aguardando_pix": "Aguardando PIX",
    "pago": "PIX pago",
    "preparando": "Preparando",
    "pronto": "Pronto",
    "entregue": "Entregue",
    "cancelado": "Cancelado",
}
TYPE_LABEL = {"balcao": "Balcão", "retirada": "Retirada", "delivery": "Delivery"}


def brl(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


app.jinja_env.filters["brl"] = brl
app.jinja_env.globals["CATEGORIES"] = CATEGORIES
app.jinja_env.globals["STATUS_LABEL"] = STATUS_LABEL
app.jinja_env.globals["TYPE_LABEL"] = TYPE_LABEL


def today_range():
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def create_order_from_payload(data):
    items = data.get("items")
    if isinstance(items, str):
        items = json.loads(items)
    if not items:
        return None, "Carrinho vazio."
    name = (data.get("customer_name") or "").strip()
    if not name:
        return None, "Informe o nome."
    order = Order(
        customer_name=name[:120],
        phone=(data.get("phone") or "").strip()[:30],
        order_type=data.get("order_type") if data.get("order_type") in TYPE_LABEL else "retirada",
        address=(data.get("address") or "").strip()[:250],
        notes=(data.get("notes") or "").strip()[:300],
        payment="pix",
        status="aguardando_pix",
    )
    total = 0.0
    for it in items:
        prod = db.session.get(Product, int(it["id"]))
        if not prod or not prod.active:
            continue
        qty = max(1, int(it.get("qty", 1)))
        if prod.stock < qty:
            return None, f"Estoque insuficiente: {prod.name}"
        prod.stock -= qty
        total += qty * prod.price
        order.items.append(OrderItem(
            product_id=prod.id, product_name=prod.name, quantity=qty, unit_price=prod.price
        ))
    if not order.items:
        return None, "Nenhum item válido."
    order.total = total
    db.session.add(order)
    db.session.flush()  # obtém order.id
    order.pix_txid = make_txid(order.id)
    cfg: Config = current_app.config.get("ENCANTO_CFG", CFG)
    if cfg.pix_configured:
        try:
            order.pix_copia_cola = build_pix_payload(
                amount=order.total,
                txid=order.pix_txid,
                key=cfg.pix_key,
                merchant=cfg.pix_merchant,
                city=cfg.pix_city,
                description=f"Pedido {order.id} Encanto Gelato",
            )
        except ValueError:
            order.pix_copia_cola = ""
    else:
        order.pix_copia_cola = ""
    db.session.commit()
    return order, None


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    destaques = Product.query.filter_by(active=True).filter(
        Product.category.in_(["sorvete", "acai", "milkshake"])
    ).limit(8).all()
    return render_template("index.html", destaques=destaques)


@app.route("/cardapio")
def cardapio():
    cat = request.args.get("cat")
    q = Product.query.filter_by(active=True)
    if cat:
        q = q.filter_by(category=cat)
    products = q.order_by(Product.category, Product.name).all()
    grouped = {}
    for p in products:
        grouped.setdefault(p.category, []).append(p)
    return render_template("cardapio.html", grouped=grouped, cat=cat)


@app.route("/pedido")
def pedido():
    products = Product.query.filter_by(active=True).order_by(Product.category, Product.name).all()
    grouped = {}
    for p in products:
        grouped.setdefault(p.category, []).append(p)
    return render_template("pedido.html", grouped=grouped)


@app.route("/pedido", methods=["POST"])
def pedido_criar():
    if not csrf_ok():
        return jsonify({"ok": False, "msg": "Sessão expirada. Recarregue a página."}), 400
    data = request.get_json(silent=True) or request.form
    order, err = create_order_from_payload(data)
    if err:
        return jsonify({"ok": False, "msg": err}), 400
    return jsonify({"ok": True, "order_id": order.id, "total": order.total})


@app.route("/confirmacao/<int:oid>")
def confirmacao(oid):
    order = db.session.get(Order, oid)
    if not order:
        return redirect(url_for("index"))
    cfg: Config = current_app.config.get("ENCANTO_CFG", CFG)
    # regenera se chave foi configurada depois e ainda não tem payload
    if cfg.pix_configured and not order.pix_copia_cola and order.status == "aguardando_pix":
        if not order.pix_txid:
            order.pix_txid = make_txid(order.id)
        try:
            order.pix_copia_cola = build_pix_payload(
                amount=order.total,
                txid=order.pix_txid,
                key=cfg.pix_key,
                merchant=cfg.pix_merchant,
                city=cfg.pix_city,
                description=f"Pedido {order.id} Encanto Gelato",
            )
            db.session.commit()
        except ValueError:
            pass
    return render_template(
        "confirmacao.html",
        order=order,
        pix=cfg.as_pix_dict(),
    )


@app.route("/api/pedido/<int:oid>/status")
def pedido_status_api(oid):
    order = db.session.get(Order, oid)
    if not order:
        return jsonify({"ok": False}), 404
    return jsonify({
        "ok": True,
        "status": order.status,
        "label": STATUS_LABEL.get(order.status, order.status),
        "paid": order.status in ("pago", "preparando", "pronto", "entregue"),
    })


@app.route("/contato")
def contato():
    return render_template("contato.html")


@app.route("/garantia")
def garantia():
    return render_template("garantia.html")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user():
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = (request.form.get("user") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter(db.func.lower(User.username) == username).first()
        if not user or not user.active:
            flash("Usuário ou senha inválidos.", "error")
            audit("login_falhou", f"usuario={username}")
            return render_template("admin/login.html")
        if user.is_locked():
            mins = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
            flash(f"Conta bloqueada. Tente de novo em {mins} min.", "error")
            audit("login_bloqueado", user.username)
            return render_template("admin/login.html")
        if not user.check_password(password):
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)
                user.failed_logins = 0
                flash("Muitas tentativas. Conta bloqueada por 15 minutos.", "error")
                audit("conta_bloqueada", user.username)
            else:
                left = MAX_LOGIN_ATTEMPTS - user.failed_logins
                flash(f"Usuário ou senha inválidos. Restam {left} tentativas.", "error")
                audit("login_falhou", user.username)
            db.session.commit()
            return render_template("admin/login.html")
        user.failed_logins = 0
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = client_ip()
        db.session.commit()
        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role
        session["_last_seen"] = datetime.utcnow().isoformat()
        issue_csrf()
        audit("login_ok", user.username)
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    if session.get("username"):
        audit("logout", session.get("username"))
    session.clear()
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@app.route("/admin")
@login_required
@role_required("dashboard")
def admin_dashboard():
    start, end = today_range()
    today_orders = Order.query.filter(Order.created_at >= start, Order.created_at < end).all()
    today_sales = sum(o.total for o in today_orders if o.status != "cancelado")
    today_count = len([o for o in today_orders if o.status != "cancelado"])
    pending = Order.query.filter(Order.status.in_(["novo", "aguardando_pix", "pago", "preparando"])).count()
    low_stock = Product.query.filter(Product.stock <= 10, Product.active.is_(True)).all()
    days = []
    for i in range(6, -1, -1):
        d0 = start - timedelta(days=i)
        d1 = d0 + timedelta(days=1)
        s = db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)).filter(
            Order.created_at >= d0, Order.created_at < d1, Order.status != "cancelado"
        ).scalar()
        days.append({"label": d0.strftime("%d/%m"), "total": float(s)})
    top = (
        db.session.query(OrderItem.product_name, db.func.sum(OrderItem.quantity).label("qtd"))
        .join(Order).filter(Order.status != "cancelado")
        .group_by(OrderItem.product_name).order_by(db.desc("qtd")).limit(5).all()
    )
    recent = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    return render_template(
        "admin/dashboard.html",
        today_sales=today_sales, today_count=today_count, pending=pending,
        low_stock=low_stock, days=days, top=top, recent=recent,
        products_count=Product.query.filter_by(active=True).count(),
    )


@app.route("/admin/pdv")
@login_required
@role_required("pdv")
def admin_pdv():
    products = Product.query.filter_by(active=True).order_by(Product.category, Product.name).all()
    grouped = {}
    for p in products:
        grouped.setdefault(p.category, []).append(p)
    return render_template("admin/pdv.html", grouped=grouped)


@app.route("/admin/pedidos")
@login_required
@role_required("pedidos")
def admin_pedidos():
    status = request.args.get("status")
    q = Order.query.order_by(Order.created_at.desc())
    if status:
        q = q.filter_by(status=status)
    return render_template("admin/pedidos.html", orders=q.limit(200).all(), status=status)


@app.route("/admin/pedidos/<int:oid>/status", methods=["POST"])
@login_required
@role_required("pedidos")
def admin_pedido_status(oid):
    order = db.session.get(Order, oid)
    if not order:
        return jsonify({"ok": False}), 404
    new_status = request.form.get("status") or (request.get_json(silent=True) or {}).get("status")
    if new_status not in STATUS_LABEL:
        return jsonify({"ok": False}), 400
    if new_status == "cancelado" and order.status != "cancelado":
        for it in order.items:
            if it.product:
                it.product.stock += it.quantity
    old = order.status
    order.status = new_status
    if new_status == "pago" and not order.pix_paid_at:
        order.pix_paid_at = datetime.utcnow()
    db.session.commit()
    audit("pedido_status", f"#{order.id} {old}->{new_status}")
    flash("Status atualizado.", "success")
    return redirect(url_for("admin_pedidos"))


@app.route("/admin/pedidos/<int:oid>/confirmar-pix", methods=["POST"])
@login_required
@role_required("pedidos")
def admin_confirmar_pix(oid):
    order = db.session.get(Order, oid)
    if not order:
        flash("Pedido não encontrado.", "error")
        return redirect(url_for("admin_pedidos"))
    if order.status == "cancelado":
        flash("Pedido cancelado não pode ser confirmado.", "error")
        return redirect(url_for("admin_pedidos"))
    order.status = "pago"
    order.pix_paid_at = datetime.utcnow()
    db.session.commit()
    audit("pix_confirmado", f"#{order.id} {order.total}")
    flash(f"PIX do pedido #{order.id} confirmado.", "success")
    return redirect(url_for("admin_pedidos"))


@app.route("/admin/produtos")
@login_required
@role_required("produtos")
def admin_produtos():
    return render_template("admin/produtos.html", products=Product.query.order_by(Product.category, Product.name).all())


@app.route("/admin/produtos/novo", methods=["GET", "POST"])
@login_required
@role_required("produtos")
def admin_produto_novo():
    if request.method == "POST":
        p = Product(
            name=request.form["name"].strip()[:120],
            description=request.form.get("description", "").strip()[:300],
            category=request.form.get("category", "sorvete"),
            price=float(request.form.get("price") or 0),
            stock=int(request.form.get("stock") or 0),
            image=request.form.get("image", "").strip()[:400],
            unit=request.form.get("unit", "un").strip()[:30],
            active=bool(request.form.get("active")),
        )
        db.session.add(p)
        db.session.commit()
        audit("produto_novo", p.name)
        flash("Produto cadastrado.", "success")
        return redirect(url_for("admin_produtos"))
    return render_template("admin/produto_form.html", product=None)


@app.route("/admin/produtos/<int:pid>/editar", methods=["GET", "POST"])
@login_required
@role_required("produtos")
def admin_produto_editar(pid):
    product = db.session.get(Product, pid)
    if not product:
        return redirect(url_for("admin_produtos"))
    if request.method == "POST":
        product.name = request.form["name"].strip()[:120]
        product.description = request.form.get("description", "").strip()[:300]
        product.category = request.form.get("category", "sorvete")
        product.price = float(request.form.get("price") or 0)
        product.stock = int(request.form.get("stock") or 0)
        product.image = request.form.get("image", "").strip()[:400]
        product.unit = request.form.get("unit", "un").strip()[:30]
        product.active = bool(request.form.get("active"))
        db.session.commit()
        audit("produto_editar", product.name)
        flash("Produto atualizado.", "success")
        return redirect(url_for("admin_produtos"))
    return render_template("admin/produto_form.html", product=product)


@app.route("/admin/produtos/<int:pid>/toggle", methods=["POST"])
@login_required
@role_required("produtos")
def admin_produto_toggle(pid):
    product = db.session.get(Product, pid)
    if product:
        product.active = not product.active
        db.session.commit()
        audit("produto_toggle", f"{product.name} ativo={product.active}")
    return redirect(url_for("admin_produtos"))


@app.route("/admin/estoque", methods=["GET", "POST"])
@login_required
@role_required("estoque")
def admin_estoque():
    if request.method == "POST":
        product = db.session.get(Product, int(request.form["product_id"]))
        qty = int(request.form.get("qty") or 0)
        if product:
            product.stock = max(0, product.stock + qty)
            db.session.commit()
            audit("estoque", f"{product.name} {qty:+d} -> {product.stock}")
            flash(f"Estoque de {product.name} atualizado para {product.stock}.", "success")
        return redirect(url_for("admin_estoque"))
    return render_template("admin/estoque.html", products=Product.query.order_by(Product.stock.asc(), Product.name).all())


@app.route("/admin/relatorios")
@login_required
@role_required("relatorios")
def admin_relatorios():
    start, end = today_range()
    today_orders = Order.query.filter(Order.created_at >= start, Order.created_at < end, Order.status != "cancelado").all()
    all_ok = Order.query.filter(Order.status != "cancelado").all()
    by_type, by_pay = {}, {}
    for o in all_ok:
        by_type[o.order_type] = by_type.get(o.order_type, 0) + o.total
        by_pay[o.payment] = by_pay.get(o.payment, 0) + o.total
    items = (
        db.session.query(OrderItem.product_name, db.func.sum(OrderItem.quantity),
                         db.func.sum(OrderItem.quantity * OrderItem.unit_price))
        .join(Order).filter(Order.status != "cancelado")
        .group_by(OrderItem.product_name)
        .order_by(db.desc(db.func.sum(OrderItem.quantity))).all()
    )
    return render_template(
        "admin/relatorios.html",
        today_orders=today_orders,
        today_total=sum(o.total for o in today_orders),
        all_total=sum(o.total for o in all_ok),
        all_count=len(all_ok),
        by_type=by_type, by_pay=by_pay, items=items,
    )


# ---------------------------------------------------------------------------
# Security module
# ---------------------------------------------------------------------------
@app.route("/admin/seguranca")
@login_required
@role_required("seguranca")
def admin_seguranca():
    users = User.query.order_by(User.created_at.desc()).all()
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(80).all()
    return render_template("admin/seguranca.html", users=users, logs=logs)


@app.route("/admin/seguranca/usuarios", methods=["POST"])
@login_required
@role_required("seguranca")
def admin_usuario_criar():
    name = (request.form.get("name") or "").strip()
    username = (request.form.get("username") or "").strip().lower()
    password = request.form.get("password") or ""
    role = request.form.get("role") or "caixa"
    if not name or not username:
        flash("Preencha nome e usuário.", "error")
        return redirect(url_for("admin_seguranca"))
    if role not in ROLES:
        flash("Perfil inválido.", "error")
        return redirect(url_for("admin_seguranca"))
    err = valid_password(password)
    if err:
        flash(err, "error")
        return redirect(url_for("admin_seguranca"))
    if User.query.filter(db.func.lower(User.username) == username).first():
        flash("Este usuário já existe.", "error")
        return redirect(url_for("admin_seguranca"))
    user = User(name=name[:120], username=username[:60], role=role, active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    audit("usuario_criar", f"{username} ({role})")
    flash("Usuário criado.", "success")
    return redirect(url_for("admin_seguranca"))


@app.route("/admin/seguranca/usuarios/<int:uid>/toggle", methods=["POST"])
@login_required
@role_required("seguranca")
def admin_usuario_toggle(uid):
    user = db.session.get(User, uid)
    if not user:
        return redirect(url_for("admin_seguranca"))
    if user.id == session.get("user_id"):
        flash("Você não pode desativar a própria conta.", "error")
        return redirect(url_for("admin_seguranca"))
    if user.role == "admin" and user.active:
        others = User.query.filter_by(role="admin", active=True).count()
        if others <= 1:
            flash("Não é possível desativar o último administrador.", "error")
            return redirect(url_for("admin_seguranca"))
    user.active = not user.active
    if user.active:
        user.failed_logins = 0
        user.locked_until = None
    db.session.commit()
    audit("usuario_toggle", f"{user.username} ativo={user.active}")
    flash("Usuário atualizado.", "success")
    return redirect(url_for("admin_seguranca"))


@app.route("/admin/seguranca/usuarios/<int:uid>/reset", methods=["POST"])
@login_required
@role_required("seguranca")
def admin_usuario_reset(uid):
    user = db.session.get(User, uid)
    password = request.form.get("password") or ""
    err = valid_password(password)
    if not user or err:
        flash(err or "Usuário não encontrado.", "error")
        return redirect(url_for("admin_seguranca"))
    user.set_password(password)
    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()
    audit("usuario_reset_senha", user.username)
    flash(f"Senha de {user.username} redefinida.", "success")
    return redirect(url_for("admin_seguranca"))


@app.route("/admin/seguranca/senha", methods=["GET", "POST"])
@login_required
def admin_minha_senha():
    if request.method == "POST":
        user = current_user()
        current = request.form.get("current") or ""
        new = request.form.get("new") or ""
        confirm = request.form.get("confirm") or ""
        if not user.check_password(current):
            flash("Senha atual incorreta.", "error")
            return render_template("admin/senha.html")
        err = valid_password(new)
        if err:
            flash(err, "error")
            return render_template("admin/senha.html")
        if new != confirm:
            flash("A confirmação não confere.", "error")
            return render_template("admin/senha.html")
        user.set_password(new)
        db.session.commit()
        audit("troca_senha", user.username)
        flash("Senha alterada.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/senha.html")


# ---------------------------------------------------------------------------
def _ensure_pix_columns():
    """Adiciona colunas PIX em bancos já existentes (SQLite)."""
    try:
        cols = {row[1] for row in db.session.execute(db.text("PRAGMA table_info(order)")).fetchall()}
    except Exception:
        return
    alters = []
    if "pix_txid" not in cols:
        alters.append("ALTER TABLE \"order\" ADD COLUMN pix_txid VARCHAR(32) DEFAULT ''")
    if "pix_copia_cola" not in cols:
        alters.append("ALTER TABLE \"order\" ADD COLUMN pix_copia_cola VARCHAR(512) DEFAULT ''")
    if "pix_paid_at" not in cols:
        alters.append("ALTER TABLE \"order\" ADD COLUMN pix_paid_at DATETIME")
    for sql in alters:
        db.session.execute(db.text(sql))
    if alters:
        db.session.commit()


def create_app():
    with app.app_context():
        db.create_all()
        _ensure_pix_columns()
        seed_if_empty()
    return app


if __name__ == "__main__":
    create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
