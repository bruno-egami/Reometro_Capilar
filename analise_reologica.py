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
from scipy.interpolate import interp1d

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
        if abs(value) < 10**(-decimal_places) and value != 0 and abs(value) > 1e-12 :
             return f"{value:.{max(1,decimal_places)}g}"
        return f"{value:.{decimal_places}f}"
    return str(value)

# --- FUNÇÕES PARA CORREÇÕES E RELATÓRIO ---

def plotar_ajuste_bagley(L_over_R_vals, P_vals, slope, intercept, target_gamma_aw_str, output_folder, timestamp):
    if len(L_over_R_vals) < 2: return
    plt.figure(figsize=(8, 6))
    plt.scatter(L_over_R_vals, np.array(P_vals) / 1e5, marker='o', label='Dados Interpolados')
    line_x = np.array(sorted(L_over_R_vals))
    line_y_pa = slope * line_x + intercept
    plt.plot(line_x, line_y_pa / 1e5, color='red', label="Ajuste Linear (" + rf"$\tau_w_corr$={slope/2:.1f} Pa)") # AJUSTADO
    plt.xlabel('Razão Comprimento/Raio (L/R) (adimensional)')
    plt.ylabel("Pressão Total Medida (" + r"$\Delta P$" + ") (bar)") # AJUSTADO
    # Título com f-string e r-string para LaTeX
    title_str = "Plot de Bagley para Taxa de Cis. Aparente Alvo " + \
                rf"$\dot{{\gamma}}_{{aw}}^* \approx$ {float(target_gamma_aw_str):.1f} s$^{{-1}}$" # AJUSTADO
    plt.title(title_str)
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
        cap_data['R_m'] = (common_D_mm_bagley / 2000.0)
        cap_data['volumes_m3'] = cap_data['massas_kg'] / rho_si
        cap_data['vazoes_Q_m3_s'] = cap_data['volumes_m3'] / cap_data['tempos_s']
        cap_data['gamma_dot_aw'] = (4*cap_data['vazoes_Q_m3_s'])/(np.pi*cap_data['R_m']**3) if cap_data['R_m'] > 0 else np.zeros_like(cap_data['vazoes_Q_m3_s'])
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

def perform_mooney_correction(
    capilares_data, 
    common_L_mm,
    rho_si,
    t_ext_si,
    output_folder,
    timestamp,
    tau_w_targets_ref=None
):
    common_L_m = common_L_mm / 1000
    print("\n--- Iniciando Análise de Correção de Mooney (Deslizamento) ---")
    if not capilares_data or len(capilares_data) < 2:
        print("ALERTA (Mooney): São necessários dados de pelo menos 2 capilares com diâmetros diferentes para a correção de Mooney.")
        return np.array([]), np.array([])

    capilares_mooney_calc = []
    min_tau_overall_calc, max_tau_overall_calc = np.inf, -np.inf

    for cap in capilares_data:
        D_m = cap['D_mm'] / 1000.0
        R_m = D_m / 2.0
        massas_kg = np.array(cap['massas_kg'])
        pressoes_Pa = np.array(cap['pressoes_Pa'])
        if R_m <= 0:
            print(f"  ALERTA (Mooney Calc): Raio do capilar inválido (D={cap['D_mm']}mm). Pulando este capilar.")
            continue
        volumes_m3 = massas_kg / rho_si
        Q_m3_s = volumes_m3 / t_ext_si
        gamma_dot_aw_calc = (4 * Q_m3_s) / (np.pi * R_m**3) if R_m > 0 else np.zeros_like(Q_m3_s)
        if common_L_m <= 0:
            print(f"  ALERTA (Mooney Calc): Comprimento comum inválido (L={common_L_mm}mm). tau_w será NaN.")
            tau_w_calc = np.full_like(pressoes_Pa, np.nan)
        else:
            tau_w_calc = (pressoes_Pa * R_m) / (2 * common_L_m) if R_m > 0 and common_L_m > 0 else np.full_like(pressoes_Pa, np.nan)
        valid_tau_for_range = tau_w_calc[~np.isnan(tau_w_calc) & (massas_kg > 1e-9)]
        if len(valid_tau_for_range) > 0:
            min_tau_overall_calc = min(min_tau_overall_calc, np.min(valid_tau_for_range))
            max_tau_overall_calc = max(max_tau_overall_calc, np.max(valid_tau_for_range))
        capilares_mooney_calc.append({
            'R_m': R_m, '1/R': 1 / R_m if R_m > 0 else np.nan,
            'gamma_dot_aw': gamma_dot_aw_calc, 'tau_w': tau_w_calc,
            'D_mm': cap['D_mm']
        })
    
    if len(capilares_mooney_calc) < 2:
        print("ALERTA (Mooney): Menos de 2 capilares com dados válidos após cálculos iniciais.")
        return np.array([]), np.array([])

    tau_targets = np.array([])
    if tau_w_targets_ref is not None and len(tau_w_targets_ref) > 0:
        print("  Usando tau_w da correção de Bagley (ou entrada anterior) como alvos para Mooney.")
        tau_targets = np.sort(tau_w_targets_ref[~np.isnan(tau_w_targets_ref) & (tau_w_targets_ref > 0)])
    else:
        if not (np.isfinite(min_tau_overall_calc) and np.isfinite(max_tau_overall_calc) and min_tau_overall_calc < max_tau_overall_calc):
            print("ALERTA (Mooney): Faixa inválida de tensões de cisalhamento para definir alvos. Verifique dados.")
            return np.array([]), np.array([])
        tau_targets = np.geomspace(max(1e-2, min_tau_overall_calc), max_tau_overall_calc, 15)
        print(f"  Gerando {len(tau_targets)} alvos de tau_w para Mooney entre {min_tau_overall_calc:.2e} e {max_tau_overall_calc:.2e} Pa.")

    if len(tau_targets) == 0:
        print("ALERTA (Mooney): Nenhum alvo de tau_w válido para prosseguir."); return np.array([]), np.array([])

    gamma_dot_s_corr_list, tau_w_targets_ok_list = [], []
    for target_tau_k_val in tau_targets:
        inv_R_list, gamma_aw_interp_list, cap_radii_used_for_target = [], [], []
        for cap_calc_data in capilares_mooney_calc:
            if np.isnan(cap_calc_data['1/R']): continue
            valid_indices_interp = ~np.isnan(cap_calc_data['tau_w']) & ~np.isnan(cap_calc_data['gamma_dot_aw'])
            if np.sum(valid_indices_interp) < 2: continue
            tau_w_cap, gamma_aw_cap = cap_calc_data['tau_w'][valid_indices_interp], cap_calc_data['gamma_dot_aw'][valid_indices_interp]
            sort_indices = np.argsort(tau_w_cap)
            tau_w_cap_sorted, gamma_aw_cap_sorted = tau_w_cap[sort_indices], gamma_aw_cap[sort_indices]
            unique_tau_w_cap, unique_indices = np.unique(tau_w_cap_sorted, return_index=True)
            unique_gamma_aw_cap = gamma_aw_cap_sorted[unique_indices]
            if len(unique_tau_w_cap) < 2: continue
            if unique_tau_w_cap[0] <= target_tau_k_val <= unique_tau_w_cap[-1]:
                try:
                    interp_func = interp1d(unique_tau_w_cap, unique_gamma_aw_cap, kind='linear', bounds_error=False, fill_value=np.nan)
                    gamma_aw_interp = interp_func(target_tau_k_val)
                    if not np.isnan(gamma_aw_interp):
                        inv_R_list.append(cap_calc_data['1/R'])
                        gamma_aw_interp_list.append(gamma_aw_interp)
                        cap_radii_used_for_target.append(cap_calc_data['R_m'])
                except Exception as e: print(f"  Aviso (Mooney Interp Ex) D={cap_calc_data['D_mm']}mm: {e}")
        unique_radii_for_this_target = np.unique(np.array(cap_radii_used_for_target))
        if len(inv_R_list) >= 2 and len(unique_radii_for_this_target) >= 2:
            try:
                slope, intercept, r_val, p_val, std_err = linregress(inv_R_list, gamma_aw_interp_list)
                if intercept < 0 : print(f"  Aviso (Mooney Fit): Intercepto (gamma_s) negativo ({intercept:.2e}). Descartado."); continue 
                gamma_dot_s_corr_list.append(intercept); tau_w_targets_ok_list.append(target_tau_k_val)
                plt.figure(figsize=(8, 6))
                plt.scatter(inv_R_list, gamma_aw_interp_list, marker='o', color='blue', label="Dados Interpolados (" + r"$\dot{\gamma}_{aw}$" + ")") #AJUSTADO
                line_x_fit = np.array(sorted(inv_R_list))
                line_y_fit_gamma_aw = slope * line_x_fit + intercept
                plt.plot(line_x_fit, line_y_fit_gamma_aw, color='red', linestyle='--', label="Ajuste Linear (" + rf"$\dot{{\gamma}}_{{s}}$={intercept:.2e} s$^{{-1}}$" + ")") #AJUSTADO
                plt.xlabel('Inverso do Raio do Capilar (1/R) (m' + r'$^{-1}$' + ')') #AJUSTADO
                plt.ylabel("Taxa de Cisalhamento Aparente na Parede (" + r"$\dot{\gamma}_{aw}$" + ") (s" + r'$^{-1}$' + ')') #AJUSTADO
                title_str_mooney = "Plot de Mooney para Tensão na Parede Alvo " + \
                                   rf"$\tau_w \approx$ {float(target_tau_k_val):.1f} Pa" #AJUSTADO
                plt.title(title_str_mooney)
                plt.legend(); plt.grid(True)
                filename_tau_w_part = f"{float(target_tau_k_val):.0f}".replace('.', '_') 
                plot_filename = os.path.join(output_folder, f"{timestamp}_mooney_plot_tau_w_{filename_tau_w_part}.png")
                try: plt.savefig(plot_filename, dpi=150, bbox_inches='tight'); print(f"  Plot de Mooney salvo em: {plot_filename}")
                except Exception as e_save: print(f"  ERRO ao salvar plot de Mooney: {e_save}")
                plt.close()
            except Exception as e_fit: print(f"  Aviso (Mooney Fit LinReg) tau_w_target={target_tau_k_val:.2e}: {e_fit}")
        elif len(inv_R_list) < 2 : print(f"  Aviso (Mooney): <2 pontos (1/R) para ajuste em tau_w_target={target_tau_k_val:.2e}.")
        elif len(unique_radii_for_this_target) < 2: print(f"  Aviso (Mooney): Pontos de 1/R não são de capilares distintos para tau_w_target={target_tau_k_val:.2e}.")
    if not tau_w_targets_ok_list: print("ALERTA (Mooney): Nenhuma curva de fluxo corrigida para deslizamento foi gerada."); return np.array([]), np.array([]) 
    print("--- Correção de Mooney (Deslizamento) Concluída ---")
    return np.array(gamma_dot_s_corr_list), np.array(tau_w_targets_ok_list)

