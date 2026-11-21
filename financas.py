import csv
import json
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ARQUIVO_DADOS = "dados_financeiros.json"

# ==================== PALETA FUTURISTA (DARK TECH) ====================
cor_fundo = "#090d16"
cor_card = "#111827"
cor_card_alt = "#162033"
cor_input = "#0f172a"
cor_ciano = "#00e5ff"
cor_azul = "#3b82f6"
cor_roxo = "#8b5cf6"
cor_verde = "#10b981"
cor_vermelho = "#ff4d6d"
cor_amarelo = "#fbbf24"
cor_texto = "#e2e8f0"
cor_muted = "#94a3b8"
cor_borda = "#1e293b"

ganhos = []
gastos = []
fixos = []
saldo_em_caixa = 0.0
filtro_mes_atual = "Todos"


def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def salvar_dados():
    dados = {
        "saldo_em_caixa": saldo_em_caixa,
        "ganhos": ganhos,
        "gastos": gastos,
        "fixos": fixos,
    }
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def carregar_dados():
    global saldo_em_caixa, ganhos, gastos, fixos
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                dados = json.load(f)
            saldo_em_caixa = float(dados.get("saldo_em_caixa", 0.0))
            ganhos = dados.get("ganhos", [])
            gastos = dados.get("gastos", [])
            fixos = dados.get("fixos", [])
        except Exception:
            pass


def limpar_texto(valor):
    valor = valor.strip().replace("R$", "").strip()
    if "," in valor and "." in valor:
        valor = valor.replace(".", "").replace(",", ".")
    elif "," in valor:
        valor = valor.replace(",", ".")
    return valor


def pegar_data():
    return datetime.now().strftime("%d/%m/%Y")


def extrair_mes_ano(data_str):
    partes = data_str.strip().split("/")
    if len(partes) == 3 and len(partes[1]) == 2 and len(partes[2]) == 4:
        return f"{partes[1]}/{partes[2]}"
    return None


def obter_meses_disponiveis():
    meses = set()
    for item in ganhos + gastos:
        ma = extrair_mes_ano(item.get("data", ""))
        if ma:
            meses.add(ma)
    meses.add(datetime.now().strftime("%m/%Y"))
    return ["Todos"] + sorted(meses, reverse=True)


def itens_filtrados(lista):
    if filtro_mes_atual == "Todos":
        return list(enumerate(lista, 1))
    resultado = []
    for idx, item in enumerate(lista, 1):
        if extrair_mes_ano(item.get("data", "")) == filtro_mes_atual:
            resultado.append((idx, item))
    return resultado


def atualizar_filtro_opcoes():
    opcoes = obter_meses_disponiveis()
    combo_filtro["values"] = opcoes
    if filtro_mes_atual not in opcoes:
        combo_filtro.set("Todos")


def aplicar_filtro(event=None):
    global filtro_mes_atual
    filtro_mes_atual = combo_filtro.get() or "Todos"
    atualizar_tudo()


