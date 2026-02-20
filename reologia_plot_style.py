# -*- coding: utf-8 -*-
"""
reologia_plot_style.py
======================
Módulo de estilo e funções de plotagem para o Reômetro Capilar.

Contém:
  - STYLE: dicionário central com todas as configurações visuais
  - apply_dark_style(): aplica o tema escuro globalmente ao matplotlib
  - make_figure() / make_subplots(): cria figuras já estilizadas
  - Funções de plotagem prontas: plot_flow_curve, plot_viscosity,
    plot_nprime, plot_bagley, plot_mooney, plot_overlay

Uso mínimo no app:
    from reologia_plot_style import apply_dark_style, make_figure, STYLE
    apply_dark_style()
    fig, ax = make_figure()
    ax.scatter(gd, tau, **STYLE['scatter']['data'])
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import LogLocator, LogFormatter


# ══════════════════════════════════════════════════════════════════════════════
# 1. PALETA E CONFIGURAÇÕES CENTRAIS
# ══════════════════════════════════════════════════════════════════════════════

# Cores base — escuras para fundo do customtkinter
BG_DARK   = "#1e1e2e"   # fundo da figura (combine com a cor do frame CTk)
BG_AXES   = "#2a2a3e"   # fundo do painel de plot
FG_TEXT   = "#cdd6f4"   # cor do texto / rótulos
FG_GRID   = "#45475a"   # linhas de grade
FG_SPINE  = "#585b70"   # bordas dos eixos (spines)
FG_TICK   = "#cdd6f4"   # marcações dos eixos

# Paleta de dados — alta visibilidade no fundo escuro
PALETTE = {
    "data"    : "#89b4fa",   # azul suave (pontos experimentais principais)
    "fit"     : "#f38ba8",   # rosa/vermelho (curva ajustada / melhor modelo)
    "alt1"    : "#a6e3a1",   # verde (modelo alternativo 1)
    "alt2"    : "#fab387",   # laranja (modelo alternativo 2)
    "alt3"    : "#cba6f7",   # lilás (modelo alternativo 3)
    "ref"     : "#f9e2af",   # amarelo claro (dado de referência / rotacional)
    "std"     : "#89b4fa",   # mesmo azul para barras de erro (mais transparente)
    "region"  : "#a6e3a1",   # verde para regiões sombreadas (axvspan)
    "warning" : "#f38ba8",   # vermelho para pontos descartados / alertas
    "neutral" : "#6c7086",   # cinza para pontos desativados / fora da faixa
}

# Configurações por tipo de elemento
STYLE = {
    # ── scatter de dados principais ───────────────────────────────────────────
    "scatter": {
        "data": dict(
            color=PALETTE["data"],
            s=60,
            zorder=7,
            edgecolors="#1e1e2e",
            linewidths=0.6,
        ),
        "reference": dict(         # dado do rotacional / referência externa
            color=PALETTE["ref"],
            s=55,
            marker="D",
            zorder=6,
            edgecolors="#1e1e2e",
            linewidths=0.5,
            alpha=0.90,
        ),
        "discarded": dict(         # pontos desativados / outliers
            color=PALETTE["warning"],
            s=50,
            marker="x",
            zorder=4,
            alpha=0.50,
            linewidths=1.4,
        ),
        "neutral": dict(           # pontos fora da faixa de interesse
            color=PALETTE["neutral"],
            s=35,
            zorder=4,
            alpha=0.45,
        ),
    },

    # ── linhas de ajuste ──────────────────────────────────────────────────────
    "line": {
        "best_fit": dict(
            color=PALETTE["fit"],
            linewidth=2.4,
            linestyle="-",
            zorder=9,
        ),
        "alt1": dict(
            color=PALETTE["alt1"],
            linewidth=1.7,
            linestyle="--",
            zorder=8,
            alpha=0.85,
        ),
        "alt2": dict(
            color=PALETTE["alt2"],
            linewidth=1.7,
            linestyle="-.",
            zorder=8,
            alpha=0.85,
        ),
        "alt3": dict(
            color=PALETTE["alt3"],
            linewidth=1.5,
            linestyle=":",
            zorder=8,
            alpha=0.80,
        ),
        "reference": dict(         # curva do rotacional / referência
            color=PALETTE["ref"],
            linewidth=1.8,
            linestyle="--",
            zorder=7,
            alpha=0.80,
        ),
    },

    # ── barras de erro ────────────────────────────────────────────────────────
    "errorbar": dict(
        fmt="none",
        color=PALETTE["std"],
        alpha=0.55,
        capsize=3.5,
        capthick=1.0,
        elinewidth=1.2,
        zorder=6,
    ),

    # ── região sombreada (ex.: faixa do capilar) ──────────────────────────────
    "band": dict(
        color=PALETTE["region"],
        alpha=0.08,
        zorder=1,
    ),

    # ── anotações de texto inline ─────────────────────────────────────────────
    "annotation_box": dict(
        boxstyle="round,pad=0.4",
        facecolor="#313244",
        edgecolor=FG_SPINE,
        alpha=0.90,
    ),
    "annotation_text": dict(
        color=FG_TEXT,
        fontsize=8.5,
    ),

    # ── grade ─────────────────────────────────────────────────────────────────
    "grid_major": dict(
        color=FG_GRID,
        linestyle="--",
        linewidth=0.55,
        alpha=0.70,
    ),
    "grid_minor": dict(
        color=FG_GRID,
        linestyle=":",
        linewidth=0.35,
        alpha=0.40,
    ),

    # ── legenda ───────────────────────────────────────────────────────────────
    "legend": dict(
        fontsize=8.5,
        framealpha=0.85,
        facecolor="#313244",
        edgecolor=FG_SPINE,
        labelcolor=FG_TEXT,
        handlelength=1.8,
        handleheight=0.9,
        borderpad=0.5,
        labelspacing=0.35,
    ),

    # ── rótulos e títulos ─────────────────────────────────────────────────────
    "xlabel": dict(fontsize=11, color=FG_TEXT, labelpad=8),
    "ylabel": dict(fontsize=11, color=FG_TEXT, labelpad=8),
    "title":  dict(fontsize=12, color=FG_TEXT, fontweight="bold", pad=10),
    "suptitle": dict(fontsize=13, color=FG_TEXT, fontweight="bold"),
}


# ══════════════════════════════════════════════════════════════════════════════
# 2. APLICAR TEMA ESCURO GLOBALMENTE
# ══════════════════════════════════════════════════════════════════════════════

def apply_dark_style():
    """
    Aplica o tema escuro ao matplotlib via rcParams.
    Chamar UMA VEZ na inicialização do app (antes de criar qualquer figura).

    Exemplo:
        import reologia_plot_style as rps
        rps.apply_dark_style()
    """
    plt.rcParams.update({
        # fundo
        "figure.facecolor"      : BG_DARK,
        "axes.facecolor"        : BG_AXES,
        "savefig.facecolor"     : BG_DARK,

        # texto e rótulos
        "text.color"            : FG_TEXT,
        "axes.labelcolor"       : FG_TEXT,
        "xtick.color"           : FG_TICK,
        "ytick.color"           : FG_TICK,
        "axes.titlecolor"       : FG_TEXT,

        # spines
        "axes.edgecolor"        : FG_SPINE,
        "axes.linewidth"        : 0.8,

        # ticks
        "xtick.major.size"      : 4.5,
        "xtick.minor.size"      : 2.5,
        "ytick.major.size"      : 4.5,
        "ytick.minor.size"      : 2.5,
        "xtick.major.width"     : 0.8,
        "ytick.major.width"     : 0.8,
        "xtick.direction"       : "out",
        "ytick.direction"       : "out",

        # grade
        "axes.grid"             : True,
        "axes.grid.which"       : "both",
        "grid.color"            : FG_GRID,
        "grid.linestyle"        : "--",
        "grid.linewidth"        : 0.5,
        "grid.alpha"            : 0.60,

        # fonte global
        "font.family"           : "DejaVu Sans",
        "font.size"             : 10,

        # linhas
        "lines.linewidth"       : 1.8,
        "lines.markersize"      : 6,

        # legenda
        "legend.framealpha"     : 0.85,
        "legend.facecolor"      : "#313244",
        "legend.edgecolor"      : FG_SPINE,
        "legend.labelcolor"     : FG_TEXT,
        "legend.fontsize"       : 9,

        # figura
        "figure.dpi"            : 110,
        "figure.autolayout"     : False,
    })


# ══════════════════════════════════════════════════════════════════════════════
# 3. HELPERS DE CRIAÇÃO DE FIGURA / EIXOS
# ══════════════════════════════════════════════════════════════════════════════

def _style_axes(ax):
    """Aplica estilo padrão a um eixo já criado."""
    ax.set_facecolor(BG_AXES)
    for spine in ax.spines.values():
        spine.set_color(FG_SPINE)
        spine.set_linewidth(0.8)
    ax.tick_params(colors=FG_TICK, which="both", direction="out",
                   labelsize=9.5, length=4)
    ax.tick_params(which="minor", length=2.5)
    ax.xaxis.label.set_color(FG_TEXT)
    ax.yaxis.label.set_color(FG_TEXT)
    ax.title.set_color(FG_TEXT)
    ax.grid(**STYLE["grid_major"])
    ax.grid(which="minor", **STYLE["grid_minor"])
    return ax


def make_figure(figsize=(9, 6), dpi=110):
    """
    Cria uma figura com um único eixo já estilizado.

    Returns
    -------
    fig, ax
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(BG_DARK)
    _style_axes(ax)
    return fig, ax


