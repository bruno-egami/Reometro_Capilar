"""
Teste visual — gera os 4 gráficos padronizados para comparação
com a referência em Analise-melhorias/melhoria-graficos/preview_novo_estilo.png.
"""
import numpy as np
import reologia_plot as rp
import reologia_plot_style as rps
import modelos_reologicos as models
from scipy.optimize import curve_fit

# Aplica tema escuro (como no gui_main.py)
rps.apply_dark_style()

# --- Dados sintéticos realistas ---
gd_app_arr = np.array([10, 20, 50, 100, 200, 500, 1000])
tau_arr    = np.array([1000, 1600, 3000, 5000, 8000, 15000, 25000], dtype=float)
tau_err    = tau_arr * 0.05

# W-R correction
log_gd = np.log(gd_app_arr)
log_tau = np.log(tau_arr)
local_n_primes = np.gradient(log_tau, log_gd)
local_n_primes = np.clip(local_n_primes, 0.05, 3.0)
n_prime_global = float(np.mean(local_n_primes))

gd_true = gd_app_arr * ((3 * n_prime_global + 1) / (4 * n_prime_global))

# Viscosidades
eta_app = tau_arr / gd_app_arr   # APARENTE (pré-W-R)
eta_true = tau_arr / gd_true     # REAL (pós-W-R)
eta_err = tau_err / gd_app_arr

# Domínio suave para modelos
gd_fit = np.logspace(np.log10(gd_app_arr.min() * 0.9), np.log10(gd_app_arr.max() * 1.1), 400)

# Ajuste dos modelos
all_mods = []
for m_name, (m_func, p_names, g_func, bnds) in models.MODELS.items():
    try:
        p0 = g_func(gd_true, tau_arr)
        popt, _ = curve_fit(m_func, gd_true, tau_arr, p0=p0, bounds=bnds, maxfev=10000)
        tau_fit_m = m_func(gd_fit, *popt)
        ss_tot = np.sum((tau_arr - np.mean(tau_arr))**2)
        ss_res = np.sum((tau_arr - m_func(gd_true, *popt))**2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        p_str = " | ".join([f"{n}={v:.3g}" for n, v in zip(p_names, popt)])
        all_mods.append({'nome': m_name, 'tau_fit': tau_fit_m, 'r2': r2, 'params': p_str})
    except Exception as e:
        print(f"  Skip {m_name}: {e}")

all_mods.sort(key=lambda x: x['r2'], reverse=True)
best = all_mods[0] if all_mods else None

# ─── Figura 1: Curva de Fluxo ──────────────────────────────
tau_fit_best = best['tau_fit'] if best else np.zeros_like(gd_fit)
fig1, _ = rp.plotar_curva_fluxo(
    gd_true, tau_arr,              # brutos
    gd_true, tau_arr, tau_err,     # médios
    gd_fit, tau_fit_best,
    best['nome'] if best else 'Nenhum',
    best['r2'] if best else 0.0,
    best['params'] if best else '',
    titulo='Curva de Fluxo — TESTE'
)
fig1.savefig('test_plot_curva_fluxo.png', dpi=150, bbox_inches='tight')
print("✓ Figura 1 salva")

# ─── Figura 2: Viscosidade (Aparente + Real) ────────────────
fig2, _ = rp.plotar_viscosidade(
    gd_true, eta_true,                   # brutos (eta real)
    gd_app_arr, eta_app, eta_err,        # médios APARENTES
    n_prime=n_prime_global,              # aplica W-R internamente
    titulo='Viscosidade Aparente — TESTE'
)
fig2.savefig('test_plot_viscosidade.png', dpi=150, bbox_inches='tight')
print("✓ Figura 2 salva")

# ─── Figura 3: Ajuste de Modelos (Tensão) ───────────────────
fig3, _ = rp.plotar_ajuste_modelos(
    gd_true, tau_arr,
    gd_true, tau_arr, tau_err,
    gd_fit, all_mods,
    titulo='Ajuste de Modelos — Curva de Fluxo'
)
fig3.savefig('test_plot_ajuste_modelos.png', dpi=150, bbox_inches='tight')
print("✓ Figura 3 salva")

# ─── Figura 4: Ajuste de Modelos (Viscosidade) ──────────────
fig4, _ = rp.plotar_ajuste_viscosidade(
    gd_true, eta_true,
    gd_true, eta_true, eta_err,
    gd_fit, all_mods,
    titulo='Viscosidade — Ajuste'
)
fig4.savefig('test_plot_ajuste_visc.png', dpi=150, bbox_inches='tight')
print("✓ Figura 4 salva")

print(f"\nn' global = {n_prime_global:.3f}")
print(f"Melhor modelo: {best['nome']} (R²={best['r2']:.4f})")
print("Todos os 4 gráficos gerados com sucesso!")
