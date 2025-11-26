# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score
from modelos_reologicos import MODELS

def ajustar_modelos(gamma_dot, tau_w):
    """
    Ajusta todos os modelos reológicos disponíveis aos dados fornecidos.
    
    Args:
        gamma_dot (array): Taxa de cisalhamento (s-1).
        tau_w (array): Tensão de cisalhamento (Pa).
        
    Returns:
        tuple: (model_results, best_model_nome, df_sum_modelo)
            - model_results: Dicionário com params e R2 de cada modelo.
            - best_model_nome: Nome do modelo com maior R2.
            - df_sum_modelo: DataFrame com resumo dos ajustes.
    """
    model_results = {}
    best_model_nome = ""
    best_r2 = -np.inf
    summary_list = []
    
    # Filtra dados válidos para ajuste
    valid_fit = (gamma_dot > 0) & (tau_w > 0) & ~np.isnan(gamma_dot) & ~np.isnan(tau_w)
    gd_fit = gamma_dot[valid_fit]
    tau_fit = tau_w[valid_fit]
    
    if len(gd_fit) < 3:
        print("  AVISO: Pontos insuficientes para ajuste de modelos (mínimo 3).")
        return {}, "", pd.DataFrame()

    for nome_modelo, (func_modelo, param_names, initial_guess_func, bounds) in MODELS.items():
        try:
            p0 = initial_guess_func(gd_fit, tau_fit)
            # Ajuste com limites (bounds) para garantir parâmetros físicos
            popt, pcov = curve_fit(func_modelo, gd_fit, tau_fit, p0=p0, bounds=bounds, maxfev=10000)
            
            tau_pred = func_modelo(gd_fit, *popt)
            r2 = r2_score(tau_fit, tau_pred)
            
            model_results[nome_modelo] = {'params': popt, 'R2': r2}
            
            # Formata parâmetros para o resumo
            params_str = ", ".join([f"{n}={v:.4g}" for n, v in zip(param_names, popt)])
            summary_list.append({'Modelo': nome_modelo, 'R2': r2, 'Parametros': params_str})
            
            if r2 > best_r2:
                best_r2 = r2
                best_model_nome = nome_modelo
                
        except Exception as e:
            # Falhas pontuais em um modelo não devem parar o processo
            # print(f"  Falha ao ajustar {nome_modelo}: {e}") 
            pass

    df_sum_modelo = pd.DataFrame(summary_list).sort_values(by='R2', ascending=False)
    
    return model_results, best_model_nome, df_sum_modelo

def inferir_comportamento_fluido(best_model_nome, model_results):
    """
    Infere o comportamento do fluido com base no melhor modelo ajustado.
    """
    if not best_model_nome or best_model_nome not in model_results:
        return "Indeterminado"
        
    params = model_results[best_model_nome]['params']
    
    if best_model_nome == "Lei de Potencia":
        # params: [K, n]
        n_val = params[1]
        if n_val < 1: return "Pseudoplastico (Shear Thinning)"
        elif n_val > 1: return "Dilatante (Shear Thickening)"
        else: return "Newtoniano"
        
    elif best_model_nome in ["Bingham", "Herschel-Bulkley", "Casson"]:
        return "Viscoplastico (Com Tensao de Escoamento)"
        
    else:
        return "Newtoniano"
