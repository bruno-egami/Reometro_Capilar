import numpy as np

# -----------------------------------------------------------------------------
# --- DEFINIÇÕES DOS MODELOS REOLÓGICOS ---
# -----------------------------------------------------------------------------

def model_newtonian(gd, eta): 
    """
    Modelo Newtoniano: tau = eta * gamma_dot
    """
    return eta * gd

def model_power_law(gd, K_pl, n_pl): 
    """
    Modelo Lei da Potência (Ostwald-de Waele): tau = K * (gamma_dot)^n
    """
    return K_pl * np.power(np.maximum(gd, 1e-9), n_pl)

def model_bingham(gd, t0, ep): 
    """
    Modelo de Bingham: tau = tau0 + eta_p * gamma_dot
    """
    return t0 + ep * gd

def model_hb(gd, t0, K_hb, n_hb): 
    """
    Modelo Herschel-Bulkley: tau = tau0 + K * (gamma_dot)^n
    """
    return t0 + K_hb * np.power(np.maximum(gd, 1e-9), n_hb)

def model_casson(gd, tau0_cas, eta_cas):
    """
    Modelo de Casson: sqrt(tau) = sqrt(tau0) + sqrt(eta_cas) * sqrt(gamma_dot)
    """
    sqrt_tau0 = np.sqrt(np.maximum(tau0_cas, 0))
    sqrt_eta_cas_val = np.sqrt(np.maximum(eta_cas, 1e-9))
    sqrt_gd_val = np.sqrt(np.maximum(gd, 1e-9))
    return (sqrt_tau0 + sqrt_eta_cas_val * sqrt_gd_val)**2

# Funções de estimativa inicial (chute) para os parâmetros
def guess_newtonian(gd, tau):
    eta_guess = np.mean(tau / gd)
    return [eta_guess]

def guess_power_law(gd, tau):
    # Linearização log-log: ln(tau) = ln(K) + n*ln(gd)
    try:
        slope, intercept, _, _, _ = linregress(np.log(gd), np.log(tau))
        return [np.exp(intercept), slope]
    except:
        return [1.0, 1.0]

def guess_bingham(gd, tau):
    # Regressão linear simples: tau = t0 + ep*gd
    try:
        slope, intercept, _, _, _ = linregress(gd, tau)
        return [max(0, intercept), max(0, slope)]
    except:
        return [0.0, 1.0]

def guess_hb(gd, tau):
    # Difícil estimar t0, K, n juntos. Chute inicial genérico.
    # Assume t0 pequeno, e ajusta PL no restante
    return [np.min(tau)*0.5, 1.0, 0.5]

def guess_casson(gd, tau):
    # Linearização: sqrt(tau) = sqrt(t0) + sqrt(eta)*sqrt(gd)
    try:
        slope, intercept, _, _, _ = linregress(np.sqrt(gd), np.sqrt(tau))
        return [max(0, intercept**2), max(0, slope**2)]
    except:
        return [0.0, 1.0]

from scipy.stats import linregress

# Dicionário contendo as funções, nomes dos parâmetros, função de estimativa inicial e limites (bounds)
# Formato: "Nome": (funcao_modelo, lista_nomes_params, funcao_chute_inicial, bounds)
MODELS = {
    "Newtoniano": (model_newtonian, ["eta"], guess_newtonian, ([1e-9], [np.inf])),
    "Lei de Potencia": (model_power_law, ["K", "n"], guess_power_law, ([1e-9, 1e-9], [np.inf, 5.0])),
    "Bingham": (model_bingham, ["tau0", "eta_p"], guess_bingham, ([0, 1e-9], [np.inf, np.inf])),
    "Herschel-Bulkley": (model_hb, ["tau0", "K", "n"], guess_hb, ([0, 1e-9, 1e-9], [np.inf, np.inf, 5.0])),
    "Casson": (model_casson, ["tau0", "eta_c"], guess_casson, ([0, 1e-9], [np.inf, np.inf]))
}

# Mapeamento de nomes de parâmetros para relatórios
PARAM_NAMES_MAP = {
    "Newtoniano": ["eta (Pa.s)"],
    "Lei da Potência": ["K (Pa.s^n)", "n (-)"],
    "Bingham": ["t0 (Pa)", "ep (Pa.s)"],
    "Herschel-Bulkley": ["t0 (Pa)", "K (Pa.s^n)", "n (-)"],
    "Casson": ["t0 (Pa)", "eta_cas (Pa.s)"]
}
