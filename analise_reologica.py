# -----------------------------------------------------------------------------
# SCRIPT PARA ANÁLISE REOLÓGICA DE PASTAS EM REÔMETRO CAPILAR
# (Versão SUPER AVANÇADA com CSV, Bagley & Plots, Mooney & Plots, Relatório TXT)
# -----------------------------------------------------------------------------

# 1. Importação de Bibliotecas
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import os # Para manipulação de caminhos de arquivo

# -----------------------------------------------------------------------------
# --- FUNÇÕES AUXILIARES ---
# -----------------------------------------------------------------------------
def input_sim_nao(mensagem_prompt):
    while True:
        resposta = input(mensagem_prompt).strip().lower()
        if resposta in ['s', 'sim']: return True
        elif resposta in ['n', 'nao', 'não']: return False
        else: print("ERRO: Resposta inválida. Digite 's' ou 'n'.")

def input_float_com_virgula(mensagem_prompt):
    while True:
        try: return float(input(mensagem_prompt).replace(',', '.'))
        except ValueError: print("ERRO: Entrada inválida. Insira um número.")

def format_float_for_table(value, decimal_places=4):
    if isinstance(value, (float, np.floating)):
        if np.isnan(value): return "NaN"
        if abs(value) < 10**(-decimal_places) and value != 0 and abs(value) > 1e-12 : # Evitar para zero absoluto
             return f"{value:.{max(1,decimal_places)}g}" # Usar 'g' para pequenos números, mantendo alguns significativos
        return f"{value:.{decimal_places}f}"
    return str(value)

# --- FUNÇÕES PARA CORREÇÕES E RELATÓRIO ---

def plotar_ajuste_bagley(L_over_R_vals, P_vals, slope, intercept, target_gamma_aw_str, output_folder, timestamp):
    """Gera e salva um plot do ajuste de Bagley para um target_gamma_aw."""
    if len(L_over_R_vals) < 2: return
    plt.figure(figsize=(8, 6))
    plt.scatter(L_over_R_vals, np.array(P_vals) / 1e5, marker='o', label='Dados Interpolados') # Pressão em bar para o plot
    line_x = np.array(sorted(L_over_R_vals)) # Garante que a linha seja plotada na ordem correta
    line_y_pa = slope * line_x + intercept
    plt.plot(line_x, line_y_pa / 1e5, color='red', label=f'Ajuste Linear (τw_corr={slope/2:.1f} Pa)')
    plt.xlabel('L/R (adimensional)')
    plt.ylabel('ΔP Total Medido (bar)')
    plt.title(rf'Plot de Bagley para $\dot{{\gamma}}_{{aw}}^* \approx$ {float(target_gamma_aw_str):.1f} s⁻¹')
    plt.legend(); plt.grid(True)
    filename = os.path.join(output_folder, f"{timestamp}_bagley_plot_gamma_aw_{float(target_gamma_aw_str):.0f}.png")
    try:
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"  Plot de Bagley salvo em: {filename}")
    except Exception as e: print(f"  ERRO ao salvar plot de Bagley: {e}")
    plt.close()

def perform_bagley_correction(lista_cap_data_bagley, common_D_mm_bagley, rho_si, t_ext_si, output_folder, timestamp, num_bagley_pts_final=15):
    print("\n--- Iniciando Análise de Correção de Bagley ---")
    min_gamma_overall, max_gamma_overall = np.inf, -np.inf
    
    for cap_data in lista_cap_data_bagley:
        cap_data['R_m'] = (common_D_mm_bagley / 2000.0) # Raio comum
        cap_data['volumes_m3'] = cap_data['massas_kg'] / rho_si
        cap_data['vazoes_Q_m3_s'] = cap_data['volumes_m3'] / cap_data['tempos_s']
        cap_data['gamma_dot_aw'] = (4*cap_data['vazoes_Q_m3_s'])/(np.pi*cap_data['R_m']**3)
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
            sort_idx = np.argsort(cap_data['gamma_dot_aw'])
            sorted_gamma_cap, sorted_P_cap = cap_data['gamma_dot_aw'][sort_idx], cap_data['pressoes_Pa'][sort_idx]
            unique_gamma, unique_idx_u = np.unique(sorted_gamma_cap, return_index=True)
            unique_P = sorted_P_cap[unique_idx_u]
            if len(unique_gamma) < 2: continue
            if unique_gamma[0] <= target_gamma_k_val <= unique_gamma[-1]:
                try:
                    P_interp = np.interp(target_gamma_k_val, unique_gamma, unique_P)
                    P_target_list.append(P_interp)
                    L_R_target_list.append(cap_data['L_m'] / cap_data['R_m'])
                except Exception as e: print(f"  Aviso (Bagley Interp) L={cap_data['L_mm']}mm: {e}")
        
        if len(L_R_target_list) >= 2:
            try:
                slope, intercept, r_val, _, _ = linregress(L_R_target_list, P_target_list)
                if slope < 0: print(f"  Aviso (Bagley Fit): Inclinação negativa para gamma_target={target_gamma_k_val:.2e}. Descartado."); continue
                tau_w_corr_list.append(slope / 2.0)
                gamma_aw_targets_ok_list.append(target_gamma_k_val)
                plotar_ajuste_bagley(L_R_target_list, P_target_list, slope, intercept, f"{target_gamma_k_val:.2e}", output_folder, timestamp)
            except Exception as e: print(f"  Aviso (Bagley Fit) gamma_target={target_gamma_k_val:.2e}: {e}")
        else: print(f"  Aviso (Bagley): Pontos L/R insuficientes para gamma_target={target_gamma_k_val:.2e}.")
            
    if not gamma_aw_targets_ok_list: print("ALERTA (Bagley): Nenhuma curva de fluxo corrigida gerada.")
    print("--- Correção de Bagley Concluída ---")
    return np.array(gamma_aw_targets_ok_list), np.array(tau_w_corr_list)

def plotar_ajuste_mooney(inv_R_vals, gamma_aw_vals, slope, intercept, target_tau_w_str, output_folder, timestamp):
    """Gera e salva um plot do ajuste de Mooney para um target_tau_w."""
    if len(inv_R_vals) < 2: return
    plt.figure(figsize=(8, 6))
    plt.scatter(inv_R_vals, gamma_aw_vals, marker='o', label=r'Dados Interpolados ($\dot{\gamma}_{aw}$)')
    line_x = np.array(sorted(inv_R_vals))
    line_y_gamma_aw = slope * line_x + intercept
    plt.plot(line_x, line_y_gamma_aw, color='blue', label=rf'Ajuste Linear ($\dot{{\gamma}}_{{s}}$={intercept:.2e} s⁻¹)')
    plt.xlabel('1/R (m⁻¹)')
    plt.ylabel(r'$\dot{\gamma}_{aw}$ (s⁻¹)')
    plt.title(rf'Plot de Mooney para $\tau_w \approx$ {float(target_tau_w_str):.1f} Pa')
    plt.legend(); plt.grid(True)
    # Garantir que o nome do arquivo seja válido, especialmente target_tau_w_str
    filename_tau_w_part = f"{float(target_tau_w_str):.0f}".replace('.', '_')
    filename = os.path.join(output_folder, f"{timestamp}_mooney_plot_tau_w_{filename_tau_w_part}.png")
    try:
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"  Plot de Mooney salvo em: {filename}")
    except Exception as e: print(f"  ERRO ao salvar plot de Mooney: {e}")
    plt.close()

