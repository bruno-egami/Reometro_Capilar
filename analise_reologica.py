# -----------------------------------------------------------------------------
# SCRIPT PARA ANÁLISE REOLÓGICA DE PASTAS EM REÔMETRO CAPILAR
# (Versão com Timestamp no início dos nomes de arquivos, tabelas apenas em CSV/Console)
# -----------------------------------------------------------------------------

# 1. Importação de Bibliotecas
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

# -----------------------------------------------------------------------------
# --- FUNÇÕES AUXILIARES ---
# -----------------------------------------------------------------------------
def input_sim_nao(mensagem_prompt):
    while True:
        resposta = input(mensagem_prompt).strip().lower()
        if resposta in ['s', 'sim']: return True
        elif resposta in ['n', 'nao', 'não']: return False
        else: print("Resposta inválida. Por favor, digite 's' ou 'n'.")

def input_float_com_virgula(mensagem_prompt):
    while True:
        try:
            return float(input(mensagem_prompt).replace(',', '.'))
        except ValueError: print("ERRO: Entrada inválida. Insira um número (use '.' ou ',' decimal).")

def format_float_for_table(value, decimal_places=4):
    if isinstance(value, (float, np.floating)):
        if np.isnan(value): return "NaN"
        # Para números muito pequenos onde .4f resultaria em 0.0000, mas não são zero,
        # usar formatação 'g' pode ser melhor para manter algarismos significativos.
        # No entanto, para consistência e evitar 'e', mantemos 'f'.
        if abs(value) < 10**(-decimal_places) and value != 0:
             # Para números muito pequenos, f pode resultar em 0.0000
             # Poderíamos mostrar mais casas decimais ou aceitar a representação.
             # Por ora, manteremos o f fixo.
             pass
        return f"{value:.{decimal_places}f}"
    return str(value)

# A função dataframe_to_image FOI REMOVIDA conforme solicitado.

# --- NOVA FUNÇÃO PARA CORREÇÃO DE BAGLEY ---
def perform_bagley_correction(lista_dados_capilares_bagley, common_D_mm_bagley, rho_pasta_si, tempo_extrusao_si, num_pontos_bagley_final=15):
    print("\n--- Iniciando Análise de Correção de Bagley ---")
    min_overall_gamma_aw, max_overall_gamma_aw = np.inf, -np.inf
    
    for cap_data in lista_dados_capilares_bagley:
        cap_data['volumes_m3'] = cap_data['massas_kg'] / rho_pasta_si
        cap_data['vazoes_Q_m3_s'] = cap_data['volumes_m3'] / cap_data['tempos_s']
        cap_data['gamma_dot_aw'] = (4*cap_data['vazoes_Q_m3_s']) / (np.pi*cap_data['R_m']**3)
        gamma_aw_com_fluxo = cap_data['gamma_dot_aw'][cap_data['massas_kg'] > 1e-9]
        if len(gamma_aw_com_fluxo) > 0:
            min_overall_gamma_aw = min(min_overall_gamma_aw, np.min(gamma_aw_com_fluxo))
            max_overall_gamma_aw = max(max_overall_gamma_aw, np.max(gamma_aw_com_fluxo))

    if not (np.isfinite(min_overall_gamma_aw) and np.isfinite(max_overall_gamma_aw) and min_overall_gamma_aw < max_overall_gamma_aw):
        print("ALERTA (Bagley): Faixa inválida de taxas de cisalhamento. Verifique dados."); return np.array([]), np.array([])
    
    target_gamma_dot_aw_values = np.geomspace(max(1e-3, min_overall_gamma_aw), max_overall_gamma_aw, num_pontos_bagley_final)
    corrected_tau_w_bagley_list, final_gamma_dot_aw_targets_list = [], []

    for target_gamma_k in target_gamma_dot_aw_values:
        pressures_for_this_target, L_over_R_for_this_target = [], []
        for cap_data in lista_dados_capilares_bagley:
            sort_indices = np.argsort(cap_data['gamma_dot_aw'])
            sorted_gamma_aw, sorted_P = cap_data['gamma_dot_aw'][sort_indices], cap_data['pressoes_Pa'][sort_indices]
            unique_gamma_aw, unique_idx = np.unique(sorted_gamma_aw, return_index=True)
            unique_sorted_P = sorted_P[unique_idx]
            if len(unique_gamma_aw) < 2: continue
            if unique_gamma_aw[0] <= target_gamma_k <= unique_gamma_aw[-1]:
                try:
                    interpolated_P = np.interp(target_gamma_k, unique_gamma_aw, unique_sorted_P)
                    pressures_for_this_target.append(interpolated_P)
                    L_over_R_for_this_target.append(cap_data['L_m'] / cap_data['R_m'])
                except Exception as e: print(f"  Aviso (Bagley Interp) L={cap_data['L_mm']}mm, gamma={target_gamma_k:.2e}: {e}")
        
        if len(L_over_R_for_this_target) >= 2:
            try:
                slope, intercept, _, _, _ = linregress(L_over_R_for_this_target, pressures_for_this_target)
                if slope < 0: print(f"  Aviso (Bagley Fit): Inclinação negativa ({slope:.2e}) para gamma={target_gamma_k:.2e}. Descartado."); continue
                corrected_tau_w_bagley_list.append(slope / 2.0)
                final_gamma_dot_aw_targets_list.append(target_gamma_k)
            except Exception as e: print(f"  Aviso (Bagley Fit) gamma={target_gamma_k:.2e}: {e}")
        else: print(f"  Aviso (Bagley): Pontos L/R insuficientes ({len(L_over_R_for_this_target)}) para gamma={target_gamma_k:.2e}.")
    
    if not final_gamma_dot_aw_targets_list: print("ALERTA (Bagley): Nenhuma curva de fluxo corrigida gerada.")
    print("--- Correção de Bagley Concluída ---")
    return np.array(final_gamma_dot_aw_targets_list), np.array(corrected_tau_w_bagley_list)

