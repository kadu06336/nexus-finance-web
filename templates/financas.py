import csv
import io
import json
import os
from datetime import datetime

from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)
app.secret_key = os.environ.get("NEXUS_SECRET_KEY", "nexus-finance-secret-key")

ARQUIVO_DADOS = os.environ.get("NEXUS_DATA_FILE", "dados_financeiros.json")

estado = {
    "saldo_em_caixa": 0.0,
    "ganhos": [],
    "gastos": [],
    "fixos": [],
}


def carregar_dados():
    global estado
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                dados = json.load(f)
            estado["saldo_em_caixa"] = float(dados.get("saldo_em_caixa", 0.0))
            estado["ganhos"] = dados.get("ganhos", [])
            estado["gastos"] = dados.get("gastos", [])
            estado["fixos"] = dados.get("fixos", [])
        except Exception:
            pass


def salvar_dados():
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def limpar_valor(valor):
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("R$", "").strip()
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    return float(texto)


def data_hoje():
    return datetime.now().strftime("%d/%m/%Y")


def extrair_mes_ano(data_str):
    partes = str(data_str).strip().split("/")
    if len(partes) == 3 and len(partes[1]) == 2 and len(partes[2]) == 4:
        return f"{partes[1]}/{partes[2]}"
    return None


def meses_disponiveis():
    meses = set()
    for item in estado["ganhos"] + estado["gastos"]:
        ma = extrair_mes_ano(item.get("data", ""))
        if ma:
            meses.add(ma)
    meses.add(datetime.now().strftime("%m/%Y"))
    return ["Todos"] + sorted(meses, reverse=True)


def itens_filtrados(lista, periodo):
    if not periodo or periodo == "Todos":
        return [{"idx": i, **item} for i, item in enumerate(lista, 1)]
    saida = []
    for i, item in enumerate(lista, 1):
        if extrair_mes_ano(item.get("data", "")) == periodo:
            saida.append({"idx": i, **item})
    return saida


def montar_resumo(periodo="Todos"):
    ganhos_f = itens_filtrados(estado["ganhos"], periodo)
    gastos_f = itens_filtrados(estado["gastos"], periodo)
    fixos_lista = [{"idx": i, **item} for i, item in enumerate(estado["fixos"], 1)]

    total_ganhos = sum(float(x["valor"]) for x in ganhos_f)
    total_gastos = sum(float(x["valor"]) for x in gastos_f)
    total_fixos = sum(float(x["valor"]) for x in fixos_lista)

    saldo_disponivel = float(estado["saldo_em_caixa"]) + total_ganhos - total_gastos
    sobra_apos_fixos = saldo_disponivel - total_fixos

    totais_desc = {}
    for g in gastos_f:
        desc = g["descricao"]
        totais_desc[desc] = totais_desc.get(desc, 0.0) + float(g["valor"])

    top_gastos = sorted(totais_desc.items(), key=lambda x: x[1], reverse=True)[:7]

    return {
        "periodo": periodo,
        "meses": meses_disponiveis(),
        "saldo_em_caixa": float(estado["saldo_em_caixa"]),
        "total_ganhos": total_ganhos,
        "total_gastos": total_gastos,
        "total_fixos": total_fixos,
        "saldo_disponivel": saldo_disponivel,
        "sobra_apos_fixos": sobra_apos_fixos,
        "ganhos": ganhos_f,
        "gastos": gastos_f,
        "fixos": fixos_lista,
        "top_gastos": [{"descricao": k, "valor": v} for k, v in top_gastos],
    }


carregar_dados()


@app.route("/")
def index():
    return render_template("index.html", hoje=data_hoje())


@app.route("/api/estado")
def api_estado():
    periodo = request.args.get("periodo", "Todos")
    return jsonify(montar_resumo(periodo))


@app.route("/api/ganhos", methods=["POST"])
def add_ganho():
    dados = request.get_json(force=True)
    desc = str(dados.get("descricao", "")).strip()
    dt = str(dados.get("data", "")).strip() or data_hoje()
    if not desc:
        return jsonify({"erro": "Coloque uma descrição!"}), 400
    try:
        val = limpar_valor(dados.get("valor", 0))
    except ValueError:
        return jsonify({"erro": "Valor inválido!"}), 400
    if val <= 0:
        return jsonify({"erro": "O valor deve ser maior que zero!"}), 400

    estado["ganhos"].append({"descricao": desc, "valor": val, "data": dt})
    salvar_dados()
    return jsonify({"ok": True, "estado": montar_resumo(dados.get("periodo", "Todos"))})


