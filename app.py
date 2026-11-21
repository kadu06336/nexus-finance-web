import csv
import io
import json
import os
from datetime import datetime
from functools import wraps

from flask import Flask, Response, jsonify, render_template, request
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("NEXUS_SECRET_KEY", "nexus-finance-chave-secreta-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE = f"sqlite:///{os.path.join(BASE_DIR, 'nexus_finance.db')}"

database_url = (os.environ.get("DATABASE_URL") or "").strip()
if not database_url:
    database_url = DEFAULT_SQLITE
elif database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "index"


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(256), nullable=False)
    saldo_em_caixa = db.Column(db.Float, default=0.0, nullable=False)
    meta_mensal = db.Column(db.Float, default=0.0, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ganhos = db.relationship("Ganho", backref="usuario", cascade="all, delete-orphan", lazy=True)
    gastos = db.relationship("Gasto", backref="usuario", cascade="all, delete-orphan", lazy=True)
    fixos = db.relationship("GastoFixo", backref="usuario", cascade="all, delete-orphan", lazy=True)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Ganho(db.Model):
    __tablename__ = "ganhos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    descricao = db.Column(db.String(255), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.String(20), nullable=False)


class Gasto(db.Model):
    __tablename__ = "gastos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    descricao = db.Column(db.String(255), nullable=False)
    categoria = db.Column(db.String(100), default="Geral", nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.String(20), nullable=False)


class GastoFixo(db.Model):
    __tablename__ = "gastos_fixos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    descricao = db.Column(db.String(255), nullable=False)
    valor = db.Column(db.Float, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    try:
        return Usuario.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


def hoje_str():
    return datetime.now().strftime("%d/%m/%Y")


def parse_valor(raw):
    if raw is None:
        raise ValueError("Valor vazio")
    txt = str(raw).strip().replace("R$", "").replace(" ", "")
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    return float(txt)


def login_obrigatorio_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"erro": "Não autorizado. Faça login."}), 401
        return fn(*args, **kwargs)

    return wrapper


def carregar_dados_usuario(user_id):
    u = Usuario.query.get(user_id)
    if not u:
        return {
            "saldo_em_caixa": 0.0,
            "meta_mensal": 0.0,
            "ganhos": [],
            "gastos": [],
            "fixos": [],
        }

    ganhos_db = Ganho.query.filter_by(user_id=user_id).order_by(Ganho.id.asc()).all()
    gastos_db = Gasto.query.filter_by(user_id=user_id).order_by(Gasto.id.asc()).all()
    fixos_db = GastoFixo.query.filter_by(user_id=user_id).order_by(GastoFixo.id.asc()).all()

    return {
        "saldo_em_caixa": float(u.saldo_em_caixa or 0.0),
        "meta_mensal": float(u.meta_mensal or 0.0),
        "ganhos": [
            {"descricao": g.descricao, "valor": float(g.valor), "data": g.data}
            for g in ganhos_db
        ],
        "gastos": [
            {
                "descricao": g.descricao,
                "categoria": g.categoria or "Geral",
                "valor": float(g.valor),
                "data": g.data,
            }
            for g in gastos_db
        ],
        "fixos": [
            {"descricao": fx.descricao, "valor": float(fx.valor)}
            for fx in fixos_db
        ],
    }


def extrair_mes_ano(data_str):
    partes = str(data_str or "").strip().split("/")
    if len(partes) == 3 and len(partes[1]) in (1, 2) and len(partes[2]) == 4:
        return f"{partes[1].zfill(2)}/{partes[2]}"
    return None


def listar_periodos(dados):
    periodos = set()
    for item in dados.get("ganhos", []) + dados.get("gastos", []):
        m = extrair_mes_ano(item.get("data"))
        if m:
            periodos.add(m)
    mes_atual = datetime.now().strftime("%m/%Y")
    periodos.add(mes_atual)
    ordenados = sorted(
        periodos,
        key=lambda x: tuple(reversed(x.split("/"))),
        reverse=True,
    )
    return ["Todos"] + ordenados


