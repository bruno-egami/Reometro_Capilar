# -*- coding: utf-8 -*-
import numpy as np
import reologia_plot
from scipy.stats import linregress

def perform_bagley_correction(lista_cap_data_bagley, common_D_mm_bagley, rho_si, t_ext_s_array_map, output_folder, timestamp, num_bagley_pts_final=15):
    """
    Executa a correção de Bagley completa. Usa dados de capilares de diferentes comprimentos
    para determinar a tensão de cisalhamento na parede corrigida.
    """
    print("\n--- Iniciando Análise de Correção de Bagley ---")
    min_gamma_overall, max_gamma_overall = np.inf, -np.inf

    for cap_data in lista_cap_data_bagley:
        cap_data['R_m'] = (common_D_mm_bagley / 2000.0)
        # Associa o array de tempos correspondente ao capilar
        cap_id = f"{cap_data['D_mm']:.3f}_{cap_data['L_mm']:.2f}"
        t_s_array = t_ext_s_array_map.get(cap_id, None)

        if t_s_array is None or len(t_s_array) != len(cap_data['massas_kg']):
            print(f"ERRO (Bagley): Array de tempos inválido ou incompatível para D={cap_data['D_mm']}mm, L={cap_data['L_mm']}mm. Pulando.")
            continue
            
        # MODIFICADO: Cálculo de vazão com array de tempos
        cap_data['volumes_m3'] = cap_data['massas_kg'] / rho_si
        cap_data['vazoes_Q_m3_s'] = cap_data['volumes_m3'] / t_s_array 
        cap_data['gamma_dot_aw'] = (4*cap_data['vazoes_Q_m3_s']) / (np.pi*cap_data['R_m']**3) if cap_data['R_m'] > 0 else np.zeros_like(cap_data['vazoes_Q_m3_s'])
        
        gamma_aw_flow = cap_data['gamma_dot_aw'][cap_data['massas_kg'] > 1e-9]
        if len(gamma_aw_flow) > 0:
            min_gamma_overall = min(min_gamma_overall, np.min(gamma_aw_flow))
            max_gamma_overall = max(max_gamma_overall, np.max(gamma_aw_flow))

    if not (np.isfinite(min_gamma_overall) and np.isfinite(max_gamma_overall) and min_gamma_overall < max_gamma_overall):
        print("ALERTA (Bagley): Faixa inválida de taxas de cisalhamento. Verifique dados."); return np.array([]), np.array([])

    targets_gamma_aw = np.geomspace(max(1e-3, min_gamma_overall), max_gamma_overall, num_bagley_pts_final)
    tau_w_corr_list, gamma_aw_targets_ok_list = [], []

    for target_gamma_k_val in targets_gamma_aw:
        P_target_list, L_R_target_list = [], []
        for cap_data in lista_cap_data_bagley:
            # Devemos ter certeza que o cap_data['gamma_dot_aw'] foi calculado
            if 'gamma_dot_aw' not in cap_data: continue 

            sort_idx = np.argsort(cap_data['gamma_dot_aw'])
            g_sorted = cap_data['gamma_dot_aw'][sort_idx]
            P_sorted = cap_data['pressoes_Pa'][sort_idx]
            
            # Interpolação da Pressão para a taxa de cisalhamento alvo
            if g_sorted.size > 1 and g_sorted[0] <= target_gamma_k_val <= g_sorted[-1]:
                P_interp = np.interp(target_gamma_k_val, g_sorted, P_sorted)
                P_target_list.append(P_interp)
                L_R_target_list.append(cap_data['L_mm'] / cap_data['D_mm'])
        
        if len(P_target_list) >= 2:
            slope, intercept, r_value, _, _ = linregress(L_R_target_list, P_target_list)
            if slope > 0:
                tau_w_corr = slope / 2.0 # Definição de Bagley: Slope = 2 * tau_w
                tau_w_corr_list.append(tau_w_corr)
                gamma_aw_targets_ok_list.append(target_gamma_k_val)
                # Plota um exemplo de ajuste de Bagley (opcional, para não gerar muitos gráficos)
                if target_gamma_k_val == targets_gamma_aw[len(targets_gamma_aw)//2]:
                     reologia_plot.plotar_ajuste_bagley(L_R_target_list, P_target_list, slope, intercept, str(target_gamma_k_val), output_folder, timestamp)

    return np.array(tau_w_corr_list), np.array(gamma_aw_targets_ok_list)

def perform_mooney_correction(capilares_data, common_L_mm, rho_si, t_ext_s_array_map, output_folder, timestamp, tau_w_targets_ref=None):
    """
    Executa a correção de Mooney completa (versão final com geração de alvos aprimorada).
    """
    print("\n--- Iniciando Análise de Correção de Mooney ---")
    
    # 1. Pré-processamento: Calcula gamma_aw e tau_w_aparente para cada capilar
    min_tau_overall, max_tau_overall = np.inf, -np.inf
    
    for cap in capilares_data:
        cap['R_m'] = (cap['D_mm'] / 2000.0)
        
        # Associa o array de tempos correspondente ao capilar
        cap_id = f"{cap['D_mm']:.3f}_{cap['L_mm']:.2f}"
        t_s_array = t_ext_s_array_map.get(cap_id, None)

        if t_s_array is None or len(t_s_array) != len(cap['massas_kg']):
            print(f"ERRO (Mooney): Array de tempos inválido ou incompatível para D={cap['D_mm']}mm. Pulando.")
            continue

        # MODIFICADO: Cálculo de vazão com array de tempos
        cap['volumes_m3'] = cap['massas_kg'] / rho_si
        cap['vazoes_Q_m3_s'] = cap['volumes_m3'] / t_s_array
        
        cap['gamma_dot_aw'] = (4 * cap['vazoes_Q_m3_s']) / (np.pi * cap['R_m']**3) if cap['R_m'] > 0 else np.zeros_like(cap['vazoes_Q_m3_s'])
        cap['tau_w_aparente'] = (cap['pressoes_Pa'] * cap['R_m']) / (2 * (common_L_mm/1000.0)) # L deve ser em metros
        
        # Filtra dados válidos para definir range de interpolação
        valid_idx = (cap['tau_w_aparente'] > 0) & (cap['gamma_dot_aw'] > 0)
        if np.any(valid_idx):
            min_tau_overall = min(min_tau_overall, np.min(cap['tau_w_aparente'][valid_idx]))
            max_tau_overall = max(max_tau_overall, np.max(cap['tau_w_aparente'][valid_idx]))

    # 2. Definição dos Alvos de Tensão (Tau Targets)
    # Se recebermos alvos de Bagley (tau_w_targets_ref), usamos a interseção com o range disponível em Mooney
    if tau_w_targets_ref is not None and len(tau_w_targets_ref) > 0:
        tau_targets = np.array([t for t in tau_w_targets_ref if min_tau_overall <= t <= max_tau_overall])
        if len(tau_targets) < 3: # Se a interseção for muito pobre, faz fallback
             print("Aviso (Mooney): Alvos de Bagley fora do range de Mooney. Gerando novos alvos baseados em Mooney.")
             tau_targets = np.geomspace(max(1e-3, min_tau_overall), max_tau_overall, 15)
    else:
        # Se não houver Bagley, gera alvos baseados nos dados de Mooney
        if np.isinf(min_tau_overall) or np.isinf(max_tau_overall):
             print("ERRO (Mooney): Não há dados válidos para gerar alvos de tensão."); return np.array([]), np.array([])
        tau_targets = np.geomspace(max(1e-3, min_tau_overall), max_tau_overall, 15)

    gamma_dot_true_list = []
    tau_w_final_list = []
    
    # 3. Loop de Correção para cada Tensão Alvo
    for tau_target in tau_targets:
        inv_R_vals = [] # 1/R
        gamma_aw_vals = [] # Taxa aparente interpolada
        
        for cap in capilares_data:
            if 'tau_w_aparente' not in cap: continue
            
            # Ordena para interpolação
            sort_idx = np.argsort(cap['tau_w_aparente'])
            tau_sorted = cap['tau_w_aparente'][sort_idx]
            gamma_sorted = cap['gamma_dot_aw'][sort_idx]
            
            # Interpola gamma_aw para o tau_target
            if tau_sorted.size > 1 and tau_sorted[0] <= tau_target <= tau_sorted[-1]:
                gamma_interp = np.interp(tau_target, tau_sorted, gamma_sorted)
                inv_R_vals.append(1.0 / cap['R_m'])
                gamma_aw_vals.append(gamma_interp)
        
        # Requer pelo menos 2 diâmetros para regressão
        if len(inv_R_vals) >= 2:
            # Mooney: gamma_aw = gamma_true + (8 * V_slip / D) -> gamma_aw = gamma_true + (4 * V_slip) * (1/R)
            # Plot: Y = gamma_aw, X = 1/R
            # Intercept = gamma_true (Taxa de cisalhamento real na parede sem deslizamento)
            # Slope = 4 * V_slip
            
            slope, intercept, r_value, _, _ = linregress(inv_R_vals, gamma_aw_vals)
            
            # O intercept é a taxa de cisalhamento corrigida (gamma_dot_true)
            # Deve ser positivo. Se for negativo, indica problemas nos dados ou "deslizamento negativo" (físicamente impossível neste modelo simples)
            if intercept > 0:
                gamma_dot_true_list.append(intercept)
                tau_w_final_list.append(tau_target)
            else:
                 # Fallback: Se intercept < 0, assume deslizamento desprezível ou erro, 
                 # pode-se pegar a média dos gamma_aw ou ignorar. Aqui ignoramos.
                 pass

    return np.array(tau_w_final_list), np.array(gamma_dot_true_list)