@app.route("/api/gastos", methods=["POST"])
def add_gasto():
    dados = request.get_json(force=True)
    desc = str(dados.get("descricao", "")).strip()
    dt = str(dados.get("data", "")).strip() or data_hoje()
    if not desc:
        return jsonify({"erro": "Coloque uma descrição!"}), 400
    try:
        val = limpar_valor(dados.get("valor", 0))
    except ValueError:
        return jsonify({"erro": "Valor inválido!"}), 400
    if val <= 0:
        return jsonify({"erro": "O valor deve ser maior que zero!"}), 400

    estado["gastos"].append({"descricao": desc, "valor": val, "data": dt})
    salvar_dados()
    return jsonify({"ok": True, "estado": montar_resumo(dados.get("periodo", "Todos"))})


@app.route("/api/lancamentos/remover", methods=["POST"])
def remover_lancamento():
    dados = request.get_json(force=True)
    tipo = str(dados.get("tipo", "")).strip()
    try:
        idx = int(dados.get("numero", 0)) - 1
    except (TypeError, ValueError):
        return jsonify({"erro": "Digite um número válido!"}), 400

    if tipo == "1":
        if 0 <= idx < len(estado["ganhos"]):
            estado["ganhos"].pop(idx)
            salvar_dados()
            return jsonify({"ok": True, "estado": montar_resumo(dados.get("periodo", "Todos"))})
        return jsonify({"erro": "Número de ganho inválido!"}), 400

    if tipo == "2":
        if 0 <= idx < len(estado["gastos"]):
            estado["gastos"].pop(idx)
            salvar_dados()
            return jsonify({"ok": True, "estado": montar_resumo(dados.get("periodo", "Todos"))})
        return jsonify({"erro": "Número de gasto inválido!"}), 400

    return jsonify({"erro": "Escolha 1 para Ganho ou 2 para Gasto!"}), 400


@app.route("/api/fixos", methods=["POST"])
def add_fixo():
    dados = request.get_json(force=True)
    desc = str(dados.get("descricao", "")).strip()
    if not desc:
        return jsonify({"erro": "Digite uma descrição para o gasto fixo!"}), 400
    try:
        val = limpar_valor(dados.get("valor", 0))
    except ValueError:
        return jsonify({"erro": "Valor mensal inválido!"}), 400
    if val <= 0:
        return jsonify({"erro": "O valor mensal deve ser maior que zero!"}), 400

    estado["fixos"].append({"descricao": desc, "valor": val})
    salvar_dados()
    return jsonify({"ok": True, "estado": montar_resumo(dados.get("periodo", "Todos"))})


@app.route("/api/fixos/remover", methods=["POST"])
def remover_fixo():
    dados = request.get_json(force=True)
    try:
        idx = int(dados.get("numero", 0)) - 1
    except (TypeError, ValueError):
        return jsonify({"erro": "Digite um número válido!"}), 400

    if 0 <= idx < len(estado["fixos"]):
        estado["fixos"].pop(idx)
        salvar_dados()
        return jsonify({"ok": True, "estado": montar_resumo(dados.get("periodo", "Todos"))})
    return jsonify({"erro": "Número inválido!"}), 400


@app.route("/api/caixa", methods=["POST"])
def definir_caixa():
    dados = request.get_json(force=True)
    try:
        novo_saldo = limpar_valor(dados.get("valor", 0))
    except ValueError:
        return jsonify({"erro": "Digite um valor válido para o saldo em caixa!"}), 400

    estado["saldo_em_caixa"] = novo_saldo
    salvar_dados()
    return jsonify({"ok": True, "estado": montar_resumo(dados.get("periodo", "Todos"))})


@app.route("/exportar.csv")
def exportar_csv():
    saida = io.StringIO()
    writer = csv.writer(saida, delimiter=";")
    writer.writerow(["Tipo", "Descrição", "Valor (R$)", "Data"])
    for item in estado["ganhos"]:
        writer.writerow(["Ganho", item["descricao"], f"{float(item['valor']):.2f}", item["data"]])
    for item in estado["gastos"]:
        writer.writerow(["Gasto", item["descricao"], f"{float(item['valor']):.2f}", item["data"]])
    for item in estado["fixos"]:
        writer.writerow(["Gasto Fixo Mensal", item["descricao"], f"{float(item['valor']):.2f}", "Mensal"])
    writer.writerow([])
    writer.writerow(["Saldo em Caixa", "", f"{float(estado['saldo_em_caixa']):.2f}", ""])

    nome_arq = f"nexus_finance_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        "\ufeff" + saida.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={nome_arq}"},
    )


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta)