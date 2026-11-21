import json
import os
from functools import wraps
from flask import Flask, redirect, render_template, request, session, url_for

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get("NEXUS_SECRET_KEY", "nexus-chave-secreta-troque-aqui")

USUARIO_CORRETO = os.environ.get("NEXUS_USER", "admin")
SENHA_CORRETA = os.environ.get("NEXUS_PASS", "1234")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_DADOS = os.path.join(BASE_DIR, "dados_financeiros.json")


def formatar_moeda(valor):
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_moeda(texto):
    bruto = str(texto or "").strip().replace("R$", "").replace(" ", "")
    if not bruto:
        raise ValueError("Valor vazio")
    if "," in bruto and "." in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    else:
        bruto = bruto.replace(",", ".")
    return float(bruto)


def extrair_valor(item):
    if isinstance(item, (int, float)):
        return float(item)
    if isinstance(item, dict):
        for chave in ("valor", "quantia", "amount", "preco", "preço"):
            if chave in item and item[chave] is not None:
                try:
                    return float(str(item[chave]).replace(",", "."))
                except ValueError:
                    pass
    return 0.0


def extrair_descricao(item, padrao="Lançamento"):
    if isinstance(item, dict):
        for chave in ("descricao", "descrição", "cliente", "nome", "titulo", "título"):
            if item.get(chave):
                return str(item[chave]).strip()
    return padrao


def carregar_dados_web():
    padrao = {"saldo_em_caixa": 0.0, "ganhos": [], "gastos": [], "fixos": []}
    if not os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
            json.dump(padrao, f, ensure_ascii=False, indent=2)
        return padrao
    try:
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return {
            "saldo_em_caixa": float(dados.get("saldo_em_caixa", 0.0)),
            "ganhos": dados.get("ganhos", []),
            "gastos": dados.get("gastos", []),
            "fixos": dados.get("fixos", []),
        }
    except Exception:
        return padrao


def salvar_dados_web(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def montar_itens_exibicao(lista, padrao):
    itens = []
    for idx, item in enumerate(lista):
        val = extrair_valor(item)
        itens.append({
            "indice": idx,
            "descricao": extrair_descricao(item, padrao),
            "valor": val,
            "valor_fmt": formatar_moeda(val),
        })
    return itens


def login_obrigatorio(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if not session.get("logado"):
            return redirect(url_for("home"))
        return funcao(*args, **kwargs)
    return wrapper


@app.route("/", methods=["GET", "POST"])
def home():
    erro = None
    if request.method == "POST":
        usuario = request.form.get("username", "").strip()
        senha = request.form.get("password", "").strip()
        if usuario == USUARIO_CORRETO and senha == SENHA_CORRETA:
            session["logado"] = True
            return redirect(url_for("dashboard"))
        erro = "Usuário ou senha inválidos."
    return render_template("login.html", erro=erro)


@app.route("/dashboard")
@login_obrigatorio
def dashboard():
    dados = carregar_dados_web()
    caixa = dados["saldo_em_caixa"]
    total_ganhos = sum(extrair_valor(x) for x in dados["ganhos"])
    total_gastos = sum(extrair_valor(x) for x in dados["gastos"])
    total_fixos = sum(extrair_valor(x) for x in dados["fixos"])
    entradas = total_ganhos
    saidas = total_gastos + total_fixos
    saldo_atual = caixa + entradas - saidas

    return render_template(
        "dashboard.html",
        saldo_atual_fmt=formatar_moeda(saldo_atual),
        entradas_fmt=formatar_moeda(entradas),
        saidas_fmt=formatar_moeda(saidas),
        total_ganhos_fmt=formatar_moeda(total_ganhos),
        total_gastos_fmt=formatar_moeda(total_gastos),
        total_fixos_fmt=formatar_moeda(total_fixos),
        caixa_fmt=formatar_moeda(caixa),
        caixa_valor=f"{caixa:.2f}",
        ganhos_itens=montar_itens_exibicao(dados["ganhos"], "Ganho"),
        gastos_itens=montar_itens_exibicao(dados["gastos"], "Gasto"),
        fixos_itens=montar_itens_exibicao(dados["fixos"], "Fixo"),
    )


@app.route("/lancamento", methods=["POST"])
@login_obrigatorio
def adicionar_lancamento():
    tipo = request.form.get("tipo", "ganho").strip().lower()
    descricao = request.form.get("descricao", "").strip()
    valor_bruto = request.form.get("valor", "")

    chave_mapa = {
        "ganho": ("ganhos", "Ganho"),
        "gasto": ("gastos", "Gasto"),
        "fixo": ("fixos", "Fixo"),
    }

    if tipo in chave_mapa:
        chave_lista, padrao_desc = chave_mapa[tipo]
        try:
            valor = parse_moeda(valor_bruto)
            dados = carregar_dados_web()
            dados[chave_lista].append({
                "descricao": descricao if descricao else padrao_desc,
                "valor": valor,
            })
            salvar_dados_web(dados)
        except ValueError:
            pass

    return redirect(url_for("dashboard"))


@app.route("/lancamento/excluir", methods=["POST"])
@login_obrigatorio
def excluir_lancamento():
    categoria = request.form.get("categoria", "").strip().lower()
    try:
        indice = int(request.form.get("indice", "-1"))
    except ValueError:
        indice = -1

    if categoria in ("ganhos", "gastos", "fixos") and indice >= 0:
        dados = carregar_dados_web()
        lista = dados[categoria]
        if indice < len(lista):
            lista.pop(indice)
            salvar_dados_web(dados)

    return redirect(url_for("dashboard"))


@app.route("/caixa", methods=["POST"])
@login_obrigatorio
def atualizar_caixa():
    dados = carregar_dados_web()
    try:
        dados["saldo_em_caixa"] = parse_moeda(request.form.get("saldo_em_caixa", "0"))
        salvar_dados_web(dados)
    except ValueError:
        pass
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=False)

if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