def atualizar_tudo():
    ganhos_f = [item for _, item in itens_filtrados(ganhos)]
    gastos_f = [item for _, item in itens_filtrados(gastos)]

    total_g = sum(item["valor"] for item in ganhos_f)
    total_ga = sum(item["valor"] for item in gastos_f)
    total_fixos_val = sum(item["valor"] for item in fixos)

    saldo_atual = saldo_em_caixa + total_g - total_ga
    saldo_mensal = saldo_atual - total_fixos_val

    lbl_total_g.config(text=f"📈 GANHOS: {formatar_moeda(total_g)}")
    lbl_total_ga.config(text=f"📉 GASTOS: {formatar_moeda(total_ga)}")
    lbl_fixos_total.config(text=f"🔄 FIXOS: {formatar_moeda(total_fixos_val)}")
    lbl_sobra.config(
        text=f"⚡ SALDO: {formatar_moeda(saldo_atual)}",
        fg=cor_verde if saldo_atual >= 0 else cor_vermelho,
    )

    lbl_res_caixa.config(text=f"💵 SALDO EM CAIXA\n{formatar_moeda(saldo_em_caixa)}")
    lbl_res_ganhos.config(text=f"📈 GANHOS ({filtro_mes_atual})\n{formatar_moeda(total_g)}")
    lbl_res_gastos.config(text=f"📉 GASTOS ({filtro_mes_atual})\n{formatar_moeda(total_ga)}")
    lbl_res_disponivel.config(
        text=f"⚡ SALDO DISPONÍVEL\n{formatar_moeda(saldo_atual)}",
        fg=cor_verde if saldo_atual >= 0 else cor_vermelho,
    )
    lbl_res_fixos.config(text=f"🔄 FIXOS MENSAIS\n{formatar_moeda(total_fixos_val)}")
    lbl_mensal_final.config(
        text=f"💎 SOBRA APÓS FIXOS\n{formatar_moeda(saldo_mensal)}",
        fg=cor_verde if saldo_mensal >= 0 else cor_vermelho,
    )

    lbl_caixa_atual_aba.config(text=formatar_moeda(saldo_em_caixa))

    lista_ganhos.delete(1.0, tk.END)
    filtrados_g = itens_filtrados(ganhos)
    if not filtrados_g:
        lista_ganhos.insert(tk.END, "        Nenhum ganho registrado para o filtro selecionado.\n")
    else:
        lista_ganhos.insert(tk.END, f"{'Nº':<5} {'Data':<12} {'Descrição':<28} {'Valor':>14}\n")
        lista_ganhos.insert(tk.END, "─" * 62 + "\n")
        for idx_real, item in filtrados_g:
            desc = item["descricao"][:28]
            lista_ganhos.insert(
                tk.END, f"{idx_real:<5} {item['data']:<12} {desc:<28}  +R$ {item['valor']:>9.2f}\n"
            )

    lista_gastos.delete(1.0, tk.END)
    filtrados_ga = itens_filtrados(gastos)
    if not filtrados_ga:
        lista_gastos.insert(tk.END, "        Nenhum gasto registrado para o filtro selecionado.\n")
    else:
        lista_gastos.insert(tk.END, f"{'Nº':<5} {'Data':<12} {'Descrição':<28} {'Valor':>14}\n")
        lista_gastos.insert(tk.END, "─" * 62 + "\n")
        for idx_real, item in filtrados_ga:
            desc = item["descricao"][:28]
            lista_gastos.insert(
                tk.END, f"{idx_real:<5} {item['data']:<12} {desc:<28}  -R$ {item['valor']:>9.2f}\n"
            )

    lista_fixos.delete(1.0, tk.END)
    if not fixos:
        lista_fixos.insert(tk.END, "        Nenhum gasto fixo cadastrado.\n")
    else:
        lista_fixos.insert(tk.END, f"{'Nº':<5} {'Descrição':<34} {'Valor Mensal':>16}\n")
        lista_fixos.insert(tk.END, "─" * 60 + "\n")
        for i, item in enumerate(fixos, 1):
            desc = item["descricao"][:34]
            lista_fixos.insert(tk.END, f"{i:<5} {desc:<34}  -R$ {item['valor']:>9.2f}\n")

    atualizar_grafico(total_g, total_ga, total_fixos_val, saldo_mensal, gastos_f)