# -----------------------------------------------------------------------------
# --- INÍCIO DA EXECUÇÃO PRINCIPAL ---
# -----------------------------------------------------------------------------
timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S") # <<<<<<<<<<<<<<< Timestamp no início
print("="*70+"\n--- ANÁLISE REOLÓGICA DE PASTAS ---\n"+f"--- Sessão: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ({timestamp_str}) ---\n"+"="*70)

print("\n--- Dados Fixos Globais da Pasta e Ensaio ---")
rho_pasta_g_cm3_fixo = input_float_com_virgula("Densidade da pasta (rho) em [g/cm³]: ")
tempo_extrusao_fixo_s_val = input_float_com_virgula("Tempo de extrusão fixo para todos os testes [s]: ")
if rho_pasta_g_cm3_fixo <= 0 or tempo_extrusao_fixo_s_val <= 0: print("ERRO: Densidade e tempo >0."); exit()
rho_pasta_si = rho_pasta_g_cm3_fixo * 1000

realizar_bagley = input_sim_nao("\nDeseja realizar a Correção de Bagley? (s/n): ")
capilares_bagley_data_input = []
num_testes_para_analise = 0
gamma_dot_aw_an, tau_w_an = np.array([]), np.array([])
R_cap_analise_si, D_cap_mm_display, L_cap_mm_display = 0, "N/A", "N/A"
pressoes_bar_display_tab, massas_g_display_tab = [],[]
D_cap_mm_bagley_comum_val = 0 