def gerar_relatorio_texto(timestamp_str_report, rho_g_cm3, t_ext_s,
                          realizar_bagley, D_bagley_mm, capilares_bagley_info, 
                          realizar_mooney, L_mooney_mm, capilares_mooney_D_info, 
                          D_unico_mm, L_unico_mm,
                          df_res, df_sum_modelo, best_model_nome, best_model_r2,
                          comportamento_fluido_relatorio, 
                          lista_arquivos_gerados, output_folder):
    filename = os.path.join(output_folder, f"{timestamp_str_report}_relatorio_analise.txt")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\nRELATÓRIO DE ANÁLISE REOLÓGICA\n" + "="*70 + "\n")
            f.write(f"Sessão: {timestamp_str_report}\nData da Geração: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n--- PARÂMETROS FIXOS GLOBAIS ---\n")
            f.write(f"Densidade da Pasta: {rho_g_cm3:.3f} g/cm³\nTempo de Extrusão Fixo: {t_ext_s:.2f} s\n")
            f.write("\n--- CONFIGURAÇÃO DE CORREÇÕES ---\n")
            f.write(f"Correção de Bagley: {'Sim' if realizar_bagley else 'Não'}\n")
            if realizar_bagley:
                f.write(f"  Diâmetro Comum Capilares Bagley: {D_bagley_mm:.3f} mm\n  Capilares Usados (L em mm):\n")
                for i, cap_l in enumerate(capilares_bagley_info): f.write(f"    - Capilar {i+1}: L = {cap_l:.2f} mm\n")
            f.write(f"Correção de Mooney (Deslizamento): {'Sim' if realizar_mooney else 'Não'}\n")
            if realizar_mooney:
                f.write(f"  Comprimento Comum Capilares Mooney: {L_mooney_mm:.2f} mm\n  Diâmetros Usados (D em mm):\n")
                for i, cap_d in enumerate(capilares_mooney_D_info): f.write(f"    - Capilar {i+1}: D = {cap_d:.3f} mm\n")
            if not realizar_bagley and not realizar_mooney:
                f.write("\n--- GEOMETRIA DO CAPILAR ÚNICO UTILIZADO ---\n")
                f.write(f"Diâmetro: {D_unico_mm:.3f} mm\nComprimento: {L_unico_mm:.2f} mm\n")
            f.write("\n--- RESULTADOS PRINCIPAIS (CURVA DE FLUXO PROCESSADA) ---\n")
            if df_res is not None and not df_res.empty:
                f.write(df_res.to_string(index=False, formatters={col: (lambda x, dp=4: format_float_for_table(x, dp)) for col in df_res.columns}, na_rep='N/A') + "\n")
            else: f.write("Não foram gerados dados processados para a tabela principal.\n")
            if best_model_nome and df_sum_modelo is not None and not df_sum_modelo.empty:
                f.write("\n--- MELHOR MODELO AJUSTADO ---\n")
                f.write(df_sum_modelo.to_string(index=False) + "\n") 
            else: f.write("Nenhum modelo foi ajustado ou selecionado como o melhor.\n")
            f.write("\n--- ARQUIVOS GERADOS NESTA SESSÃO ---\n")
            for arq in lista_arquivos_gerados: f.write(f"- {arq}\n")
            f.write("\n" + "="*70 + "\nFIM DO RELATÓRIO\n" + "="*70 + "\n")
        print(f"\nRelatório de texto salvo em: {filename}")
    except Exception as e: print(f"ERRO ao gerar relatório de texto: {e}")

# -----------------------------------------------------------------------------
# --- INÍCIO DA EXECUÇÃO PRINCIPAL ---
# -----------------------------------------------------------------------------
timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
output_folder = "resultados_analise_" + timestamp_str 
if not os.path.exists(output_folder): os.makedirs(output_folder)
print("="*70+f"\n--- ANÁLISE REOLÓGICA (Sessão: {timestamp_str}) ---\n"+"="*70)
print(f"Todos os arquivos de saída serão salvos na pasta: {output_folder}")
arquivos_gerados_lista = []

rho_pasta_g_cm3_fixo, tempo_extrusao_fixo_s_val, metodo_entrada, csv_path = 0.0, 0.0, "", ""
realizar_bagley, realizar_mooney = False, False
D_cap_mm_bagley_comum_val, L_cap_mm_mooney_comum_val = 0.0, 0.0
D_cap_mm_unico_val, L_cap_mm_unico_val = 0.0, 0.0
num_pontos_cap_bagley_manual, num_pontos_cap_mooney_manual, num_testes_unico_manual = 0, 0, 0

