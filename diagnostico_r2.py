"""
Diagnóstico — Por que R² está baixo no ensaio ID 2?
Compara OLS (original) vs WLS (atual) e identifica a raiz do problema.
"""
import numpy as np
import sqlite3, os
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score
import modelos_reologicos as models

# ── 1. Carregar dados do banco ────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reometria.db')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

cur = conn.cursor()
cur.execute("SELECT * FROM amostras WHERE id=2")
amostra = dict(cur.fetchone())
print(f"Amostra: {amostra['nome']}")
D_mm = amostra['d_capilar_mm']
L_mm = amostra['l_capilar_mm']
rho = amostra['densidade_g_cm3']
print(f"D={D_mm} mm, L={L_mm} mm, rho={rho} g/cm³")

R = (D_mm / 2) * 1e-3
L = L_mm * 1e-3

# Busca ensaios ativos
df_ens = pd.read_sql_query("SELECT * FROM ensaios WHERE amostra_id=2 AND ativo=1 ORDER BY ponto_n", conn)
conn.close()
print(f"Ensaios ativos: {len(df_ens)}")

# ── 2. Calcular grandezas reológicas ─────────────────────────────────
# Calcula como o analise.py faz
p_pasta_bar = df_ens['pressao_pasta_bar'].values
massa_g = df_ens['massa_g'].values
duracao_s = df_ens['duracao_s'].values

# Filtrar pontos inválidos
valid = (massa_g > 0) & (duracao_s > 0) & (p_pasta_bar > 0)
p_pasta_bar = p_pasta_bar[valid]
massa_g = massa_g[valid]
duracao_s = duracao_s[valid]
print(f"Pontos válidos: {np.sum(valid)}")

# Grandezas reológicas
P_Pa = p_pasta_bar * 1e5
tau_arr = (P_Pa * R) / (2 * L)

Q = (massa_g / 1000.0) / (rho * 1000 * duracao_s)  # m³/s
gd_app_arr = (32 * Q) / (np.pi * (2*R)**3)

print(f"Faixa gd_app: {gd_app_arr.min():.1f} - {gd_app_arr.max():.1f} s⁻¹")
print(f"Faixa tau: {tau_arr.min():.1f} - {tau_arr.max():.1f} Pa")

# ── 3. Agrupamento ───────────────────────────────────────────────────
df_calc = pd.DataFrame({'gamma_dot_app': gd_app_arr, 'tau_w': tau_arr})
df_calc['log_gd'] = np.round(np.log10(df_calc['gamma_dot_app']), 1)
grouped = df_calc.groupby('log_gd')

gd_app_mean = grouped['gamma_dot_app'].mean().values
tau_mean = grouped['tau_w'].mean().values
tau_std = grouped['tau_w'].std().fillna(0).values
N_per_group = grouped.size().values

print(f"\n{'Grp':>4} {'N':>3} {'gd_app':>10} {'tau_mean':>10} {'tau_std':>10} {'CV%':>8}")
for i in range(len(tau_mean)):
    cv = (tau_std[i] / tau_mean[i] * 100) if tau_mean[i] > 0 else 0
    print(f"{i+1:>4} {N_per_group[i]:>3} {gd_app_mean[i]:>10.1f} {tau_mean[i]:>10.1f} {tau_std[i]:>10.1f} {cv:>8.1f}")

# ── 4. Weissenberg-Rabinowitsch ──────────────────────────────────────
log_tau = np.log(tau_mean)
log_gd = np.log(gd_app_mean)
local_n = np.gradient(log_tau, log_gd)
local_n = np.clip(local_n, 0.05, 3.0)
n_prime = float(np.mean(local_n))
print(f"\nn' global = {n_prime:.4f}")
print(f"local_n = {local_n}")

gd_true = gd_app_mean * ((3 * local_n + 1) / (4 * local_n))
gd_mean = gd_true

# ── 5. Comparação completa ───────────────────────────────────────────
# Sigma WLS
unc_teorica = tau_mean * 0.054
sigma_wls = np.where(tau_std > 0, tau_std, unc_teorica)
sigma_wls = np.maximum(sigma_wls, 1e-6)

print(f"\n{'='*80}")
print(f"{'Método':<45} {'Lei Pot':>8} {'H-B':>8} {'Casson':>8} {'Bingham':>8} {'Newton':>8}")
print(f"{'='*80}")

configs = [
    ("1. Brutos sem W-R (OLS) [ORIGINAL]", gd_app_arr, tau_arr, None),
    ("2. Médias sem W-R (OLS)", gd_app_mean, tau_mean, None),
    ("3. Médias com W-R (OLS)", gd_mean, tau_mean, None),
    ("4. Médias com W-R (WLS abs=False) [ATUAL]", gd_mean, tau_mean, sigma_wls),
]

for label, gd, tau, sig in configs:
    r2s = []
    for m_name in ["Lei da Potência", "Herschel-Bulkley", "Casson", "Bingham", "Newtoniano"]:
        m_func, p_names, g_func, bnds = models.MODELS[m_name]
        try:
            p0 = g_func(gd, tau)
            if sig is not None:
                popt, _ = curve_fit(m_func, gd, tau, p0=p0, bounds=bnds, sigma=sig, absolute_sigma=False, maxfev=10000)
            else:
                popt, _ = curve_fit(m_func, gd, tau, p0=p0, bounds=bnds, maxfev=10000)
            r2 = r2_score(tau, m_func(gd, *popt))
            r2s.append(f"{r2:>8.4f}")
        except Exception as e:
            r2s.append(f"{'ERR':>8}")
    print(f"{label:<45} {' '.join(r2s)}")

# ── 6. Detalhes do melhor caso ───────────────────────────────────────
print(f"\n{'='*80}")
print("DETALHES — Lei da Potência (tau = K * gd^n)")
print(f"{'='*80}")

for label, gd, tau, sig in configs:
    m_func, p_names, g_func, bnds = models.MODELS["Lei da Potência"]
    try:
        p0 = g_func(gd, tau)
        if sig is not None:
            popt, _ = curve_fit(m_func, gd, tau, p0=p0, bounds=bnds, sigma=sig, absolute_sigma=False, maxfev=10000)
        else:
            popt, _ = curve_fit(m_func, gd, tau, p0=p0, bounds=bnds, maxfev=10000)
        r2 = r2_score(tau, m_func(gd, *popt))
        print(f"  {label}")
        print(f"    K={popt[0]:.4g}, n={popt[1]:.4f}, R²={r2:.4f}")
    except Exception as e:
        print(f"  {label}: ERRO {e}")