if realizar_bagley:
    print("\n--- Entrada de Dados para Correção de Bagley ---")
    D_cap_mm_bagley_comum_val = input_float_com_virgula("Diâmetro COMUM dos capilares de Bagley [mm]: ")
    if D_cap_mm_bagley_comum_val <= 0: print("ERRO: Diâmetro >0."); exit()
    R_cap_analise_si = (D_cap_mm_bagley_comum_val / 2000)
    D_cap_mm_display = D_cap_mm_bagley_comum_val
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
        print(f"\n--- Capilar de Bagley {i+1}/{num_L_bagley} (D = {D_cap_mm_bagley_comum_val} mm) ---")
        L_i_mm = input_float_com_virgula(f"Comprimento L do capilar {i+1} [mm]: ")
        if L_i_mm <= 0: print("ERRO: Comprimento >0."); exit()
        p_bar_cap_i, m_g_cap_i = [], []
        print(f"  Insira os {num_pontos_cap} pontos para L={L_i_mm}mm:")
        for j in range(num_pontos_cap):
            p = input_float_com_virgula(f"    Teste {j+1} - Pressão [bar]: ")
            m = input_float_com_virgula(f"    Teste {j+1} - Massa [g] (0 se não fluiu): ")
            if p <= 0: print("ERRO: Pressão >0."); exit()
            if m < 0: print("ERRO: Massa >=0."); exit()
            p_bar_cap_i.append(p); m_g_cap_i.append(m)
        capilares_bagley_data_input.append({'L_mm':L_i_mm, 'L_m':L_i_mm/1000, 'R_m':R_cap_analise_si,
                                      'pressoes_Pa':np.array(p_bar_cap_i)*1e5, 
                                      'massas_kg':np.array(m_g_cap_i)/1000,
                                      'tempos_s':np.full(num_pontos_cap, tempo_extrusao_fixo_s_val)})
    gamma_dot_aw_an, tau_w_an = perform_bagley_correction(capilares_bagley_data_input, D_cap_mm_bagley_comum_val, rho_pasta_si, tempo_extrusao_fixo_s_val)
    num_testes_para_analise = len(gamma_dot_aw_an)
    if num_testes_para_analise > 0:
        pressoes_bar_display_tab = [np.nan] * num_testes_para_analise
        massas_g_display_tab = [np.nan] * num_testes_para_analise
    else: print("ALERTA: Correção de Bagley não resultou em pontos válidos para análise.")
else: # Sem Correção de Bagley
    print("\n--- Dados do Capilar Único ---")
    D_cap_mm_unico = input_float_com_virgula("Diâmetro do capilar (D_cap) em [mm]: ")
    L_cap_mm_unico = input_float_com_virgula("Comprimento do capilar (L_cap) em [mm]: ")
    if D_cap_mm_unico <= 0 or L_cap_mm_unico <= 0: print("ERRO: Dimensões >0."); exit()
    R_cap_analise_si, L_cap_m_analise = (D_cap_mm_unico/2000), L_cap_mm_unico/1000
    D_cap_mm_display, L_cap_mm_display = D_cap_mm_unico, L_cap_mm_unico
    try: num_testes_para_analise = int(input("Quantos testes (Pressão/Massa) para este capilar? "))
    except ValueError: print("ERRO: Número inválido."); exit()
    if num_testes_para_analise <= 0: print("ERRO: Número de testes >0."); exit()
    for i in range(num_testes_para_analise):
        print(f"\n--- Teste {i+1} de {num_testes_para_analise} ---")
        p = input_float_com_virgula(f"Pressão (P) [bar]: "); m = input_float_com_virgula(f"Massa (m) [g] (0 se não fluiu): ")
        if p <= 0: print("ERRO: Pressão >0."); exit()
        if m < 0: print("ERRO: Massa >=0."); exit()
        pressoes_bar_display_tab.append(p); massas_g_display_tab.append(m)
    pressoes_Pa_raw_unico = np.array(pressoes_bar_display_tab)*1e5
    massas_kg_raw_unico = np.array(massas_g_display_tab)/1000
    tempos_s_raw_unico = np.full(num_testes_para_analise, tempo_extrusao_fixo_s_val)
    volumes_m3_raw = massas_kg_raw_unico / rho_pasta_si
    vazoes_Q_m3_s_raw = volumes_m3_raw / tempos_s_raw_unico
    tau_w_an = pressoes_Pa_raw_unico * R_cap_analise_si / (2 * L_cap_m_analise)
    if R_cap_analise_si == 0: print("ERRO: Raio do capilar é zero."); exit()
    gamma_dot_aw_an = (4 * vazoes_Q_m3_s_raw) / (np.pi * R_cap_analise_si**3)