def perform_mooney_correction(lista_cap_data_mooney, common_L_mm_mooney, rho_si, t_ext_si, 
                              tau_w_targets_ref, output_folder, timestamp, 
                              num_mooney_pts_final=15):
    print("\n--- Iniciando Análise de Correção de Mooney (Deslizamento) ---")
    if not lista_cap_data_mooney or len(lista_cap_data_mooney) < 2:
        print("ALERTA (Mooney): São necessários dados de pelo menos 2 capilares com diâmetros diferentes para a correção de Mooney.")
        return np.array([]), np.array([])

    # 1. Calcular tau_w e gamma_dot_aw para todos os pontos de todos os capilares de Mooney.
    L_common_m = common_L_mm_mooney / 1000.0
    min_tau_overall, max_tau_overall = np.inf, -np.inf

    for cap_data in lista_cap_data_mooney:
        cap_data['L_m'] = L_common_m
        # D_mm já deve estar em cap_data a partir da entrada
        cap_data['R_m'] = cap_data['D_mm'] / 2000.0
        cap_data['volumes_m3'] = cap_data['massas_kg'] / rho_si
        cap_data['vazoes_Q_m3_s'] = cap_data['volumes_m3'] / cap_data['tempos_s']
        
        if cap_data['R_m'] <= 0:
            print(f"  ALERTA (Mooney): Raio do capilar inválido (D={cap_data['D_mm']}mm). Pulando este capilar para cálculos de gamma_dot_aw.")
            cap_data['gamma_dot_aw'] = np.full_like(cap_data['vazoes_Q_m3_s'], np.nan)
        else:
            cap_data['gamma_dot_aw'] = (4 * cap_data['vazoes_Q_m3_s']) / (np.pi * cap_data['R_m']**3)

        if L_common_m <= 0:
            print(f"  ALERTA (Mooney): Comprimento do capilar inválido (L={common_L_mm_mooney}mm). Pulando este capilar para cálculos de tau_w_raw.")
            cap_data['tau_w_raw'] = np.full_like(cap_data['pressoes_Pa'], np.nan)
        else:
            cap_data['tau_w_raw'] = (cap_data['pressoes_Pa'] * cap_data['R_m']) / (2 * L_common_m)
        
        tau_w_flow = cap_data['tau_w_raw'][~np.isnan(cap_data['tau_w_raw']) & (cap_data['massas_kg'] > 1e-9)]
        if len(tau_w_flow) > 0:
            min_tau_overall = min(min_tau_overall, np.min(tau_w_flow))
            max_tau_overall = max(max_tau_overall, np.max(tau_w_flow))

    targets_tau_w_final = np.array([])
    if tau_w_targets_ref is not None and len(tau_w_targets_ref) > 0:
        print("  Usando tau_w da correção de Bagley (ou entrada anterior) como alvos para Mooney.")
        targets_tau_w_final = np.sort(tau_w_targets_ref[~np.isnan(tau_w_targets_ref) & (tau_w_targets_ref > 0)])
    else:
        if not (np.isfinite(min_tau_overall) and np.isfinite(max_tau_overall) and min_tau_overall < max_tau_overall):
            print("ALERTA (Mooney): Faixa inválida de tensões de cisalhamento para definir alvos. Verifique dados."); return np.array([]), np.array([])
        targets_tau_w_final = np.geomspace(max(1e-2, min_tau_overall), max_tau_overall, num_mooney_pts_final)
        print(f"  Gerando {num_mooney_pts_final} alvos de tau_w para Mooney entre {min_tau_overall:.2e} e {max_tau_overall:.2e} Pa.")

    if len(targets_tau_w_final) == 0:
        print("ALERTA (Mooney): Nenhum alvo de tau_w válido para prosseguir."); return np.array([]), np.array([])

    gamma_dot_s_corr_list, tau_w_targets_ok_list = [], []

    for target_tau_k_val in targets_tau_w_final:
        gamma_aw_interp_list, inv_R_list = [], []
        cap_radii_used_for_target = [] 

        for cap_data in lista_cap_data_mooney:
            if cap_data['R_m'] <= 0: continue 

            valid_indices = ~np.isnan(cap_data['tau_w_raw']) & ~np.isnan(cap_data['gamma_dot_aw'])
            if np.sum(valid_indices) < 2: continue 

            sorted_tau_cap_unique, unique_indices = np.unique(cap_data['tau_w_raw'][valid_indices], return_index=True)
            sorted_gamma_cap_unique = cap_data['gamma_dot_aw'][valid_indices][unique_indices]
            
            sort_order = np.argsort(sorted_tau_cap_unique)
            sorted_tau_cap_final = sorted_tau_cap_unique[sort_order]
            sorted_gamma_cap_final = sorted_gamma_cap_unique[sort_order]

            if len(sorted_tau_cap_final) < 2: continue

            if sorted_tau_cap_final[0] <= target_tau_k_val <= sorted_tau_cap_final[-1]:
                try:
                    gamma_aw_interp = np.interp(target_tau_k_val, sorted_tau_cap_final, sorted_gamma_cap_final)
                    gamma_aw_interp_list.append(gamma_aw_interp)
                    inv_R_list.append(1.0 / cap_data['R_m'])
                    cap_radii_used_for_target.append(cap_data['R_m'])
                except Exception as e:
                    print(f"  Aviso (Mooney Interp) D={cap_data['D_mm']}mm para tau_w_target={target_tau_k_val:.2e}: {e}")
        
        unique_radii_for_target = np.unique(np.array(cap_radii_used_for_target))
        if len(inv_R_list) >= 2 and len(unique_radii_for_target) >=2:
            try:
                slope, intercept, r_val, _, _ = linregress(inv_R_list, gamma_aw_interp_list)
                if intercept < 0 : 
                    print(f"  Aviso (Mooney Fit): Intercepto (gamma_s) negativo ({intercept:.2e}) para tau_w={target_tau_k_val:.2e}. Descartado.")
                    continue
                
                gamma_dot_s_corr_list.append(intercept) 
                tau_w_targets_ok_list.append(target_tau_k_val)
                plotar_ajuste_mooney(inv_R_list, gamma_aw_interp_list, slope, intercept, f"{target_tau_k_val:.2e}", output_folder, timestamp)
            except Exception as e:
                print(f"  Aviso (Mooney Fit) tau_w_target={target_tau_k_val:.2e}: {e}")
        else:
            print(f"  Aviso (Mooney): Pontos 1/R insuficientes ou de um único raio para tau_w_target={target_tau_k_val:.2e} (necessários >=2 capilares distintos).")

    if not tau_w_targets_ok_list:
        print("ALERTA (Mooney): Nenhuma curva de fluxo corrigida para deslizamento foi gerada.")
        return np.array([]), np.array([])
        
    print("--- Correção de Mooney (Deslizamento) Concluída ---")
    return np.array(tau_w_targets_ok_list), np.array(gamma_dot_s_corr_list)