def atualizar_grafico(total_g, total_ga, total_fixos_val, saldo_mensal, gastos_f):
    ax_bar.clear()
    ax_donut.clear()

    fig.patch.set_facecolor(cor_card)
    ax_bar.set_facecolor(cor_input)
    ax_donut.set_facecolor(cor_card)

    if not gastos_f:
        ax_bar.text(
            0.5,
            0.5,
            "Sem gastos no período\nAdicione lançamentos para visualizar",
            ha="center",
            va="center",
            color=cor_muted,
            fontsize=11,
            transform=ax_bar.transAxes,
        )
        ax_bar.set_xticks([])
        ax_bar.set_yticks([])
    else:
        descricoes = {}
        for item in gastos_f:
            d = item["descricao"]
            descricoes[d] = descricoes.get(d, 0.0) + item["valor"]

        ordenados = sorted(descricoes.items(), key=lambda x: x[1], reverse=True)[:7]
        ordenados.reverse()
        nomes = [n[:18] for n, _ in ordenados]
        valores = [v for _, v in ordenados]

        paleta_barras = [cor_roxo, cor_azul, cor_ciano, "#06b6d4", "#f97316", cor_amarelo, cor_vermelho]
        cores_usadas = paleta_barras[-len(valores) :]

        y_pos = range(len(nomes))
        barras = ax_bar.barh(
            y_pos,
            valores,
            height=0.56,
            color=cores_usadas,
            edgecolor=cor_ciano,
            linewidth=0.8,
            alpha=0.92,
        )

        ax_bar.set_yticks(list(y_pos))
        ax_bar.set_yticklabels(nomes, color=cor_texto, fontsize=10, fontweight="bold")
        ax_bar.tick_params(axis="x", colors=cor_muted, labelsize=9)
        ax_bar.set_xlabel("Valor (R$)", color=cor_muted, fontsize=10)
        ax_bar.grid(axis="x", linestyle="--", alpha=0.2, color=cor_ciano)
        ax_bar.spines["top"].set_visible(False)
        ax_bar.spines["right"].set_visible(False)
        ax_bar.spines["left"].set_color(cor_borda)
        ax_bar.spines["bottom"].set_color(cor_borda)

        max_v = max(valores) if valores else 1
        ax_bar.set_xlim(0, max_v * 1.24)
        for barra, v in zip(barras, valores):
            ax_bar.text(
                v + (max_v * 0.025),
                barra.get_y() + barra.get_height() / 2,
                formatar_moeda(v),
                va="center",
                ha="left",
                color=cor_texto,
                fontsize=9,
                fontweight="bold",
            )

    ax_bar.set_title(
        f"TOP GASTOS • {filtro_mes_atual}",
        color=cor_ciano,
        fontsize=11,
        fontweight="bold",
        pad=12,
    )

    valores_donut = [total_g, total_ga, total_fixos_val]
    labels_donut = ["Ganhos", "Gastos Diários", "Fixos Mensais"]
    cores_donut = [cor_verde, cor_vermelho, cor_amarelo]

    ativos = [(l, v, c) for l, v, c in zip(labels_donut, valores_donut, cores_donut) if v > 0]
    if not ativos:
        ax_donut.text(
            0.5,
            0.5,
            "Sem movimentação\npara compor o painel",
            ha="center",
            va="center",
            color=cor_muted,
            fontsize=11,
            transform=ax_donut.transAxes,
        )
    else:
        l_act = [x[0] for x in ativos]
        v_act = [x[1] for x in ativos]
        c_act = [x[2] for x in ativos]

        _, _, autotexts = ax_donut.pie(
            v_act,
            labels=l_act,
            autopct="%1.1f%%",
            startangle=140,
            colors=c_act,
            pctdistance=0.76,
            wedgeprops=dict(width=0.38, edgecolor=cor_card, linewidth=2.5),
            textprops=dict(color=cor_texto, fontsize=9, fontweight="bold"),
        )
        for autotext in autotexts:
            autotext.set_color("#090d16")
            autotext.set_fontsize(8.5)
            autotext.set_fontweight("bold")

        cor_centro = cor_verde if saldo_mensal >= 0 else cor_vermelho
        ax_donut.text(
            0,
            0.05,
            "SOBRA LÍQUIDA",
            ha="center",
            va="center",
            color=cor_muted,
            fontsize=8,
            fontweight="bold",
        )
        ax_donut.text(
            0,
            -0.16,
            f"R$ {saldo_mensal:,.0f}".replace(",", "."),
            ha="center",
            va="center",
            color=cor_centro,
            fontsize=11,
            fontweight="bold",
        )

    ax_donut.set_title(
        "FLUXO FINANCEIRO",
        color=cor_ciano,
        fontsize=11,
        fontweight="bold",
        pad=12,
    )

    fig.tight_layout(pad=2.0)
    canvas.draw()


def exportar_csv():
    caminho = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("Arquivo CSV", "*.csv")],
        initialfile=f"nexus_finance_{datetime.now().strftime('%Y%m%d')}.csv",
        title="Exportar Relatório Financeiro",
    )
    if not caminho:
        return
    try:
        with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Tipo", "Descrição", "Valor (R$)", "Data"])
            for item in ganhos:
                writer.writerow(["Ganho", item["descricao"], f"{item['valor']:.2f}", item["data"]])
            for item in gastos:
                writer.writerow(["Gasto", item["descricao"], f"{item['valor']:.2f}", item["data"]])
            for item in fixos:
                writer.writerow(["Gasto Fixo Mensal", item["descricao"], f"{item['valor']:.2f}", "Mensal"])
            writer.writerow([])
            writer.writerow(["Saldo em Caixa", "", f"{saldo_em_caixa:.2f}", ""])
        messagebox.showinfo("Exportado", "Relatório CSV salvo com sucesso!")
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível exportar o CSV:\n{e}")