def montar_resumo(periodo="Todos", user_id=None):
    uid = user_id if user_id is not None else current_user.id
    dados = carregar_dados_usuario(uid)
    usuario_obj = Usuario.query.get(uid)

    periodo = periodo or "Todos"
    meses = listar_periodos(dados)
    if periodo not in meses:
        periodo = "Todos"

    ganhos_filtrados = []
    for i, item in enumerate(dados["ganhos"], start=1):
        if periodo == "Todos" or extrair_mes_ano(item.get("data")) == periodo:
            ganhos_filtrados.append({**item, "idx": i})

    gastos_filtrados = []
    for i, item in enumerate(dados["gastos"], start=1):
        if periodo == "Todos" or extrair_mes_ano(item.get("data")) == periodo:
            gastos_filtrados.append({**item, "idx": i})

    fixos_lista = [{**fx, "idx": i} for i, fx in enumerate(dados["fixos"], start=1)]

    total_ganhos = sum(float(x.get("valor", 0.0)) for x in ganhos_filtrados)
    total_gastos = sum(float(x.get("valor", 0.0)) for x in gastos_filtrados)
    total_fixos = sum(float(x.get("valor", 0.0)) for x in fixos_lista)
    saldo_caixa = float(dados.get("saldo_em_caixa", 0.0))
    meta_mensal = float(dados.get("meta_mensal", 0.0))

    saldo_disponivel = saldo_caixa + total_ganhos - total_gastos
    sobra_apos_fixos = saldo_disponivel - total_fixos

    agrupado_desc = {}
    for g in gastos_filtrados:
        chave = g.get("descricao") or "Sem descrição"
        agrupado_desc[chave] = agrupado_desc.get(chave, 0.0) + float(g.get("valor", 0.0))

    top_gastos = [
        {"descricao": k, "valor": v}
        for k, v in sorted(agrupado_desc.items(), key=lambda kv: kv[1], reverse=True)[:7]
    ]

    agrupado_cat = {}
    for g in gastos_filtrados:
        cat = g.get("categoria") or "Geral"
        agrupado_cat[cat] = agrupado_cat.get(cat, 0.0) + float(g.get("valor", 0.0))

    gastos_por_categoria = [
        {"categoria": k, "valor": v}
        for k, v in sorted(agrupado_cat.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return {
        "periodo": periodo,
        "meses": meses,
        "saldo_em_caixa": saldo_caixa,
        "meta_mensal": meta_mensal,
        "total_ganhos": total_ganhos,
        "total_gastos": total_gastos,
        "total_fixos": total_fixos,
        "saldo_disponivel": saldo_disponivel,
        "sobra_apos_fixos": sobra_apos_fixos,
        "ganhos": ganhos_filtrados,
        "gastos": gastos_filtrados,
        "fixos": fixos_lista,
        "top_gastos": top_gastos,
        "gastos_por_categoria": gastos_por_categoria,
        "autenticado": True,
        "usuario_email": usuario_obj.email if usuario_obj else "",
    }


@app.route("/")
def index():
    return render_template("index.html", hoje=hoje_str())


@app.route("/api/sessao")
def api_sessao():
    if current_user.is_authenticated:
        return jsonify({"autenticado": True, "usuario_email": current_user.email})
    return jsonify({"autenticado": False, "usuario_email": None})


@app.route("/api/registrar", methods=["POST"])
def api_registrar():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    senha = str(payload.get("senha", ""))

    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"erro": "Informe um e-mail válido."}), 400
    if len(senha) < 6:
        return jsonify({"erro": "A senha deve ter pelo menos 6 caracteres."}), 400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"erro": "Este e-mail já está cadastrado."}), 409

    novo_usuario = Usuario(email=email)
    novo_usuario.definir_senha(senha)
    db.session.add(novo_usuario)
    db.session.commit()

    login_user(novo_usuario, remember=True)
    return jsonify({
        "ok": True,
        "usuario_email": novo_usuario.email,
        "estado": montar_resumo("Todos", user_id=novo_usuario.id),
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    senha = str(payload.get("senha", ""))

    if not email or not senha:
        return jsonify({"erro": "Informe e-mail e senha."}), 400

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario or not usuario.verificar_senha(senha):
        return jsonify({"erro": "E-mail ou senha incorretos."}), 401

    login_user(usuario, remember=True)
    return jsonify({
        "ok": True,
        "usuario_email": usuario.email,
        "estado": montar_resumo("Todos", user_id=usuario.id),
    })


@app.route("/api/logout", methods=["POST"])
@login_obrigatorio_api
def api_logout():
    logout_user()
    return jsonify({"ok": True})


@app.route("/api/estado")
@login_obrigatorio_api
def api_estado():
    periodo = request.args.get("periodo", "Todos")
    return jsonify(montar_resumo(periodo))


@app.route("/api/ganhos", methods=["POST"])
@login_obrigatorio_api
def api_adicionar_ganho():
    payload = request.get_json(silent=True) or {}
    descricao = str(payload.get("descricao", "")).strip()
    data_str = str(payload.get("data", "")).strip() or hoje_str()
    if not descricao:
        return jsonify({"erro": "Informe a descrição do ganho."}), 400
    try:
        valor = parse_valor(payload.get("valor"))
        if valor <= 0:
            raise ValueError()
    except ValueError:
        return jsonify({"erro": "Informe um valor de ganho maior que zero."}), 400

    novo = Ganho(
        user_id=current_user.id,
        descricao=descricao,
        valor=valor,
        data=data_str,
    )
    db.session.add(novo)
    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/gastos", methods=["POST"])
@login_obrigatorio_api
def api_adicionar_gasto():
    payload = request.get_json(silent=True) or {}
    descricao = str(payload.get("descricao", "")).strip()
    categoria = str(payload.get("categoria", "Geral") or "Geral").strip()
    data_str = str(payload.get("data", "")).strip() or hoje_str()
    if not descricao:
        return jsonify({"erro": "Informe a descrição do gasto."}), 400
    try:
        valor = parse_valor(payload.get("valor"))
        if valor <= 0:
            raise ValueError()
    except ValueError:
        return jsonify({"erro": "Informe um valor de gasto maior que zero."}), 400

    novo = Gasto(
        user_id=current_user.id,
        descricao=descricao,
        categoria=categoria,
        valor=valor,
        data=data_str,
    )
    db.session.add(novo)
    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/lancamentos/remover", methods=["POST"])
@login_obrigatorio_api
def api_remover_lancamento():
    payload = request.get_json(silent=True) or {}
    tipo = str(payload.get("tipo", "")).strip()
    try:
        numero = int(payload.get("numero"))
    except (TypeError, ValueError):
        return jsonify({"erro": "Número inválido."}), 400

    if tipo == "1":
        lista = Ganho.query.filter_by(user_id=current_user.id).order_by(Ganho.id.asc()).all()
    elif tipo == "2":
        lista = Gasto.query.filter_by(user_id=current_user.id).order_by(Gasto.id.asc()).all()
    else:
        return jsonify({"erro": "Tipo inválido (use 1 para ganho ou 2 para gasto)."}), 400

    if numero < 1 or numero > len(lista):
        return jsonify({"erro": "Item não encontrado."}), 404

    db.session.delete(lista[numero - 1])
    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/lancamentos/editar", methods=["POST"])
@login_obrigatorio_api
def api_editar_lancamento():
    payload = request.get_json(silent=True) or {}
    tipo = str(payload.get("tipo", "")).strip()
    descricao = str(payload.get("descricao", "")).strip()
    data_str = str(payload.get("data", "")).strip()
    categoria = str(payload.get("categoria", "Geral") or "Geral").strip()
    if not descricao:
        return jsonify({"erro": "A descrição não pode ficar vazia."}), 400

    try:
        idx = int(payload.get("idx"))
        valor = parse_valor(payload.get("valor"))
        if valor <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"erro": "Dados inválidos para edição."}), 400

    if tipo == "ganho":
        lista = Ganho.query.filter_by(user_id=current_user.id).order_by(Ganho.id.asc()).all()
    elif tipo == "gasto":
        lista = Gasto.query.filter_by(user_id=current_user.id).order_by(Gasto.id.asc()).all()
    else:
        return jsonify({"erro": "Tipo inválido."}), 400

    if idx < 1 or idx > len(lista):
        return jsonify({"erro": "Item não encontrado."}), 404

    item = lista[idx - 1]
    item.descricao = descricao
    item.valor = valor
    if data_str:
        item.data = data_str
    if tipo == "gasto":
        item.categoria = categoria

    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/fixos", methods=["POST"])