if num_testes_para_analise > 0:
    eta_a_an = np.full_like(gamma_dot_aw_an, np.nan)
    valid_an_idx = gamma_dot_aw_an != 0
    if np.any(valid_an_idx): eta_a_an[valid_an_idx] = tau_w_an[valid_an_idx] / gamma_dot_aw_an[valid_an_idx]
    if num_testes_para_analise > 1:
        idx_final_sort = np.argsort(gamma_dot_aw_an)
        gamma_dot_aw_an, tau_w_an, eta_a_an = gamma_dot_aw_an[idx_final_sort], tau_w_an[idx_final_sort], eta_a_an[idx_final_sort]
        if not realizar_bagley:
            pressoes_bar_display_tab = np.array(pressoes_bar_display_tab)[idx_final_sort].tolist()
            massas_g_display_tab = np.array(massas_g_display_tab)[idx_final_sort].tolist()
else: print("ALERTA: Nenhum dado de fluxo para análise. Encerrando."); exit()
    
gamma_dot_w_an = np.zeros_like(gamma_dot_aw_an)
n_prime_global, log_K_prime = 1.0, 0.0
if num_testes_para_analise == 1 and gamma_dot_aw_an[0]==0: print("\nALERTA: 1 ponto sem fluxo. n'=1.")
elif num_testes_para_analise == 1 and gamma_dot_aw_an[0]>0: print("\nALERTA: 1 ponto com fluxo. n'=1.")
elif num_testes_para_analise > 1:
    valid_log_idx = (tau_w_an > 0) & (gamma_dot_aw_an > 0)
    if np.sum(valid_log_idx) < 2: print("ALERTA: <2 pontos com fluxo para n'. n'=1.")
    else:
        log_tau, log_gamma_aw = np.log(tau_w_an[valid_log_idx]), np.log(gamma_dot_aw_an[valid_log_idx])
        try:
            coeffs, _, _, _, _ = np.polyfit(log_gamma_aw, log_tau, 1, full=True)
            n_prime_global, log_K_prime = coeffs[0], coeffs[1]
            K_prime_global = np.exp(log_K_prime)
            print(f"\nn' global: {n_prime_global:.4f}, K' global: {K_prime_global:.4f}")
            if n_prime_global <= 0: print("ALERTA: n' <= 0. Usando n'=1."); n_prime_global = 1.0
        except Exception as e: print(f"ERRO n': {e}. Assumindo n'=1."); n_prime_global = 1.0
n_corr = n_prime_global if n_prime_global != 0 else 1.0
gamma_dot_w_an = ((3*n_corr + 1)/(4*n_corr)) * gamma_dot_aw_an
eta_true_an = np.full_like(gamma_dot_w_an, np.nan)
valid_gw_idx = gamma_dot_w_an > 0
if np.any(valid_gw_idx): eta_true_an[valid_gw_idx] = tau_w_an[valid_gw_idx] / gamma_dot_w_an[valid_gw_idx]