# ==================== JANELA PRINCIPAL ====================
janela = tk.Tk()
janela.title("NEXUS FINANCE • Cyber Ledger")
janela.geometry("1280x840")
janela.minsize(1040, 720)
janela.configure(bg=cor_fundo)

estilo = ttk.Style()
estilo.theme_use("clam")
estilo.configure(
    "TNotebook",
    background=cor_fundo,
    borderwidth=0,
    tabmargins=[2, 4, 2, 0],
)
estilo.configure(
    "TNotebook.Tab",
    background=cor_card,
    foreground=cor_muted,
    padding=[16, 9],
    font=("Segoe UI", 10, "bold"),
    borderwidth=1,
)
estilo.map(
    "TNotebook.Tab",
    background=[("selected", cor_card_alt)],
    foreground=[("selected", cor_ciano)],
)
estilo.configure(
    "TCombobox",
    fieldbackground=cor_input,
    background=cor_card_alt,
    foreground=cor_texto,
    arrowcolor=cor_ciano,
    bordercolor=cor_borda,
)

topo = tk.Frame(janela, bg=cor_fundo)
topo.pack(fill="x", padx=22, pady=(14, 6))

tk.Label(
    topo,
    text="◆ NEXUS FINANCE ◆",
    font=("Segoe UI", 22, "bold"),
    bg=cor_fundo,
    fg=cor_ciano,
).pack(side="left")

controles_topo = tk.Frame(topo, bg=cor_fundo)
controles_topo.pack(side="right")

tk.Label(
    controles_topo,
    text="PERÍODO:",
    font=("Segoe UI", 9, "bold"),
    bg=cor_fundo,
    fg=cor_muted,
).pack(side="left", padx=(0, 6))

combo_filtro = ttk.Combobox(
    controles_topo,
    values=["Todos"],
    state="readonly",
    width=12,
    font=("Segoe UI", 10, "bold"),
)
combo_filtro.set("Todos")
combo_filtro.pack(side="left", padx=(0, 12))
combo_filtro.bind("<<ComboboxSelected>>", aplicar_filtro)

tk.Button(
    controles_topo,
    text="⬇ EXPORTAR CSV",
    command=exportar_csv,
    bg=cor_card_alt,
    fg=cor_ciano,
    activebackground=cor_azul,
    activeforeground="white",
    font=("Segoe UI", 9, "bold"),
    relief="solid",
    bd=1,
    padx=10,
    pady=4,
    cursor="hand2",
).pack(side="left")

abas = ttk.Notebook(janela)
abas.pack(fill="both", expand=True, padx=22, pady=(6, 18))

aba_diario = tk.Frame(abas, bg=cor_fundo)
aba_fixos = tk.Frame(abas, bg=cor_fundo)
aba_resumo = tk.Frame(abas, bg=cor_fundo)
aba_caixa = tk.Frame(abas, bg=cor_fundo)

abas.add(aba_diario, text=" 📅 LANÇAMENTOS DIÁRIOS ")
abas.add(aba_fixos, text=" 🔄 GASTOS FIXOS MENSAIS ")
abas.add(aba_resumo, text=" 📊 RESUMO & GRÁFICO ")
abas.add(aba_caixa, text=" 💵 SALDO EM CAIXA ")


def criar_entry(parent, width=None, pady=(0, 6)):
    kwargs = dict(
        font=("Segoe UI", 10),
        bg=cor_input,
        fg=cor_texto,
        insertbackground=cor_ciano,
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=cor_borda,
        highlightcolor=cor_ciano,
    )
    if width:
        kwargs["width"] = width
    e = tk.Entry(parent, **kwargs)
    e.pack(anchor="w", fill=None if width else "x", padx=10, pady=pady)
    return e


# ==================== ABA 1: LANÇAMENTOS DIÁRIOS ====================
frame_esq = tk.Frame(aba_diario, bg=cor_fundo, width=320)
frame_esq.pack(side="left", fill="y", padx=(0, 16), pady=10)

frame_ganho = tk.LabelFrame(
    frame_esq,
    text=" 💰 REGISTRAR GANHO ",
    font=("Segoe UI", 10, "bold"),
    fg=cor_verde,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
frame_ganho.pack(fill="x", pady=(0, 12), ipady=6, ipadx=10)

tk.Label(frame_ganho, text="Descrição", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)).pack(
    anchor="w", padx=10
)
desc_ganho = criar_entry(frame_ganho)