@login_obrigatorio_api
def api_adicionar_fixo():
    payload = request.get_json(silent=True) or {}
    descricao = str(payload.get("descricao", "")).strip()
    if not descricao:
        return jsonify({"erro": "Informe a descrição do gasto fixo."}), 400
    try:
        valor = parse_valor(payload.get("valor"))
        if valor <= 0:
            raise ValueError()
    except ValueError:
        return jsonify({"erro": "Informe um valor fixo maior que zero."}), 400

    novo = GastoFixo(user_id=current_user.id, descricao=descricao, valor=valor)
    db.session.add(novo)
    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/fixos/remover", methods=["POST"])
@login_obrigatorio_api
def api_remover_fixo():
    payload = request.get_json(silent=True) or {}
    try:
        numero = int(payload.get("numero"))
    except (TypeError, ValueError):
        return jsonify({"erro": "Número inválido."}), 400

    lista = GastoFixo.query.filter_by(user_id=current_user.id).order_by(GastoFixo.id.asc()).all()
    if numero < 1 or numero > len(lista):
        return jsonify({"erro": "Gasto fixo não encontrado."}), 404

    db.session.delete(lista[numero - 1])
    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/fixos/editar", methods=["POST"])
@login_obrigatorio_api
def api_editar_fixo():
    payload = request.get_json(silent=True) or {}
    descricao = str(payload.get("descricao", "")).strip()
    if not descricao:
        return jsonify({"erro": "A descrição do gasto fixo não pode ficar vazia."}), 400

    try:
        idx = int(payload.get("idx"))
        valor = parse_valor(payload.get("valor"))
        if valor <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"erro": "Dados inválidos para edição."}), 400

    lista = GastoFixo.query.filter_by(user_id=current_user.id).order_by(GastoFixo.id.asc()).all()
    if idx < 1 or idx > len(lista):
        return jsonify({"erro": "Gasto fixo não encontrado."}), 404

    item = lista[idx - 1]
    item.descricao = descricao
    item.valor = valor
    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/caixa", methods=["POST"])