dados_confirmados = False
while not dados_confirmados:
    capilares_bagley_data_input, capilares_mooney_data_input = [], []
    bagley_capilares_L_mm_info, mooney_capilares_D_mm_info = [], []
    pressoes_bar_display_tab, massas_g_display_tab = [], []
    
    print("\n--- Dados Fixos Globais da Pasta e Ensaio ---")
    rho_pasta_g_cm3_fixo = input_float_com_virgula("Densidade da pasta (rho) em [g/cm³]: ")
    tempo_extrusao_fixo_s_val = input_float_com_virgula("Tempo de extrusão fixo para todos os testes [s]: ")
    if rho_pasta_g_cm3_fixo <= 0 or tempo_extrusao_fixo_s_val <= 0: 
        print("ERRO: Densidade e tempo devem ser >0. Tente novamente."); continue
    rho_pasta_si = rho_pasta_g_cm3_fixo * 1000

    print("\n--- Método de Entrada de Dados Experimentais ---\n1. Manual\n2. CSV")
    metodo_entrada = ""
    while metodo_entrada not in ["1", "2"]: metodo_entrada = input("Escolha o método (1 ou 2): ").strip()
    realizar_bagley = input_sim_nao("\nCorreção de Bagley? (s/n): ")
    realizar_mooney = input_sim_nao("\nCorreção de Mooney? (s/n): ")

    num_testes_para_analise = 0 
    _D_cap_mm_bagley_comum_val_resumo, _L_cap_mm_mooney_comum_val_resumo = "N/A", "N/A"
    _D_cap_mm_unico_val_resumo, _L_cap_mm_unico_val_resumo = "N/A", "N/A"
    _csv_path_resumo = "N/A"
    
    num_pontos_cap_bagley_manual, num_pontos_cap_mooney_manual, num_testes_unico_manual = 0,0,0

    if metodo_entrada == "1": 
        if realizar_bagley:
            print("\n--- Entrada Manual: Bagley ---")
            D_cap_mm_bagley_comum_val = input_float_com_virgula("Diâmetro COMUM (Bagley) [mm]: ")
            if D_cap_mm_bagley_comum_val <= 0: print("ERRO: Diâmetro >0."); bagley_capilares_L_mm_info.clear(); capilares_bagley_data_input.clear(); continue
            _D_cap_mm_bagley_comum_val_resumo = f"{D_cap_mm_bagley_comum_val:.3f}"
            num_L_bagley = 0
            while num_L_bagley < 2:
                try: num_L_bagley = int(input("No. capilares L DIFERENTES (Bagley, min 2): "))
                except ValueError: print("ERRO: No. inválido.")
                if num_L_bagley < 2: print("ERRO: Mínimo 2.")
            try: num_pontos_cap_bagley_manual = int(input("No. pontos (P/M) POR CAPILAR (Bagley): "))
            except ValueError: print("ERRO: No. inválido."); bagley_capilares_L_mm_info.clear(); capilares_bagley_data_input.clear(); continue
            if num_pontos_cap_bagley_manual <= 0: print("ERRO: No. pontos >0."); bagley_capilares_L_mm_info.clear(); capilares_bagley_data_input.clear(); continue
            
            temp_capilares_bagley_data = []
            temp_bagley_L_info = []
            all_bagley_manual_ok = True
            for i in range(num_L_bagley):
                L_i_mm = input_float_com_virgula(f"L capilar Bagley {i+1} [mm]: ")
                if L_i_mm <= 0: print("ERRO: L >0."); all_bagley_manual_ok=False; break
                temp_bagley_L_info.append(L_i_mm)
                p_bar_cap_i, m_g_cap_i = [], []
                print(f"  Insira {num_pontos_cap_bagley_manual} pontos para L={L_i_mm}mm (D={D_cap_mm_bagley_comum_val}mm):")
                for j in range(num_pontos_cap_bagley_manual):
                    p = input_float_com_virgula(f"    T{j+1}-P[bar]: "); m = input_float_com_virgula(f"    T{j+1}-M[g]: ")
                    if p <= 0 or m < 0: print("ERRO: P>0, M>=0."); all_bagley_manual_ok=False; break
                    p_bar_cap_i.append(p); m_g_cap_i.append(m)
                if not all_bagley_manual_ok: break
                temp_capilares_bagley_data.append({'L_mm':L_i_mm, 'L_m':L_i_mm/1000, 'D_mm': D_cap_mm_bagley_comum_val,
                                              'pressoes_Pa':np.array(p_bar_cap_i)*1e5, 
                                              'massas_kg':np.array(m_g_cap_i)/1000,
                                              'tempos_s':np.full(num_pontos_cap_bagley_manual, tempo_extrusao_fixo_s_val)})
            if not all_bagley_manual_ok: bagley_capilares_L_mm_info.clear(); capilares_bagley_data_input.clear(); continue
            capilares_bagley_data_input = temp_capilares_bagley_data
            bagley_capilares_L_mm_info = temp_bagley_L_info

        if realizar_mooney: 
            print("\n--- Entrada Manual: Mooney ---")
            L_cap_mm_mooney_comum_val = input_float_com_virgula("Comprimento COMUM (Mooney) [mm]: ")
            if L_cap_mm_mooney_comum_val <= 0: print("ERRO: L >0."); mooney_capilares_D_mm_info.clear(); capilares_mooney_data_input.clear(); continue
            _L_cap_mm_mooney_comum_val_resumo = f"{L_cap_mm_mooney_comum_val:.2f}"
            num_D_mooney = 0
            while num_D_mooney < 2:
                try: num_D_mooney = int(input("No. capilares D DIFERENTES (Mooney, min 2): "))
                except ValueError: print("ERRO: No. inválido.")
                if num_D_mooney < 2: print("ERRO: Mínimo 2.")
            try: num_pontos_cap_mooney_manual = int(input("No. pontos (P/M) POR CAPILAR (Mooney): "))
            except ValueError: print("ERRO: No. inválido."); mooney_capilares_D_mm_info.clear(); capilares_mooney_data_input.clear(); continue
            if num_pontos_cap_mooney_manual <= 0: print("ERRO: No. pontos >0."); mooney_capilares_D_mm_info.clear(); capilares_mooney_data_input.clear(); continue

            temp_capilares_mooney_data = []
            temp_mooney_D_info = []
            all_mooney_manual_ok = True
            for i in range(num_D_mooney):
                D_i_mm = input_float_com_virgula(f"D capilar Mooney {i+1} [mm]: ")
                if D_i_mm <= 0: print("ERRO: D >0."); all_mooney_manual_ok=False; break
                temp_mooney_D_info.append(D_i_mm)
                p_bar_cap_i, m_g_cap_i = [], []
                print(f"  Insira {num_pontos_cap_mooney_manual} pontos para D={D_i_mm}mm (L={L_cap_mm_mooney_comum_val}mm):")
                for j in range(num_pontos_cap_mooney_manual):
                    p = input_float_com_virgula(f"    T{j+1}-P[bar]: "); m = input_float_com_virgula(f"    T{j+1}-M[g]: ")
                    if p <= 0 or m < 0: print("ERRO: P>0, M>=0."); all_mooney_manual_ok=False; break
                    p_bar_cap_i.append(p); m_g_cap_i.append(m)
                if not all_mooney_manual_ok: break
                temp_capilares_mooney_data.append({'D_mm':D_i_mm, 'L_mm': L_cap_mm_mooney_comum_val, 
                                                    'L_m':L_cap_mm_mooney_comum_val/1000, 
                                                    'pressoes_Pa':np.array(p_bar_cap_i)*1e5, 
                                                    'massas_kg':np.array(m_g_cap_i)/1000,
                                                    'tempos_s':np.full(num_pontos_cap_mooney_manual, tempo_extrusao_fixo_s_val)})
            if not all_mooney_manual_ok: mooney_capilares_D_mm_info.clear(); capilares_mooney_data_input.clear(); continue
            capilares_mooney_data_input = temp_capilares_mooney_data
            mooney_capilares_D_mm_info = temp_mooney_D_info

        if not realizar_bagley and not realizar_mooney: 
            print("\n--- Entrada Manual: Capilar Único ---")
            D_cap_mm_unico_val = input_float_com_virgula("D capilar [mm]: ")
            L_cap_mm_unico_val = input_float_com_virgula("L capilar [mm]: ")
            if D_cap_mm_unico_val <= 0 or L_cap_mm_unico_val <= 0: print("ERRO: Dimensões >0."); continue
            _D_cap_mm_unico_val_resumo = f"{D_cap_mm_unico_val:.3f}"; _L_cap_mm_unico_val_resumo = f"{L_cap_mm_unico_val:.2f}"
            try: num_testes_unico_manual = int(input(f"Quantos testes (P,m) para D={D_cap_mm_unico_val}mm, L={L_cap_mm_unico_val}mm? "))
            except ValueError: print("ERRO: No. inválido."); continue
            if num_testes_unico_manual <= 0: print("ERRO: No. testes >0."); continue
            num_testes_para_analise = num_testes_unico_manual
            temp_pressoes_bar, temp_massas_g = [], []
            all_unico_manual_ok = True
            for i in range(num_testes_unico_manual):
                p = input_float_com_virgula(f"  T{i+1}-P[bar]: "); m = input_float_com_virgula(f"  T{i+1}-M[g]: ")
                if p <= 0 or m < 0: print("ERRO: P>0, M>=0."); all_unico_manual_ok=False; break
                temp_pressoes_bar.append(p); temp_massas_g.append(m)
            if not all_unico_manual_ok : continue
            pressoes_bar_display_tab, massas_g_display_tab = temp_pressoes_bar, temp_massas_g
    elif metodo_entrada == "2": 
        print("\n--- Carregando Dados de Arquivo CSV ---")
        csv_path = input("Caminho para o arquivo CSV: ").strip().replace("\"", "")
        _csv_path_resumo = csv_path
        try:
            df_csv = pd.read_csv(csv_path, sep=None, decimal=',', engine='python', na_filter=False) 
            cols_esperadas = ['diametro_mm', 'comprimento_mm', 'pressao_bar', 'massa_g']
            df_csv.columns = df_csv.columns.str.lower().str.replace(' ', '_').str.replace('[^a-z0-9_]', '', regex=True)
            if not all(col in df_csv.columns for col in cols_esperadas):
                print(f"ERRO: Colunas faltando! Esperado: {cols_esperadas}. Encontradas: {df_csv.columns.tolist()}"); continue
            if realizar_bagley:
                diam_csv_bagley = df_csv['diametro_mm'].astype(float).unique()
                if len(diam_csv_bagley) > 1: D_cap_mm_bagley_comum_val = input_float_com_virgula(f"Múltiplos D ({diam_csv_bagley}). D COMUM Bagley [mm]: ")
                elif len(diam_csv_bagley) == 1: D_cap_mm_bagley_comum_val = diam_csv_bagley[0]
                else: print("ERRO CSV Bagley: Nenhum diâmetro."); continue
                if D_cap_mm_bagley_comum_val <=0: print("ERRO CSV Bagley: D inválido."); continue
                _D_cap_mm_bagley_comum_val_resumo = f"{D_cap_mm_bagley_comum_val:.3f}"
                df_b_sub = df_csv[df_csv['diametro_mm'].astype(float) == D_cap_mm_bagley_comum_val]
                if df_b_sub.empty: print(f"ERRO CSV Bagley: Nenhum dado para D={D_cap_mm_bagley_comum_val}mm."); continue
                L_unicos_mm_b = sorted(df_b_sub['comprimento_mm'].astype(float).unique())
                if len(L_unicos_mm_b) < 2: print(f"ERRO CSV Bagley: <2 L únicos para D={D_cap_mm_bagley_comum_val}mm."); continue
                for L_mm_csv in L_unicos_mm_b:
                    bagley_capilares_L_mm_info.append(L_mm_csv) 
                    df_cap_csv = df_b_sub[df_b_sub['comprimento_mm'].astype(float) == L_mm_csv]
                    if df_cap_csv.empty: continue
                    p_bar, m_g = df_cap_csv['pressao_bar'].astype(float).tolist(), df_cap_csv['massa_g'].astype(float).tolist()
                    if not p_bar: continue
                    capilares_bagley_data_input.append({'L_mm': L_mm_csv, 'L_m': L_mm_csv/1000.0, 'D_mm': D_cap_mm_bagley_comum_val, 
                                                      'pressoes_Pa': np.array(p_bar)*1e5, 'massas_kg': np.array(m_g)/1000.0,
                                                      'tempos_s': np.full(len(p_bar), tempo_extrusao_fixo_s_val)})
                print(f"Dados CSV Bagley: {len(capilares_bagley_data_input)} capilares (D={D_cap_mm_bagley_comum_val}mm).")
            if realizar_mooney:
                L_csv_mooney = df_csv['comprimento_mm'].astype(float).unique()
                if len(L_csv_mooney) > 1: L_cap_mm_mooney_comum_val = input_float_com_virgula(f"Múltiplos L ({L_csv_mooney}). L COMUM Mooney [mm]: ")
                elif len(L_csv_mooney) == 1: L_cap_mm_mooney_comum_val = L_csv_mooney[0]
                else: print("ERRO CSV Mooney: Nenhum comprimento."); continue
                if L_cap_mm_mooney_comum_val <=0: print("ERRO CSV Mooney: L inválido."); continue
                _L_cap_mm_mooney_comum_val_resumo = f"{L_cap_mm_mooney_comum_val:.2f}"
                df_m_sub = df_csv[df_csv['comprimento_mm'].astype(float) == L_cap_mm_mooney_comum_val]
                if df_m_sub.empty: print(f"ERRO CSV Mooney: Nenhum dado para L={L_cap_mm_mooney_comum_val}mm."); continue
                D_unicos_mm_m = sorted(df_m_sub['diametro_mm'].astype(float).unique())
                if len(D_unicos_mm_m) < 2: print(f"ERRO CSV Mooney: <2 D únicos para L={L_cap_mm_mooney_comum_val}mm."); continue
                for D_mm_csv in D_unicos_mm_m:
                    mooney_capilares_D_mm_info.append(D_mm_csv)
                    df_cap_csv = df_m_sub[df_m_sub['diametro_mm'].astype(float) == D_mm_csv]
                    if df_cap_csv.empty: continue
                    p_bar, m_g = df_cap_csv['pressao_bar'].astype(float).tolist(), df_cap_csv['massa_g'].astype(float).tolist()
                    if not p_bar: continue
                    capilares_mooney_data_input.append({'D_mm': D_mm_csv, 'L_mm': L_cap_mm_mooney_comum_val, 'L_m': L_cap_mm_mooney_comum_val/1000.0,
                                                       'pressoes_Pa': np.array(p_bar)*1e5, 'massas_kg': np.array(m_g)/1000.0,
                                                       'tempos_s': np.full(len(p_bar), tempo_extrusao_fixo_s_val)})
                print(f"Dados CSV Mooney: {len(capilares_mooney_data_input)} capilares (L={L_cap_mm_mooney_comum_val}mm).")
            if not realizar_bagley and not realizar_mooney: 
                if len(df_csv['diametro_mm'].astype(float).unique()) > 1 or len(df_csv['comprimento_mm'].astype(float).unique()) > 1:
                    print("ALERTA CSV: Múltiplos D/L para capilar único. Usando D/L da primeira linha.")
                D_cap_mm_unico_val = float(df_csv['diametro_mm'].iloc[0])
                L_cap_mm_unico_val = float(df_csv['comprimento_mm'].iloc[0])
                _D_cap_mm_unico_val_resumo = f"{D_cap_mm_unico_val:.3f}"; _L_cap_mm_unico_val_resumo = f"{L_cap_mm_unico_val:.2f}"
                pressoes_bar_display_tab = df_csv['pressao_bar'].astype(float).tolist()
                massas_g_display_tab = df_csv['massa_g'].astype(float).tolist()
                num_testes_para_analise = len(pressoes_bar_display_tab)
                if num_testes_para_analise == 0: print("ERRO CSV: Capilar único sem dados P/m."); continue
            print("Dados carregados do CSV com sucesso.")
        except FileNotFoundError: print(f"ERRO: CSV não encontrado '{csv_path}'. Tente novamente."); continue
        except Exception as e_csv: print(f"ERRO ao processar CSV: {e_csv}. Tente novamente."); continue
    else: print("ERRO: Método de entrada desconhecido."); continue

    # --- EXIBIR RESUMO DOS DADOS INSERIDOS PARA CONFIRMAÇÃO ---
    print("\n" + "="*25 + " RESUMO DOS DADOS INSERIDOS PARA CONFIRMAÇÃO " + "="*25)
    print(f"Densidade da Pasta: {rho_pasta_g_cm3_fixo:.3f} g/cm³")
    print(f"Tempo de Extrusão Fixo: {tempo_extrusao_fixo_s_val:.2f} s")
    print(f"Método de Entrada: {'Manual' if metodo_entrada == '1' else 'Arquivo CSV'}")
    if metodo_entrada == '2': print(f"  Caminho do Arquivo CSV: {_csv_path_resumo}")
    print(f"\nCorreção de Bagley: {'Sim' if realizar_bagley else 'Não'}")
    if realizar_bagley:
        print(f"  Diâmetro Comum (Bagley): {_D_cap_mm_bagley_comum_val_resumo} mm")
        if capilares_bagley_data_input:
            print("  Dados dos Testes para Bagley:")
            for i, cap_data in enumerate(capilares_bagley_data_input):
                print(f"    Capilar Bagley {i+1} (L = {cap_data['L_mm']:.2f} mm):")
                pressoes_bar_cap = cap_data['pressoes_Pa'] / 1e5
                massas_g_cap = cap_data['massas_kg'] * 1000
                for j in range(len(pressoes_bar_cap)):
                    print(f"      - Teste {j+1}: {pressoes_bar_cap[j]:.2f} bar | {massas_g_cap[j]:.2f} g")
    print(f"\nCorreção de Mooney: {'Sim' if realizar_mooney else 'Não'}")
    if realizar_mooney:
        print(f"  Comprimento Comum (Mooney): {_L_cap_mm_mooney_comum_val_resumo} mm")
        if capilares_mooney_data_input:
            print("  Dados dos Testes para Mooney:")
            for i, cap_data in enumerate(capilares_mooney_data_input):
                print(f"    Capilar Mooney {i+1} (D = {cap_data['D_mm']:.3f} mm):")
                pressoes_bar_cap = cap_data['pressoes_Pa'] / 1e5
                massas_g_cap = cap_data['massas_kg'] * 1000
                for j in range(len(pressoes_bar_cap)):
                    print(f"      - Teste {j+1}: {pressoes_bar_cap[j]:.2f} bar | {massas_g_cap[j]:.2f} g")
    if not realizar_bagley and not realizar_mooney:
        print("\nAnálise com Capilar Único:")
        print(f"  Diâmetro do Capilar: {_D_cap_mm_unico_val_resumo} mm")
        print(f"  Comprimento do Capilar: {_L_cap_mm_unico_val_resumo} mm")
        num_testes_exibir = 0
        if metodo_entrada == '1': num_testes_exibir = num_testes_unico_manual
        elif metodo_entrada == '2': num_testes_exibir = num_testes_para_analise
        if num_testes_exibir > 0: print(f"  Número de Testes (P,m): {num_testes_exibir}")
        if pressoes_bar_display_tab and massas_g_display_tab and len(pressoes_bar_display_tab) == len(massas_g_display_tab) and len(pressoes_bar_display_tab) > 0:
            print("  Dados dos Testes (Pressão [bar] | Massa [g]):")
            for i in range(len(pressoes_bar_display_tab)):
                p_val, m_val = pressoes_bar_display_tab[i], massas_g_display_tab[i]
                p_d = f"{p_val:.2f}" if isinstance(p_val,(int,float)) else str(p_val)
                m_d = f"{m_val:.2f}" if isinstance(m_val,(int,float)) else str(m_val)
                print(f"    - Teste {i+1}: {p_d} bar | {m_d} g")
    print("="* (50 + len(" RESUMO DOS DADOS INSERIDOS PARA CONFIRMAÇÃO ")))
    if input_sim_nao("\nDados corretos para prosseguir? (s/n): "): dados_confirmados = True
    else: print("\n--- ENTRADA DE DADOS REINICIADA. ---")

