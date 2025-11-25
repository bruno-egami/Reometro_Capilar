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

# Dicionário contendo as funções e os limites (bounds) para ajuste de curvas (scipy.optimize.curve_fit)
# Formato: "Nome": (funcao, ([limites_inferiores], [limites_superiores]))
MODELS = {
    "Newtoniano": (model_newtonian, ([1e-9], [np.inf])),
    "Lei da Potência": (model_power_law, ([1e-9, 1e-9], [np.inf, 5.0])),
    "Bingham": (model_bingham, ([0, 1e-9], [np.inf, np.inf])),
    "Herschel-Bulkley": (model_hb, ([0, 1e-9, 1e-9], [np.inf, np.inf, 5.0])),
    "Casson": (model_casson, ([0, 1e-9], [np.inf, np.inf]))
}

# Mapeamento de nomes de parâmetros para relatórios
PARAM_NAMES_MAP = {
    "Newtoniano": ["eta (Pa.s)"],
    "Lei da Potência": ["K (Pa.s^n)", "n (-)"],
    "Bingham": ["t0 (Pa)", "ep (Pa.s)"],
    "Herschel-Bulkley": ["t0 (Pa)", "K (Pa.s^n)", "n (-)"],
    "Casson": ["t0 (Pa)", "eta_cas (Pa.s)"]
}