@login_obrigatorio_api
def api_atualizar_caixa():
    payload = request.get_json(silent=True) or {}
    try:
        valor = parse_valor(payload.get("valor"))
    except ValueError:
        return jsonify({"erro": "Informe um valor válido para o saldo em caixa."}), 400

    usuario = Usuario.query.get(current_user.id)
    usuario.saldo_em_caixa = valor
    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/meta", methods=["POST"])
@login_obrigatorio_api
def api_atualizar_meta():
    payload = request.get_json(silent=True) or {}
    try:
        valor = parse_valor(payload.get("meta_mensal"))
        if valor < 0:
            raise ValueError()
    except ValueError:
        return jsonify({"erro": "Informe uma meta mensal válida (0 ou maior)."}), 400

    usuario = Usuario.query.get(current_user.id)
    usuario.meta_mensal = valor
    db.session.commit()
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/exportar.csv")
@login_obrigatorio_api
def exportar_csv():
    dados = carregar_dados_usuario(current_user.id)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["tipo", "descricao", "valor", "data", "categoria"])

    for g in dados.get("ganhos", []):
        writer.writerow(["ganho", g.get("descricao", ""), f"{float(g.get('valor', 0.0)):.2f}", g.get("data", ""), ""])

    for g in dados.get("gastos", []):
        writer.writerow([
            "gasto",
            g.get("descricao", ""),
            f"{float(g.get('valor', 0.0)):.2f}",
            g.get("data", ""),
            g.get("categoria", "Geral"),
        ])

    for fx in dados.get("fixos", []):
        writer.writerow(["fixo", fx.get("descricao", ""), f"{float(fx.get('valor', 0.0)):.2f}", "", ""])

    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=nexus_finance.csv"},
    )