def make_subplots(nrows=1, ncols=2, figsize=None, dpi=110, **kwargs):
    """
    Cria figura com subplots já estilizados.

    Returns
    -------
    fig, axes  (axes é array numpy)
    """
    if figsize is None:
        figsize = (8 * ncols, 5.5 * nrows)
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, dpi=dpi, **kwargs)
    fig.patch.set_facecolor(BG_DARK)
    for ax in np.array(axes).flat:
        _style_axes(ax)
    return fig, axes


def make_gridspec_figure(figsize=(16, 10), dpi=110):
    """
    Cria figura com GridSpec 2×3 para o painel principal da análise.
    Layout:
      [0,0:2] curva de fluxo grande  |  [0,2] viscosidade
      [1,0]   n' vs γ̇               |  [1,1] resíduos     |  [1,2] parâmetros (tabela)

    Returns
    -------
    fig, dict com chaves: 'flow', 'visc', 'nprime', 'residuals', 'params'
    """
    fig = plt.figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(BG_DARK)
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.38, wspace=0.32)

    axes = {
        "flow"     : fig.add_subplot(gs[0, :2]),
        "visc"     : fig.add_subplot(gs[0, 2]),
        "nprime"   : fig.add_subplot(gs[1, 0]),
        "residuals": fig.add_subplot(gs[1, 1]),
        "params"   : fig.add_subplot(gs[1, 2]),
    }
    for ax in axes.values():
        _style_axes(ax)
    return fig, axes