# --- PREPARAÇÃO FINAL E CÁLCULOS (APÓS CONFIRMAÇÃO) ---
if not realizar_bagley and not realizar_mooney: 
    p_Pa = np.array(pressoes_bar_display_tab)*1e5; m_kg = np.array(massas_g_display_tab)/1000
    t_s = np.full(num_testes_para_analise, tempo_extrusao_fixo_s_val)
    R_cap_si, L_cap_m = (D_cap_mm_unico_val/2000), L_cap_mm_unico_val/1000
    vol_m3 = m_kg/rho_pasta_si; Q_m3_s = vol_m3/t_s
    if L_cap_m > 0 and R_cap_si > 0:
        tau_w_an = p_Pa * R_cap_si / (2 * L_cap_m)
        gamma_dot_aw_an = (4*Q_m3_s) / (np.pi * R_cap_si**3) if R_cap_si > 0 else np.zeros_like(Q_m3_s)
    else:
        tau_w_an = np.full_like(p_Pa, np.nan); gamma_dot_aw_an = np.full_like(p_Pa, np.nan)
        print("ALERTA: Dimensões capilar único inválidas.")

tau_w_for_mooney = np.array([]) 
if realizar_bagley and capilares_bagley_data_input:
    gamma_dot_aw_bagley_targets, tau_w_bagley_corrected = perform_bagley_correction(
        capilares_bagley_data_input, D_cap_mm_bagley_comum_val, 
        rho_pasta_si, tempo_extrusao_fixo_s_val, output_folder, timestamp_str)
    if len(tau_w_bagley_corrected) > 0:
        tau_w_an, gamma_dot_aw_an = tau_w_bagley_corrected, gamma_dot_aw_bagley_targets
        num_testes_para_analise = len(tau_w_an)
        tau_w_for_mooney = tau_w_an 
        pressoes_bar_display_tab = [np.nan]*num_testes_para_analise 
        massas_g_display_tab = [np.nan]*num_testes_para_analise
    else: print("ALERTA: Bagley não resultou em pontos válidos."); realizar_bagley = False