tk.Label(frame_ganho, text="Valor R$", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)).pack(
    anchor="w", padx=10
)
val_ganho = criar_entry(frame_ganho)

tk.Label(frame_ganho, text="Data (DD/MM/AAAA)", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)).pack(
    anchor="w", padx=10
)
data_ganho = criar_entry(frame_ganho)
data_ganho.insert(0, pegar_data())


def add_ganho():
    try:
        d = desc_ganho.get().strip()
        v = float(limpar_texto(val_ganho.get()))
        dt = data_ganho.get().strip() or pegar_data()
        if not d:
            messagebox.showwarning("Aviso", "Coloque uma descrição!")
            return
        if v <= 0:
            messagebox.showwarning("Aviso", "O valor deve ser maior que zero!")
            return
        ganhos.append({"descricao": d, "valor": v, "data": dt})
        desc_ganho.delete(0, tk.END)
        val_ganho.delete(0, tk.END)
        data_ganho.delete(0, tk.END)
        data_ganho.insert(0, pegar_data())
        atualizar_filtro_opcoes()
        atualizar_tudo()
        salvar_dados()
    except ValueError:
        messagebox.showerror("Erro", "Valor inválido!")


tk.Button(
    frame_ganho,
    text="➕ ADICIONAR GANHO",
    command=add_ganho,
    bg=cor_verde,
    fg="#06281e",
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    pady=4,
    cursor="hand2",
).pack(fill="x", padx=10, pady=4)

frame_gasto = tk.LabelFrame(
    frame_esq,
    text=" 💸 REGISTRAR GASTO ",
    font=("Segoe UI", 10, "bold"),
    fg=cor_vermelho,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
frame_gasto.pack(fill="x", pady=(0, 12), ipady=6, ipadx=10)

tk.Label(
    frame_gasto,
    text="Descrição (ex: Mercado, Restaurante)",
    fg=cor_muted,
    bg=cor_card,
    font=("Segoe UI", 9),
).pack(anchor="w", padx=10)
desc_gasto = criar_entry(frame_gasto)

tk.Label(frame_gasto, text="Valor R$", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)).pack(
    anchor="w", padx=10
)
val_gasto = criar_entry(frame_gasto)

tk.Label(frame_gasto, text="Data (DD/MM/AAAA)", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)).pack(
    anchor="w", padx=10
)
data_gasto = criar_entry(frame_gasto)
data_gasto.insert(0, pegar_data())


def add_gasto():
    try:
        d = desc_gasto.get().strip()
        v = float(limpar_texto(val_gasto.get()))
        dt = data_gasto.get().strip() or pegar_data()
        if not d:
            messagebox.showwarning("Aviso", "Coloque uma descrição!")
            return
        if v <= 0:
            messagebox.showwarning("Aviso", "O valor deve ser maior que zero!")
            return
        gastos.append({"descricao": d, "valor": v, "data": dt})
        desc_gasto.delete(0, tk.END)
        val_gasto.delete(0, tk.END)
        data_gasto.delete(0, tk.END)
        data_gasto.insert(0, pegar_data())
        atualizar_filtro_opcoes()
        atualizar_tudo()
        salvar_dados()
    except ValueError:
        messagebox.showerror("Erro", "Valor inválido!")


tk.Button(
    frame_gasto,
    text="➖ ADICIONAR GASTO",
    command=add_gasto,
    bg=cor_vermelho,
    fg="white",
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    pady=4,
    cursor="hand2",
).pack(fill="x", padx=10, pady=4)

frame_del = tk.LabelFrame(
    frame_esq,
    text=" 🗑️ REMOVER LANÇAMENTO ",
    font=("Segoe UI", 10, "bold"),
    fg=cor_amarelo,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
frame_del.pack(fill="x", ipady=6, ipadx=10)

tk.Label(
    frame_del, text="Tipo: 1=Ganho  2=Gasto", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)
).pack(anchor="w", padx=10)
tipo_del = criar_entry(frame_del, width=6, pady=(0, 4))
tipo_del.insert(0, "2")

tk.Label(frame_del, text="Número do item (Nº)", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)).pack(
    anchor="w", padx=10
)
num_del = criar_entry(frame_del, width=6, pady=(0, 6))