# ══════════════════════════════════════════════════════════════════════════════
# 4. FUNÇÕES DE PLOTAGEM PRONTAS
# ══════════════════════════════════════════════════════════════════════════════

def _log_axes(ax, which="both"):
    """Configura escala log + grid de minor ticks em eixos logarítmicos."""
    if which in ("x", "both"):
        ax.set_xscale("log")
        ax.xaxis.set_minor_locator(LogLocator(subs=np.arange(2, 10)))
    if which in ("y", "both"):
        ax.set_yscale("log")
        ax.yaxis.set_minor_locator(LogLocator(subs=np.arange(2, 10)))
    ax.grid(**STYLE["grid_major"])
    ax.grid(which="minor", **STYLE["grid_minor"])


def plot_flow_curve(ax, gd, tau,
                    tau_std=None,
                    gd_fit=None, tau_fit_best=None, label_best="",
                    extra_fits=None,        # lista de (gd_fit, tau_fit, label, key)
                    gd_ref=None, tau_ref=None, label_ref="Referência",
                    band_range=None,        # (gd_min, gd_max) para região sombreada
                    log_log=True,
                    xlabel="Taxa de Cisalhamento γ̇ (s⁻¹)",
                    ylabel="Tensão de Cisalhamento τ_w (Pa)",
                    title="Curva de Fluxo"):
    """
    Plota a curva de fluxo completa com todos os elementos visuais.

    Parâmetros
    ----------
    ax          : eixo matplotlib
    gd, tau     : arrays dos dados experimentais
    tau_std     : desvio-padrão de tau por ponto (opcional → barras de erro)
    gd_fit      : array de γ̇ para a curva suave dos modelos
    tau_fit_best: τ do melhor modelo
    label_best  : texto da legenda do melhor modelo
    extra_fits  : [(gd_fit, tau_fit, label, 'alt1'|'alt2'|'alt3'), ...]
    gd_ref      : γ̇ do dado de referência (ex: rotacional)
    tau_ref     : τ do dado de referência
    band_range  : (50, 2000) → sombreia a faixa de operação do capilar
    log_log     : True = escala log-log
    """
    # Região sombreada (faixa do capilar)
    if band_range is not None:
        ax.axvspan(band_range[0], band_range[1], label="Faixa do capilar",
                   **STYLE["band"])

    # Dado de referência (rotacional)
    if gd_ref is not None and tau_ref is not None:
        ax.scatter(gd_ref, tau_ref, label=label_ref, **STYLE["scatter"]["reference"])

    # Barras de erro ou pontos simples
    if tau_std is not None:
        ax.errorbar(gd, tau, yerr=tau_std, **STYLE["errorbar"])
    ax.scatter(gd, tau, label="Dados experimentais", **STYLE["scatter"]["data"])

    # Curvas de ajuste secundárias
    if extra_fits:
        line_keys = ["alt1", "alt2", "alt3"]
        for i, (gd_f, tau_f, lbl, *key) in enumerate(extra_fits):
            k = key[0] if key else line_keys[i % 3]
            ax.plot(gd_f, tau_f, label=lbl, **STYLE["line"][k])

    # Melhor ajuste (por cima)
    if gd_fit is not None and tau_fit_best is not None:
        ax.plot(gd_fit, tau_fit_best, label=label_best, **STYLE["line"]["best_fit"])

    if log_log:
        _log_axes(ax)

    ax.set_xlabel(xlabel, **STYLE["xlabel"])
    ax.set_ylabel(ylabel, **STYLE["ylabel"])
    ax.set_title(title, **STYLE["title"])
    ax.legend(loc="lower right", **STYLE["legend"])
    return ax