if realizar_mooney and capilares_mooney_data_input:
    gamma_dot_aw_slip_corrected, tau_w_mooney_corrected = perform_mooney_correction(
        capilares_mooney_data_input, L_cap_mm_mooney_comum_val, rho_pasta_si, 
        tempo_extrusao_fixo_s_val, tau_w_for_mooney, output_folder, timestamp_str)
    if len(tau_w_mooney_corrected) > 0 and len(gamma_dot_aw_slip_corrected) > 0 : 
        tau_w_an, gamma_dot_aw_an = tau_w_mooney_corrected, gamma_dot_aw_slip_corrected
        num_testes_para_analise = len(tau_w_an)
        pressoes_bar_display_tab = [np.nan]*num_testes_para_analise
        massas_g_display_tab = [np.nan]*num_testes_para_analise
    else: 
        print("ALERTA: Mooney não resultou em pontos válidos.")
        if not (realizar_bagley and len(tau_w_for_mooney) > 0) : realizar_mooney = False
        elif realizar_bagley and len(tau_w_for_mooney) > 0:
            print("  INFO: Mooney falhou. Usando dados de Bagley (se houver)."); realizar_mooney = False

D_cap_mm_display, L_cap_mm_display = "N/A", "N/A"
if realizar_bagley: D_cap_mm_display, L_cap_mm_display = f"Bagley (D={D_cap_mm_bagley_comum_val:.3f}mm)", "Bagley (Vários L)"
elif realizar_mooney: D_cap_mm_display, L_cap_mm_display = "Mooney (Vários D)", f"Mooney (L={L_cap_mm_mooney_comum_val:.2f}mm)"
elif not realizar_bagley and not realizar_mooney: D_cap_mm_display,L_cap_mm_display = f"{D_cap_mm_unico_val:.3f}",f"{L_cap_mm_unico_val:.2f}"

comportamento_fluido_final_para_relatorio = "Não foi possível determinar (nenhum modelo selecionado/ajustado)." 

