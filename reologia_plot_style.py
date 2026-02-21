import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import LogLocator
 
# ─── Cores de fundo ───────────────────────────────────────────────────
BG_DARK  = "#1e1e2e"   # fundo da figura — deve ser igual ao CTkFrame pai
BG_AXES  = "#2a2a3e"   # fundo do painel de plot
FG_TEXT  = "#cdd6f4"   # todo o texto: rótulos, títulos, ticks, legenda
FG_GRID  = "#45475a"   # linhas de grade
FG_SPINE = "#585b70"   # bordas dos eixos (spines) e borda da legenda
FG_TICK  = "#cdd6f4"   # marcações dos eixos
 
# ─── Paleta de dados ──────────────────────────────────────────────────
PALETTE = {
    "data"   : "#89b4fa",   # AZUL  — pontos experimentais (média)
    "raw"    : "#6c7086",   # CINZA — dados brutos / individuais
    "fit"    : "#f38ba8",   # ROSA  — melhor modelo (linha principal)
    "alt1"   : "#a6e3a1",   # VERDE — 2º modelo
    "alt2"   : "#fab387",   # LARANJA — 3º modelo
    "alt3"   : "#cba6f7",   # LILÁS — 4º modelo
    "alt4"   : "#94e2d5",   # TEAL — 5º modelo
    "ref"    : "#f9e2af",   # AMARELO — dado de referência externo (MCR102)
    "warn"   : "#f38ba8",   # VERMELHO — pontos descartados / alertas
    "std"    : "#7f849c",   # CINZA MÉDIO — barras de erro / desvio padrão
}
 
# ─── Kwargs reutilizáveis ─────────────────────────────────────────────
SC_DATA = dict(color=PALETTE['data'], s=65, zorder=7,
               edgecolors=BG_DARK, linewidths=0.6)
SC_RAW  = dict(color=PALETTE['raw'],  s=20, zorder=4,
               alpha=0.35, edgecolors='none')
SC_REF  = dict(color=PALETTE['ref'],  s=55, marker='D', zorder=6,
               edgecolors=BG_DARK, linewidths=0.5, alpha=0.90)
EB_KW   = dict(fmt='none', alpha=0.55, capsize=3.5,
               capthick=1.0, elinewidth=1.2, zorder=6)
LN_BEST = dict(linewidth=2.4, linestyle='-',  zorder=9)
LN_ALT1 = dict(linewidth=1.7, linestyle='--', zorder=8, alpha=0.85)
LN_ALT2 = dict(linewidth=1.5, linestyle='-.', zorder=7, alpha=0.70)
LN_ALT3 = dict(linewidth=1.3, linestyle=':',  zorder=6, alpha=0.55)
LN_ALT4 = dict(linewidth=1.2, linestyle=':',  zorder=5, alpha=0.45)
BAND_KW = dict(alpha=0.08, zorder=1)    # axvspan sombreado
ANNOT_BOX = dict(boxstyle='round,pad=0.4', facecolor='#313244',
                 edgecolor=FG_SPINE, alpha=0.90)
LEGEND_KW = dict(fontsize=8.5, framealpha=0.85, facecolor='#313244',
                 edgecolor=FG_SPINE, labelcolor=FG_TEXT,
                 handlelength=1.8, borderpad=0.5, labelspacing=0.35)
XLABEL_KW = dict(fontsize=11, color=FG_TEXT, labelpad=8)
YLABEL_KW = dict(fontsize=11, color=FG_TEXT, labelpad=8)
TITLE_KW  = dict(fontsize=12, color=FG_TEXT, fontweight='bold', pad=10)
 
# ─── Funções de setup ─────────────────────────────────────────────────
def apply_dark_style():
    '''Chamar UMA VEZ antes do mainloop do app.'''
    plt.rcParams.update({
        'figure.facecolor': BG_DARK,  'axes.facecolor': BG_AXES,
        'savefig.facecolor': BG_DARK,  'text.color': FG_TEXT,
        'axes.labelcolor': FG_TEXT,    'xtick.color': FG_TICK,
        'ytick.color': FG_TICK,        'axes.titlecolor': FG_TEXT,
        'axes.edgecolor': FG_SPINE,    'axes.linewidth': 0.8,
        'xtick.major.size': 4.5,       'xtick.minor.size': 2.5,
        'ytick.major.size': 4.5,       'ytick.minor.size': 2.5,
        'xtick.major.width': 0.8,      'ytick.major.width': 0.8,
        'xtick.direction': 'out',      'ytick.direction': 'out',
        'axes.grid': True,             'axes.grid.which': 'both',
        'grid.color': FG_GRID,         'grid.linestyle': '--',
        'grid.linewidth': 0.5,         'grid.alpha': 0.60,
        'font.size': 10,               'lines.linewidth': 1.8,
        'legend.framealpha': 0.85,     'legend.facecolor': '#313244',
        'legend.edgecolor': FG_SPINE,  'legend.labelcolor': FG_TEXT,
        'figure.dpi': 110,
    })
 
def style_ax(ax):
    '''Aplicar a qualquer eixo recém-criado ou após ax.clear().'''
    ax.set_facecolor(BG_AXES)
    for sp in ax.spines.values():
        sp.set_color(FG_SPINE); sp.set_linewidth(0.8)
    ax.tick_params(colors=FG_TICK, which='both', direction='out',
                   labelsize=9.5, length=4)
    ax.tick_params(which='minor', length=2.5)
    ax.xaxis.label.set_color(FG_TEXT)
    ax.yaxis.label.set_color(FG_TEXT)
    ax.title.set_color(FG_TEXT)
    ax.grid(color=FG_GRID, linestyle='--', linewidth=0.55, alpha=0.70)
    ax.grid(which='minor', color=FG_GRID, linestyle=':', linewidth=0.35, alpha=0.40)
 
def log_axes(ax, which='both'):
    '''Escala log + minor ticks corretos em log.'''
    if which in ('x','both'):
        ax.set_xscale('log')
        ax.xaxis.set_minor_locator(LogLocator(subs=np.arange(2,10)))
    if which in ('y','both'):
        ax.set_yscale('log')
        ax.yaxis.set_minor_locator(LogLocator(subs=np.arange(2,10)))
    ax.grid(color=FG_GRID, linestyle='--', linewidth=0.55, alpha=0.70)
    ax.grid(which='minor', color=FG_GRID, linestyle=':', linewidth=0.35, alpha=0.40)
 
def make_fig(figsize=(9,6), dpi=110):
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(BG_DARK)
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