def plot_viscosity(ax, gd, eta, eta_std=None,
                   gd_ref=None, eta_ref=None, label_ref="Referência",
                   band_range=None,
                   title="Viscosidade Aparente"):
    """Plota η = τ/γ̇ vs γ̇ em log-log."""
    if band_range is not None:
        ax.axvspan(band_range[0], band_range[1], **STYLE["band"])
    if gd_ref is not None and eta_ref is not None:
        ax.scatter(gd_ref, eta_ref, label=label_ref, **STYLE["scatter"]["reference"])
    if eta_std is not None:
        ax.errorbar(gd, eta, yerr=eta_std, **STYLE["errorbar"])
    ax.scatter(gd, eta, label="η experimental", **STYLE["scatter"]["data"])
    _log_axes(ax)
    ax.set_xlabel("Taxa de Cisalhamento γ̇ (s⁻¹)", **STYLE["xlabel"])
    ax.set_ylabel("Viscosidade η (Pa·s)", **STYLE["ylabel"])
    ax.set_title(title, **STYLE["title"])
    ax.legend(**STYLE["legend"])
    return ax


def plot_nprime(ax, gd_app, tau, n_prime_global=None, n_prime_local=None):
    """
    Gráfico de determinação de n' — ln(τ) vs ln(γ̇_app).
    Mostra a reta global e, se fornecido, a variação local de n'(γ̇).
    """
    valid = (gd_app > 0) & (tau > 0)
    log_gd = np.log(gd_app[valid])
    log_tau = np.log(tau[valid])

    ax.scatter(log_gd, log_tau, label="ln(τ) vs ln(γ̇_app)",
               **STYLE["scatter"]["data"])

    if n_prime_global is not None:
        # Linha de regressão global
        from scipy.stats import linregress
        slope, intercept, *_ = linregress(log_gd, log_tau)
        x_line = np.linspace(log_gd.min(), log_gd.max(), 80)
        ax.plot(x_line, slope * x_line + intercept,
                label=f"n' global = {slope:.3f}",
                **STYLE["line"]["best_fit"])

    ax.set_xlabel("ln(γ̇_app) (s⁻¹)", **STYLE["xlabel"])
    ax.set_ylabel("ln(τ_w) (Pa)", **STYLE["ylabel"])
    ax.set_title("Determinação de n' (Weissenberg-Rabinowitsch)", **STYLE["title"])
    ax.legend(**STYLE["legend"])
    return ax