def gerar_relatorio_texto(timestamp_str_report, rho_g_cm3, t_ext_s,
                          realizar_bagley, D_bagley_mm, capilares_bagley_info, # Changed from realizou_bagley
                          realizar_mooney, L_mooney_mm, capilares_mooney_D_info, # Changed from realizou_mooney
                          D_unico_mm, L_unico_mm,
                          df_res, df_sum_modelo, best_model_nome, best_model_r2,
                          lista_arquivos_gerados, output_folder):
    filename = os.path.join(output_folder, f"{timestamp_str_report}_relatorio_analise.txt")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("RELATÓRIO DE ANÁLISE REOLÓGICA\n")
            f.write("="*70 + "\n")
            f.write(f"Sessão: {timestamp_str_report}\n")
            f.write(f"Data da Geração do Relatório: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            f.write("\n--- PARÂMETROS FIXOS GLOBAIS ---\n")
            f.write(f"Densidade da Pasta: {rho_g_cm3:.3f} g/cm³\n")
            f.write(f"Tempo de Extrusão Fixo: {t_ext_s:.2f} s\n")

            f.write("\n--- CONFIGURAÇÃO DE CORREÇÕES ---\n")
            if realizar_bagley: # Corrected variable name
                f.write(f"Correção de Bagley: Sim\n")
                f.write(f"  Diâmetro Comum Capilares Bagley: {D_bagley_mm:.3f} mm\n")
                f.write(f"  Capilares Usados para Bagley (L em mm):\n")
                for i, cap_l in enumerate(capilares_bagley_info): 
                    f.write(f"    - Capilar {i+1}: L = {cap_l:.2f} mm\n")
            else:
                f.write("Correção de Bagley: Não\n")
            
            if realizar_mooney: # Corrected variable name
                f.write(f"Correção de Mooney (Deslizamento): Sim\n")
                f.write(f"  Comprimento Comum Capilares Mooney: {L_mooney_mm:.2f} mm\n")
                f.write(f"  Diâmetros Usados para Mooney (D em mm):\n")
                for i, cap_d in enumerate(capilares_mooney_D_info):
                    f.write(f"    - Capilar {i+1}: D = {cap_d:.3f} mm\n")
            else:
                f.write("Correção de Mooney (Deslizamento): Não\n")

            if not realizar_bagley and not realizar_mooney: # Corrected variable names
                f.write("\n--- GEOMETRIA DO CAPILAR ÚNICO UTILIZADO ---\n")
                f.write(f"Diâmetro: {D_unico_mm:.3f} mm\n")
                f.write(f"Comprimento: {L_unico_mm:.2f} mm\n")

            f.write("\n--- RESULTADOS PRINCIPAIS (CURVA DE FLUXO PROCESSADA) ---\n")
            if df_res is not None and not df_res.empty:
                f.write(df_res.to_string(index=False, formatters={
                    col: (lambda x, dp=4: format_float_for_table(x, decimal_places=dp))
                    for col in df_res.columns
                }, na_rep='N/A'))
                f.write("\n")
            else:
                f.write("Não foram gerados dados processados para a tabela principal.\n")

            if best_model_nome and df_sum_modelo is not None and not df_sum_modelo.empty:
                f.write("\n--- MELHOR MODELO AJUSTADO ---\n")
                f.write(f"Modelo: {best_model_nome}\n")
                f.write(f"R²: {best_model_r2:.5f}\n")
                f.write(df_sum_modelo.to_string(index=False))
                f.write("\n")
            else:
                f.write("Nenhum modelo foi ajustado ou selecionado como o melhor.\n")

            f.write("\n--- ARQUIVOS GERADOS NESTA SESSÃO ---\n")
            for arq in lista_arquivos_gerados:
                f.write(f"- {arq}\n")
            
            f.write("\n" + "="*70 + "\n")
            f.write("FIM DO RELATÓRIO\n")
            f.write("="*70 + "\n")
        print(f"\nRelatório de texto salvo em: {filename}")
    except Exception as e:
        print(f"ERRO ao gerar relatório de texto: {e}")

# -----------------------------------------------------------------------------
# --- INÍCIO DA EXECUÇÃO PRINCIPAL ---
# -----------------------------------------------------------------------------
timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
output_folder = "resultados_analise_" + timestamp_str 
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
print("="*70+f"\n--- ANÁLISE REOLÓGICA (Sessão: {timestamp_str}) ---\n"+"="*70)
print(f"Todos os arquivos de saída serão salvos na pasta: {output_folder}")

arquivos_gerados_lista = []

print("\n--- Dados Fixos Globais da Pasta e Ensaio ---")
rho_pasta_g_cm3_fixo = input_float_com_virgula("Densidade da pasta (rho) em [g/cm³]: ")
tempo_extrusao_fixo_s_val = input_float_com_virgula("Tempo de extrusão fixo para todos os testes [s]: ")
if rho_pasta_g_cm3_fixo <= 0 or tempo_extrusao_fixo_s_val <= 0: print("ERRO: Densidade e tempo >0."); exit()
rho_pasta_si = rho_pasta_g_cm3_fixo * 1000

print("\n--- Método de Entrada de Dados Experimentais ---")
print("1. Entrada Manual via Console")
print("2. Carregar de Arquivo CSV")
metodo_entrada = ""
while metodo_entrada not in ["1", "2"]:
    metodo_entrada = input("Escolha o método (1 ou 2): ").strip()

realizar_bagley = input_sim_nao("\nDeseja realizar a Correção de Bagley (Perdas de Carga nas Extremidades)? (s/n): ")
realizar_mooney = input_sim_nao("\nDeseja realizar a Correção de Mooney (Deslizamento na Parede)? (s/n): ")

capilares_bagley_data_input = []
capilares_mooney_data_input = [] 
num_testes_para_analise = 0
gamma_dot_aw_an, tau_w_an = np.array([]), np.array([])
D_cap_mm_display, L_cap_mm_display = "N/A", "N/A"
R_cap_eff_final_si = np.nan 

pressoes_bar_display_tab, massas_g_display_tab = [],[]
D_cap_mm_bagley_comum_val = 0
L_cap_mm_mooney_comum_val = 0
L_cap_mm_unico_val, D_cap_mm_unico_val = 0,0 
bagley_capilares_L_mm_info = [] 
mooney_capilares_D_mm_info = [] 

if metodo_entrada == "1": 
    if realizar_bagley:
        print("\n--- Entrada Manual de Dados para Correção de Bagley ---")
        D_cap_mm_bagley_comum_val = input_float_com_virgula("Diâmetro COMUM dos capilares de Bagley [mm]: ")
        if D_cap_mm_bagley_comum_val <= 0: print("ERRO: Diâmetro >0."); exit()
        D_cap_mm_display = f"Bagley (D={D_cap_mm_bagley_comum_val:.3f}mm)"
        L_cap_mm_display = "Bagley (Vários L)"
        num_L_bagley = 0
        while num_L_bagley < 2:
            try: num_L_bagley = int(input("Número de capilares com comprimentos DIFERENTES (mínimo 2): "))
            except ValueError: print("ERRO: Número inválido.")
            if num_L_bagley < 2: print("ERRO: Mínimo 2 capilares para Bagley.")
        num_pontos_cap = 0
        try: num_pontos_cap = int(input("Número de pontos de teste (Pressão/Massa) POR CAPILAR: "))
        except ValueError: print("ERRO: Número inválido.")
        if num_pontos_cap <= 0: print("ERRO: Número de pontos >0."); exit()
        for i in range(num_L_bagley):
            L_i_mm = input_float_com_virgula(f"Comprimento L do capilar Bagley {i+1} [mm]: ")
            if L_i_mm <= 0: print("ERRO: Comprimento >0."); exit()
            bagley_capilares_L_mm_info.append(L_i_mm) 
            p_bar_cap_i, m_g_cap_i = [], []
            print(f"  Insira os {num_pontos_cap} pontos para L={L_i_mm}mm (D={D_cap_mm_bagley_comum_val}mm):")
            for j in range(num_pontos_cap):
                p = input_float_com_virgula(f"    Teste {j+1} - Pressão [bar]: ")
                m = input_float_com_virgula(f"    Teste {j+1} - Massa [g] (0 se não fluiu): ")
                if p <= 0 or m < 0: print("ERRO: Pressão >0, Massa >=0."); exit()
                p_bar_cap_i.append(p); m_g_cap_i.append(m)
            capilares_bagley_data_input.append({'L_mm':L_i_mm, 'L_m':L_i_mm/1000, 'D_mm': D_cap_mm_bagley_comum_val,
                                          'pressoes_Pa':np.array(p_bar_cap_i)*1e5, 
                                          'massas_kg':np.array(m_g_cap_i)/1000,
                                          'tempos_s':np.full(num_pontos_cap, tempo_extrusao_fixo_s_val)})
    
    if realizar_mooney: 
        print("\n--- Entrada Manual de Dados para Correção de Mooney ---")
        L_cap_mm_mooney_comum_val = input_float_com_virgula("Comprimento COMUM dos capilares de Mooney [mm]: ")
        if L_cap_mm_mooney_comum_val <= 0: print("ERRO: Comprimento >0."); exit()
        D_cap_mm_display = "Mooney (Vários D)"
        L_cap_mm_display = f"Mooney (L={L_cap_mm_mooney_comum_val:.2f}mm)"
        num_D_mooney = 0
        while num_D_mooney < 2:
            try: num_D_mooney = int(input("Número de capilares com diâmetros DIFERENTES (mínimo 2): "))
            except ValueError: print("ERRO: Número inválido.")
            if num_D_mooney < 2: print("ERRO: Mínimo 2 capilares para Mooney.")
        num_pontos_cap = 0
        try: num_pontos_cap = int(input("Número de pontos de teste (Pressão/Massa) POR CAPILAR: "))
        except ValueError: print("ERRO: Número inválido.")
        if num_pontos_cap <= 0: print("ERRO: Número de pontos >0."); exit()
        for i in range(num_D_mooney):
            D_i_mm = input_float_com_virgula(f"Diâmetro D do capilar Mooney {i+1} [mm]: ")
            if D_i_mm <= 0: print("ERRO: Diâmetro >0."); exit()
            mooney_capilares_D_mm_info.append(D_i_mm)
            p_bar_cap_i, m_g_cap_i = [], []
            print(f"  Insira os {num_pontos_cap} pontos para D={D_i_mm}mm (L={L_cap_mm_mooney_comum_val}mm):")
            for j in range(num_pontos_cap):
                p = input_float_com_virgula(f"    Teste {j+1} - Pressão [bar]: ")
                m = input_float_com_virgula(f"    Teste {j+1} - Massa [g] (0 se não fluiu): ")
                if p <= 0 or m < 0: print("ERRO: Pressão >0, Massa >=0."); exit()
                p_bar_cap_i.append(p); m_g_cap_i.append(m)
            capilares_mooney_data_input.append({'D_mm':D_i_mm, 'L_mm': L_cap_mm_mooney_comum_val, 
                                                'L_m':L_cap_mm_mooney_comum_val/1000, 
                                                'pressoes_Pa':np.array(p_bar_cap_i)*1e5, 
                                                'massas_kg':np.array(m_g_cap_i)/1000,
                                                'tempos_s':np.full(num_pontos_cap, tempo_extrusao_fixo_s_val)})

    if not realizar_bagley and not realizar_mooney: 
        print("\n--- Entrada Manual de Dados do Capilar Único ---")
        D_cap_mm_unico_val = input_float_com_virgula("Diâmetro do capilar (D_cap) em [mm]: ")
        L_cap_mm_unico_val = input_float_com_virgula("Comprimento do capilar (L_cap) em [mm]: ")
        if D_cap_mm_unico_val <= 0 or L_cap_mm_unico_val <= 0: print("ERRO: Dimensões >0."); exit()
        R_cap_analise_si, L_cap_m_analise = (D_cap_mm_unico_val/2000), L_cap_mm_unico_val/1000
        R_cap_eff_final_si = R_cap_analise_si 
        D_cap_mm_display, L_cap_mm_display = D_cap_mm_unico_val, L_cap_mm_unico_val
        try: num_testes_para_analise = int(input(f"Quantos testes (P,m) para o capilar D={D_cap_mm_display}mm, L={L_cap_mm_display}mm? "))
        except ValueError: print("ERRO: Número inválido."); exit()
        if num_testes_para_analise <= 0: print("ERRO: Número de testes >0."); exit()
        temp_pressoes_bar, temp_massas_g = [], []
        for i in range(num_testes_para_analise):
            p = input_float_com_virgula(f"  Teste {i+1} - Pressão [bar]: "); m = input_float_com_virgula(f"  Teste {i+1} - Massa [g]: ")
            if p <= 0 or m < 0: print("ERRO: Pressão >0, Massa >=0."); exit()
            temp_pressoes_bar.append(p); temp_massas_g.append(m)
        pressoes_bar_display_tab, massas_g_display_tab = temp_pressoes_bar, temp_massas_g 
        p_Pa = np.array(temp_pressoes_bar)*1e5; m_kg = np.array(temp_massas_g)/1000
        t_s = np.full(num_testes_para_analise, tempo_extrusao_fixo_s_val)
        vol_m3 = m_kg/rho_pasta_si; Q_m3_s = vol_m3/t_s
        tau_w_an = p_Pa * R_cap_analise_si / (2 * L_cap_m_analise)
        gamma_dot_aw_an = (4*Q_m3_s) / (np.pi * R_cap_analise_si**3) if R_cap_analise_si >0 else np.zeros_like(Q_m3_s)

elif metodo_entrada == "2": 
    print("\n--- Carregando Dados de Arquivo CSV ---")
    print("O arquivo CSV deve ter colunas: 'Diametro_mm', 'Comprimento_mm', 'Pressao_bar', 'Massa_g'")
    print("Para Bagley: todas as linhas de um conjunto de Bagley devem ter o mesmo 'Diametro_mm' e L diferentes.")
    print("Para Mooney: todas as linhas de um conjunto de Mooney devem ter o mesmo 'Comprimento_mm' e D diferentes.")
    csv_path = input("Digite o caminho para o arquivo CSV: ").strip().replace("\"", "")
    try:
        df_csv = pd.read_csv(csv_path, sep=None, decimal=',', engine='python', na_filter=False) 
        cols_esperadas = ['diametro_mm', 'comprimento_mm', 'pressao_bar', 'massa_g']
        df_csv.columns = df_csv.columns.str.lower().str.replace(' ', '_').str.replace('[^a-z0-9_]', '', regex=True)
        
        if not all(col in df_csv.columns for col in cols_esperadas):
            print(f"ERRO: Colunas faltando no CSV! Esperado (case insensitive, sem espaços/especiais): {cols_esperadas}")
            print(f"Colunas encontradas: {df_csv.columns.tolist()}"); exit()

        if realizar_bagley:
            diametros_csv_bagley = df_csv['diametro_mm'].astype(float).unique()
            if len(diametros_csv_bagley) > 1:
                print(f"Múltiplos diâmetros ({diametros_csv_bagley}) no CSV. Qual diâmetro usar para Bagley?")
                D_cap_mm_bagley_comum_val = input_float_com_virgula(f"Digite o Diâmetro COMUM para Bagley [mm] (ex: {diametros_csv_bagley[0]}): ")
            elif len(diametros_csv_bagley) == 1:
                 D_cap_mm_bagley_comum_val = diametros_csv_bagley[0]
            else: print("ERRO (Bagley CSV): Nenhum diâmetro encontrado."); exit()
            
            if D_cap_mm_bagley_comum_val <=0: print("ERRO (Bagley CSV): Diâmetro inválido."); exit()
            
            df_bagley_subset = df_csv[df_csv['diametro_mm'].astype(float) == D_cap_mm_bagley_comum_val]
            if df_bagley_subset.empty: print(f"ERRO (Bagley CSV): Nenhum dado para D={D_cap_mm_bagley_comum_val}mm."); exit()

            D_cap_mm_display = f"Bagley (D={D_cap_mm_bagley_comum_val:.3f}mm)"
            L_cap_mm_display = "Bagley (Vários L)"

            comprimentos_unicos_mm_bagley = sorted(df_bagley_subset['comprimento_mm'].astype(float).unique())
            if len(comprimentos_unicos_mm_bagley) < 2: print(f"ERRO (Bagley CSV): Menos de 2 comprimentos únicos encontrados para D={D_cap_mm_bagley_comum_val}mm."); exit()
            
            for L_mm_csv in comprimentos_unicos_mm_bagley:
                bagley_capilares_L_mm_info.append(L_mm_csv) 
                df_cap_csv = df_bagley_subset[df_bagley_subset['comprimento_mm'].astype(float) == L_mm_csv]
                if df_cap_csv.empty: continue
 
                p_bar_cap_i = df_cap_csv['pressao_bar'].astype(float).tolist()
                m_g_cap_i = df_cap_csv['massa_g'].astype(float).tolist()
                num_pontos_cap_csv = len(p_bar_cap_i)
                if num_pontos_cap_csv == 0: continue

                capilares_bagley_data_input.append({
                    'L_mm': L_mm_csv, 'L_m': L_mm_csv / 1000.0, 'D_mm': D_cap_mm_bagley_comum_val, 
                    'pressoes_Pa': np.array(p_bar_cap_i) * 1e5, 
                    'massas_kg': np.array(m_g_cap_i) / 1000.0,
                    'tempos_s': np.full(num_pontos_cap_csv, tempo_extrusao_fixo_s_val)
                })
            print(f"Dados lidos para {len(capilares_bagley_data_input)} capilares de Bagley (D={D_cap_mm_bagley_comum_val}mm) do CSV.")

        if realizar_mooney:
            comprimentos_csv_mooney = df_csv['comprimento_mm'].astype(float).unique()
            if len(comprimentos_csv_mooney) > 1:
                print(f"Múltiplos comprimentos ({comprimentos_csv_mooney}) no CSV. Qual comprimento usar para Mooney?")
                L_cap_mm_mooney_comum_val = input_float_com_virgula(f"Digite o Comprimento COMUM para Mooney [mm] (ex: {comprimentos_csv_mooney[0]}): ")
            elif len(comprimentos_csv_mooney) == 1:
                L_cap_mm_mooney_comum_val = comprimentos_csv_mooney[0]
            else: print("ERRO (Mooney CSV): Nenhum comprimento encontrado."); exit()

            if L_cap_mm_mooney_comum_val <=0: print("ERRO (Mooney CSV): Comprimento inválido."); exit()

            df_mooney_subset = df_csv[df_csv['comprimento_mm'].astype(float) == L_cap_mm_mooney_comum_val]
            if df_mooney_subset.empty: print(f"ERRO (Mooney CSV): Nenhum dado para L={L_cap_mm_mooney_comum_val}mm."); exit()

            D_cap_mm_display = "Mooney (Vários D)"
            L_cap_mm_display = f"Mooney (L={L_cap_mm_mooney_comum_val:.2f}mm)"

            diametros_unicos_mm_mooney = sorted(df_mooney_subset['diametro_mm'].astype(float).unique())
            if len(diametros_unicos_mm_mooney) < 2: print(f"ERRO (Mooney CSV): Menos de 2 diâmetros únicos encontrados para L={L_cap_mm_mooney_comum_val}mm."); exit()
            
            for D_mm_csv in diametros_unicos_mm_mooney:
                mooney_capilares_D_mm_info.append(D_mm_csv)
                df_cap_csv = df_mooney_subset[df_mooney_subset['diametro_mm'].astype(float) == D_mm_csv]
                if df_cap_csv.empty: continue
                
                p_bar_cap_i = df_cap_csv['pressao_bar'].astype(float).tolist()
                m_g_cap_i = df_cap_csv['massa_g'].astype(float).tolist()
                num_pontos_cap_csv = len(p_bar_cap_i)
                if num_pontos_cap_csv == 0: continue

                capilares_mooney_data_input.append({
                    'D_mm': D_mm_csv, 'L_mm': L_cap_mm_mooney_comum_val, 
                    'L_m': L_cap_mm_mooney_comum_val / 1000.0, 
                    'pressoes_Pa': np.array(p_bar_cap_i) * 1e5,
                    'massas_kg': np.array(m_g_cap_i) / 1000.0,
                    'tempos_s': np.full(num_pontos_cap_csv, tempo_extrusao_fixo_s_val)
                })
            print(f"Dados lidos para {len(capilares_mooney_data_input)} capilares de Mooney (L={L_cap_mm_mooney_comum_val}mm) do CSV.")

        if not realizar_bagley and not realizar_mooney: 
            unique_D_csv_unico = df_csv['diametro_mm'].astype(float).unique()
            unique_L_csv_unico = df_csv['comprimento_mm'].astype(float).unique()

            if len(unique_D_csv_unico) > 1 or len(unique_L_csv_unico) > 1:
                print("ALERTA: Múltiplos diâmetros/comprimentos no CSV para análise de capilar único.")
                print("Usando D e L da primeira linha. Certifique-se que o CSV contém dados de um único capilar.")
            
            D_cap_mm_unico_val = float(df_csv['diametro_mm'].iloc[0])
            L_cap_mm_unico_val = float(df_csv['comprimento_mm'].iloc[0])
            R_cap_analise_si, L_cap_m_analise = (D_cap_mm_unico_val/2000), L_cap_mm_unico_val/1000
            R_cap_eff_final_si = R_cap_analise_si
            D_cap_mm_display, L_cap_mm_display = D_cap_mm_unico_val, L_cap_mm_unico_val
            
            pressoes_bar_display_tab = df_csv['pressao_bar'].astype(float).tolist()
            massas_g_display_tab = df_csv['massa_g'].astype(float).tolist()
            num_testes_para_analise = len(pressoes_bar_display_tab)
            if num_testes_para_analise == 0: print("ERRO: CSV de capilar único não contém dados de P/m."); exit()

            p_Pa = np.array(pressoes_bar_display_tab)*1e5; m_kg = np.array(massas_g_display_tab)/1000
            t_s = np.full(num_testes_para_analise, tempo_extrusao_fixo_s_val)
            vol_m3 = m_kg/rho_pasta_si; Q_m3_s = vol_m3/t_s
            tau_w_an = p_Pa * R_cap_analise_si / (2 * L_cap_m_analise)
            gamma_dot_aw_an = (4*Q_m3_s) / (np.pi * R_cap_analise_si**3) if R_cap_analise_si >0 else np.zeros_like(Q_m3_s)
        
        print("Dados carregados do CSV com sucesso.")
    except FileNotFoundError: print(f"ERRO: Arquivo CSV não encontrado em '{csv_path}'."); exit()
    except Exception as e_csv: print(f"ERRO ao processar arquivo CSV: {e_csv}"); exit()
else: print("ERRO: Método de entrada desconhecido."); exit()


tau_w_for_mooney = np.array([]) 

if realizar_bagley and capilares_bagley_data_input:
    gamma_dot_aw_bagley_targets, tau_w_bagley_corrected = perform_bagley_correction(
        capilares_bagley_data_input, D_cap_mm_bagley_comum_val, 
        rho_pasta_si, tempo_extrusao_fixo_s_val, output_folder, timestamp_str
    )
    if len(tau_w_bagley_corrected) > 0:
        tau_w_an = tau_w_bagley_corrected
        gamma_dot_aw_an = gamma_dot_aw_bagley_targets 
        num_testes_para_analise = len(tau_w_an)
        tau_w_for_mooney = tau_w_an 
        pressoes_bar_display_tab = [np.nan] * num_testes_para_analise
        massas_g_display_tab = [np.nan] * num_testes_para_analise
    else:
        print("ALERTA: Correção de Bagley não resultou em pontos válidos. Pulando para próximas etapas se houver dados.")
        realizar_bagley = False 

if realizar_mooney and capilares_mooney_data_input:
    tau_w_mooney_corrected, gamma_dot_aw_slip_corrected = perform_mooney_correction(
        capilares_mooney_data_input, L_cap_mm_mooney_comum_val,
        rho_pasta_si, tempo_extrusao_fixo_s_val, 
        tau_w_for_mooney, 
        output_folder, timestamp_str
    )
    if len(tau_w_mooney_corrected) > 0:
        tau_w_an = tau_w_mooney_corrected
        gamma_dot_aw_an = gamma_dot_aw_slip_corrected 
        num_testes_para_analise = len(tau_w_an)
        pressoes_bar_display_tab = [np.nan] * num_testes_para_analise
        massas_g_display_tab = [np.nan] * num_testes_para_analise
    else:
        print("ALERTA: Correção de Mooney não resultou em pontos válidos.")
        realizar_mooney = False 

if num_testes_para_analise > 0:
    eta_a_an = np.full_like(gamma_dot_aw_an, np.nan)
    valid_an_idx = (gamma_dot_aw_an != 0) & (~np.isnan(gamma_dot_aw_an)) & (~np.isnan(tau_w_an))
    if np.any(valid_an_idx): eta_a_an[valid_an_idx] = tau_w_an[valid_an_idx] / gamma_dot_aw_an[valid_an_idx]

    if num_testes_para_analise > 1: 
        idx_final_sort = np.argsort(gamma_dot_aw_an) 
        gamma_dot_aw_an = gamma_dot_aw_an[idx_final_sort]
        tau_w_an = tau_w_an[idx_final_sort]
        if len(eta_a_an) == len(idx_final_sort): eta_a_an = eta_a_an[idx_final_sort]

        if not realizar_bagley and not realizar_mooney and metodo_entrada == "1":
             if len(pressoes_bar_display_tab) == len(idx_final_sort):
                pressoes_bar_display_tab = np.array(pressoes_bar_display_tab)[idx_final_sort].tolist()
             if len(massas_g_display_tab) == len(idx_final_sort):
                massas_g_display_tab = np.array(massas_g_display_tab)[idx_final_sort].tolist()
    
    gamma_dot_w_an_wr = np.zeros_like(gamma_dot_aw_an) 
    n_prime_global, log_K_prime_val = 1.0, 0.0 
    if num_testes_para_analise == 1 and (gamma_dot_aw_an[0] == 0 or np.isnan(gamma_dot_aw_an[0])): print("\nALERTA: 1 ponto sem fluxo ou NaN. n'=1.")
    elif num_testes_para_analise == 1 and gamma_dot_aw_an[0] > 0: print("\nALERTA: 1 ponto com fluxo. n'=1.")
    elif num_testes_para_analise > 1:
        valid_log_idx = (tau_w_an > 0) & (gamma_dot_aw_an > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_aw_an))
        if np.sum(valid_log_idx) < 2: print("ALERTA: <2 pontos com fluxo e válidos para n'. n'=1.")
        else:
            log_tau, log_gamma_aw = np.log(tau_w_an[valid_log_idx]), np.log(gamma_dot_aw_an[valid_log_idx])
            try:
                coeffs, residuals, _, _, _ = np.polyfit(log_gamma_aw, log_tau, 1, full=True) 
                n_prime_global = coeffs[0] 
                log_K_prime_val = coeffs[1] 
                K_prime_global = np.exp(log_K_prime_val)
                print(f"\nn' global (de log(τw) vs log(γaw_corrigida)): {n_prime_global:.4f}, K' global: {K_prime_global:.4f}")
                if n_prime_global <= 0: print("ALERTA: n' <= 0. Usando n'=1."); n_prime_global = 1.0
            except Exception as e: print(f"ERRO no cálculo de n': {e}. Assumindo n'=1."); n_prime_global = 1.0
    n_corr = n_prime_global if (n_prime_global != 0 and not np.isnan(n_prime_global)) else 1.0
    gamma_dot_w_an_wr = ((3*n_corr + 1)/(4*n_corr)) * gamma_dot_aw_an 
    
    eta_true_an = np.full_like(gamma_dot_w_an_wr, np.nan)
    valid_gw_idx = (gamma_dot_w_an_wr > 0) & (~np.isnan(gamma_dot_w_an_wr))
    if np.any(valid_gw_idx): eta_true_an[valid_gw_idx] = tau_w_an[valid_gw_idx] / gamma_dot_w_an_wr[valid_gw_idx]

    print("\n--- Ajustando Modelos Reológicos ---")
    def model_newtonian(gd,eta): return eta*gd
    def model_power_law(gd,K,n): return K*np.power(np.maximum(gd, 1e-9),n)
    def model_bingham(gd,t0,ep): return t0+ep*gd
    def model_hb(gd,t0,K,n): return t0+K*np.power(np.maximum(gd, 1e-9),n)

    models = {"Newtoniano":model_newtonian, "Lei da Potência":model_power_law, "Bingham":model_bingham, "Herschel-Bulkley":model_hb}
    model_results = {}
    valid_fit_idx = (tau_w_an > 0) & (gamma_dot_w_an_wr > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_w_an_wr))
    gd_fit_final = np.array([]) 
    if np.sum(valid_fit_idx)<1: print("ERRO: Sem pontos totalmente corrigidos para ajuste de modelos.")
    else:
        gd_fit_final,tau_fit_final = gamma_dot_w_an_wr[valid_fit_idx],tau_w_an[valid_fit_idx]
        for name,func in models.items():
            print(f"\nAjustando: {name}")
            n_params = func.__code__.co_argcount-1
            if len(gd_fit_final)<n_params: print(f"  Dados corrigidos insuficientes para {name}."); continue
            p0,bnds = None,(-np.inf, np.inf)
            n_model_guess = n_prime_global if (n_prime_global > 0 and not np.isnan(n_prime_global)) else 0.5
            if name=="Newtoniano": bnds=(0,np.inf)
            elif name=="Lei da Potência": p0,bnds = [1.0,n_model_guess],([1e-9,1e-9],[np.inf,np.inf])
            elif name=="Bingham": p0,bnds = [0.1,0.1],([0,1e-9],[np.inf,np.inf])
            elif name=="Herschel-Bulkley": p0,bnds = [0.1,1.0,n_model_guess],([0,1e-9,1e-9],[np.inf,np.inf,np.inf])
            try: 
                p,cov = curve_fit(func,gd_fit_final,tau_fit_final,p0=p0,bounds=bnds,maxfev=10000, method='trf')
                tau_pred = func(gd_fit_final,*p)
                ss_r,ss_t = np.sum((tau_fit_final-tau_pred)**2),np.sum((tau_fit_final-np.mean(tau_fit_final))**2)
                r2 = 1-(ss_r/ss_t) if ss_t > 1e-9 else (1.0 if ss_r < 1e-9 else 0.0)
                model_results[name] = {'params':p,'R2':r2,'covariance':cov}
                p_names = list(func.__code__.co_varnames[1:n_params+1])
                params_str = [format_float_for_table(val,5) for val in p]
                print(f"  Params ({', '.join(p_names)}): {', '.join(params_str)}, R²: {r2:.5f}")
            except Exception as e: print(f"  Falha no ajuste de {name}: {e}")
 
    best_model,best_r2_val = "",-np.inf
    if model_results:
        for name,data in model_results.items():
            if data['R2']>best_r2_val: best_r2_val,best_model = data['R2'],name
        if best_model: print(f"\n--- Melhor Modelo: {best_model} (R² = {best_r2_val:.5f}) ---")
        else: print("\n--- Nenhum modelo selecionado como o melhor. ---")
    else: print("\n--- Nenhum modelo foi ajustado. ---")

    print("\n\n"+"="*70+"\n--- TABELAS DE RESULTADOS --- (Valores numéricos formatados)\n"+"="*70)
    
    q_calc_mm3_s_tab = np.full_like(gamma_dot_aw_an, np.nan)
    d_tab_display = D_cap_mm_display 
    l_tab_display = L_cap_mm_display

    if not realizar_bagley and not realizar_mooney and D_cap_mm_unico_val > 0: 
        R_eff_q = D_cap_mm_unico_val / 2000.0
        q_calc_mm3_s_tab = (gamma_dot_aw_an * np.pi * R_eff_q**3 / 4) * 1e9
        d_tab_display = f"{D_cap_mm_unico_val:.3f}"
        l_tab_display = f"{L_cap_mm_unico_val:.2f}"
    elif realizar_bagley and D_cap_mm_bagley_comum_val > 0 : 
        R_eff_q = D_cap_mm_bagley_comum_val / 2000.0
        q_calc_mm3_s_tab = (gamma_dot_aw_an * np.pi * R_eff_q**3 / 4) * 1e9 
        d_tab_display = f"{D_cap_mm_bagley_comum_val:.3f} (Bagley Comum)"
        l_tab_display = "Bagley (Vários L)"
    elif realizar_mooney: 
        d_tab_display = "Mooney (Vários D)"
        if L_cap_mm_mooney_comum_val > 0: 
             l_tab_display = f"{L_cap_mm_mooney_comum_val:.2f} (Mooney Comum)"
        else:
             l_tab_display = "Mooney (L Comum N/A)" 
    
    d_cap_mm_col_tab = [d_tab_display] * num_testes_para_analise
    l_cap_mm_col_tab = [l_tab_display] * num_testes_para_analise
    rho_g_cm3_col_tab = np.full(num_testes_para_analise, rho_pasta_g_cm3_fixo)
    tempos_s_col_tab = np.full(num_testes_para_analise, tempo_extrusao_fixo_s_val)
    
    tabela_dict_main = {
        "Ponto Análise": list(range(1,num_testes_para_analise+1)),
        "Diâmetro Capilar (mm)": d_cap_mm_col_tab, 
        "Compr. Capilar (mm)": l_cap_mm_col_tab,
        "Densidade Pasta (g/cm³)": rho_g_cm3_col_tab, 
        "Tempo Extrusão (s)": tempos_s_col_tab,
        "Pressão Extrusão (bar)": pressoes_bar_display_tab, 
        "Massa Extrudada (g)": massas_g_display_tab,       
        "Vazão Vol. Calc. (mm³/s)": q_calc_mm3_s_tab,      
        "Tensão Cis. Parede τw (Pa)": tau_w_an, 
        "Taxa Cis. Apar. γ̇aw (s⁻¹)": gamma_dot_aw_an, 
        "Viscosidade Apar. ηa (Pa·s)": eta_a_an, 
        "Taxa Cis. Real Parede γ̇w (s⁻¹)": gamma_dot_w_an_wr, 
        "Viscosidade Real η (Pa·s)": eta_true_an 
    }
    df_resultados = pd.DataFrame(tabela_dict_main)
    pd.set_option('display.max_columns',None); pd.set_option('display.width',200)
    print("\n--- Tabela de Dados Processados ---")
    custom_formatters = {}
    for col in df_resultados.columns:
        dp=4; 
        if "mm³/s" in col or "s⁻¹" in col or "Pa)" in col: dp=2
        elif "bar" in col or "(s)" in col or "(mm)" in col or "(g/cm³)" in col or "(g)" in col: dp=3
        elif "Pa·s" in col: dp=4
        custom_formatters[col] = (lambda x, places=dp: format_float_for_table(x, decimal_places=places)) \
                                 if df_resultados[col].dtype == 'float64' or \
                                    isinstance(df_resultados[col].dtype, np.floating) or \
                                    col in ["Pressão Extrusão (bar)", "Massa Extrudada (g)"] \
                                 else str
    print(df_resultados.to_string(index=False, formatters=custom_formatters, na_rep='N/A_Corr', line_width=None)) 
    csv_filename = os.path.join(output_folder, f"{timestamp_str}_resultados_reologicos_compilados.csv")
    arquivos_gerados_lista.append(os.path.basename(csv_filename))
    try:
        df_resultados.to_csv(csv_filename,index=False,sep=';',decimal=',',float_format='%.4f', na_rep='N/A_Corr')
        print(f"\n\nTabela de dados compilados salva em: {csv_filename}")
    except Exception as e: print(f"\nERRO CSV: {e}")

    if realizar_bagley and capilares_bagley_data_input:
        print("\n--- Gerando CSV com Dados Brutos da Correção de Bagley ---")
        lista_dados_brutos_bagley_para_df = []
        for idx_cap, cap_data_raw in enumerate(capilares_bagley_data_input):
            num_pontos_neste_capilar = len(cap_data_raw['pressoes_Pa'])
            pressoes_bar_cap_raw = cap_data_raw['pressoes_Pa'] / 1e5
            massas_g_cap_raw = cap_data_raw['massas_kg'] * 1000
            if 'vazoes_Q_m3_s' not in cap_data_raw or 'gamma_dot_aw' not in cap_data_raw:
                 vol_temp = cap_data_raw['massas_kg'] / rho_pasta_si
                 cap_data_raw['vazoes_Q_m3_s'] = vol_temp / cap_data_raw['tempos_s']
                 R_m_bruto_bagley = (cap_data_raw.get('D_mm', D_cap_mm_bagley_comum_val) / 2000.0)
                 if R_m_bruto_bagley > 0:
                    cap_data_raw['gamma_dot_aw'] = (4*cap_data_raw['vazoes_Q_m3_s'])/(np.pi*R_m_bruto_bagley**3)
                 else:
                    cap_data_raw['gamma_dot_aw'] = np.zeros_like(vol_temp)

            vazoes_q_mm3_s_cap_raw = cap_data_raw['vazoes_Q_m3_s'] * 1e9
            volumes_mm3_cap_raw = cap_data_raw.get('volumes_m3', np.full(num_pontos_neste_capilar, np.nan)) * 1e9
            tau_w_nao_corrigida_Pa_col = np.full(num_pontos_neste_capilar, np.nan)
            eta_a_nao_corrigida_Pas_col = np.full(num_pontos_neste_capilar, np.nan)
            
            for j in range(num_pontos_neste_capilar):
                delta_p_pa_ponto = cap_data_raw['pressoes_Pa'][j]
                raio_m_ponto = (cap_data_raw.get('D_mm', D_cap_mm_bagley_comum_val) / 2000.0)
                compr_m_ponto = cap_data_raw['L_m']
                gamma_dot_aw_ponto = cap_data_raw['gamma_dot_aw'][j] 
                if compr_m_ponto > 0 and raio_m_ponto > 0: 
                    tau_w_nao_corrigida_Pa_col[j] = (delta_p_pa_ponto * raio_m_ponto) / (2 * compr_m_ponto)
                if gamma_dot_aw_ponto != 0 and not np.isnan(tau_w_nao_corrigida_Pa_col[j]):
                    eta_a_nao_corrigida_Pas_col[j] = tau_w_nao_corrigida_Pa_col[j] / gamma_dot_aw_ponto
                lista_dados_brutos_bagley_para_df.append({
                    "ID_Capilar_Bagley": idx_cap + 1, "Diametro_Comum_Bagley (mm)": cap_data_raw.get('D_mm', D_cap_mm_bagley_comum_val),
                    "Comprimento_Capilar_Usado (mm)": cap_data_raw['L_mm'], "Densidade_Pasta_Utilizada (g/cm3)": rho_pasta_g_cm3_fixo,
                    "Tempo_Extrusao_Fixo (s)": tempo_extrusao_fixo_s_val, "Ponto_Teste_No": j + 1,
                    "Pressao_Entrada_Medida (bar)": pressoes_bar_cap_raw[j], "Massa_Extrudada_Medida (g)": massas_g_cap_raw[j],
                    "Volume_Extrudado_Calculado (mm3)": volumes_mm3_cap_raw[j], "Vazao_Q_Calculada (mm3/s)": vazoes_q_mm3_s_cap_raw[j],
                    "DeltaP_Total_Medida (Pa)": delta_p_pa_ponto, "Taxa_Cis_Apar_gamma_dot_aw_Bruta (s-1)": gamma_dot_aw_ponto, 
                    "Tensao_Cis_Parede_Raw_Capilar (Pa)": tau_w_nao_corrigida_Pa_col[j],
                    "Viscosidade_Apar_Raw_Capilar (Pa.s)": eta_a_nao_corrigida_Pas_col[j] })
        if lista_dados_brutos_bagley_para_df:
            df_bagley_bruto = pd.DataFrame(lista_dados_brutos_bagley_para_df)
            csv_bagley_bruto_filename = os.path.join(output_folder, f"{timestamp_str}_dados_brutos_bagley.csv")
            arquivos_gerados_lista.append(os.path.basename(csv_bagley_bruto_filename))
            try:
                df_bagley_bruto.to_csv(csv_bagley_bruto_filename, index=False, sep=';', decimal=',', float_format='%.5f')
                print(f"Dados brutos Bagley salvos em: {csv_bagley_bruto_filename}")
            except Exception as e: print(f"ERRO CSV Bagley: {e}")
        else: print("Nenhum dado bruto de Bagley para salvar.")
    
    if realizar_mooney and capilares_mooney_data_input:
        print("\n--- Gerando CSV com Dados Brutos da Correção de Mooney ---")
        lista_dados_brutos_mooney_para_df = []
        for idx_cap, cap_data_raw in enumerate(capilares_mooney_data_input):
            num_pontos_neste_capilar = len(cap_data_raw['pressoes_Pa'])
            pressoes_bar_cap_raw = cap_data_raw['pressoes_Pa'] / 1e5
            massas_g_cap_raw = cap_data_raw['massas_kg'] * 1000
            
            if 'vazoes_Q_m3_s' not in cap_data_raw or 'gamma_dot_aw' not in cap_data_raw or 'tau_w_raw' not in cap_data_raw:
                 vol_temp = cap_data_raw['massas_kg'] / rho_pasta_si
                 cap_data_raw['vazoes_Q_m3_s'] = vol_temp / cap_data_raw['tempos_s']
                 R_m_bruto_mooney = cap_data_raw['D_mm'] / 2000.0
                 L_m_bruto_mooney = cap_data_raw['L_m'] 
                 if R_m_bruto_mooney > 0:
                    cap_data_raw['gamma_dot_aw'] = (4*cap_data_raw['vazoes_Q_m3_s'])/(np.pi*R_m_bruto_mooney**3)
                 else:
                    cap_data_raw['gamma_dot_aw'] = np.zeros_like(vol_temp)
                 if L_m_bruto_mooney > 0 and R_m_bruto_mooney > 0:
                    cap_data_raw['tau_w_raw'] = (cap_data_raw['pressoes_Pa'] * R_m_bruto_mooney) / (2 * L_m_bruto_mooney)
                 else:
                    cap_data_raw['tau_w_raw'] = np.full_like(cap_data_raw['pressoes_Pa'], np.nan)

            vazoes_q_mm3_s_cap_raw = cap_data_raw['vazoes_Q_m3_s'] * 1e9
            volumes_mm3_cap_raw = cap_data_raw.get('volumes_m3', np.full(num_pontos_neste_capilar,np.nan)) * 1e9
            
            for j in range(num_pontos_neste_capilar):
                lista_dados_brutos_mooney_para_df.append({
                    "ID_Capilar_Mooney": idx_cap + 1, 
                    "Comprimento_Comum_Mooney (mm)": cap_data_raw['L_mm'],
                    "Diametro_Capilar_Usado (mm)": cap_data_raw['D_mm'], 
                    "Densidade_Pasta_Utilizada (g/cm3)": rho_pasta_g_cm3_fixo,
                    "Tempo_Extrusao_Fixo (s)": tempo_extrusao_fixo_s_val, 
                    "Ponto_Teste_No": j + 1,
                    "Pressao_Entrada_Medida (bar)": pressoes_bar_cap_raw[j], 
                    "Massa_Extrudada_Medida (g)": massas_g_cap_raw[j],
                    "Volume_Extrudado_Calculado (mm3)": volumes_mm3_cap_raw[j], 
                    "Vazao_Q_Calculada (mm3/s)": vazoes_q_mm3_s_cap_raw[j],
                    "DeltaP_Total_Medida (Pa)": cap_data_raw['pressoes_Pa'][j], 
                    "Taxa_Cis_Apar_gamma_dot_aw_Bruta (s-1)": cap_data_raw['gamma_dot_aw'][j], 
                    "Tensao_Cis_Parede_Raw_Capilar (Pa)": cap_data_raw['tau_w_raw'][j], 
                    "Viscosidade_Apar_Raw_Capilar (Pa.s)": cap_data_raw['tau_w_raw'][j] / cap_data_raw['gamma_dot_aw'][j] if cap_data_raw['gamma_dot_aw'][j] !=0 else np.nan
                })
        if lista_dados_brutos_mooney_para_df:
            df_mooney_bruto = pd.DataFrame(lista_dados_brutos_mooney_para_df)
            csv_mooney_bruto_filename = os.path.join(output_folder, f"{timestamp_str}_dados_brutos_mooney.csv")
            arquivos_gerados_lista.append(os.path.basename(csv_mooney_bruto_filename))
            try:
                df_mooney_bruto.to_csv(csv_mooney_bruto_filename, index=False, sep=';', decimal=',', float_format='%.5f')
                print(f"Dados brutos Mooney salvos em: {csv_mooney_bruto_filename}")
            except Exception as e: print(f"ERRO CSV Mooney: {e}")
        else: print("Nenhum dado bruto de Mooney para salvar.")

    df_summary = None 
    if best_model and best_model in model_results:
        print("\n\n--- Resumo do Melhor Modelo Ajustado ---")
        model_data = model_results[best_model]
        params,r2_val = model_data['params'],model_data['R2']
        p_names = []
        if best_model=="Newtoniano": p_names=["Viscosidade Newtoniana (Pa·s)"]
        elif best_model=="Lei da Potência": p_names=["K (Pa·sⁿ)","n (-)"]
        elif best_model=="Bingham": p_names=["τ₀ (Pa)","ηₚ (Pa·s)"]
        elif best_model=="Herschel-Bulkley": p_names=["τ₀ (Pa)","K (Pa·sⁿ)","n (-)"]
        else: p_names=[f"Parâmetro {j+1}" for j in range(len(params))]
        summary_dict = {"Parâmetro":[],"Valor Estimado":[],"Erro Padrão (+/-)":[]}
        errors = [np.nan]*len(params)
        if 'covariance' in model_data and isinstance(model_data['covariance'],np.ndarray):
            cov = np.atleast_2d(model_data['covariance'])
            if cov.shape[0]==cov.shape[1] and cov.shape[0]==len(params):
                diag_cov = np.diag(cov)
                if np.all(diag_cov>=0): errors=np.sqrt(diag_cov)
        for name_param,val_param,err_param in zip(p_names,params,errors):
            summary_dict["Parâmetro"].append(name_param)
            summary_dict["Valor Estimado"].append(format_float_for_table(val_param,5))
            summary_dict["Erro Padrão (+/-)"].append(format_float_for_table(err_param,4) if not np.isnan(err_param) else "N/A")
        df_summary = pd.DataFrame(summary_dict)
        print(f"Modelo: {best_model}")
        print(df_summary.to_string(index=False, line_width=None))
        print(f"R²: {r2_val:.5f}")
        csv_resumo_modelo_filename = os.path.join(output_folder, f"{timestamp_str}_resumo_melhor_modelo.csv")
        arquivos_gerados_lista.append(os.path.basename(csv_resumo_modelo_filename))
        try:
            df_summary.to_csv(csv_resumo_modelo_filename, index=False, sep=';', decimal=',')
            print(f"\nResumo do melhor modelo salvo em: {csv_resumo_modelo_filename}")
        except Exception as e: print(f"\nERRO CSV Resumo Modelo: {e}")

    if num_testes_para_analise > 0 and model_results: 
        print("\n\n"+"="*70+"\n--- GERANDO GRÁFICOS ---\n"+"="*70)
        min_gp,max_gp = 0.001,1.0
        if len(gd_fit_final)>0: 
            min_g_obs_candidates = gd_fit_final[gd_fit_final>0]
            if len(min_g_obs_candidates) > 0:
                min_g_obs = np.min(min_g_obs_candidates)
                min_gp = min_g_obs * 0.5 
            else: # Fallback if all gd_fit_final are zero or negative (should not happen with valid_fit_idx)
                min_g_obs = 1e-3 
                min_gp = 1e-3

            max_g_obs = np.max(gd_fit_final)
            min_gp = max(min_gp, 1e-9) 
            max_gp = max_g_obs*1.5 if max_g_obs > 0 else min_gp * 100 + 1 # Ensure max_gp > min_gp
            if max_gp <= min_gp: max_gp = min_gp * 100 +1  
        
        if min_gp <= 1e-9: min_gp = 1e-3
        
        try:
            gd_plot_eff_pos = np.geomspace(min_gp,max_gp,200) if max_gp > min_gp else np.array([min_gp, min_gp*10])
            if len(gd_plot_eff_pos)<2 or np.any(np.diff(gd_plot_eff_pos)<=0) or not np.all(np.isfinite(gd_plot_eff_pos)): 
                raise ValueError("geomspace fail or non-finite values")
        except Exception: 
            gd_plot_eff_pos = np.linspace(min_gp,max_gp,200) if max_gp > min_gp else np.array([min_gp, min_gp*10])
            
        gd_plot_eff_pos = gd_plot_eff_pos[gd_plot_eff_pos>1e-9]
        if len(gd_plot_eff_pos)<2: 
            gd_plot_eff_pos = np.array([0.001,0.01]) if max_gp <= min_gp else np.array([max(1e-9,min_gp),max_gp])
        
        fig1, ax1 = plt.subplots(figsize=(10,7))
        ax1.scatter(gamma_dot_w_an_wr[valid_fit_idx], tau_w_an[valid_fit_idx], label=r'Dados Processados (Corrigidos)', c='k', marker='o', s=60, zorder=10)
        if len(gd_plot_eff_pos) > 0:
            for name, data in model_results.items():
                try: ax1.plot(gd_plot_eff_pos, models[name](gd_plot_eff_pos, *data['params']), label=fr'{name} (R²={data["R2"]:.4f})', lw=2.5, alpha=0.8)
                except: pass 
        ax1.set_xlabel(r'Taxa Cis. Real Parede (W-R Corrigida), $\dot{\gamma}_w$ (s⁻¹)'); ax1.set_ylabel(r'Tensão Cis. Parede (Bagley Corrigida), $\tau_w$ (Pa)')
        ax1.set_title(r'Curva de Fluxo e Modelos Ajustados'); ax1.legend(); ax1.grid(True,which="both",ls="--"); ax1.set_xscale('log'); ax1.set_yscale('log'); fig1.tight_layout()
        plot_filename_flow = os.path.join(output_folder, f"{timestamp_str}_curva_fluxo_corrigida.png")
        arquivos_gerados_lista.append(os.path.basename(plot_filename_flow))
        try: fig1.savefig(plot_filename_flow, dpi=300, bbox_inches='tight'); print(f"Gráfico Curva de Fluxo salvo: {plot_filename_flow}")
        except Exception as e: print(f"ERRO Salvar Curva de Fluxo: {e}")

        if num_testes_para_analise > 1 and 'n_prime_global' in locals() and not np.isnan(n_prime_global) and n_prime_global != 1.0 and 'log_K_prime_val' in locals() and not np.isnan(log_K_prime_val):
            valid_log_p_n_prime = (tau_w_an > 0) & (gamma_dot_aw_an > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_aw_an))
            if np.sum(valid_log_p_n_prime) > 1:
                log_tau_p, log_gamma_aw_p = np.log(tau_w_an[valid_log_p_n_prime]), np.log(gamma_dot_aw_an[valid_log_p_n_prime])
                fig2, ax2 = plt.subplots(figsize=(10,7))
                ax2.scatter(log_gamma_aw_p, log_tau_p, label=r'ln($\dot{\gamma}_{aw,s}$) vs ln($\tau_w$)',c='r',marker='x',s=60)
                if len(log_gamma_aw_p) > 1: 
                    min_log_g = np.min(log_gamma_aw_p)
                    max_log_g = np.max(log_gamma_aw_p)
                    if max_log_g > min_log_g : 
                         log_gamma_line = np.linspace(min_log_g, max_log_g, 50)
                         ax2.plot(log_gamma_line, n_prime_global * log_gamma_line + log_K_prime_val, '--', c='b', lw=2, label=fr'Ajuste Linear (n\'={n_prime_global:.3f})')
                ax2.set_xlabel(r'ln($\dot{\gamma}_{aw,s}$) (Corrigido por Slip, se aplicável)'); ax2.set_ylabel(r'ln($\tau_w$) (Corrigido por Bagley, se aplicável)'); ax2.set_title(r'Determinação de n\''); ax2.legend(); ax2.grid(True,which="both",ls="--"); fig2.tight_layout()
                plot_filename_nprime = os.path.join(output_folder, f"{timestamp_str}_determinacao_n_prime.png")
                arquivos_gerados_lista.append(os.path.basename(plot_filename_nprime))
                try: fig2.savefig(plot_filename_nprime, dpi=300, bbox_inches='tight'); print(f"Gráfico n' salvo: {plot_filename_nprime}")
                except Exception as e: print(f"ERRO Salvar n': {e}")
            else: print("  Aviso: Gráfico n' não gerado (pontos insuficientes após filtro).")
        elif num_testes_para_analise > 1 : print("  Aviso: Gráfico n' não gerado (n_prime_global ou log_K_prime_val inválidos).")

        fig3, ax3 = plt.subplots(figsize=(10,7))
        valid_eta_p = ~np.isnan(eta_true_an) & (gamma_dot_w_an_wr > 0) & (eta_true_an > 0) & (~np.isinf(eta_true_an))
        if np.any(valid_eta_p): ax3.scatter(gamma_dot_w_an_wr[valid_eta_p], eta_true_an[valid_eta_p], label=r'Viscosidade Real Processada ($\eta$)', c='g', marker='s', s=60, zorder=10)
        if len(gd_plot_eff_pos) > 0:
            for name, data in model_results.items():
                try:
                    tau_m_plot = models[name](gd_plot_eff_pos, *data['params'])
                    eta_m_plot = tau_m_plot / gd_plot_eff_pos
                    if name == "Newtoniano": eta_m_plot = np.full_like(gd_plot_eff_pos, data['params'][0])
                    ax3.plot(gd_plot_eff_pos, eta_m_plot, label=fr'Modelo {name} ($\eta$)', lw=2.5, alpha=0.8)
                except: pass
        ax3.set_xlabel(r'Taxa Cis. Real Parede (W-R Corrigida), $\dot{\gamma}_w$ (s⁻¹)'); ax3.set_ylabel(r'Viscosidade Real, $\eta$ (Pa·s)'); ax3.set_title(r'Viscosidade Real vs. Taxa de Cisalhamento'); ax3.legend(); ax3.grid(True,which="both",ls="--"); ax3.set_xscale('log'); ax3.set_yscale('log');
        fig3.tight_layout()
        plot_filename_visc = os.path.join(output_folder, f"{timestamp_str}_curva_viscosidade_real.png")
        arquivos_gerados_lista.append(os.path.basename(plot_filename_visc))
        try: fig3.savefig(plot_filename_visc, dpi=300, bbox_inches='tight'); print(f"Gráfico Viscosidade Real salvo: {plot_filename_visc}")
        except Exception as e: print(f"ERRO Salvar Viscosidade Real: {e}")
        
        if not realizar_bagley and not realizar_mooney and num_testes_para_analise > 0:
            if len(pressoes_bar_display_tab) == len(eta_true_an):
                pressoes_Pa_para_plot_pv = np.array(pressoes_bar_display_tab) * 1e5
                valid_plot_indices_pv = ~np.isnan(eta_true_an) & ~np.isnan(pressoes_Pa_para_plot_pv) & (eta_true_an > 0) & (pressoes_Pa_para_plot_pv > 0)
                if np.any(valid_plot_indices_pv):
                    fig4, ax4 = plt.subplots(figsize=(10,7))
                    ax4.scatter(pressoes_Pa_para_plot_pv[valid_plot_indices_pv], eta_true_an[valid_plot_indices_pv], label=r'Viscosidade Real vs. Pressão', c='purple', marker='D', s=60)
                    ax4.set_xlabel(r'Pressão Total Aplicada, $\Delta P_{total}$ (Pa)'); ax4.set_ylabel(r'Viscosidade Real, $\eta_{true}$ (Pa·s)')
                    ax4.set_title(r'Pressão Total Aplicada vs. Viscosidade Real'); ax4.legend(); ax4.grid(True,which="both",ls="--"); ax4.set_xscale('log'); ax4.set_yscale('log'); fig4.tight_layout()
                    plot_filename_pv = os.path.join(output_folder, f"{timestamp_str}_pressao_vs_viscosidade.png")
                    arquivos_gerados_lista.append(os.path.basename(plot_filename_pv))
                    try: fig4.savefig(plot_filename_pv, dpi=300, bbox_inches='tight'); print(f"Gráfico P vs Viscosidade salvo: {plot_filename_pv}")
                    except Exception as e: print(f"ERRO Salvar P vs Viscosidade: {e}")
                else: print("  Aviso: Gráfico P vs Viscosidade não gerado (sem dados válidos para plot).")
            else: print("  Aviso: Gráfico P vs Viscosidade não gerado (incompatibilidade de tamanho de dados).")
        elif realizar_bagley or realizar_mooney: print("  Info: Gráfico P vs Viscosidade (original) não gerado (Correções de Bagley/Mooney aplicadas).")

        print("\nFeche as janelas dos gráficos para finalizar o script.")
        plt.show()
    else: print("\n--- Gráficos principais não gerados (sem dados ou modelos). ---")