def remover_item():
    try:
        t = tipo_del.get().strip()
        n = int(num_del.get()) - 1
        if t == "1":
            if 0 <= n < len(ganhos):
                ganhos.pop(n)
                num_del.delete(0, tk.END)
                atualizar_filtro_opcoes()
                atualizar_tudo()
                salvar_dados()
                messagebox.showinfo("Sucesso", "Ganho removido!")
            else:
                messagebox.showwarning("Aviso", "Número inválido!")
        elif t == "2":
            if 0 <= n < len(gastos):
                gastos.pop(n)
                num_del.delete(0, tk.END)
                atualizar_filtro_opcoes()
                atualizar_tudo()
                salvar_dados()
                messagebox.showinfo("Sucesso", "Gasto removido!")
            else:
                messagebox.showwarning("Aviso", "Número inválido!")
        else:
            messagebox.showwarning("Aviso", "Digite 1 para Ganho ou 2 para Gasto!")
    except ValueError:
        messagebox.showerror("Erro", "Digite um número válido!")


tk.Button(
    frame_del,
    text="REMOVER ITEM",
    command=remover_item,
    bg=cor_amarelo,
    fg="#1f1600",
    font=("Segoe UI", 9, "bold"),
    relief="flat",
    pady=4,
    cursor="hand2",
).pack(fill="x", padx=10, pady=4)

frame_dir = tk.Frame(aba_diario, bg=cor_fundo)
frame_dir.pack(side="right", fill="both", expand=True, pady=10)

resumo_top = tk.Frame(
    frame_dir, bg=cor_card, bd=1, highlightthickness=1, highlightbackground=cor_borda
)
resumo_top.pack(fill="x", pady=(0, 12))

lbl_total_g = tk.Label(
    resumo_top, text="📈 GANHOS: R$ 0,00", font=("Segoe UI", 10, "bold"), fg=cor_verde, bg=cor_card
)
lbl_total_g.pack(side="left", padx=14, pady=10)

lbl_total_ga = tk.Label(
    resumo_top, text="📉 GASTOS: R$ 0,00", font=("Segoe UI", 10, "bold"), fg=cor_vermelho, bg=cor_card
)
lbl_total_ga.pack(side="left", padx=14, pady=10)

lbl_fixos_total = tk.Label(
    resumo_top, text="🔄 FIXOS: R$ 0,00", font=("Segoe UI", 10, "bold"), fg=cor_amarelo, bg=cor_card
)
lbl_fixos_total.pack(side="left", padx=14, pady=10)

lbl_sobra = tk.Label(
    resumo_top, text="⚡ SALDO: R$ 0,00", font=("Segoe UI", 11, "bold"), fg=cor_ciano, bg=cor_card
)
lbl_sobra.pack(side="right", padx=14, pady=10)

