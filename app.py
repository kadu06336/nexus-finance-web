import csv
import io
import json
import os
from datetime import datetime
from functools import wraps

from flask import Flask, Response, jsonify, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("NEXUS_SECRET_KEY", "nexus-finance-chave-secreta-2026")
SENHA_ACESSO = os.environ.get("NEXUS_SENHA", "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "dados_financeiros.json")


def hoje_str():
    return datetime.now().strftime("%d/%m/%Y")


def estado_padrao():
    return {
        "saldo_em_caixa": 0.0,
        "meta_mensal": 0.0,
        "ganhos": [],
        "gastos": [],
        "fixos": [],
    }


def parse_valor(raw):
    if raw is None:
        raise ValueError("Valor vazio")
    txt = str(raw).strip().replace("R$", "").replace(" ", "")
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    return float(txt)


def carregar_dados():
    if not os.path.exists(DATA_FILE):
        dados = estado_padrao()
        salvar_dados(dados)
        return dados

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except Exception:
        dados = estado_padrao()

    if not isinstance(dados, dict):
        dados = estado_padrao()

    base = estado_padrao()
    base["saldo_em_caixa"] = float(dados.get("saldo_em_caixa", 0.0) or 0.0)
    base["meta_mensal"] = float(dados.get("meta_mensal", 0.0) or 0.0)

    for g in dados.get("ganhos", []):
        if isinstance(g, dict):
            base["ganhos"].append({
                "descricao": str(g.get("descricao", "")).strip(),
                "valor": float(g.get("valor", 0.0) or 0.0),
                "data": str(g.get("data", hoje_str())).strip() or hoje_str(),
            })

    for g in dados.get("gastos", []):
        if isinstance(g, dict):
            base["gastos"].append({
                "descricao": str(g.get("descricao", "")).strip(),
                "categoria": str(g.get("categoria", "Geral") or "Geral").strip(),
                "valor": float(g.get("valor", 0.0) or 0.0),
                "data": str(g.get("data", hoje_str())).strip() or hoje_str(),
            })

    for fx in dados.get("fixos", []):
        if isinstance(fx, dict):
            base["fixos"].append({
                "descricao": str(fx.get("descricao", "")).strip(),
                "valor": float(fx.get("valor", 0.0) or 0.0),
            })

    return base


def salvar_dados(dados):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def esta_autenticado():
    return (not SENHA_ACESSO) or bool(session.get("autenticado"))


def login_obrigatorio_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if SENHA_ACESSO and not session.get("autenticado"):
            return jsonify({"erro": "Não autorizado. Faça login."}), 401
        return fn(*args, **kwargs)
    return wrapper


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


def montar_resumo(periodo="Todos"):
    dados = carregar_dados()
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
        "autenticado": esta_autenticado(),
        "senha_ativa": bool(SENHA_ACESSO),
    }


@app.route("/")
def index():
    return render_template("index.html", hoje=hoje_str())


@app.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha", ""))
    if not SENHA_ACESSO or senha == SENHA_ACESSO:
        session["autenticado"] = True
        return jsonify({"ok": True})
    return jsonify({"erro": "Senha incorreta."}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("autenticado", None)
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

    dados = carregar_dados()
    dados["ganhos"].append({"descricao": descricao, "valor": valor, "data": data_str})
    salvar_dados(dados)
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

    dados = carregar_dados()
    dados["gastos"].append({
        "descricao": descricao,
        "categoria": categoria,
        "valor": valor,
        "data": data_str,
    })
    salvar_dados(dados)
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

    dados = carregar_dados()
    lista = dados["ganhos"] if tipo == "1" else dados["gastos"] if tipo == "2" else None
    if lista is None:
        return jsonify({"erro": "Tipo inválido (use 1 para ganho ou 2 para gasto)."}), 400
    if numero < 1 or numero > len(lista):
        return jsonify({"erro": "Item não encontrado."}), 404

    lista.pop(numero - 1)
    salvar_dados(dados)
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

    dados = carregar_dados()
    lista = dados["ganhos"] if tipo == "ganho" else dados["gastos"] if tipo == "gasto" else None
    if lista is None or idx < 1 or idx > len(lista):
        return jsonify({"erro": "Item não encontrado."}), 404

    item = lista[idx - 1]
    item["descricao"] = descricao
    item["valor"] = valor
    if data_str:
        item["data"] = data_str
    if tipo == "gasto":
        item["categoria"] = categoria

    salvar_dados(dados)
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

    dados = carregar_dados()
    dados["fixos"].append({"descricao": descricao, "valor": valor})
    salvar_dados(dados)
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/fixos/remover", methods=["POST"])
@login_obrigatorio_api
def api_remover_fixo():
    payload = request.get_json(silent=True) or {}
    try:
        numero = int(payload.get("numero"))
    except (TypeError, ValueError):
        return jsonify({"erro": "Número inválido."}), 400

    dados = carregar_dados()
    if numero < 1 or numero > len(dados["fixos"]):
        return jsonify({"erro": "Gasto fixo não encontrado."}), 404

    dados["fixos"].pop(numero - 1)
    salvar_dados(dados)
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

    dados = carregar_dados()
    if idx < 1 or idx > len(dados["fixos"]):
        return jsonify({"erro": "Gasto fixo não encontrado."}), 404

    dados["fixos"][idx - 1]["descricao"] = descricao
    dados["fixos"][idx - 1]["valor"] = valor
    salvar_dados(dados)
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/api/caixa", methods=["POST"])
@login_obrigatorio_api
def api_atualizar_caixa():
    payload = request.get_json(silent=True) or {}
    try:
        valor = parse_valor(payload.get("valor"))
    except ValueError:
        return jsonify({"erro": "Informe um valor válido para o saldo em caixa."}), 400

    dados = carregar_dados()
    dados["saldo_em_caixa"] = valor
    salvar_dados(dados)
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

    dados = carregar_dados()
    dados["meta_mensal"] = valor
    salvar_dados(dados)
    return jsonify({"ok": True, "estado": montar_resumo(payload.get("periodo", "Todos"))})


@app.route("/exportar.csv")
@login_obrigatorio_api
def exportar_csv():
    dados = carregar_dados()
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
    dados = carregar_dados()
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

    dados = carregar_dados()

    if nome.endswith(".json"):
        try:
            importado = json.loads(texto)
        except Exception:
            return jsonify({"erro": "Arquivo JSON inválido."}), 400
        if not isinstance(importado, dict):
            return jsonify({"erro": "Estrutura JSON inválida."}), 400

        dados["saldo_em_caixa"] = float(importado.get("saldo_em_caixa", dados["saldo_em_caixa"]) or 0.0)
        dados["meta_mensal"] = float(importado.get("meta_mensal", dados["meta_mensal"]) or 0.0)
        if isinstance(importado.get("ganhos"), list):
            dados["ganhos"] = importado["ganhos"]
        if isinstance(importado.get("gastos"), list):
            dados["gastos"] = importado["gastos"]
        if isinstance(importado.get("fixos"), list):
            dados["fixos"] = importado["fixos"]

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
                dados["ganhos"].append({"descricao": desc, "valor": val, "data": data_item})
            elif tipo in ("gasto", "gastos"):
                dados["gastos"].append({"descricao": desc, "categoria": cat_item, "valor": val, "data": data_item})
            elif tipo in ("fixo", "fixos"):
                dados["fixos"].append({"descricao": desc, "valor": val})
    else:
        return jsonify({"erro": "Envie um arquivo .json ou .csv."}), 400

    salvar_dados(dados)
    return jsonify({"ok": True, "estado": montar_resumo("Todos")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)