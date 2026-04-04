# reologia_plot_style.py — Estilo científico claro (publicação)
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import LogLocator

# ─── Cores de fundo (tema claro) ──────────────────────────────────────
BG_FIG   = "#ffffff"   # fundo da figura
BG_AXES  = "#ffffff"   # fundo do painel de plot
FG_TEXT  = "#1a1a1a"   # texto: rótulos, títulos, ticks
FG_GRID  = "#a6a6a6"   # linhas de grade (escurecido para melhor visibilidade)
FG_SPINE = "#333333"   # bordas dos eixos (spines)
FG_TICK  = "#333333"   # marcações dos eixos

# Alias legado (usado em make_fig e SC_DATA)
BG_DARK  = BG_FIG

# ─── Paleta de dados (cores vivas sobre fundo branco) ────────────────
PALETTE = {
    "data"   : "#1f77b4",   # AZUL  — pontos experimentais (média)
    "raw"    : "#999999",   # CINZA — dados brutos / individuais
    "fit"    : "#d62728",   # VERMELHO — melhor modelo (linha principal)
    "alt1"   : "#2ca02c",   # VERDE — 2º modelo
    "alt2"   : "#ff7f0e",   # LARANJA — 3º modelo
    "alt3"   : "#9467bd",   # ROXO — 4º modelo
    "alt4"   : "#17becf",   # CIANO — 5º modelo
    "ref"    : "#e6b800",   # AMARELO ESCURO — referência externa (MCR102)
    "warn"   : "#d62728",   # VERMELHO — pontos descartados / alertas
    "std"    : "#7f7f7f",   # CINZA MÉDIO — barras de erro / desvio padrão
}

# ─── Kwargs reutilizáveis ─────────────────────────────────────────────
SC_DATA = dict(color=PALETTE['data'], s=60, zorder=7,
               edgecolors='black', linewidths=0.5)
SC_RAW  = dict(color=PALETTE['raw'],  s=18, zorder=4,
               alpha=0.40, edgecolors='none')
SC_REF  = dict(color=PALETTE['ref'],  s=55, marker='D', zorder=6,
               edgecolors='black', linewidths=0.5, alpha=0.90)
EB_KW   = dict(fmt='none', alpha=0.60, capsize=3.5,
               capthick=1.0, elinewidth=1.2, zorder=6)
LN_BEST = dict(linewidth=2.2, linestyle='-',  zorder=9)
LN_ALT1 = dict(linewidth=1.7, linestyle='--', zorder=8, alpha=0.85)
LN_ALT2 = dict(linewidth=1.5, linestyle='-.', zorder=7, alpha=0.75)
LN_ALT3 = dict(linewidth=1.3, linestyle=':',  zorder=6, alpha=0.60)
LN_ALT4 = dict(linewidth=1.2, linestyle=':',  zorder=5, alpha=0.50)
BAND_KW = dict(alpha=0.12, zorder=1)    # axvspan sombreado
ANNOT_BOX = dict(boxstyle='round,pad=0.4', facecolor='#ffffee',
                 edgecolor='#999999', alpha=0.92)
LEGEND_KW = dict(fontsize=8.5, framealpha=0.92, facecolor='white',
                 edgecolor='#999999', labelcolor=FG_TEXT,
                 handlelength=1.8, borderpad=0.5, labelspacing=0.35)
XLABEL_KW = dict(fontsize=11, color=FG_TEXT, labelpad=8)
YLABEL_KW = dict(fontsize=11, color=FG_TEXT, labelpad=8)
TITLE_KW  = dict(fontsize=12, color=FG_TEXT, fontweight='bold', pad=10)

# ─── Funções de setup ─────────────────────────────────────────────────
def apply_dark_style():
    '''Chamar UMA VEZ antes do mainloop do app.
    Nome legado mantido para compatibilidade; aplica o tema claro.'''
    plt.rcParams.update({
        'figure.facecolor': BG_FIG,    'axes.facecolor': BG_AXES,
        'savefig.facecolor': BG_FIG,   'text.color': FG_TEXT,
        'axes.labelcolor': FG_TEXT,     'xtick.color': FG_TICK,
        'ytick.color': FG_TICK,         'axes.titlecolor': FG_TEXT,
        'axes.edgecolor': FG_SPINE,     'axes.linewidth': 0.8,
        'xtick.major.size': 5,          'xtick.minor.size': 3,
        'ytick.major.size': 5,          'ytick.minor.size': 3,
        'xtick.major.width': 0.8,       'ytick.major.width': 0.8,
        'xtick.direction': 'in',        'ytick.direction': 'in',
        'axes.grid': True,              'axes.grid.which': 'major',
        'grid.color': FG_GRID,          'grid.linestyle': '-',
        'grid.linewidth': 0.6,          'grid.alpha': 0.70,
        'font.size': 10,                'lines.linewidth': 1.8,
        'legend.framealpha': 0.92,      'legend.facecolor': 'white',
        'legend.edgecolor': '#999999',  'legend.labelcolor': FG_TEXT,
        'figure.dpi': 110,
    })

def style_ax(ax):
    '''Aplicar a qualquer eixo recém-criado ou após ax.clear().'''
    ax.set_facecolor(BG_AXES)
    for sp in ax.spines.values():
        sp.set_color(FG_SPINE); sp.set_linewidth(0.8)
    ax.tick_params(colors=FG_TICK, which='both', direction='in',
                   labelsize=9.5, length=5)
    ax.tick_params(which='minor', length=3)
    ax.xaxis.label.set_color(FG_TEXT)
    ax.yaxis.label.set_color(FG_TEXT)
    ax.title.set_color(FG_TEXT)
    ax.grid(color=FG_GRID, linestyle='-', linewidth=0.6, alpha=0.70)
    ax.grid(which='minor', color=FG_GRID, linestyle=':', linewidth=0.5, alpha=0.50)

def log_axes(ax, which='both'):
    '''Escala log + minor ticks corretos em log.'''
    if which in ('x','both'):
        ax.set_xscale('log')
        ax.xaxis.set_minor_locator(LogLocator(subs=np.arange(2,10)))
    if which in ('y','both'):
        ax.set_yscale('log')
        ax.yaxis.set_minor_locator(LogLocator(subs=np.arange(2,10)))
    ax.grid(color=FG_GRID, linestyle='-', linewidth=0.6, alpha=0.70)
    ax.grid(which='minor', color=FG_GRID, linestyle=':', linewidth=0.5, alpha=0.50)

def make_fig(figsize=(9,6), dpi=110):
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(BG_FIG)
    style_ax(ax); return fig, ax

def annot(ax, text, pos='lower right'):
    '''Caixa de texto com parâmetros do modelo dentro do gráfico.'''
    lm = {'lower right':(0.97,0.04,'right','bottom'),
          'upper left' :(0.03,0.96,'left','top'),
          'upper right':(0.97,0.96,'right','top'),
          'lower left' :(0.03,0.04,'left','bottom')}
    x,y,ha,va = lm.get(pos, lm['lower right'])
    ax.text(x, y, text, transform=ax.transAxes, ha=ha, va=va,
            bbox=ANNOT_BOX, color=FG_TEXT, fontsize=8.5)