print("\n--- Ajustando Modelos Reológicos ---")
def model_newtonian(gd,eta): return eta*gd
def model_power_law(gd,K,n): return K*np.power(gd,n)
def model_bingham(gd,t0,ep): return t0+ep*gd
def model_hb(gd,t0,K,n): return t0+K*np.power(gd,n)
models = {"Newtoniano":model_newtonian, "Lei da Potência":model_power_law, "Bingham":model_bingham, "Herschel-Bulkley":model_hb}
model_results = {}
valid_fit_idx = (tau_w_an > 0) & (gamma_dot_w_an > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_w_an))
gd_fit = np.array([]) 
if np.sum(valid_fit_idx)<1: print("ERRO: Sem pontos com fluxo para ajuste de modelos.")
else:
    gd_fit,tau_fit = gamma_dot_w_an[valid_fit_idx],tau_w_an[valid_fit_idx]
    for name,func in models.items():
        print(f"\nAjustando: {name}")
        n_params = func.__code__.co_argcount-1
        if len(gd_fit)<n_params: print(f"  Dados com fluxo insuficientes para {name}."); continue
        p0,bnds = None,(-np.inf, np.inf)
        n_pg = n_prime_global if n_prime_global>0 else 0.5
        if name=="Newtoniano": bnds=(0,np.inf)
        elif name=="Lei da Potência": p0,bnds = [1.0,n_pg],([1e-9,1e-9],[np.inf,np.inf])
        elif name=="Bingham": p0,bnds = [0.1,0.1],([0,1e-9],[np.inf,np.inf])
        elif name=="Herschel-Bulkley": p0,bnds = [0.1,1.0,n_pg],([0,1e-9,1e-9],[np.inf,np.inf,np.inf])
        try:
            p,cov = curve_fit(func,gd_fit,tau_fit,p0=p0,bounds=bnds,maxfev=10000, method='trf' if name in ["Lei da Potência", "Herschel-Bulkley"] else 'lm')
            tau_pred = func(gd_fit,*p)
            ss_r,ss_t = np.sum((tau_fit-tau_pred)**2),np.sum((tau_fit-np.mean(tau_fit))**2)
            r2 = 1-(ss_r/ss_t) if ss_t > 1e-9 else (1.0 if ss_r < 1e-9 else 0.0)
            model_results[name] = {'params':p,'R2':r2,'covariance':cov}
            p_names = list(func.__code__.co_varnames[1:n_params+1])
            params_str = [format_float_for_table(val,5) for val in p]
            print(f"  Params ({', '.join(p_names)}): {', '.join(params_str)}, R²: {r2:.5f}")
        except Exception as e: print(f"  Falha no ajuste de {name}: {e}")
best_model,best_r2 = "",-np.inf
if model_results:
    for name,data in model_results.items():
        if data['R2']>best_r2: best_r2,best_model = data['R2'],name
    if best_model: print(f"\n--- Melhor Modelo: {best_model} (R² = {best_r2:.5f}) ---")
    else: print("\n--- Nenhum modelo selecionado. ---")
else: print("\n--- Nenhum modelo foi ajustado. ---")