frame_lg = tk.LabelFrame(
    frame_dir,
    text=" 📈 HISTÓRICO DE GANHOS ",
    font=("Segoe UI", 10, "bold"),
    fg=cor_verde,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
frame_lg.pack(fill="both", expand=True, pady=(0, 10))
lista_ganhos = tk.Text(
    frame_lg,
    height=10,
    bg=cor_input,
    fg=cor_texto,
    relief="solid",
    bd=1,
    font=("Consolas", 10),
    highlightthickness=0,
)
lista_ganhos.pack(fill="both", expand=True, padx=10, pady=8)

frame_lgasto = tk.LabelFrame(
    frame_dir,
    text=" 📉 HISTÓRICO DE GASTOS ",
    font=("Segoe UI", 10, "bold"),
    fg=cor_vermelho,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
frame_lgasto.pack(fill="both", expand=True)
lista_gastos = tk.Text(
    frame_lgasto,
    height=10,
    bg=cor_input,
    fg=cor_texto,
    relief="solid",
    bd=1,
    font=("Consolas", 10),
    highlightthickness=0,
)
lista_gastos.pack(fill="both", expand=True, padx=10, pady=8)

# ==================== ABA 2: GASTOS FIXOS MENSAIS ====================
frame_fixos_esq = tk.Frame(aba_fixos, bg=cor_fundo, width=340)
frame_fixos_esq.pack(side="left", fill="y", padx=(0, 16), pady=12)

card_add_fixo = tk.LabelFrame(
    frame_fixos_esq,
    text=" 🔄 NOVO GASTO FIXO ",
    font=("Segoe UI", 11, "bold"),
    fg=cor_amarelo,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
card_add_fixo.pack(fill="x", pady=(0, 12), ipady=10, ipadx=12)

tk.Label(
    card_add_fixo,
    text="Descrição (ex: Aluguel, Internet, SaaS)",
    fg=cor_muted,
    bg=cor_card,
    font=("Segoe UI", 9),
).pack(anchor="w", padx=10)
desc_fixo = criar_entry(card_add_fixo)

tk.Label(
    card_add_fixo, text="Valor Mensal R$", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)
).pack(anchor="w", padx=10)
val_fixo = criar_entry(card_add_fixo, pady=(0, 8))


def add_fixo():
    try:
        d = desc_fixo.get().strip()
        v = float(limpar_texto(val_fixo.get()))
        if not d:
            messagebox.showwarning("Aviso", "Digite uma descrição para o gasto fixo!")
            return
        if v <= 0:
            messagebox.showwarning("Aviso", "O valor mensal deve ser maior que zero!")
            return
        fixos.append({"descricao": d, "valor": v})
        desc_fixo.delete(0, tk.END)
        val_fixo.delete(0, tk.END)
        atualizar_tudo()
        salvar_dados()
    except ValueError:
        messagebox.showerror("Erro", "Valor mensal inválido!")


tk.Button(
    card_add_fixo,
    text="➕ ADICIONAR GASTO FIXO",
    command=add_fixo,
    bg=cor_amarelo,
    fg="#1f1600",
    font=("Segoe UI", 10, "bold"),
    relief="flat",
    pady=4,
    cursor="hand2",
).pack(fill="x", padx=10, pady=4)

card_del_fixo = tk.LabelFrame(
    frame_fixos_esq,
    text=" 🗑️ REMOVER GASTO FIXO ",
    font=("Segoe UI", 11, "bold"),
    fg=cor_ciano,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
card_del_fixo.pack(fill="x", ipady=10, ipadx=12)

tk.Label(
    card_del_fixo, text="Número do gasto fixo", fg=cor_muted, bg=cor_card, font=("Segoe UI", 9)
).pack(anchor="w", padx=10)
num_fixo_del = criar_entry(card_del_fixo, width=8, pady=(0, 8))


def remover_fixo():
    try:
        n = int(num_fixo_del.get()) - 1
        if 0 <= n < len(fixos):
            fixos.pop(n)
            num_fixo_del.delete(0, tk.END)
            atualizar_tudo()
            salvar_dados()
            messagebox.showinfo("Sucesso", "Gasto fixo removido!")
        else:
            messagebox.showwarning("Aviso", "Número inválido!")
    except ValueError:
        messagebox.showerror("Erro", "Digite um número válido!")


tk.Button(
    card_del_fixo,
    text="REMOVER FIXO",
    command=remover_fixo,
    bg=cor_card_alt,
    fg=cor_texto,
    font=("Segoe UI", 9, "bold"),
    relief="solid",
    bd=1,
    pady=4,
    cursor="hand2",
).pack(fill="x", padx=10, pady=4)

frame_fixos_dir = tk.LabelFrame(
    aba_fixos,
    text=" 📋 LISTA DE GASTOS FIXOS MENSAIS ",
    font=("Segoe UI", 11, "bold"),
    fg=cor_amarelo,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
frame_fixos_dir.pack(side="right", fill="both", expand=True, pady=12)

lista_fixos = tk.Text(
    frame_fixos_dir,
    bg=cor_input,
    fg=cor_texto,
    relief="solid",
    bd=1,
    font=("Consolas", 11),
    highlightthickness=0,
)
lista_fixos.pack(fill="both", expand=True, padx=12, pady=12)


# ==================== ABA 3: RESUMO & GRÁFICO ====================
cards_resumo = tk.Frame(aba_resumo, bg=cor_fundo)
cards_resumo.pack(fill="x", pady=(10, 12))

for col in range(6):
    cards_resumo.columnconfigure(col, weight=1, uniform="resumo")

card_estilo = dict(
    font=("Segoe UI", 10, "bold"),
    bg=cor_card,
    bd=1,
    relief="solid",
    padx=8,
    pady=12,
    justify="center",
)

lbl_res_caixa = tk.Label(cards_resumo, text="💵 SALDO EM CAIXA\nR$ 0,00", fg=cor_ciano, **card_estilo)
lbl_res_caixa.grid(row=0, column=0, padx=4, sticky="nsew")

lbl_res_ganhos = tk.Label(cards_resumo, text="📈 GANHOS\nR$ 0,00", fg=cor_verde, **card_estilo)
lbl_res_ganhos.grid(row=0, column=1, padx=4, sticky="nsew")

lbl_res_gastos = tk.Label(cards_resumo, text="📉 GASTOS\nR$ 0,00", fg=cor_vermelho, **card_estilo)
lbl_res_gastos.grid(row=0, column=2, padx=4, sticky="nsew")

lbl_res_disponivel = tk.Label(
    cards_resumo, text="⚡ SALDO DISPONÍVEL\nR$ 0,00", fg=cor_verde, **card_estilo
)
lbl_res_disponivel.grid(row=0, column=3, padx=4, sticky="nsew")

lbl_res_fixos = tk.Label(
    cards_resumo, text="🔄 FIXOS MENSAIS\nR$ 0,00", fg=cor_amarelo, **card_estilo
)
lbl_res_fixos.grid(row=0, column=4, padx=4, sticky="nsew")

lbl_mensal_final = tk.Label(
    cards_resumo, text="💎 SOBRA APÓS FIXOS\nR$ 0,00", fg=cor_verde, **card_estilo
)
lbl_mensal_final.grid(row=0, column=5, padx=4, sticky="nsew")

frame_grafico = tk.Frame(
    aba_resumo, bg=cor_card, bd=1, highlightthickness=1, highlightbackground=cor_borda
)
frame_grafico.pack(fill="both", expand=True, pady=(0, 6))

fig, (ax_bar, ax_donut) = plt.subplots(1, 2, figsize=(11, 4.6), dpi=100)
fig.patch.set_facecolor(cor_card)

canvas = FigureCanvasTkAgg(fig, master=frame_grafico)
canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)


# ==================== ABA 4: SALDO EM CAIXA ====================
card_caixa = tk.LabelFrame(
    aba_caixa,
    text=" 💵 CONTROLE DE SALDO EM CAIXA ",
    font=("Segoe UI", 12, "bold"),
    fg=cor_ciano,
    bg=cor_card,
    bd=1,
    highlightthickness=1,
    highlightbackground=cor_borda,
)
card_caixa.pack(fill="x", padx=40, pady=30, ipady=18, ipadx=20)

tk.Label(
    card_caixa, text="SALDO ATUAL EM CAIXA:", fg=cor_muted, bg=cor_card, font=("Segoe UI", 10, "bold")
).pack(anchor="w", padx=12, pady=(8, 2))

lbl_caixa_atual_aba = tk.Label(
    card_caixa, text="R$ 0,00", fg=cor_verde, bg=cor_card, font=("Segoe UI", 22, "bold")
)
lbl_caixa_atual_aba.pack(anchor="w", padx=12, pady=(0, 14))

tk.Label(
    card_caixa,
    text="Definir / Atualizar Valor em Caixa (R$):",
    fg=cor_muted,
    bg=cor_card,
    font=("Segoe UI", 10),
).pack(anchor="w", padx=12)

entry_caixa = criar_entry(card_caixa, width=24, pady=(2, 10))


def definir_caixa():
    global saldo_em_caixa
    try:
        novo_saldo = float(limpar_texto(entry_caixa.get()))
        saldo_em_caixa = novo_saldo
        entry_caixa.delete(0, tk.END)
        atualizar_tudo()
        salvar_dados()
        messagebox.showinfo("Salvo", "Saldo em caixa atualizado com sucesso!")
    except ValueError:
        messagebox.showerror("Erro", "Digite um valor válido para o saldo em caixa!")


tk.Button(
    card_caixa,
    text="💾 ATUALIZAR SALDO EM CAIXA",
    command=definir_caixa,
    bg=cor_ciano,
    fg="#06131a",
    font=("Segoe UI", 10, "bold"),
    relief="flat",
    padx=14,
    pady=6,
    cursor="hand2",
).pack(anchor="w", padx=12, pady=4)


# ==================== INICIALIZAÇÃO ====================
carregar_dados()
atualizar_filtro_opcoes()
atualizar_tudo()
janela.mainloop()