@app.route("/exportar.json")
@login_obrigatorio_api
def exportar_json():
    dados = carregar_dados_usuario(current_user.id)
    conteudo = json.dumps(dados, ensure_ascii=False, indent=2)
    return Response(
        conteudo,
        mimetype="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=nexus_finance_backup.json"},
    )


@app.route("/api/importar", methods=["POST"])
@login_obrigatorio_api
def api_importar():
    if "arquivo" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400

    arq = request.files["arquivo"]
    nome = (arq.filename or "").lower()
    texto = arq.read().decode("utf-8-sig", errors="replace")

    usuario = Usuario.query.get(current_user.id)

    if nome.endswith(".json"):
        try:
            importado = json.loads(texto)
        except Exception:
            return jsonify({"erro": "Arquivo JSON inválido."}), 400
        if not isinstance(importado, dict):
            return jsonify({"erro": "Estrutura JSON inválida."}), 400

        if "saldo_em_caixa" in importado:
            usuario.saldo_em_caixa = float(importado.get("saldo_em_caixa") or 0.0)
        if "meta_mensal" in importado:
            usuario.meta_mensal = float(importado.get("meta_mensal") or 0.0)

        if isinstance(importado.get("ganhos"), list):
            Ganho.query.filter_by(user_id=current_user.id).delete()
            for g in importado["ganhos"]:
                if isinstance(g, dict) and str(g.get("descricao", "")).strip():
                    db.session.add(Ganho(
                        user_id=current_user.id,
                        descricao=str(g.get("descricao", "")).strip(),
                        valor=float(g.get("valor", 0.0) or 0.0),
                        data=str(g.get("data", hoje_str())).strip() or hoje_str(),
                    ))

        if isinstance(importado.get("gastos"), list):
            Gasto.query.filter_by(user_id=current_user.id).delete()
            for g in importado["gastos"]:
                if isinstance(g, dict) and str(g.get("descricao", "")).strip():
                    db.session.add(Gasto(
                        user_id=current_user.id,
                        descricao=str(g.get("descricao", "")).strip(),
                        categoria=str(g.get("categoria", "Geral") or "Geral").strip(),
                        valor=float(g.get("valor", 0.0) or 0.0),
                        data=str(g.get("data", hoje_str())).strip() or hoje_str(),
                    ))

        if isinstance(importado.get("fixos"), list):
            GastoFixo.query.filter_by(user_id=current_user.id).delete()
            for fx in importado["fixos"]:
                if isinstance(fx, dict) and str(fx.get("descricao", "")).strip():
                    db.session.add(GastoFixo(
                        user_id=current_user.id,
                        descricao=str(fx.get("descricao", "")).strip(),
                        valor=float(fx.get("valor", 0.0) or 0.0),
                    ))

        db.session.commit()

    elif nome.endswith(".csv"):
        leitor = csv.reader(io.StringIO(texto), delimiter=";")
        linhas = list(leitor)
        if not linhas:
            return jsonify({"erro": "Arquivo CSV vazio."}), 400

        for idx_linha, linha in enumerate(linhas):
            if not linha or len(linha) < 3:
                continue
            tipo = linha[0].strip().lower()
            if idx_linha == 0 and tipo == "tipo":
                continue
            desc = linha[1].strip()
            if not desc:
                continue
            try:
                val = parse_valor(linha[2])
            except ValueError:
                continue
            data_item = linha[3].strip() if len(linha) > 3 and linha[3].strip() else hoje_str()
            cat_item = linha[4].strip() if len(linha) > 4 and linha[4].strip() else "Geral"

            if tipo in ("ganho", "ganhos"):
                db.session.add(Ganho(user_id=current_user.id, descricao=desc, valor=val, data=data_item))
            elif tipo in ("gasto", "gastos"):
                db.session.add(Gasto(user_id=current_user.id, descricao=desc, categoria=cat_item, valor=val, data=data_item))
            elif tipo in ("fixo", "fixos"):
                db.session.add(GastoFixo(user_id=current_user.id, descricao=desc, valor=val))

        db.session.commit()
    else:
        return jsonify({"erro": "Envie um arquivo .json ou .csv."}), 400

    return jsonify({"ok": True, "estado": montar_resumo("Todos")})


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)