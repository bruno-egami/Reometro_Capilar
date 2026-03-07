import numpy as np
from scipy.stats import linregress

# -----------------------------------------------------------------------------
# --- DEFINIÇÕES DOS MODELOS REOLÓGICOS ---
# -----------------------------------------------------------------------------
"""
Módulo contendo os modelos reológicos clássicos para reometria capilar.

Fórmulas Fundamentais (Reometria Capilar):
------------------------------------------
- Taxa de cisalhamento aparente: γ̇_app = 4Q / (πR³)
- Tensão de cisalhamento na parede: τ_w = (ΔP × R) / (2L)
- Correção Weissenberg-Rabinowitsch: γ̇_true = γ̇_app × (3n' + 1) / (4n')
  onde n' = d(log τ_w) / d(log γ̇_app)

Referências:
- Steffe, J.F. (1996). Rheological Methods in Food Process Engineering.
- Mezger, T.G. (2014). The Rheology Handbook.
"""

def model_newtonian(gd, eta): 
    """
    Modelo Newtoniano (fluido ideal).
    
    Fórmula:
        τ = η × γ̇
    
    Parâmetros:
        gd : array - Taxa de cisalhamento γ̇ (s⁻¹)
        eta : float - Viscosidade dinâmica η (Pa.s)
    
    Comportamento:
        - Viscosidade constante independente da taxa de cisalhamento
        - Exemplos: água, óleos minerais, soluções diluídas
    """
    return eta * gd

def model_power_law(gd, K_pl, n_pl): 
    """
    Modelo Lei da Potência (Ostwald-de Waele).
    
    Fórmula:
        τ = K × γ̇ⁿ
    
    Parâmetros:
        gd : array - Taxa de cisalhamento γ̇ (s⁻¹)
        K_pl : float - Índice de consistência K (Pa.sⁿ)
        n_pl : float - Índice de comportamento de fluxo n (adimensional)
    
    Comportamento:
        - n < 1: Pseudoplástico (shear thinning) - maioria das pastas cerâmicas
        - n = 1: Newtoniano
        - n > 1: Dilatante (shear thickening) - suspensões concentradas
    """
    return K_pl * np.power(np.maximum(gd, 1e-9), n_pl)

def model_bingham(gd, t0, ep): 
    """
    Modelo de Bingham (viscoplástico ideal).
    
    Fórmula:
        τ = τ₀ + ηₚ × γ̇    (para τ > τ₀)
    
    Parâmetros:
        gd : array - Taxa de cisalhamento γ̇ (s⁻¹)
        t0 : float - Tensão de escoamento τ₀ (Pa)
        ep : float - Viscosidade plástica ηₚ (Pa.s)
    
    Comportamento:
        - Não flui abaixo da tensão de escoamento
        - Após escoamento, comportamento Newtoniano
        - Exemplos: pasta de dentes, lamas, argamassas
    """
    return t0 + ep * gd

def model_hb(gd, t0, K_hb, n_hb): 
    """
    Modelo Herschel-Bulkley (viscoplástico generalizado).
    
    Fórmula:
        τ = τ₀ + K × γ̇ⁿ    (para τ > τ₀)
    
    Parâmetros:
        gd : array - Taxa de cisalhamento γ̇ (s⁻¹)
        t0 : float - Tensão de escoamento τ₀ (Pa)
        K_hb : float - Índice de consistência K (Pa.sⁿ)
        n_hb : float - Índice de comportamento de fluxo n (adimensional)
    
    Comportamento:
        - Combina tensão de escoamento (Bingham) com lei da potência
        - Modelo mais versátil para pastas cerâmicas
        - n < 1: pseudoplástico com tensão de escoamento
    """
    return t0 + K_hb * np.power(np.maximum(gd, 1e-9), n_hb)

def model_casson(gd, tau0_cas, eta_cas):
    """
    Modelo de Casson (viscoplástico não-linear).
    
    Fórmula:
        √τ = √τ₀ + √ηc × √γ̇
        ou: τ = (√τ₀ + √ηc × √γ̇)²
    
    Parâmetros:
        gd : array - Taxa de cisalhamento γ̇ (s⁻¹)
        tau0_cas : float - Tensão de escoamento de Casson τ₀ (Pa)
        eta_cas : float - Viscosidade de Casson ηc (Pa.s)
    
    Comportamento:
        - Desenvolvido originalmente para chocolate
        - Bom ajuste para suspensões com partículas floculadas
        - Usado em tintas, sangue, e algumas pastas cerâmicas
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
    except Exception:
        return [1.0, 1.0]

def guess_bingham(gd, tau):
    # Regressão linear simples: tau = t0 + ep*gd
    try:
        slope, intercept, _, _, _ = linregress(gd, tau)
        return [max(0, intercept), max(0, slope)]
    except Exception:
        return [0.0, 1.0]

def guess_hb(gd, tau):
    # Estima tau0 observando as tensões nas menores taxas de cisalhamento
    idx_sorted = np.argsort(gd)
    tau0_guess = np.mean(tau[idx_sorted][:3]) if len(tau) >= 3 else tau[idx_sorted][0] * 0.9
    
    # Para K e n, estimativa aproximada subtraindo o tau0
    tau_eff = np.maximum(tau - tau0_guess, 1e-9)
    try:
        slope, intercept, _, _, _ = linregress(np.log(gd), np.log(tau_eff))
        K_guess = np.exp(intercept)
        n_guess = slope
        return [max(0, tau0_guess), max(1e-9, K_guess), max(0, min(5.0, n_guess))]
    except Exception:
        return [max(0, tau0_guess), 1.0, 0.8]

def guess_casson(gd, tau):
    # Linearização: sqrt(tau) = sqrt(t0) + sqrt(eta)*sqrt(gd)
    try:
        slope, intercept, _, _, _ = linregress(np.sqrt(gd), np.sqrt(tau))
        return [max(0, intercept**2), max(0, slope**2)]
    except Exception:
        return [0.0, 1.0]

# Dicionário contendo as funções, nomes dos parâmetros, função de estimativa inicial e limites (bounds)
# Formato: "Nome": (funcao_modelo, lista_nomes_params, funcao_chute_inicial, bounds)
MODELS = {
    "Newtoniano": (model_newtonian, ["eta"], guess_newtonian, ([1e-9], [np.inf])),
    "Lei da Potência": (model_power_law, ["K", "n"], guess_power_law, ([1e-9, 1e-9], [np.inf, 5.0])),
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