def plot_bagley(ax, L_over_D_list, P_list, slope, intercept,
                target_gamma_label=""):
    """Gráfico do ajuste de Bagley: P vs L/D."""
    x_arr = np.array(sorted(L_over_D_list))
    y_pa  = slope * x_arr + intercept

    ax.scatter(L_over_D_list, np.array(P_list) / 1e5,
               label="Dados interpolados", **STYLE["scatter"]["data"])
    ax.plot(x_arr, y_pa / 1e5,
            label=f"Ajuste linear  τ_w,corr = {slope/2:.1f} Pa",
            **STYLE["line"]["best_fit"])

    ax.set_xlabel("L/D  (adimensional)", **STYLE["xlabel"])
    ax.set_ylabel("Pressão total ΔP (bar)", **STYLE["ylabel"])
    title_str = "Correção de Bagley"
    if target_gamma_label:
        title_str += f"  |  γ̇_app ≈ {target_gamma_label} s⁻¹"
    ax.set_title(title_str, **STYLE["title"])
    ax.legend(**STYLE["legend"])
    return ax


def plot_mooney(ax, inv_R_list, gd_app_list, slope, intercept):
    """Gráfico do ajuste de Mooney: γ̇_app vs 1/R."""
    x_arr = np.array(sorted(inv_R_list))
    ax.scatter(inv_R_list, gd_app_list,
               label="Dados", **STYLE["scatter"]["data"])
    ax.plot(x_arr, slope * x_arr + intercept,
            label=f"γ̇_true = {intercept:.1f} s⁻¹  |  V_slip = {slope/4:.4f} m/s",
            **STYLE["line"]["best_fit"])
    ax.set_xlabel("1/R  (m⁻¹)", **STYLE["xlabel"])
    ax.set_ylabel("γ̇_app  (s⁻¹)", **STYLE["ylabel"])
    ax.set_title("Correção de Mooney (Wall Slip)", **STYLE["title"])
    ax.legend(**STYLE["legend"])
    return ax


def plot_overlay(ax, datasets,
                 log_log=True,
                 band_range=None,
                 title="Comparativo — Curvas de Fluxo"):
    """
    Sobreposição de múltiplas amostras.

    datasets : lista de dicts com chaves obrigatórias:
               'gd'    : array de taxas de cisalhamento
               'tau'   : array de tensões
               'label' : str com nome da amostra
               Chaves opcionais:
               'tau_std', 'gd_fit', 'tau_fit', 'color'

    Exemplo:
        datasets = [
            {'gd': gd1, 'tau': tau1, 'label': 'Amostra A'},
            {'gd': gd2, 'tau': tau2, 'label': 'Amostra B',
             'gd_fit': gd_smooth, 'tau_fit': tau_model},
        ]
        plot_overlay(ax, datasets)
    """
    colors_cycle = [PALETTE[k] for k in
                    ("data", "fit", "alt1", "alt2", "alt3", "ref")]

    if band_range is not None:
        ax.axvspan(band_range[0], band_range[1], **STYLE["band"])

    for i, ds in enumerate(datasets):
        color = ds.get("color", colors_cycle[i % len(colors_cycle)])
        sc_kw = {**STYLE["scatter"]["data"], "color": color}
        ax.scatter(ds["gd"], ds["tau"], label=ds.get("label", f"#{i+1}"), **sc_kw)
        if "tau_std" in ds:
            eb_kw = {**STYLE["errorbar"], "color": color}
            ax.errorbar(ds["gd"], ds["tau"], yerr=ds["tau_std"], **eb_kw)
        if "gd_fit" in ds and "tau_fit" in ds:
            ln_kw = {**STYLE["line"]["best_fit"], "color": color}
            ax.plot(ds["gd_fit"], ds["tau_fit"], **ln_kw)

    if log_log:
        _log_axes(ax)
    ax.set_xlabel("Taxa de Cisalhamento γ̇ (s⁻¹)", **STYLE["xlabel"])
    ax.set_ylabel("Tensão de Cisalhamento τ_w (Pa)", **STYLE["ylabel"])
    ax.set_title(title, **STYLE["title"])
    ax.legend(**STYLE["legend"])
    return ax