if num_testes_para_analise > 0 and isinstance(tau_w_an, np.ndarray) and isinstance(gamma_dot_aw_an, np.ndarray) and len(tau_w_an) > 0 and len(gamma_dot_aw_an) > 0:
    eta_a_an = np.full_like(gamma_dot_aw_an, np.nan)
    valid_an_idx = (gamma_dot_aw_an != 0) & (~np.isnan(gamma_dot_aw_an)) & (~np.isnan(tau_w_an))
    if np.any(valid_an_idx): eta_a_an[valid_an_idx] = tau_w_an[valid_an_idx] / gamma_dot_aw_an[valid_an_idx]
    if num_testes_para_analise > 1: 
        idx_sort = np.argsort(gamma_dot_aw_an) 
        gamma_dot_aw_an, tau_w_an = gamma_dot_aw_an[idx_sort], tau_w_an[idx_sort]
        if len(eta_a_an) == len(idx_sort): eta_a_an = eta_a_an[idx_sort]
        if not realizar_bagley and not realizar_mooney and metodo_entrada == "1":
            if len(pressoes_bar_display_tab)==len(idx_sort): pressoes_bar_display_tab = [pressoes_bar_display_tab[i] for i in idx_sort]
            if len(massas_g_display_tab)==len(idx_sort): massas_g_display_tab = [massas_g_display_tab[i] for i in idx_sort]
    
    gamma_dot_w_an_wr = np.zeros_like(gamma_dot_aw_an) 
    n_prime, log_K_prime, K_prime = 1.0, 0.0, 1.0
    if num_testes_para_analise == 1 and (gamma_dot_aw_an[0] == 0 or np.isnan(gamma_dot_aw_an[0])): print("\nALERTA: 1 ponto s/ fluxo/NaN. n'=1.")
    elif num_testes_para_analise == 1 and gamma_dot_aw_an[0] > 0: print("\nALERTA: 1 ponto c/ fluxo. n'=1.")
    elif num_testes_para_analise > 1:
        valid_log = (tau_w_an > 0) & (gamma_dot_aw_an > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_aw_an))
        if np.sum(valid_log) < 2: print("ALERTA: <2 pontos válidos p/ n'. n'=1.")
        else:
            log_t, log_g_aw = np.log(tau_w_an[valid_log]), np.log(gamma_dot_aw_an[valid_log])
            try:
                coeffs, _, _, _, _ = np.polyfit(log_g_aw, log_t, 1, full=True) 
                n_prime, log_K_prime = coeffs[0], coeffs[1] 
                K_prime = np.exp(log_K_prime)
                print(f"\nn' global: {n_prime:.4f}, K' global: {K_prime:.4f}")
                if n_prime <= 0: print("ALERTA: n' <= 0. Usando n'=1."); n_prime = 1.0
            except Exception as e: print(f"ERRO cálculo n': {e}. n'=1."); n_prime = 1.0
    n_corr = n_prime if (n_prime != 0 and not np.isnan(n_prime)) else 1.0
    gamma_dot_w_an_wr = ((3*n_corr + 1)/(4*n_corr)) * gamma_dot_aw_an
    eta_true_an = np.full_like(gamma_dot_w_an_wr, np.nan)
    valid_gw = (gamma_dot_w_an_wr > 0) & (~np.isnan(gamma_dot_w_an_wr))
    if np.any(valid_gw): eta_true_an[valid_gw] = tau_w_an[valid_gw] / gamma_dot_w_an_wr[valid_gw]

    print("\n--- Ajustando Modelos Reológicos ---")
    def model_newtonian(gd,eta): return eta*gd
    def model_power_law(gd,K_pl,n_pl): return K_pl*np.power(np.maximum(gd, 1e-9),n_pl)
    def model_bingham(gd,t0,ep): return t0+ep*gd
    def model_hb(gd,t0,K_hb,n_hb): return t0+K_hb*np.power(np.maximum(gd, 1e-9),n_hb)
    models = {"Newtoniano":model_newtonian, "Lei da Potência":model_power_law, "Bingham":model_bingham, "Herschel-Bulkley":model_hb}
    model_results = {}
    valid_fit = (tau_w_an > 0) & (gamma_dot_w_an_wr > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_w_an_wr))
    gd_fit, tau_fit = np.array([]), np.array([])
    if np.sum(valid_fit)<1: print("ERRO: Sem pontos para ajuste de modelos.")
    else:
        gd_fit,tau_fit = gamma_dot_w_an_wr[valid_fit],tau_w_an[valid_fit]
        for name,func in models.items():
            print(f"\nAjustando: {name}")
            n_p = func.__code__.co_argcount-1
            if len(gd_fit)<n_p: print(f"  Dados insuficientes para {name}."); continue
            p0,bnds = None,(-np.inf, np.inf)
            n_g = n_prime if (n_prime > 0 and not np.isnan(n_prime)) else 0.5
            K_g = K_prime if (K_prime > 1e-9 and not np.isnan(K_prime)) else 1.0
            if name=="Newtoniano": bnds=(0,np.inf)
            elif name=="Lei da Potência": p0,bnds = [K_g,n_g],([1e-9,1e-9],[np.inf,np.inf])
            elif name=="Bingham": p0,bnds = [0.1,0.1],([0,1e-9],[np.inf,np.inf])
            elif name=="Herschel-Bulkley": p0,bnds = [0.1,K_g,n_g],([0,1e-9,1e-9],[np.inf,np.inf,np.inf])
            try: 
                params_fit,cov = curve_fit(func,gd_fit,tau_fit,p0=p0,bounds=bnds,maxfev=10000,method='trf')
                tau_pred = func(gd_fit,*params_fit)
                ss_r,ss_t = np.sum((tau_fit-tau_pred)**2),np.sum((tau_fit-np.mean(tau_fit))**2)
                r2 = 1-(ss_r/ss_t) if ss_t > 1e-9 else (1.0 if ss_r < 1e-9 else 0.0)
                model_results[name] = {'params':params_fit,'R2':r2,'covariance':cov}
                p_names_fit = list(func.__code__.co_varnames[1:n_p+1])
                params_str = [format_float_for_table(val,5) for val in params_fit]
                print(f"  Params ({', '.join(p_names_fit)}): {', '.join(params_str)}, R²: {r2:.5f}")
            except Exception as e: print(f"  Falha no ajuste de {name}: {e}")
    best_model_nome,best_r2 = "",-np.inf
    if model_results:
        for name,data in model_results.items():
            if data['R2']>best_r2: best_r2,best_model_nome = data['R2'],name
        # Não imprimir aqui, pois o df_summary fará isso de forma mais completa
        # if best_model_nome: print(f"\n--- Melhor Modelo: {best_model_nome} (R² = {best_r2:.5f}) ---")
        # else: print("\n--- Nenhum modelo selecionado. ---")
    else: print("\n--- Nenhum modelo ajustado. ---")

    # Movido para o final da seção de tabelas/resumos
    # print("\n\n"+"="*70+"\n--- TABELAS DE RESULTADOS --- \n"+"="*70)
    
    df_summary = None 
    comportamento_fluido_final_para_relatorio = "Não foi possível determinar (nenhum modelo selecionado/ajustado)." 

    if best_model_nome and best_model_nome in model_results:
        print("\n\n--- Resumo do Melhor Modelo Ajustado ---")
        model_data = model_results[best_model_nome]
        params,r2_val = model_data['params'],model_data['R2'] # r2_val é o R2 do melhor modelo
        p_names = []
        if best_model_nome=="Newtoniano": p_names=["Viscosidade Newtoniana (Pa·s)"]
        elif best_model_nome=="Lei da Potência": p_names=["K (Pa·sⁿ)","n (-)"]
        elif best_model_nome=="Bingham": p_names=["τ₀ (Pa)","ηₚ (Pa·s)"]
        elif best_model_nome=="Herschel-Bulkley": p_names=["τ₀ (Pa)","K (Pa·sⁿ)","n (-)"]
        else: p_names=[f"P{j+1}" for j in range(len(params))]
        
        n_behavior_param = np.nan 
        if best_model_nome == "Lei da Potência" or best_model_nome == "Herschel-Bulkley":
            try:
                n_index = p_names.index("n (-)")
                n_behavior_param = params[n_index]
            except ValueError: 
                print("ALERTA: Parâmetro 'n (-)' não encontrado para classificação do comportamento.")

        comportamento_fluido_str = "N/A"
        if best_model_nome == "Newtoniano":
            comportamento_fluido_str = "Newtoniano (n = 1 por definição)"
        elif best_model_nome == "Bingham":
            comportamento_fluido_str = "Plástico de Bingham (Newtoniano após escoamento)"
        elif not np.isnan(n_behavior_param):
            if np.isclose(n_behavior_param, 1.0):
                comportamento_fluido_str = f"Newtoniano (n ≈ {n_behavior_param:.3f})"
            elif n_behavior_param < 1.0:
                comportamento_fluido_str = f"Pseudoplástico (n = {n_behavior_param:.3f} < 1)"
            elif n_behavior_param > 1.0:
                comportamento_fluido_str = f"Dilatante (n = {n_behavior_param:.3f} > 1)"
            else:
                comportamento_fluido_str = "Índice 'n' com valor inválido para classificação."
        else:
            comportamento_fluido_str = "Comportamento não classificável com 'n' para este modelo."
        
        comportamento_fluido_final_para_relatorio = comportamento_fluido_str

        summary_dict = {"Parâmetro":[],"Valor Estimado":[],"Erro Padrão (+/-)":[]}
        
        summary_dict["Parâmetro"].append("Modelo Reológico Ajustado")
        summary_dict["Valor Estimado"].append(best_model_nome)
        summary_dict["Erro Padrão (+/-)"].append("N/A")
        
        summary_dict["Parâmetro"].append("Coeficiente de Determinação (R²)")
        summary_dict["Valor Estimado"].append(format_float_for_table(r2_val, 5)) # Usa r2_val aqui
        summary_dict["Erro Padrão (+/-)"].append("N/A")

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
        
        if comportamento_fluido_str != "N/A":
            summary_dict["Parâmetro"].append("Comportamento do Fluido")
            summary_dict["Valor Estimado"].append(comportamento_fluido_str)
            summary_dict["Erro Padrão (+/-)"].append("N/A")

        df_summary = pd.DataFrame(summary_dict) 
        print(df_summary.to_string(index=False, line_width=None)) 
        
        csv_sum_f = os.path.join(output_folder, f"{timestamp_str}_resumo_melhor_modelo.csv")
        arquivos_gerados_lista.append(os.path.basename(csv_sum_f))
        try: 
            if df_summary is not None and not df_summary.empty:
                df_summary.to_csv(csv_sum_f,index=False,sep=';',decimal=',', encoding='utf-8-sig') 
                print(f"\nResumo salvo: {csv_sum_f}")
            else:
                print("\nNenhum resumo do modelo para salvar em CSV.")
        except Exception as e: print(f"\nERRO CSV Resumo: {e}")
    
    print("\n\n"+"="*70+"\n--- TABELAS DE RESULTADOS --- \n"+"="*70) # Movido para depois do resumo do modelo
    q_calc_mm3_s = np.full_like(gamma_dot_aw_an, np.nan)
    if not realizar_bagley and not realizar_mooney and D_cap_mm_unico_val > 0: 
        R_eff_q = D_cap_mm_unico_val/2000.0
        q_calc_mm3_s = (gamma_dot_aw_an * np.pi * R_eff_q**3 / 4) * 1e9
    elif realizar_bagley and D_cap_mm_bagley_comum_val > 0 : 
        R_eff_q = D_cap_mm_bagley_comum_val/2000.0
        q_calc_mm3_s = (gamma_dot_aw_an * np.pi * R_eff_q**3 / 4) * 1e9 
    
    d_col,l_col = [D_cap_mm_display]*num_testes_para_analise, [L_cap_mm_display]*num_testes_para_analise
    rho_col,t_col = np.full(num_testes_para_analise,rho_pasta_g_cm3_fixo), np.full(num_testes_para_analise,tempo_extrusao_fixo_s_val)
    
    df_res = pd.DataFrame({
        "Ponto": list(range(1,num_testes_para_analise+1)), "D_cap(mm)": d_col, "L_cap(mm)": l_col,
        "rho(g/cm³)": rho_col, "t_ext(s)": t_col, "P_ext(bar)": pressoes_bar_display_tab, 
        "M_ext(g)": massas_g_display_tab, "Q_calc(mm³/s)": q_calc_mm3_s, "τw (Pa)": tau_w_an, 
        "γ̇aw (s⁻¹)": gamma_dot_aw_an, "ηa (Pa·s)": eta_a_an, 
        "γ̇w (s⁻¹)": gamma_dot_w_an_wr, "η (Pa·s)": eta_true_an })
    pd.set_option('display.max_columns',None); pd.set_option('display.width',200)
    print("\n--- Tabela de Dados Processados ---")
    fmt = {col: (lambda x,dp=(2 if any(s in col for s in ["mm³/s","s⁻¹","Pa)"]) else 3 if any(s in col for s in ["bar","(s)","(mm)","(g/cm³)","(g)"]) else 4): format_float_for_table(x,dp)) \
           if df_res[col].dtype=='float64' or isinstance(df_res[col].dtype,np.floating) or col in ["P_ext(bar)","M_ext(g)"] else str for col in df_res.columns}
    print(df_res.to_string(index=False, formatters=fmt, na_rep='N/A_Corr', line_width=None)) 
    csv_f = os.path.join(output_folder, f"{timestamp_str}_resultados_reologicos.csv")
    arquivos_gerados_lista.append(os.path.basename(csv_f))
    try: df_res.to_csv(csv_f,index=False,sep=';',decimal=',',float_format='%.4f',na_rep='N/A_Corr', encoding='utf-8-sig'); print(f"\nTabela salva: {csv_f}")
    except Exception as e: print(f"\nERRO CSV: {e}")

    if realizar_bagley and capilares_bagley_data_input:
        print("\n--- CSV Dados Brutos Bagley ---"); lista_dbb = []
        # ... (código para CSV de Bagley Bruto - sem alterações aqui) ...
        for i,cap_dr in enumerate(capilares_bagley_data_input):
            n_pts, P_bar, M_g = len(cap_dr['pressoes_Pa']), cap_dr['pressoes_Pa']/1e5, cap_dr['massas_kg']*1000
            v_m3 = cap_dr['massas_kg']/rho_pasta_si
            R_m_b = cap_dr.get('D_mm',D_cap_mm_bagley_comum_val)/2000.0
            Q_m3s = v_m3/cap_dr['tempos_s']
            g_aw_b = (4*Q_m3s)/(np.pi*R_m_b**3) if R_m_b>0 else np.zeros_like(v_m3)
            tau_raw_b, eta_raw_b = np.full(n_pts,np.nan), np.full(n_pts,np.nan)
            for j in range(n_pts):
                if cap_dr['L_m']>0 and R_m_b>0: tau_raw_b[j] = (cap_dr['pressoes_Pa'][j]*R_m_b)/(2*cap_dr['L_m'])
                if g_aw_b[j]!=0 and not np.isnan(tau_raw_b[j]): eta_raw_b[j] = tau_raw_b[j]/g_aw_b[j]
                lista_dbb.append({"ID_Cap_B":i+1,"D_Comum_B(mm)":cap_dr.get('D_mm',D_cap_mm_bagley_comum_val),"L_Cap_B(mm)":cap_dr['L_mm'],
                                  "rho(g/cm3)":rho_pasta_g_cm3_fixo,"t_ext(s)":cap_dr['tempos_s'][j],"Ponto":j+1,
                                  "P_med(bar)":P_bar[j],"M_med(g)":M_g[j],"V_calc(mm3)":v_m3[j]*1e9,"Q_calc(mm3/s)":Q_m3s[j]*1e9,
                                  "DeltaP(Pa)":cap_dr['pressoes_Pa'][j],"g_aw_bruta(s-1)":g_aw_b[j], 
                                  "tau_w_raw(Pa)":tau_raw_b[j],"eta_a_raw(Pa.s)":eta_raw_b[j]})
        if lista_dbb:
            df_b_b = pd.DataFrame(lista_dbb); csv_b_b = os.path.join(output_folder,f"{timestamp_str}_dados_brutos_bagley.csv")
            arquivos_gerados_lista.append(os.path.basename(csv_b_b))
            try: df_b_b.to_csv(csv_b_b,index=False,sep=';',decimal=',',float_format='%.5f', encoding='utf-8-sig'); print(f"Dados brutos Bagley: {csv_b_b}")
            except Exception as e: print(f"ERRO CSV Bagley: {e}")
        else: print("Nenhum dado bruto Bagley para salvar.")
    if realizar_mooney and capilares_mooney_data_input:
        print("\n--- CSV Dados Brutos Mooney ---"); lista_dbm = []
        # ... (código para CSV de Mooney Bruto - sem alterações aqui) ...
        for i,cap_dr in enumerate(capilares_mooney_data_input):
            n_pts,P_bar,M_g = len(cap_dr['pressoes_Pa']),cap_dr['pressoes_Pa']/1e5,cap_dr['massas_kg']*1000
            v_m3 = cap_dr['massas_kg']/rho_pasta_si
            R_m_m,L_m_m = cap_dr['D_mm']/2000.0,cap_dr['L_m']
            Q_m3s=v_m3/cap_dr['tempos_s']
            g_aw_m = (4*Q_m3s)/(np.pi*R_m_m**3) if R_m_m>0 else np.zeros_like(v_m3)
            tau_raw_m = (cap_dr['pressoes_Pa']*R_m_m)/(2*L_m_m) if L_m_m>0 and R_m_m>0 else np.full(n_pts,np.nan)
            for j in range(n_pts):
                eta_raw_m = tau_raw_m[j]/g_aw_m[j] if g_aw_m[j]!=0 and not np.isnan(g_aw_m[j]) and not np.isnan(tau_raw_m[j]) else np.nan
                lista_dbm.append({"ID_Cap_M":i+1,"L_Comum_M(mm)":cap_dr['L_mm'],"D_Cap_M(mm)":cap_dr['D_mm'],
                                  "rho(g/cm3)":rho_pasta_g_cm3_fixo,"t_ext(s)":cap_dr['tempos_s'][j],"Ponto":j+1,
                                  "P_med(bar)":P_bar[j],"M_med(g)":M_g[j],"V_calc(mm3)":v_m3[j]*1e9,"Q_calc(mm3/s)":Q_m3s[j]*1e9,
                                  "DeltaP(Pa)":cap_dr['pressoes_Pa'][j],"g_aw_bruta(s-1)":g_aw_m[j],
                                  "tau_w_raw(Pa)":tau_raw_m[j],"eta_a_raw(Pa.s)":eta_raw_m})
        if lista_dbm:
            df_m_b = pd.DataFrame(lista_dbm); csv_m_b = os.path.join(output_folder,f"{timestamp_str}_dados_brutos_mooney.csv")
            arquivos_gerados_lista.append(os.path.basename(csv_m_b))
            try: df_m_b.to_csv(csv_m_b,index=False,sep=';',decimal=',',float_format='%.5f', encoding='utf-8-sig'); print(f"Dados brutos Mooney: {csv_m_b}")
            except Exception as e: print(f"ERRO CSV Mooney: {e}")
        else: print("Nenhum dado bruto Mooney para salvar.")

   # --- GERANDO GRÁFICOS ---
    if num_testes_para_analise > 0 and len(gd_fit)>0 and model_results: 
        print("\n\n"+"="*70+"\n--- GERANDO GRÁFICOS ---\n"+"="*70)
        min_gp = (np.min(gd_fit[gd_fit>0])*0.5 if len(gd_fit[gd_fit>0])>0 else 1e-3)
        max_gp = (np.max(gd_fit)*1.5 if len(gd_fit[gd_fit>0])>0 else 1.0)
        min_gp = max(min_gp,1e-9); max_gp = max(max_gp, min_gp*100+1)
        try: gd_plot = np.geomspace(min_gp,max_gp,200) if max_gp>min_gp else np.array([min_gp,min_gp*10])
        except: gd_plot = np.linspace(min_gp,max_gp,200) if max_gp>min_gp else np.array([min_gp,min_gp*10])
        gd_plot = gd_plot[gd_plot>1e-9]; gd_plot = np.array([0.001,0.01]) if len(gd_plot)<2 else gd_plot
        
        # Gráfico 1: Curva de Fluxo
        fig1,ax1=plt.subplots(figsize=(10,7))
        ax1.scatter(gamma_dot_w_an_wr[valid_fit],tau_w_an[valid_fit],label='Dados Experimentais Processados',c='k',marker='o',s=60,zorder=10)
        if len(gd_plot)>0:
            for n_model_name,d_model_data in model_results.items(): 
                try: ax1.plot(gd_plot,models[n_model_name](gd_plot,*d_model_data['params']),label=fr'Modelo {n_model_name} (R²={d_model_data["R2"]:.4f})',lw=2.5,alpha=0.8)
                except: pass 
        ax1.set_xlabel("Taxa de Cisalhamento Corrigida (" + r"$\dot{\gamma}_w$" + ", s⁻¹)")
        ax1.set_ylabel("Tensão de Cisalhamento na Parede Corrigida (" + r"$\tau_w$" + ", Pa)")
        ax1.set_title("Curva de Fluxo: Tensão de Cisalhamento vs. Taxa de Cisalhamento")
        ax1.legend(); ax1.grid(True,which="both",ls="--"); ax1.set_xscale('log'); ax1.set_yscale('log'); fig1.tight_layout()
        f1_name = os.path.join(output_folder,f"{timestamp_str}_curva_fluxo.png"); arquivos_gerados_lista.append(os.path.basename(f1_name))
        try: fig1.savefig(f1_name,dpi=300); print(f"Gráfico Curva Fluxo: {f1_name}")
        except Exception as e: print(f"ERRO Salvar Curva Fluxo: {e}")
        # plt.close(fig1) # Fecha a figura para liberar memória

        # Gráfico 2: Determinação de n'
        if num_testes_para_analise > 1 and 'n_prime' in locals() and not np.isnan(n_prime) and n_prime != 1.0 and 'log_K_prime' in locals() and not np.isnan(log_K_prime):
            valid_log_np = (tau_w_an > 0) & (gamma_dot_aw_an > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_aw_an))
            if np.sum(valid_log_np) > 1:
                log_t_p,log_g_aw_p = np.log(tau_w_an[valid_log_np]),np.log(gamma_dot_aw_an[valid_log_np])
                fig2,ax2=plt.subplots(figsize=(10,7))
                ax2.scatter(log_g_aw_p,log_t_p,label='Dados Experimentais ln(γ̇aw,s) vs ln(τw)',c='r',marker='x',s=60)
                if len(log_g_aw_p)>1: 
                    min_lg,max_lg = np.min(log_g_aw_p),np.max(log_g_aw_p)
                    if max_lg>min_lg: log_g_line = np.linspace(min_lg,max_lg,50); ax2.plot(log_g_line,n_prime*log_g_line+log_K_prime,'--',c='b',lw=2,label=fr'Ajuste Linear (n\'={n_prime:.3f})')
                ax2.set_xlabel("ln(Taxa de Cis. Apar. na Parede, Pós-Mooney) (ln(γ̇aw,s))")
                ax2.set_ylabel("ln(Tensão de Cis. na Parede, Pós-Bagley) (ln(τw))")
                ax2.set_title("Determinação de n' (Índice da Lei de Potência Aparente)")
                ax2.legend(); ax2.grid(True,which="both",ls="--"); fig2.tight_layout()
                f2_name = os.path.join(output_folder,f"{timestamp_str}_n_prime.png"); arquivos_gerados_lista.append(os.path.basename(f2_name))
                try: fig2.savefig(f2_name,dpi=300); print(f"Gráfico n': {f2_name}")
                except Exception as e: print(f"ERRO Salvar n': {e}")
                # plt.close(fig2) # Fecha a figura
        
        # Gráfico 3: Curva de Viscosidade Real
        fig3,ax3=plt.subplots(figsize=(10,7))
        valid_eta = ~np.isnan(eta_true_an) & (gamma_dot_w_an_wr > 0) & (eta_true_an > 0) & (~np.isinf(eta_true_an))
        if np.any(valid_eta): ax3.scatter(gamma_dot_w_an_wr[valid_eta],eta_true_an[valid_eta],label='Viscosidade Real Experimental (η)',c='g',marker='s',s=60,zorder=10)
        if len(gd_plot)>0:
            for n_model_name,d_model_data in model_results.items(): 
                try:
                    tau_m = models[n_model_name](gd_plot,*d_model_data['params']); eta_m = tau_m/gd_plot if np.all(gd_plot != 0) else np.full_like(gd_plot, np.nan)
                    if n_model_name=="Newtoniano": eta_m = np.full_like(gd_plot,d_model_data['params'][0])
                    valid_plot_model = ~np.isnan(eta_m) & ~np.isinf(eta_m) & (eta_m > 0)
                    if np.any(valid_plot_model):
                         ax3.plot(gd_plot[valid_plot_model],eta_m[valid_plot_model],label=fr'Modelo {n_model_name} ($\eta$)',lw=2.5,alpha=0.8)
                except: pass
        ax3.set_xlabel("Taxa de Cisalhamento Corrigida (γ̇w, s⁻¹)")
        ax3.set_ylabel("Viscosidade Real (η, Pa·s)")
        ax3.set_title("Viscosidade Real (η) vs. Taxa de Cisalhamento Corrigida (γ̇w)")
        ax3.legend(); ax3.grid(True,which="both",ls="--"); ax3.set_xscale('log'); ax3.set_yscale('log'); fig3.tight_layout()
        f3_name = os.path.join(output_folder,f"{timestamp_str}_curva_viscosidade.png"); arquivos_gerados_lista.append(os.path.basename(f3_name))
        try: fig3.savefig(f3_name,dpi=300); print(f"Gráfico Viscosidade: {f3_name}")
        except Exception as e: print(f"ERRO Salvar Viscosidade: {e}")
        # plt.close(fig3) # Fecha a figura

       # Gráfico 4: Pressão vs Viscosidade (Condicional)
        if not realizar_bagley and not realizar_mooney and num_testes_para_analise > 0:
            if len(pressoes_bar_display_tab) == len(eta_true_an) and isinstance(pressoes_bar_display_tab, list) and any(isinstance(x, (int, float)) for x in pressoes_bar_display_tab if x is not None and not np.isnan(x)):
                pressoes_bar_np = np.array(pressoes_bar_display_tab, dtype=float) 
                valid_pv = (~np.isnan(eta_true_an))&(~np.isnan(pressoes_bar_np))&(eta_true_an > 0)&(pressoes_bar_np > 0)
                if np.any(valid_pv):
                    P_Pa_plot, eta_plot = pressoes_bar_np[valid_pv]*1e5, eta_true_an[valid_pv]
                    fig4,ax4=plt.subplots(figsize=(10,7))
                    # MODIFICADO de scatter para plot:
                    ax4.plot(P_Pa_plot,eta_plot,label='Viscosidade Real vs Pressão',
                             color='purple',marker='D', linestyle='-', linewidth=1.5, markersize=7) 
                    ax4.set_xlabel("Pressao Total Aplicada (ΔPtotal, Pa)")
                    ax4.set_ylabel("Viscosidade Real (ηtrue, Pa.s)")
                    ax4.set_title("Pressao Aplicada vs. Viscosidade Real (Capilar Unico s/ Correcoes)")
                    ax4.legend(); ax4.grid(True,which="both",ls="--"); ax4.set_xscale('linear'); ax4.set_yscale('linear'); fig4.tight_layout()
                    f4_name = os.path.join(output_folder,f"{timestamp_str}_pressao_vs_viscosidade.png"); arquivos_gerados_lista.append(os.path.basename(f4_name))
                    try: fig4.savefig(f4_name,dpi=300); print(f"Gráfico P vs Visc: {f4_name}")
                    except Exception as e: print(f"ERRO Salvar P vs Visc: {e}")
                    # plt.close(fig4) # Comente ou remova para exibir interativamente
        elif realizar_bagley or realizar_mooney: print("  Info: Gráfico P vs Visc (original) não gerado (Correções aplicadas).")
        
        # Gráfico 5: Comparativo Viscosidade Aparente vs Real
        fig5, ax5 = plt.subplots(figsize=(10, 7))
        
        # Pontos e Linha para Viscosidade Aparente
        valid_apparent_idx = (gamma_dot_aw_an > 0) & (~np.isnan(eta_a_an)) & (eta_a_an > 0) & (~np.isinf(eta_a_an))
        if np.any(valid_apparent_idx):
            ax5.plot(gamma_dot_aw_an[valid_apparent_idx], eta_a_an[valid_apparent_idx], 
                        label=r'Viscosidade Aparente ($\eta_a$ vs $\dot{\gamma}_{aw}$)', 
                        marker='o', linestyle='--', color='blue', alpha=0.7, linewidth=1.5) # MODIFICADO para plot com linha tracejada

        # Pontos e Linha para Viscosidade Real
        # valid_eta foi definido para fig3: ~np.isnan(eta_true_an) & (gamma_dot_w_an_wr > 0) & (eta_true_an > 0) & (~np.isinf(eta_true_an))
        if np.any(valid_eta): # valid_eta já foi definido para fig3 e pode ser usado aqui
             ax5.plot(gamma_dot_w_an_wr[valid_eta],eta_true_an[valid_eta],
                         label=r'Viscosidade Real ($\eta$ vs $\dot{\gamma}_w$)', 
                         marker='s', linestyle='-', color='green', alpha=0.7, linewidth=1.5, zorder=5) # MODIFICADO para plot com linha sólida

        ax5.set_xlabel("Taxa de Cisalhamento (s⁻¹)") 
        ax5.set_ylabel("Viscosidade (Pa·s)")
        ax5.set_title("Comparativo: Viscosidade Aparente vs. Viscosidade Real")
        ax5.legend(); ax5.grid(True,which="both",ls="--"); ax5.set_xscale('log'); ax5.set_yscale('log'); fig5.tight_layout()
        f5_name = os.path.join(output_folder,f"{timestamp_str}_comparativo_viscosidades.png"); arquivos_gerados_lista.append(os.path.basename(f5_name))
        try: fig5.savefig(f5_name,dpi=300); print(f"Gráfico Comparativo Viscosidades: {f5_name}")
        except Exception as e: print(f"ERRO Salvar Comparativo Viscosidades: {e}")
        # plt.close(fig5) # Mantenha comentado ou remova se quiser que a janela apareça com plt.show()

        print("\nFeche as janelas dos gráficos para finalizar."); plt.show()
    else: 
        print("\n--- Gráficos não gerados (sem dados válidos ou modelos ajustados para plotagem). ---")