if num_testes_para_analise > 0:
    print("\n\n"+"="*70+"\n--- TABELAS DE RESULTADOS --- (Valores numéricos formatados)\n"+"="*70)
    vazoes_Q_mm3_s_an_tab = (gamma_dot_aw_an * np.pi * R_cap_analise_si**3 / 4) * 1e9 if R_cap_analise_si > 0 else np.full_like(gamma_dot_aw_an, np.nan)
    d_cap_mm_col_tab = np.full(num_testes_para_analise, D_cap_mm_display)
    l_cap_mm_col_tab = [L_cap_mm_display] * num_testes_para_analise if isinstance(L_cap_mm_display, str) else np.full(num_testes_para_analise, L_cap_mm_display)
    rho_g_cm3_col_tab = np.full(num_testes_para_analise, rho_pasta_g_cm3_fixo)
    tempos_s_col_tab = np.full(num_testes_para_analise, tempo_extrusao_fixo_s_val)
    tabela_dict_main = {
        "Ponto Análise": list(range(1,num_testes_para_analise+1)),
        "Diâmetro Capilar (mm)": d_cap_mm_col_tab, "Compr. Capilar (mm)": l_cap_mm_col_tab,
        "Densidade Pasta (g/cm³)": rho_g_cm3_col_tab, "Tempo Extrusão (s)": tempos_s_col_tab,
        "Pressão Extrusão (bar)": pressoes_bar_display_tab, "Massa Extrudada (g)": massas_g_display_tab,
        "Vazão Volumétrica (mm³/s)": vazoes_Q_mm3_s_an_tab,
        "Tensão Cis. Parede (Pa)": tau_w_an, "Taxa Cis. Apar. Parede (s⁻¹)": gamma_dot_aw_an,
        "Viscosidade Apar. (Pa·s)": eta_a_an, "Taxa Cis. Real Parede (s⁻¹)": gamma_dot_w_an,
        "Viscosidade Real (Pa·s)": eta_true_an
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
    print(df_resultados.to_string(index=False, formatters=custom_formatters, na_rep='N/A_Bagley'))
    
    # MODIFICADO: Nome de arquivo com timestamp no início
    csv_filename = f"{timestamp_str}_resultados_reologicos_compilados.csv"
    try:
        df_resultados.to_csv(csv_filename,index=False,sep=';',decimal=',',float_format='%.4f', na_rep='N/A_Bagley')
        print(f"\n\nTabela de dados compilados salva em: {csv_filename}")
    except Exception as e: print(f"\nERRO CSV: {e}")

    # REMOVIDA a chamada para dataframe_to_image(df_resultados, ...)

    if realizar_bagley and capilares_bagley_data_input: # capilares_bagley_data_input é a lista de dicts com os dados brutos + Q e gamma_aw
        print("\n--- Gerando CSV com Dados Brutos da Correção de Bagley ---")
        lista_dados_brutos_bagley_para_df = []
        
        for idx_cap, cap_data_raw in enumerate(capilares_bagley_data_input):
            num_pontos_neste_capilar = len(cap_data_raw['pressoes_Pa'])
            # Converter pressoes_Pa de volta para bar para a tabela de dados brutos
            pressoes_bar_cap_raw = cap_data_raw['pressoes_Pa'] / 1e5
            # Converter massas_kg de volta para g
            massas_g_cap_raw = cap_data_raw['massas_kg'] * 1000
            
            # vazoes_Q_m3_s e gamma_dot_aw já foram calculados e adicionados em cap_data_raw
            # pela função perform_bagley_correction ou deveriam ser.
            # Adicionar um fallback caso não tenham sido adicionados (embora a estrutura atual sugira que sim)
            if 'vazoes_Q_m3_s' not in cap_data_raw: # Calcular se não existir
                 vol_temp = cap_data_raw['massas_kg'] / rho_pasta_si # rho_pasta_si está em kg/m³
                 cap_data_raw['vazoes_Q_m3_s'] = vol_temp / cap_data_raw['tempos_s']
                 cap_data_raw['gamma_dot_aw'] = (4 * cap_data_raw['vazoes_Q_m3_s']) / (np.pi * cap_data_raw['R_m']**3)

            vazoes_q_mm3_s_cap_raw = cap_data_raw['vazoes_Q_m3_s'] * 1e9

            for j in range(num_pontos_neste_capilar):
                ponto_bruto = {
                    "ID_Capilar_Bagley": idx_cap + 1,
                    "Diametro_Comum_Bagley (mm)": D_cap_mm_bagley_comum_val, # Diâmetro comum usado
                    "Comprimento_Capilar_Usado (mm)": cap_data_raw['L_mm'],
                    "Densidade_Pasta_Utilizada (g/cm3)": rho_pasta_g_cm3_fixo, # <<<<<<<<<<< ADICIONADO AQUI
                    "Ponto_Teste_No": j + 1,
                    "Pressao_Entrada_Medida (bar)": pressoes_bar_cap_raw[j],
                    "Massa_Extrudada_Medida (g)": massas_g_cap_raw[j],
                    "Tempo_Extrusao_Fixo (s)": tempo_extrusao_fixo_s_val, # Tempo fixo global
                    "Vazao_Q_Calculada (mm3/s)": vazoes_q_mm3_s_cap_raw[j],
                    "Taxa_Cis_Apar_gamma_dot_aw (s-1)": cap_data_raw['gamma_dot_aw'][j],
                    "DeltaP_Total_Medida (Pa)": cap_data_raw['pressoes_Pa'][j]
                }
                lista_dados_brutos_bagley_para_df.append(ponto_bruto)

        if lista_dados_brutos_bagley_para_df:
            df_bagley_bruto = pd.DataFrame(lista_dados_brutos_bagley_para_df)
            csv_bagley_bruto_filename = f"{timestamp_str}_dados_brutos_bagley.csv"
            try:
                df_bagley_bruto.to_csv(csv_bagley_bruto_filename, index=False, sep=';', decimal=',', float_format='%.4f')
                print(f"Dados brutos da Correção de Bagley salvos em: {csv_bagley_bruto_filename}")
            except Exception as e_csv_bagley:
                print(f"ERRO ao salvar CSV dos dados brutos de Bagley: {e_csv_bagley}")
        else:
            print("Nenhum dado bruto de Bagley para salvar.")

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
        print(df_summary.to_string(index=False))
        print(f"R²: {r2_val:.5f}")
        
        # MODIFICADO: Salvar resumo do modelo em CSV, com timestamp no início
        csv_resumo_modelo_filename = f"{timestamp_str}_resumo_melhor_modelo.csv"
        try:
            df_summary.to_csv(csv_resumo_modelo_filename, index=False, sep=';', decimal=',')
            print(f"\nResumo do melhor modelo salvo em: {csv_resumo_modelo_filename}")
        except Exception as e_csv_model:
            print(f"\nERRO ao salvar resumo do modelo em CSV: {e_csv_model}")
        # REMOVIDA a chamada para dataframe_to_image(df_summary, ...)

# --- GERAÇÃO DE GRÁFICOS ---
if num_testes_para_analise > 0 and model_results:
    print("\n\n"+"="*70+"\n--- GERANDO GRÁFICOS ---\n"+"="*70)
    min_gp,max_gp = 0.001,1.0
    if len(gd_fit)>0: 
        min_g_obs,max_g_obs = np.min(gd_fit),np.max(gd_fit)
        min_gp = min_g_obs*0.5 if min_g_obs*0.5 > 1e-9 else (min_g_obs if min_g_obs > 1e-9 else 1e-3)
        max_gp = max_g_obs*1.5
        if min_gp <= 1e-9: min_gp = 1e-3
        if max_gp <= min_gp: max_gp = min_gp * 100 +1 
    try:
        gd_plot_eff_pos = np.geomspace(max(1e-9,min_gp),max_gp,200)
        if len(gd_plot_eff_pos)<2 or np.any(np.diff(gd_plot_eff_pos)<=0): raise ValueError("geomspace fail")
    except:
        gd_plot_eff_pos = np.linspace(max(1e-9,min_gp),max_gp,200)
        gd_plot_eff_pos = gd_plot_eff_pos[gd_plot_eff_pos>1e-9]
        if len(gd_plot_eff_pos)<2: gd_plot_eff_pos = np.array([max(1e-9,min_gp),max_gp]) if max_gp>max(1e-9,min_gp) else np.array([0.001,0.01])
    
    # Gráfico 1: Curva de Fluxo
    fig1, ax1 = plt.subplots(figsize=(10,7))
    ax1.scatter(gamma_dot_w_an, tau_w_an, label=r'Dados Processados', c='k', marker='o', s=60, zorder=10)
    if len(gd_plot_eff_pos) > 0:
        for name, data in model_results.items():
            try: ax1.plot(gd_plot_eff_pos, models[name](gd_plot_eff_pos, *data['params']), label=fr'{name} (R²={data["R2"]:.4f})', lw=2.5, alpha=0.8)
            except: pass
    ax1.set_xlabel(r'Taxa Cis. Real Parede, $\dot{\gamma}_w$ (s⁻¹)'); ax1.set_ylabel(r'Tensão Cis. Parede, $\tau_w$ (Pa)')
    ax1.set_title(r'Curva de Fluxo e Modelos Ajustados'); ax1.legend(); ax1.grid(True,which="both",ls="--"); ax1.set_xscale('log'); ax1.set_yscale('log'); fig1.tight_layout()
    try: # MODIFICADO: Nome de arquivo com timestamp no início
        plot_filename_flow = f"{timestamp_str}_curva_fluxo.png"
        fig1.savefig(plot_filename_flow, dpi=300, bbox_inches='tight')
        print(f"Gráfico da Curva de Fluxo salvo em: {plot_filename_flow}")
    except Exception as e: print(f"ERRO ao salvar Curva de Fluxo: {e}")

    # Gráfico 2: Determinação de n'
    if num_testes_para_analise > 1 and 'n_prime_global' in locals() and n_prime_global != 1.0 and 'log_K_prime' in locals() and np.sum((tau_w_an > 0) & (gamma_dot_aw_an > 0)) > 1:
        valid_log_p = (tau_w_an > 0) & (gamma_dot_aw_an > 0)
        log_tau_p, log_gamma_aw_p = np.log(tau_w_an[valid_log_p]), np.log(gamma_dot_aw_an[valid_log_p])
        fig2, ax2 = plt.subplots(figsize=(10,7))
        ax2.scatter(log_gamma_aw_p, log_tau_p, label=r'ln($\dot{\gamma}_{aw}$) vs ln($\tau_w$)',c='r',marker='x',s=60)
        if len(log_gamma_aw_p) > 1:
            log_gamma_line = np.linspace(np.min(log_gamma_aw_p), np.max(log_gamma_aw_p), 50)
            ax2.plot(log_gamma_line, n_prime_global * log_gamma_line + log_K_prime, '--', c='b', lw=2, label=fr'Ajuste Linear (n\'={n_prime_global:.3f})')
        ax2.set_xlabel(r'ln($\dot{\gamma}_{aw}$)'); ax2.set_ylabel(r'ln($\tau_w$)')
        ax2.set_title(r'Determinação de n\' (Índice de Comportamento de Fluxo)'); ax2.legend(); ax2.grid(True,which="both",ls="--"); fig2.tight_layout()
        try: # MODIFICADO: Nome de arquivo com timestamp no início
            plot_filename_nprime = f"{timestamp_str}_determinacao_n_prime.png"
            fig2.savefig(plot_filename_nprime, dpi=300, bbox_inches='tight')
            print(f"Gráfico de Determinação de n' salvo em: {plot_filename_nprime}")
        except Exception as e: print(f"ERRO ao salvar Determinação de n': {e}")
    elif num_testes_para_analise > 1 : print("  Aviso: Gráfico para n' não gerado (n_prime_global=1.0 ou dados insuficientes).")

    # Gráfico 3: Viscosidade
    fig3, ax3 = plt.subplots(figsize=(10,7))
    valid_eta_p = ~np.isnan(eta_true_an) & (gamma_dot_w_an > 0) 
    if np.any(valid_eta_p): ax3.scatter(gamma_dot_w_an[valid_eta_p], eta_true_an[valid_eta_p], label=r'Viscosidade Processada ($\eta$)', c='g', marker='s', s=60, zorder=10)
    if len(gd_plot_eff_pos) > 0:
        for name, data in model_results.items():
            try:
                eta_m = models[name](gd_plot_eff_pos, *data['params']) / gd_plot_eff_pos
                if name == "Newtoniano": eta_m = np.full_like(gd_plot_eff_pos, data['params'][0])
                ax3.plot(gd_plot_eff_pos, eta_m, label=fr'Modelo {name} ($\eta$)', lw=2.5, alpha=0.8)
            except: pass
    ax3.set_xlabel(r'Taxa Cis. Real Parede, $\dot{\gamma}_w$ (s⁻¹)'); ax3.set_ylabel(r'Viscosidade, $\eta$ (Pa·s)')
    ax3.set_title(r'Viscosidade vs. Taxa de Cisalhamento'); ax3.legend(); ax3.grid(True,which="both",ls="--"); ax3.set_xscale('log'); ax3.set_yscale('log'); fig3.tight_layout()
    try: # MODIFICADO: Nome de arquivo com timestamp no início
        plot_filename_visc = f"{timestamp_str}_curva_viscosidade.png"
        fig3.savefig(plot_filename_visc, dpi=300, bbox_inches='tight')
        print(f"Gráfico da Curva de Viscosidade salvo em: {plot_filename_visc}")
    except Exception as e: print(f"ERRO ao salvar Curva de Viscosidade: {e}")
    
    print("\nFeche as janelas dos gráficos para finalizar o script.")
    plt.show()
else: print("\n--- Tabelas e Gráficos principais não gerados (sem dados válidos para análise ou modelos não ajustados). ---")

print("\n"+"="*70+"\n--- FIM DA ANÁLISE ---\n"+"="*70)