def add_model_annotation(ax, params_dict, position="lower right"):
    """
    Adiciona caixa de texto com parâmetros do melhor modelo.

    params_dict : dict ordenado, ex:
        {'τ₀': '42.3 Pa', 'K': '18.5 Pa·sⁿ', 'n': '0.312', 'R²': '0.9912'}
    position    : 'lower right' | 'upper left' | 'upper right' | 'lower left'
    """
    text = "\n".join(f"{k} = {v}" for k, v in params_dict.items())
    loc_map = {
        "lower right": (0.97, 0.04, "right",  "bottom"),
        "upper left" : (0.03, 0.96, "left",   "top"),
        "upper right": (0.97, 0.96, "right",  "top"),
        "lower left" : (0.03, 0.04, "left",   "bottom"),
    }
    x, y, ha, va = loc_map.get(position, loc_map["lower right"])
    ax.text(x, y, text,
            transform=ax.transAxes,
            ha=ha, va=va,
            bbox=STYLE["annotation_box"],
            **STYLE["annotation_text"])


# ══════════════════════════════════════════════════════════════════════════════
# 5. INTEGRAÇÃO COM CUSTOMTKINTER (FigureCanvasTkAgg)
# ══════════════════════════════════════════════════════════════════════════════

def embed_figure(fig, parent_widget):
    """
    Embute uma figura matplotlib em um widget CTk/tkinter.

    Parâmetros
    ----------
    fig           : figura matplotlib já populada
    parent_widget : widget customtkinter pai (CTkFrame, etc.)

    Returns
    -------
    canvas : FigureCanvasTkAgg (chamar canvas.draw() para atualizar)

    Exemplo de uso no app:
        fig, ax = make_figure()
        plot_flow_curve(ax, gd, tau, ...)
        canvas = embed_figure(fig, self.graph_frame)
        canvas.get_tk_widget().pack(fill='both', expand=True)
    """
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    canvas = FigureCanvasTkAgg(fig, master=parent_widget)
    canvas.draw()
    return canvas


def update_canvas(canvas, fig):
    """
    Atualiza o canvas após modificar a figura.
    Mais eficiente que recriar o canvas inteiro.

    Uso:
        ax.clear()
        _style_axes(ax)
        plot_flow_curve(ax, gd_new, tau_new, ...)
        update_canvas(canvas, fig)
    """
    fig.tight_layout(pad=1.5)
    canvas.draw_idle()


# ══════════════════════════════════════════════════════════════════════════════
# 6. DEMO — executa se chamado diretamente
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from scipy.optimize import curve_fit
    from sklearn.metrics import r2_score

    apply_dark_style()

    # Dados sintéticos (HB: tau0=50, K=10, n=0.4)
    np.random.seed(42)
    gd_data = np.array([50, 100, 200, 500, 1000, 2000], dtype=float)
    tau_true = 50 + 10 * gd_data**0.4
    tau_data = tau_true + np.random.normal(0, tau_true * 0.04)
    tau_std  = tau_true * 0.04

    def hb(gd, t0, K, n): return t0 + K*gd**n
    popt, _ = curve_fit(hb, gd_data, tau_data, p0=[30, 5, 0.5],
                        bounds=([0, 1e-9, 1e-9], [500, 1e4, 3]))

    gd_smooth = np.geomspace(40, 2500, 300)
    tau_smooth = hb(gd_smooth, *popt)
    r2 = r2_score(tau_data, hb(gd_data, *popt))

    # Dado de referência simulado
    gd_ref = gd_data * 1.05
    tau_ref = tau_true * 1.03

    fig, ax = make_figure(figsize=(9, 6))
    plot_flow_curve(
        ax,
        gd=gd_data, tau=tau_data, tau_std=tau_std,
        gd_fit=gd_smooth, tau_fit_best=tau_smooth,
        label_best=f"Herschel-Bulkley  R²={r2:.4f}  ★",
        gd_ref=gd_ref, tau_ref=tau_ref, label_ref="MCR102 (referência)",
        band_range=(50, 2000),
        title="Curva de Fluxo — Demo do Módulo de Estilo",
    )
    add_model_annotation(ax, {
        "Modelo": "Herschel-Bulkley",
        "τ₀":  f"{popt[0]:.2f} Pa",
        "K":   f"{popt[1]:.4f} Pa·sⁿ",
        "n":   f"{popt[2]:.4f}",
        "R²":  f"{r2:.4f}",
    })

    fig.tight_layout(pad=1.5)
    fig.savefig("/tmp/demo_style.png", dpi=130, bbox_inches="tight")
    print("Demo salvo em /tmp/demo_style.png")
    plt.show()