d_unico_rel = D_cap_mm_unico_val if not realizar_bagley and not realizar_mooney else "N/A"
l_unico_rel = L_cap_mm_unico_val if not realizar_bagley and not realizar_mooney else "N/A"
df_sum_rel = df_summary if 'df_summary' in locals() and df_summary is not None and not df_summary.empty and 'best_model_nome' in locals() and best_model_nome else pd.DataFrame() 
r2_rel = best_r2 if 'best_r2' in locals() and 'best_model_nome' in locals() and best_model_nome else np.nan
bm_rel = best_model_nome if 'best_model_nome' in locals() else ""
D_bag_rep = D_cap_mm_bagley_comum_val if realizar_bagley else "N/A"
L_moo_rep = L_cap_mm_mooney_comum_val if realizar_mooney else "N/A"
df_res_rep = df_res if 'df_res' in locals() and df_res is not None else pd.DataFrame()

gerar_relatorio_texto(timestamp_str, rho_pasta_g_cm3_fixo, tempo_extrusao_fixo_s_val,
                      realizar_bagley, D_bag_rep, bagley_capilares_L_mm_info,
                      realizar_mooney, L_moo_rep, mooney_capilares_D_mm_info,
                      d_unico_rel, l_unico_rel, df_res_rep,  
                      df_sum_rel, bm_rel, r2_rel, 
                      comportamento_fluido_final_para_relatorio, 
                      arquivos_gerados_lista, output_folder)
print("\n"+"="*70+"\n--- FIM DA ANÁLISE ---\n"+"="*70)