else: 
    print("\n--- Análise principal, tabelas e gráficos não gerados (nenhum ponto de dados válido para processar). ---")

d_unico_rel = D_cap_mm_unico_val if not realizar_bagley and not realizar_mooney else "N/A"
l_unico_rel = L_cap_mm_unico_val if not realizar_bagley and not realizar_mooney else "N/A"

df_sum_modelo_relatorio = df_summary if 'df_summary' in locals() and df_summary is not None and best_model and best_model in model_results else pd.DataFrame() 
r2_relatorio = best_r2_val if 'best_r2_val' in locals() and best_model and best_model in model_results else np.nan

D_bagley_report = D_cap_mm_bagley_comum_val if realizar_bagley else "N/A"
L_mooney_report = L_cap_mm_mooney_comum_val if realizar_mooney else "N/A"
df_resultados_report = df_resultados if 'df_resultados' in locals() and df_resultados is not None else None


gerar_relatorio_texto(timestamp_str, rho_pasta_g_cm3_fixo, tempo_extrusao_fixo_s_val,
                      realizar_bagley, D_bagley_report, bagley_capilares_L_mm_info,
                      realizar_mooney, L_mooney_report, mooney_capilares_D_mm_info,
                      d_unico_rel, l_unico_rel,
                      df_resultados_report,  
                      df_sum_modelo_relatorio, best_model if 'best_model' in locals() else "", r2_relatorio,
                      arquivos_gerados_lista, output_folder)

print("\n"+"="*70+"\n--- FIM DA ANÁLISE ---\n"+"="*70)
