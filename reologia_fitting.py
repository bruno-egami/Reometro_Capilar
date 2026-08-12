import numpy as np
import pandas as pd
import logging
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score
from modelos_reologicos import MODELS

def ajustar_modelos(gamma_dot, tau_w, tau_std=None):
    """
    Ajusta todos os modelos reológicos disponíveis aos dados fornecidos.
    
    Args:
        gamma_dot (array): Taxa de cisalhamento (s-1).
        tau_w (array): Tensão de cisalhamento (Pa).
        tau_std (array, opcional): Desvio padrão da tensão para WLS.
        
    Returns:
        tuple: (model_results, best_model_nome, df_sum_modelo)
            - model_results: Dicionário com params, r2, aic e bic (minúsculos) de cada modelo.
            - best_model_nome: Nome do modelo com menor AIC.
            - df_sum_modelo: DataFrame com resumo dos ajustes (ordenado por AIC).
            
    Nota sobre AIC (Akaike Information Criterion):
        A implementação utiliza a variante simplificada para Mínimos Quadrados Ordinários (OLS) / WLS:
        AIC = 2k + n * ln(RSS / n). A constante foi omitida, o que é matemática e internamente
        válido para comparar modelos sob o mesmo dataset.
    """
    model_results = {}
    best_model_nome = ""
    best_r2 = -np.inf
    best_aic = np.inf
    summary_list = []
    
    # Filtra dados válidos para ajuste
    valid_fit = (gamma_dot > 0) & (tau_w > 0) & ~np.isnan(gamma_dot) & ~np.isnan(tau_w)
    gd_fit = gamma_dot[valid_fit]
    tau_fit = tau_w[valid_fit]
    
    sigma_wls = None
    if tau_std is not None:
        std_fit = tau_std[valid_fit]
        valid_std = std_fit[std_fit > 0]
        if len(valid_std) > 0:
            mean_std = np.mean(valid_std)
            # Pontos com 1 réplica (std=0) têm erro desconhecido, não erro zero (peso infinito). 
            # Recebem a incerteza média do ensaio.
            raw_sigma = np.where(std_fit == 0, mean_std, std_fit)
            # Normalizar sigma para atuarem apenas como pesos relativos (WLS)
            sigma_wls = raw_sigma / np.mean(raw_sigma)
    
    n_pts = len(gd_fit)
    if n_pts < 3:
        print("  AVISO: Pontos insuficientes para ajuste de modelos (mínimo 3).")
        return {}, "", pd.DataFrame()
        
    from scipy.stats import t

    for nome_modelo, (func_modelo, param_names, initial_guess_func, bounds) in MODELS.items():
        try:
            p0 = initial_guess_func(gd_fit, tau_fit)
            print(f"DEBUG {nome_modelo} -> gd_fit: {gd_fit}, tau_fit: {tau_fit}, sigma_wls: {sigma_wls}")
            
            # Ajuste com limites (bounds) para garantir parâmetros físicos (WLS if sigma_wls passed)
            if sigma_wls is not None:
                popt, pcov = curve_fit(func_modelo, gd_fit, tau_fit, p0=p0, bounds=bounds, sigma=sigma_wls, absolute_sigma=False, maxfev=10000)
            else:
                popt, pcov = curve_fit(func_modelo, gd_fit, tau_fit, p0=p0, bounds=bounds, maxfev=10000)
            
            tau_pred = func_modelo(gd_fit, *popt)
            r2 = r2_score(tau_fit, tau_pred)
            
            # M6: Calculo de AIC/BIC
            if sigma_wls is not None:
                rss = np.sum(((tau_fit - tau_pred) / sigma_wls)**2)
            else:
                rss = np.sum((tau_fit - tau_pred)**2)
                
            k = len(popt)
            rss_safe = rss if rss > 1e-10 else 1e-10
            aic_val = 2*k + n_pts * np.log(rss_safe/n_pts)
            bic_val = k * np.log(n_pts) + n_pts * np.log(rss_safe/n_pts)
            
            # M7: Intervalo de Confianca 95% usando pcov
            ic_dict = {}
            if not np.isinf(pcov).all():
                dof = max(1, n_pts - k)
                t_val = t.ppf(0.975, dof)
                std_errs = np.sqrt(np.diag(pcov))
                for idx, p_n in enumerate(param_names):
                    ic_dict[p_n] = t_val * std_errs[idx]
            
            model_results[nome_modelo] = {'params': popt, 'r2': r2, 'aic': aic_val, 'bic': bic_val, 'ic': ic_dict, 'param_names': param_names}
            
            # Formata parâmetros para o resumo
            params_str = ", ".join([f"{n}={v:.4g}±{ic_dict.get(n, 0):.2g}" if ic_dict.get(n, 0) > 0 else f"{n}={v:.4g}" for n, v in zip(param_names, popt)])
            summary_list.append({'Modelo': nome_modelo, 'R2': r2, 'AIC': aic_val, 'BIC': bic_val, 'Parametros': params_str})
            
            if aic_val < best_aic:
                best_aic = aic_val
                best_model_nome = nome_modelo
                
        except Exception as e:
            # Falhas pontuais em um modelo não devem parar o processo
            logging.warning(f"Falha ao ajustar {nome_modelo}: {e}")

    df_sum_modelo = pd.DataFrame(summary_list).sort_values(by='AIC', ascending=True) if summary_list else pd.DataFrame()
    
    return model_results, best_model_nome, df_sum_modelo

def inferir_comportamento_fluido(best_model_nome, model_results):
    """
    Infere o comportamento do fluido com base no melhor modelo ajustado.
    """
    if not best_model_nome or best_model_nome not in model_results:
        return "Indeterminado"
        
    params = model_results[best_model_nome]['params']
    
    if best_model_nome == "Lei da Potência":
        # params: [K, n]
        n_val = params[1]
        if n_val < 1: return "Pseudoplastico (Shear Thinning)"
        elif n_val > 1: return "Dilatante (Shear Thickening)"
        else: return "Newtoniano"
        
    elif best_model_nome in ["Bingham", "Herschel-Bulkley", "Casson"]:
        return "Viscoplastico (Com Tensao de Escoamento)"
        
    else:
        return "Newtoniano"

def calcular_mape(y_true, y_pred):
    """
    Calcula o Mean Absolute Percentage Error (MAPE).
    
    Args:
        y_true: Valores reais (referência)
        y_pred: Valores preditos ou comparados
        
    Returns:
        float: Erro percentual médio.
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    # Evita divisão por zero
    mask = (y_true != 0)
    if not np.any(mask): return 0.0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
