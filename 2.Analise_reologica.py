# -----------------------------------------------------------------------------
# SCRIPT PARA ANÁLISE REOLÓGICA DE PASTAS EM REÔMETRO CAPILAR
# (Versão com CSV, JSON, Bagley & Plots, Mooney & Plots, Casson, Relatório TXT)
# --- VERSÃO MODIFICADA COM SALVAMENTO, APLICAÇÃO DE CALIBRAÇÕES E TEMPO VARIÁVEL ---
# -----------------------------------------------------------------------------

# 1. Importação de Bibliotecas
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('QtAgg') 
import pandas as pd
from datetime import datetime
import os 
import json 
from scipy.interpolate import interp1d

# -----------------------------------------------------------------------------
# --- CONFIGURAÇÃO INICIAL ---
# -----------------------------------------------------------------------------
# Define os nomes das pastas de saída e de calibrações
main_output_base_folder = "resultados_analise_reologica"
calibrations_folder = "correcoes_bagley_mooney" 

# --- CONFIGURAÇÕES GERAIS ---
# Fator de calibração empírico padrão (multiplicador final da tensão).
# Altere este valor se desejar aplicar um fator de correção global.
FATOR_CALIBRACAO_EMPIRICO_PADRAO = 1.0 

# ---- MODIFICAÇÃO: Solicita um nome para a pasta de resultados ----
while True:
    folder_prefix = input("\nDigite um prefixo para o nome da pasta de resultados (ex: LOTE_ABC_AMOSTRA_1): ").strip()
    if folder_prefix:
        break
    else:
        print("ERRO: O prefixo não pode ser vazio. Por favor, insira um identificador para a análise.")

# Cria as pastas se elas não existirem
timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
# ---- MODIFICAÇÃO: Combina o prefixo com o timestamp ----
output_folder_name = f"{folder_prefix}_{timestamp_str}"
output_folder = os.path.join(main_output_base_folder, output_folder_name)

if not os.path.exists(output_folder):
    os.makedirs(output_folder)
if not os.path.exists(calibrations_folder):
    os.makedirs(calibrations_folder)
# -----------------------------------------------------------------------------
# --- FUNÇÕES AUXILIARES ---
# -----------------------------------------------------------------------------
def input_sim_nao(mensagem_prompt):
    """Pede uma entrada do usuário e valida se é 'sim' ou 'não'."""
    while True:
        resposta = input(mensagem_prompt).strip().lower()
        if resposta in ['s', 'sim']: return True
        elif resposta in ['n', 'nao', 'não']: return False
        else: print("ERRO: Resposta inválida. Digite 's' ou 'n'.")

def input_float_com_virgula(mensagem_prompt, permitir_vazio=False):
    """Pede um número float ao usuário, aceitando ',' como decimal. Permite entrada vazia opcionalmente."""
    while True:
        entrada = input(mensagem_prompt).strip()
        if permitir_vazio and entrada == "":
            return None
        try:
            return float(entrada.replace(',', '.'))
        except ValueError:
            print("ERRO: Entrada inválida. Insira um número.")
        except Exception as e:
            print(f"Ocorreu um erro: {e}")


def format_float_for_table(value, decimal_places=4):
    """Formata um número float para exibição em tabelas, usando notação científica para valores muito pequenos."""
    if isinstance(value, (float, np.floating)):
        if np.isnan(value): return "NaN"
        if abs(value) < 10**(-decimal_places) and value != 0 and abs(value) > 1e-12 :
             return f"{value:.{max(1,decimal_places)}g}"
        return f"{value:.{decimal_places}f}"
    return str(value)

# --- FUNÇÃO PARA LER DADOS JSON (MODIFICADA PARA TEMPO VARIÁVEL) ---
def ler_dados_json(json_filepath):
    """Lê dados de um arquivo JSON, suportando duração fixa ('duracao_por_teste_s') ou variável ('duracao_real_s')."""
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Parâmetros essenciais (exceto tempo)
        json_rho_g_cm3 = data.get('densidade_pasta_g_cm3')
        D_mm = data.get('diametro_capilar_mm')
        L_mm = data.get('comprimento_capilar_mm')
        if D_mm is None or L_mm is None or json_rho_g_cm3 is None:
            print(f"ERRO JSON: Faltam dados essenciais (diametro_capilar_mm, comprimento_capilar_mm, densidade_pasta_g_cm3) em '{os.path.basename(json_filepath)}'")
            return None

        # Parâmetro de tempo (opcional global - usado para preencher se 'duracao_real_s' não existe)
        json_t_ext_s_fixo = data.get('duracao_por_teste_s')

        # Extrai listas de pressão, massa e duração (se variável)
        pressoes_bar_list, massas_g_list, duracoes_s_list = [], [], []
        
        if 'testes' in data and isinstance(data['testes'], list):
            for i, teste in enumerate(data['testes']):
                # Leitura com suporte a novos nomes (Linha/Pasta) e fallback para antigos (Barril/Entrada)
                p_linha = teste.get('media_pressao_linha_bar', teste.get('media_pressao_barril_bar'))
                p_pasta = teste.get('media_pressao_pasta_bar', teste.get('media_pressao_entrada_bar'))
                
                # Fallback para arquivos muito antigos (apenas final)
                p_final = teste.get('media_pressao_final_ponto_bar')
                
                m = teste.get('massa_g_registrada')
                t_real = teste.get('duracao_real_s') 
                
                if m is None:
                    continue
                
                # Prioridade: Linha > Barril > Final > 0.0
                p_b = float(p_linha) if p_linha is not None else (float(p_final) if p_final is not None else 0.0)
                # Prioridade: Pasta > Entrada > 0.0
                p_e = float(p_pasta) if p_pasta is not None else 0.0
                
                pressoes_bar_list.append({'linha': p_b, 'pasta': p_e})
                massas_g_list.append(float(m))
                
                if t_real is not None:
                    duracoes_s_list.append(float(t_real))
                elif json_t_ext_s_fixo is not None:
                    duracoes_s_list.append(float(json_t_ext_s_fixo))

        # Verifica se o número de tempos corresponde ao número de pontos
        if len(duracoes_s_list) != len(pressoes_bar_list):
             print(f"ERRO JSON: Inconsistência nos dados de duração variável/fixa em '{os.path.basename(json_filepath)}'")
             return None

        # Define o modo de tempo para o relatório (se todos são iguais, é fixo)
        is_fixed_time = len(set(duracoes_s_list)) <= 1
        tempo_extrusao_info = duracoes_s_list[0] if is_fixed_time and duracoes_s_list else None
        
        return {
            'D_mm': float(D_mm), 'L_mm': float(L_mm),
            'rho_g_cm3_json': float(json_rho_g_cm3),
            # MODIFICADO: Retorna o array de durações e o valor fixo (se aplicável)
            't_ext_s_fixo': tempo_extrusao_info, 
            'duracoes_s_list': duracoes_s_list, 
            'pressoes_bar_list': pressoes_bar_list,
            'massas_g_list': massas_g_list,
        }
    except FileNotFoundError: print(f"ERRO: Arquivo JSON não encontrado '{json_filepath}'."); return None
    except json.JSONDecodeError: print(f"ERRO: Falha ao decodificar o arquivo JSON '{json_filepath}'. Verifique o formato."); return None
    except Exception as e: print(f"ERRO ao ler ou processar o arquivo JSON '{json_filepath}': {e}"); return None


# --- FUNÇÕES PARA LISTAR E SELECIONAR ARQUIVO JSON ---
def listar_arquivos_json_numerados(pasta_json):
    """Lista todos os arquivos .json em uma pasta para que o usuário possa escolher pelo número."""
    if not os.path.exists(pasta_json):
        print(f"AVISO: A pasta '{pasta_json}' não existe. Não foi possível listar arquivos JSON.")
        return []
    arquivos = sorted([f for f in os.listdir(pasta_json) if f.endswith('.json') and os.path.isfile(os.path.join(pasta_json, f))])
    if not arquivos:
        print(f"Nenhum arquivo .json encontrado na pasta '{pasta_json}'.")
    else:
        print(f"\nArquivos JSON disponíveis em '{pasta_json}':")
        for i, arq in enumerate(arquivos):
            print(f"  {i+1}: {arq}")
    return arquivos

def selecionar_arquivo_json(pasta_json, mensagem_prompt):
    """Gerencia o menu para o usuário escolher um arquivo JSON da lista."""
    arquivos_disponiveis = listar_arquivos_json_numerados(pasta_json)
    if not arquivos_disponiveis:
        return None 
    while True:
        try:
            escolha_str = input(f"{mensagem_prompt} (digite o número ou '0' para nome completo): ").strip()
            if escolha_str == '0':
                 nome_manual = input("  Digite o nome completo do arquivo JSON (ex: dados.json): ").strip()
                 if not nome_manual: 
                     print("  Nome manual não pode ser vazio. Tente novamente.")
                     continue
                 if not nome_manual.lower().endswith(".json"):
                     nome_manual_original = nome_manual
                     nome_manual += ".json"
                     print(f"  ALERTA: Nome '{nome_manual_original}' não termina com .json. Usando '{nome_manual}'.")
                 
                 if os.path.exists(os.path.join(pasta_json, nome_manual)):
                     print(f"  Selecionado manualmente: {nome_manual}")
                     return nome_manual
                 else:
                     print(f"  ERRO: Arquivo '{nome_manual}' digitado manualmente não foi encontrado na pasta '{pasta_json}'.")
                     print(f"  Por favor, escolha um número da lista ou digite '0' para um nome válido.")
                     continue 
            
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_disponiveis):
                arquivo_selecionado = arquivos_disponiveis[escolha_num - 1]
                print(f"  Selecionado: {arquivo_selecionado}")
                return arquivo_selecionado
            else:
                print(f"ERRO: Escolha inválida. Digite um número entre 1 e {len(arquivos_disponiveis)}, ou '0'.")
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite um número ou '0'.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado na seleção: {e}")
            return None
# -----------------------------------------------------------------------------
# --- FUNÇÕES PARA SALVAR E CARREGAR CALIBRAÇÕES ---
# -----------------------------------------------------------------------------

def salvar_calibracao_json(tipo_correcao, tau_w_corrigido, gamma_dot_corrigido, arquivos_origem, pasta_calibracao):
    """
    Salva os resultados de uma calibração (Bagley, Mooney, etc.) em um arquivo JSON.
    Estes dados (tau vs gamma) representam a "curva mestra" da correção.
    """
    if len(tau_w_corrigido) == 0 or len(gamma_dot_corrigido) == 0:
        print("AVISO (Salvar Calibração): Não há dados corrigidos para salvar.")
        return

    timestamp_cal = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"cal_{tipo_correcao}_{timestamp_cal}.json"
    caminho_arquivo = os.path.join(pasta_calibracao, nome_arquivo)

    # Organiza os dados da calibração em um dicionário para salvar
    dados_calibracao = {
        "tipo_calibracao": tipo_correcao,
        "data_geracao": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "arquivos_origem_calibracao": arquivos_origem,
        "pontos_calibracao": {
            "tau_w_pa": tau_w_corrigido.tolist(),
            "gamma_dot_corrigido_s-1": gamma_dot_corrigido.tolist()
        }
    }

    try:
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados_calibracao, f, indent=4, ensure_ascii=False)
        print(f"\nSUCESSO: Calibração salva com sucesso em '{caminho_arquivo}'")
    except Exception as e:
        print(f"\nERRO: Falha ao salvar o arquivo de calibração: {e}")

def listar_e_selecionar_calibracao(pasta_calibracao):
    """
    Lista os arquivos de calibração .json disponíveis na pasta de calibrações
    e permite ao usuário selecionar um para aplicar em um novo ensaio.
    """
    print(f"\nBuscando calibrações salvas em '{pasta_calibracao}'...")
    if not os.path.exists(pasta_calibracao):
        print(f"AVISO: A pasta de calibrações '{pasta_calibracao}' não existe.")
        return None

    arquivos_cal = sorted([f for f in os.listdir(pasta_calibracao) if f.startswith('cal_') and f.endswith('.json')])
    
    if not arquivos_cal:
        print("Nenhuma calibração encontrada.")
        return None

    print("\nCalibrações disponíveis:")
    for i, arq in enumerate(arquivos_cal):
        print(f"  {i+1}: {arq}")
    
    while True:
        try:
            escolha = input(f"Escolha o número da calibração a ser aplicada (ou '0' para cancelar): ").strip()
            escolha_num = int(escolha)
            if escolha_num == 0:
                print("  Nenhuma calibração será aplicada.")
                return None
            if 1 <= escolha_num <= len(arquivos_cal):
                arquivo_selecionado = arquivos_cal[escolha_num - 1]
                print(f"  Calibração selecionada: {arquivo_selecionado}")
                return os.path.join(pasta_calibracao, arquivo_selecionado)
            else:
                print(f"ERRO: Escolha inválida. Digite um número entre 1 e {len(arquivos_cal)} ou 0.")
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite um número.")

def carregar_e_aplicar_calibracao(caminho_calibracao, tau_w_nao_corrigido):
    """
    Carrega os dados de um arquivo de calibração JSON e os aplica aos dados de tensão de cisalhamento
    de um capilar único, usando interpolação para encontrar a taxa de cisalhamento corrigida correspondente.
    """
    try:
        with open(caminho_calibracao, 'r', encoding='utf-8') as f:
            cal_data = json.load(f)
        
        print(f"\nAplicando calibração do tipo '{cal_data.get('tipo_calibracao', 'N/A')}' de {cal_data.get('data_geracao', 'N/A')}")
        
        pontos = cal_data.get('pontos_calibracao', {})
        tau_cal = np.array(pontos.get('tau_w_pa', []))
        gamma_cal = np.array(pontos.get('gamma_dot_corrigido_s-1', []))

        if len(tau_cal) < 2 or len(gamma_cal) < 2:
            print("ERRO na calibração: Arquivo não contém pontos suficientes para interpolação.")
            return None

        # Cria a função de interpolação. 'bounds_error=False' e 'fill_value="extrapolate"'
        # permitem que o script estime valores mesmo que a nova tensão esteja um pouco fora
        # da faixa original da calibração.
        funcao_calibracao = interp1d(tau_cal, gamma_cal, kind='linear', bounds_error=False, fill_value="extrapolate")
        
        # O passo chave: aplica a função de interpolação para encontrar a taxa de cisalhamento
        # corrigida para cada valor de tensão de cisalhamento do novo ensaio.
        gamma_dot_aplicado = funcao_calibracao(tau_w_nao_corrigido)
        
        print("SUCESSO: Calibração aplicada aos dados.")
        return gamma_dot_aplicado

    except FileNotFoundError:
        print(f"ERRO: Arquivo de calibração não encontrado: '{caminho_calibracao}'")
        return None
    except Exception as e:
        print(f"ERRO ao carregar ou aplicar calibração: {e}")
        return None

# -----------------------------------------------------------------------------
# --- FUNÇÕES PARA CORREÇÕES E RELATÓRIO ---
# -----------------------------------------------------------------------------
def plotar_ajuste_bagley(L_over_R_vals, P_vals, slope, intercept, target_gamma_aw_str, output_folder, timestamp):
    """Gera e salva um gráfico do ajuste de Bagley para uma taxa de cisalhamento específica."""
    if len(L_over_R_vals) < 2: return
    plt.figure(figsize=(8, 6))
    plt.scatter(L_over_R_vals, np.array(P_vals) / 1e5, marker='o', label='Dados Interpolados')
    line_x = np.array(sorted(L_over_R_vals))
    line_y_pa = slope * line_x + intercept
    plt.plot(line_x, line_y_pa / 1e5, color='red', label=rf"Ajuste Linear ($\tau_{{w,\text{{corr}}}} = {slope/2:.1f}$ Pa)")
    plt.xlabel('Razão Comprimento/Raio (L/R) (adimensional)')
    plt.ylabel("Pressão Total Medida (" + r"$\Delta P$" + ") (bar)")
    title_str = f"Plot de Bagley para " + \
                rf"$\dot{{\gamma}}_{{\text{{ap}}}}^* \approx {float(target_gamma_aw_str):.1f} \text{{ s}}^{{-1}}$"
    plt.title(title_str)
    plt.legend(); plt.grid(True)
    filename = os.path.join(output_folder, f"{timestamp}_bagley_plot_gamma_aw_{float(target_gamma_aw_str):.0f}.png")
    try:
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"  Plot de Bagley salvo em: {filename}")
    except Exception as e: print(f"  ERRO ao salvar plot de Bagley: {e}")
    plt.close()

# MODIFICADA: Recebe t_ext_s_array em vez de t_ext_si (tempo fixo)
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
        cap_data['vazoes_Q_m3_s'] = cap_data['volumes_m3'] / t_s_array # <--- AQUI ESTÁ A MUDANÇA
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
            # Devemos ter certeza que o cap_data['gamma_dot_aw'] foi calculado
            if 'gamma_dot_aw' not in cap_data: continue 

            sort_idx = np.argsort(cap_data['gamma_dot_aw'])
            sorted_gamma_cap, sorted_P_cap = cap_data['gamma_dot_aw'][sort_idx], cap_data['pressoes_Pa'][sort_idx]
            unique_gamma, unique_idx_u = np.unique(sorted_gamma_cap, return_index=True)
            unique_P = sorted_P_cap[unique_idx_u]
            if len(unique_gamma) < 2: continue
            
            # Interpolação (o resto da lógica de Bagley se mantém inalterada)
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


# MODIFICADA: Recebe t_ext_s_array_map em vez de t_ext_si (tempo fixo)
def perform_mooney_correction(capilares_data, common_L_mm, rho_si, t_ext_s_array_map, output_folder, timestamp, tau_w_targets_ref=None):
    """
    Executa a correção de Mooney completa (versão final com geração de alvos aprimorada).
    """
    common_L_m = common_L_mm / 1000.0
    print("\n--- Iniciando Análise de Correção de Mooney (Deslizamento) ---")
    if not capilares_data or len(capilares_data) < 2:
        print("ALERTA (Mooney): São necessários dados de pelo menos 2 capilares com diâmetros diferentes.")
        return np.array([]), np.array([])

    # Etapa 1: Pré-calcular as curvas de fluxo (tau_w vs gamma_aw) para cada capilar de Mooney
    capilar_curves = []
    for cap in capilares_data:
        D_m = cap['D_mm'] / 1000.0
        R_m = D_m / 2.0
        if R_m <= 0 or common_L_m <= 0: continue

        massas_kg = np.array(cap['massas_kg'])
        pressoes_Pa = np.array(cap['pressoes_Pa'])
        
        # Associa o array de tempos correspondente ao capilar
        cap_id = f"{cap['D_mm']:.3f}_{cap['L_mm']:.2f}"
        t_s_array = t_ext_s_array_map.get(cap_id, None)

        if t_s_array is None or len(t_s_array) != len(massas_kg):
            print(f"ERRO (Mooney): Array de tempos inválido ou incompatível para D={cap['D_mm']}mm, L={cap['L_mm']}mm. Pulando.")
            continue

        # MODIFICADO: Cálculo de vazão com array de tempos
        volumes_m3 = massas_kg / rho_si
        Q_m3_s = volumes_m3 / t_s_array # <--- AQUI ESTÁ A MUDANÇA
        
        gamma_dot_aw = (4 * Q_m3_s) / (np.pi * R_m**3)
        tau_w = (pressoes_Pa * R_m) / (2 * common_L_m)
        
        valid_indices = ~np.isnan(tau_w) & ~np.isnan(gamma_dot_aw)
        tau_w, gamma_dot_aw = tau_w[valid_indices], gamma_dot_aw[valid_indices]
        sort_idx = np.argsort(tau_w)
        tau_w, gamma_dot_aw = tau_w[sort_idx], gamma_dot_aw[sort_idx]
        
        if len(tau_w) > 1:
            capilar_curves.append({
                '1/R': 1/R_m, 'D_mm': cap['D_mm'], 'tau_w': tau_w, 'gamma_aw': gamma_dot_aw
            })

    if len(capilar_curves) < 2:
        print("ALERTA (Mooney): Menos de 2 capilares com dados válidos para análise.")
        return np.array([]), np.array([])

    # Etapa 2: Definir as tensões de cisalhamento alvo
    if tau_w_targets_ref is not None and len(tau_w_targets_ref) > 0:
        print("  Usando tau_w da correção de Bagley como alvos para Mooney.")
        tau_targets = np.sort(tau_w_targets_ref)
    else:
        # --- LÓGICA DE GERAÇÃO DE ALVOS CORRIGIDA E INTELIGENTE ---
        max_of_mins = max(curve['tau_w'][0] for curve in capilar_curves)
        min_of_maxs = min(curve['tau_w'][-1] for curve in capilar_curves)

        if max_of_mins >= min_of_maxs:
            print(f"ALERTA (Mooney): As faixas de tensão de cisalhamento dos capilares não se sobrepõem o suficiente.")
            print(f"  A sobreposição começa em {max_of_mins:.0f} Pa mas termina em {min_of_maxs:.0f} Pa.")
            return np.array([]), np.array([])
            
        print(f"  Faixa de sobreposição para análise de Mooney encontrada: {max_of_mins:.0f} a {min_of_maxs:.0f} Pa.")
        tau_targets = np.linspace(max_of_mins, min_of_maxs, 15)

    # Etapa 3: Para cada alvo, interpolar, fazer a regressão e encontrar a taxa de cisalhamento corrigida
    gamma_dot_s_final = []
    tau_w_final = []
    for target_tau in tau_targets:
        points_for_regression = []
        for curve in capilar_curves:
            if target_tau >= curve['tau_w'][0] and target_tau <= curve['tau_w'][-1]:
                gamma_aw_interp = np.interp(target_tau, curve['tau_w'], curve['gamma_aw'])
                points_for_regression.append((curve['1/R'], gamma_aw_interp))
        
        if len(points_for_regression) >= 2:
            inv_R_vals = [p[0] for p in points_for_regression]
            gamma_aw_vals = [p[1] for p in points_for_regression]
            
            try:
                slope, intercept, r_val, p_val, std_err = linregress(inv_R_vals, gamma_aw_vals)
                if intercept < 0:
                    print(f"  Aviso (Mooney Fit): Intercepto (γ̇s) negativo ({intercept:.2e}) para τw={target_tau:.0f} Pa. Ponto descartado.")
                    continue
                
                gamma_dot_s_final.append(intercept)
                tau_w_final.append(target_tau)

            except Exception as e:
                print(f"  Aviso (Mooney Fit): Falha na regressão para τw={target_tau:.0f} Pa: {e}")
        else:
             print(f"  Aviso (Mooney): <2 pontos para ajuste em τw={target_tau:.0f} Pa.")

    if not tau_w_final:
        print("ALERTA (Mooney): Nenhuma curva de fluxo corrigida para deslizamento foi gerada.")
        return np.array([]), np.array([])

    print("--- Correção de Mooney (Deslizamento) Concluída com Sucesso ---")
    return np.array(gamma_dot_s_final), np.array(tau_w_final)

def gerar_relatorio_texto(timestamp_str_report, rho_g_cm3, tempo_extrusao_info,
                          metodo_entrada_rel, json_files_usados_rel, csv_path_rel,
                          realizar_bagley, D_bagley_mm, capilares_bagley_info,
                          realizar_mooney, L_mooney_mm, capilares_mooney_D_info,
                          D_unico_mm, L_unico_mm,
                          calibracao_aplicada_info,
                          df_res, df_sum_modelo, best_model_nome,
                          comportamento_fluido_relatorio,
                          lista_arquivos_gerados, output_folder, fator_calibracao):
    """Gera um relatório de texto completo (.txt) com o resumo de toda a análise."""
    filename = os.path.join(output_folder, f"{timestamp_str_report}_relatorio_analise.txt")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\nRELATÓRIO DE ANÁLISE REOLÓGICA\n" + "="*70 + "\n")
            f.write(f"Sessão: {timestamp_str_report}\nData da Geração: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Pasta de Saída: {output_folder}\n")
            f.write("\n--- PARÂMETROS GLOBAIS DO ENSAIO ---\n")
            f.write(f"Densidade da Pasta: {rho_g_cm3:.3f} g/cm³\n")
            # MODIFICADO: Exibe informação de tempo fixo ou variável
            if isinstance(tempo_extrusao_info, str):
                 f.write(f"Tempo de Extrusão: {tempo_extrusao_info}\n")
            else:
                 f.write(f"Tempo de Extrusão Fixo: {tempo_extrusao_info:.2f} s\n")

            if fator_calibracao != 1.0:
                 f.write(f"Fator de Calibração Empírico Aplicado: {fator_calibracao:.4f}\n")

            f.write("\n--- ORIGEM DOS DADOS EXPERIMENTAIS ---\n")
            f.write(f"Método de Entrada: {metodo_entrada_rel}\n")
            if metodo_entrada_rel == "Arquivo CSV":
                f.write(f"  Caminho do Arquivo CSV: {csv_path_rel}\n")
            elif metodo_entrada_rel == "Arquivo(s) JSON":
                json_base_folder_report = "resultados_testes_reometro"
                f.write(f"  Arquivos JSON Utilizados (da pasta '{json_base_folder_report}/'):\n")
                if json_files_usados_rel:
                    for json_file in sorted(list(set(json_files_usados_rel))):
                        f.write(f"    - {json_file}\n")
                else:
                    f.write("    Nenhum arquivo JSON foi utilizado.\n")

            f.write("\n--- CONFIGURAÇÃO DE CORREÇÕES E CALIBRAÇÃO ---\n")
            f.write(f"Correção de Bagley (ao vivo): {'Sim' if realizar_bagley else 'Não'}\n")
            if realizar_bagley:
                D_bagley_mm_str = f"{D_bagley_mm:.3f}" if isinstance(D_bagley_mm, (int, float)) else str(D_bagley_mm)
                f.write(f"  Diâmetro Comum Capilares Bagley: {D_bagley_mm_str} mm\n  Capilares Usados (L em mm):\n")
                for i, cap_l in enumerate(capilares_bagley_info): f.write(f"    - Capilar {i+1}: L = {cap_l:.2f} mm\n")

            f.write(f"Correção de Mooney (ao vivo): {'Sim' if realizar_mooney else 'Não'}\n")
            if realizar_mooney:
                L_mooney_mm_str = f"{L_mooney_mm:.2f}" if isinstance(L_mooney_mm, (int, float)) else str(L_mooney_mm)
                f.write(f"  Comprimento Comum Capilares Mooney: {L_mooney_mm_str} mm\n  Diâmetros Usados (D em mm):\n")
                for i, cap_d in enumerate(capilares_mooney_D_info): f.write(f"    - Capilar {i+1}: D = {cap_d:.3f} mm\n")

            if not realizar_bagley and not realizar_mooney:
                if calibracao_aplicada_info:
                    f.write("\n--- CALIBRAÇÃO APLICADA (de arquivo) ---\n")
                    f.write(f"Arquivo de Calibração: {os.path.basename(calibracao_aplicada_info)}\n")
                    f.write("\n--- GEOMETRIA DO CAPILAR ÚNICO UTILIZADO ---\n")
                else:
                    f.write("\n--- GEOMETRIA DO CAPILAR ÚNICO (SEM CORREÇÕES) ---\n")
                D_unico_mm_str = f"{D_unico_mm:.3f}" if isinstance(D_unico_mm, (int, float)) else str(D_unico_mm)
                L_unico_mm_str = f"{L_unico_mm:.2f}" if isinstance(L_unico_mm, (int, float)) else str(L_unico_mm)
                f.write(f"Diâmetro: {D_unico_mm_str} mm\nComprimento: {L_unico_mm_str} mm\n")

            f.write("\n--- RESULTADOS PRINCIPAIS (CURVA DE FLUXO PROCESSADA) ---\n")
            if df_res is not None and not df_res.empty:
                f.write(df_res.to_string(index=False, formatters={col: (lambda x, dp=4: format_float_for_table(x, dp)) for col in df_res.columns}, na_rep='N/A') + "\n")
            else: f.write("Não foram gerados dados processados para a tabela principal.\n")

            if best_model_nome and df_sum_modelo is not None and not df_sum_modelo.empty:
                f.write("\n--- MELHOR MODELO REOLÓGICO AJUSTADO ---\n")
                f.write(df_sum_modelo.to_string(index=False) + "\n")
                f.write(f"\nComportamento do Fluido Inferido: {comportamento_fluido_relatorio}\n")
            else: f.write("\nNenhum modelo foi ajustado ou selecionado como o melhor.\n")

            f.write("\n--- ARQUIVOS GERADOS NESTA SESSÃO ---\n")
            if not lista_arquivos_gerados:
                f.write("Nenhum arquivo adicional foi gerado.\n")
            else:
                for arq in sorted(lista_arquivos_gerados):
                    f.write(f"- {arq}\n")

            f.write("\n" + "="*70 + "\nFIM DO RELATÓRIO\n" + "="*70 + "\n")
        print(f"\nRelatório de texto salvo em: {filename}")
    except Exception as e: print(f"ERRO ao gerar relatório de texto: {e}")

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# --- INÍCIO DA EXECUÇÃO PRINCIPAL ---
# -----------------------------------------------------------------------------
print("="*70+f"\n--- ANÁLISE REOLÓGICA (Sessão: {timestamp_str}) ---\n"+"="*70)
print(f"Todos os arquivos de saída serão salvos na pasta: {output_folder}")
arquivos_gerados_lista = []

# Fator de calibração empírico (assumindo 1.0 para P. Pasta)
# Pode ser alterado no topo do script (FATOR_CALIBRACAO_EMPIRICO_PADRAO)
fator_calibracao_empirico = FATOR_CALIBRACAO_EMPIRICO_PADRAO

dados_confirmados = False
while not dados_confirmados:
    # Resetar variáveis para cada tentativa de entrada
    rho_pasta_g_cm3_fixo, tempo_extrusao_fixo_s_val, rho_pasta_si = None, None, None
    D_cap_mm_bagley_comum_val, L_cap_mm_mooney_comum_val = 0.0, 0.0
    D_cap_mm_unico_val, L_cap_mm_unico_val = 0.0, 0.0
    capilares_bagley_data_input, capilares_mooney_data_input = [], []
    bagley_capilares_L_mm_info, mooney_capilares_D_mm_info = [], []
    pressoes_bar_display_tab, massas_g_display_tab, tempos_s_display_tab = [], [], []
    _json_files_resumo = []
    num_testes_para_analise = 0
    _D_cap_mm_bagley_comum_val_resumo, _L_cap_mm_mooney_comum_val_resumo = "N/A", "N/A"
    _D_cap_mm_unico_val_resumo, _L_cap_mm_unico_val_resumo = "N/A", "N/A"
    _csv_path_resumo = "N/A"
    num_pontos_cap_bagley_manual, num_pontos_cap_mooney_manual, num_testes_unico_manual = 0,0,0
    
    # NOVO: Dicionário para armazenar o array de tempos por capilar (D_L)
    t_ext_s_array_by_capilar = {} 

    print("\n--- Método de Entrada de Dados Experimentais ---\n1. Manual\n2. CSV\n3. Arquivo JSON")
    metodo_entrada = ""
    while metodo_entrada not in ["1", "2", "3"]:
        metodo_entrada = input("Escolha o método (1, 2 ou 3): ").strip()

    # SELEÇÃO DO SENSOR DE PRESSÃO
    print("\n--- Seleção do Sensor de Pressão ---")
    print("1. Sensor do BARRIL (Padrão - Requer Bagley)")
    print("2. Sensor da ENTRADA (Membrana Aflorante - Direto)")
    print("\n" + "="*30)
    print("   CONFIGURAÇÃO DA ANÁLISE")
    print("="*30)
    
    print("Fontes de Pressão Disponíveis:")
    print("  1 - Pressão da LINHA (Antes do pistão/barril)")
    print("  2 - Pressão da PASTA (Entrada do capilar - Recomendado)")
    
    fonte_pressao = input("Escolha a fonte de pressão (1 ou 2) [Enter = 2]: ").strip()
    if not fonte_pressao: fonte_pressao = '2'
    
    usar_pressao_pasta = (fonte_pressao == '2')
    
    if usar_pressao_pasta:
        print(">> USANDO PRESSÃO DA PASTA (Sensor 2). (Bagley pode ser dispensável)")
    else:
        print(">> USANDO PRESSÃO DA LINHA (Sensor 1).")

    realizar_bagley = input_sim_nao("\nCorreção de Bagley? (s/n): ")
    realizar_mooney = input_sim_nao("\nCorreção de Mooney? (s/n): ")

    json_base_path = "resultados_testes_reometro"

    # CASO A: JSON para Capilar Único (sem correções)
    if metodo_entrada == "3" and not realizar_bagley and not realizar_mooney:
        print("\n--- Entrada JSON: Capilar Único (Dados Globais e Geometria do JSON) ---")
        if not os.path.exists(json_base_path):
            print(f"ERRO: Pasta '{json_base_path}' não encontrada."); continue

        json_filename_unico = selecionar_arquivo_json(json_base_path, "Escolha o arquivo JSON para o capilar único")
        if json_filename_unico is None: continue

        json_filepath_unico = os.path.join(json_base_path, json_filename_unico)
        json_data = ler_dados_json(json_filepath_unico)

        if json_data is None: continue
        _json_files_resumo.append(json_filename_unico)

        rho_pasta_g_cm3_fixo = json_data['rho_g_cm3_json']
        D_cap_mm_unico_val = json_data['D_mm']
        L_cap_mm_unico_val = json_data['L_mm']

        # Lógica para carregar tempo fixo ou variável (duracoes_s_list é o array real)
        tempos_s_display_tab = json_data['duracoes_s_list']
        if not tempos_s_display_tab:
            print(f"ERRO: Não foi possível carregar os dados de tempo do arquivo JSON '{json_filename_unico}'."); continue
        
        is_variable_time = len(set(tempos_s_display_tab)) > 1
        if is_variable_time:
             # Para fins de relatório e compatibilidade, definimos um valor médio
            tempo_extrusao_fixo_s_val = np.mean(tempos_s_display_tab)
            print(f"  Dados de tempo: Encontrados tempos de extrusão VARIÁVEIS no JSON (média: {tempo_extrusao_fixo_s_val:.2f} s).")
        else:
            tempo_extrusao_fixo_s_val = tempos_s_display_tab[0]
            print(f"  Dados de tempo: Encontrado tempo de extrusão FIXO de {tempo_extrusao_fixo_s_val:.2f} s no JSON.")

        if rho_pasta_g_cm3_fixo <= 0 or D_cap_mm_unico_val <= 0 or L_cap_mm_unico_val <= 0:
            print(f"ERRO JSON Único: Valores inválidos (rho, D ou L <= 0) em '{json_filename_unico}'."); continue

        rho_pasta_si = rho_pasta_g_cm3_fixo * 1000
        _D_cap_mm_unico_val_resumo = f"{D_cap_mm_unico_val:.3f}"
        _L_cap_mm_unico_val_resumo = f"{L_cap_mm_unico_val:.2f}"
        
        # Extrai a pressão correta da lista de dicionários
        raw_pressures = json_data['pressoes_bar_list']
        if usar_pressao_pasta:
            pressoes_bar_display_tab = [p['pasta'] for p in raw_pressures]
        else:
            pressoes_bar_display_tab = [p['linha'] for p in raw_pressures]
            
        massas_g_display_tab = json_data['massas_g_list']
        
        # Adiciona o array de tempos ao mapa, para o caso de Correção W-R ou Plotagem
        cap_id_unico = f"{D_cap_mm_unico_val:.3f}_{L_cap_mm_unico_val:.2f}"
        t_ext_s_array_by_capilar[cap_id_unico] = np.array(tempos_s_display_tab)

        if not pressoes_bar_display_tab or not massas_g_display_tab or \
           len(pressoes_bar_display_tab) != len(massas_g_display_tab) or \
           len(pressoes_bar_display_tab) == 0:
             print(f"ERRO JSON Único: Dados de P/M inválidos, vazios ou com tamanhos diferentes em '{json_filename_unico}'."); continue

        num_testes_para_analise = len(pressoes_bar_display_tab)


    # CASO B: JSON com Correções de Bagley e/ou Mooney (AGORA SUPORTA TEMPO VARIÁVEL)
    elif metodo_entrada == "3" and (realizar_bagley or realizar_mooney):
        print("\n--- Entrada JSON com Correções (Bagley/Mooney) ---")
        print("INFO: Esta modalidade AGORA suporta tempo de extrusão variável ('duracao_real_s') nos arquivos JSON.")
        if not os.path.exists(json_base_path):
            print(f"ERRO: Pasta '{json_base_path}' não encontrada."); continue

        params_globais_definidos = False
        erro_na_leitura = False

        if realizar_bagley:
            print("\n--- Configuração JSON para Bagley ---")
            num_L_bagley = 0
            while num_L_bagley < 2:
                try: num_L_bagley = int(input(f"No. de arquivos JSON para capilares com L DIFERENTES (mínimo 2): "))
                except ValueError: print("ERRO: Número inválido.")
                if num_L_bagley < 2: print("ERRO: Mínimo 2.")

            for i in range(num_L_bagley):
                json_filename = selecionar_arquivo_json(json_base_path, f"Escolha o JSON para capilar Bagley {i+1}")
                if not json_filename: erro_na_leitura = True; break
                json_data = ler_dados_json(os.path.join(json_base_path, json_filename))
                if not json_data: erro_na_leitura = True; break
                
                # O tempo agora vem do array de durações, seja fixo ou variável
                duracoes_array = json_data.get('duracoes_s_list', [])
                if not duracoes_array:
                    print(f"ERRO: O arquivo '{json_filename}' não contém dados de duração válidos ('duracao_real_s' ou 'duracao_por_teste_s').")
                    erro_na_leitura = True; break
                
                _json_files_resumo.append(json_filename)

                if not params_globais_definidos:
                    rho_pasta_g_cm3_fixo = json_data['rho_g_cm3_json']
                    # Define tempo_extrusao_fixo_s_val como o tempo médio/único, para fins de relatório
                    tempo_extrusao_fixo_s_val = np.mean(duracoes_array) if len(duracoes_array) > 0 else 0.0
                    D_cap_mm_bagley_comum_val = json_data['D_mm']
                    if any(p <= 0 for p in [rho_pasta_g_cm3_fixo, tempo_extrusao_fixo_s_val, D_cap_mm_bagley_comum_val]):
                        print(f"ERRO: Parâmetros de referência (rho, t, D) inválidos em '{json_filename}'."); erro_na_leitura = True; break
                    rho_pasta_si = rho_pasta_g_cm3_fixo * 1000
                    _D_cap_mm_bagley_comum_val_resumo = f"{D_cap_mm_bagley_comum_val:.3f}"
                    params_globais_definidos = True
                    print(f"  Parâmetros de Referência definidos por '{json_filename}':\n"
                          f"    Densidade: {rho_pasta_g_cm3_fixo:.3f} g/cm³, Tempo Médio: {tempo_extrusao_fixo_s_val:.2f} s, D Comum: {D_cap_mm_bagley_comum_val:.3f} mm")
                else:
                    if not np.isclose(json_data['D_mm'], D_cap_mm_bagley_comum_val):
                        print(f"ERRO: D={json_data['D_mm']:.3f}mm ('{json_filename}') difere do D comum de ref. {D_cap_mm_bagley_comum_val:.3f}mm."); erro_na_leitura = True; break

                L_i_mm = json_data['L_mm']
                raw_pressures = json_data['pressoes_bar_list']
                m_g_cap_i = json_data['massas_g_list']
                
                if usar_pressao_pasta:
                    p_bar_cap_i = [p['pasta'] for p in raw_pressures]
                else:
                    p_bar_cap_i = [p['linha'] for p in raw_pressures]

                bagley_capilares_L_mm_info.append(L_i_mm)
                
                # ADICIONADO: Popula o mapa de arrays de tempo
                cap_id_bagley = f"{D_cap_mm_bagley_comum_val:.3f}_{L_i_mm:.2f}"
                t_ext_s_array_by_capilar[cap_id_bagley] = np.array(duracoes_array)

                capilares_bagley_data_input.append({'L_mm': L_i_mm, 'L_m': L_i_mm/1000.0, 'D_mm': D_cap_mm_bagley_comum_val,
                                                  'pressoes_Pa': np.array(p_bar_cap_i)*1e5, 'massas_kg': np.array(m_g_cap_i)/1000.0})
        
        if erro_na_leitura: continue

        if realizar_mooney:
            print("\n--- Configuração JSON para Mooney ---")
            num_D_mooney = 0
            while num_D_mooney < 2:
                try: num_D_mooney = int(input(f"No. de arquivos JSON para capilares com D DIFERENTES (mínimo 2): "))
                except ValueError: print("ERRO: Número inválido.")
                if num_D_mooney < 2: print("ERRO: Mínimo 2.")

            for i in range(num_D_mooney):
                json_filename = selecionar_arquivo_json(json_base_path, f"Escolha o JSON para capilar Mooney {i+1}")
                if not json_filename: erro_na_leitura = True; break
                json_data = ler_dados_json(os.path.join(json_base_path, json_filename))
                if not json_data: erro_na_leitura = True; break
                
                duracoes_array = json_data.get('duracoes_s_list', [])
                if not duracoes_array:
                    print(f"ERRO: O arquivo '{json_filename}' não contém dados de duração válidos ('duracao_real_s' ou 'duracao_por_teste_s').")
                    erro_na_leitura = True; break
                    
                _json_files_resumo.append(json_filename)

                if not params_globais_definidos:
                    rho_pasta_g_cm3_fixo = json_data['rho_g_cm3_json']
                    # Define tempo_extrusao_fixo_s_val como o tempo médio/único, para fins de relatório
                    tempo_extrusao_fixo_s_val = np.mean(duracoes_array) if len(duracoes_array) > 0 else 0.0
                    if rho_pasta_g_cm3_fixo <= 0 or tempo_extrusao_fixo_s_val <= 0:
                        print(f"ERRO: Parâmetros de referência (rho, t) inválidos em '{json_filename}'."); erro_na_leitura = True; break
                    rho_pasta_si = rho_pasta_g_cm3_fixo * 1000
                    params_globais_definidos = True
                    print(f"  Parâmetros Globais de Referência definidos por '{json_filename}':\n"
                          f"    Densidade: {rho_pasta_g_cm3_fixo:.3f} g/cm³, Tempo Médio: {tempo_extrusao_fixo_s_val:.2f} s")

                if L_cap_mm_mooney_comum_val == 0.0:
                    L_cap_mm_mooney_comum_val = json_data['L_mm']
                    if L_cap_mm_mooney_comum_val <= 0:
                        print(f"ERRO: Comprimento comum de referência para Mooney inválido em '{json_filename}'."); erro_na_leitura = True; break
                    _L_cap_mm_mooney_comum_val_resumo = f"{L_cap_mm_mooney_comum_val:.2f}"
                    print(f"  Comprimento COMUM de referência para Mooney definido como: {L_cap_mm_mooney_comum_val:.2f} mm")

                if not np.isclose(json_data['L_mm'], L_cap_mm_mooney_comum_val):
                    print(f"ERRO: L={json_data['L_mm']:.2f}mm ('{json_filename}') difere do L comum de ref. {L_cap_mm_mooney_comum_val:.2f}mm."); erro_na_leitura = True; break

                D_i_mm = json_data['D_mm']
                raw_pressures = json_data['pressoes_bar_list']
                m_g_cap_i = json_data['massas_g_list']
                
                if usar_pressao_pasta:
                    p_bar_cap_i = [p['pasta'] for p in raw_pressures]
                else:
                    p_bar_cap_i = [p['linha'] for p in raw_pressures]

                mooney_capilares_D_mm_info.append(D_i_mm)
                
                # ADICIONADO: Popula o mapa de arrays de tempo
                cap_id_mooney = f"{D_i_mm:.3f}_{L_cap_mm_mooney_comum_val:.2f}"
                t_ext_s_array_by_capilar[cap_id_mooney] = np.array(duracoes_array)

                capilares_mooney_data_input.append({'D_mm': D_i_mm, 'L_mm': L_cap_mm_mooney_comum_val, 'L_m': L_cap_mm_mooney_comum_val/1000.0,
                                                   'pressoes_Pa': np.array(p_bar_cap_i)*1e5, 'massas_kg': np.array(m_g_cap_i)/1000.0})
        
        if erro_na_leitura: continue
        
        # Se as correções não usam tempo fixo, define o tempo fixo para NaN ou média para relatório
        if not realizar_bagley and not realizar_mooney: 
             print("AVISO: JSONs com correções selecionadas, mas ambas desativadas. Analisando como Capilar Único...")
             # Retorna para a lógica de Capilar Único, mas isso não deve acontecer
             # se o usuário seguiu a lógica do menu. (Mantendo o comportamento de erro, se for o caso)
             continue 

    # CASO C: Manual ou CSV (requer tempo fixo, pois não há array de tempos)
    else:
        print("\n--- Dados Fixos Globais da Pasta e Ensaio ---")
        rho_pasta_g_cm3_fixo = input_float_com_virgula("Densidade da pasta (rho) em [g/cm³]: ")
        # Se for CSV/Manual, é assumido que o tempo é fixo (limitante do método)
        tempo_extrusao_fixo_s_val = input_float_com_virgula("Tempo de extrusão fixo para todos os testes [s]: ")
        if rho_pasta_g_cm3_fixo <= 0 or tempo_extrusao_fixo_s_val <= 0:
            print("ERRO: Densidade e tempo devem ser >0. Tente novamente."); continue
        rho_pasta_si = rho_pasta_g_cm3_fixo * 1000

        # ... (O resto da lógica Manual/CSV para Bagley, Mooney e Capilar Único
        # é mantida, usando tempo_extrusao_fixo_s_val como o valor do tempo)

        # --------------------------------------------------------------------------------------------------
        # --- AVISO: A lógica de entrada Manual/CSV abaixo forçará o uso de tempo FIXO para as correções. ---
        # --------------------------------------------------------------------------------------------------
        
        if metodo_entrada == "1": # Manual
            if realizar_bagley:
                print("\n--- Entrada Manual: Bagley ---")
                D_cap_mm_bagley_comum_val = input_float_com_virgula("Diâmetro COMUM (Bagley) [mm]: ")
                if D_cap_mm_bagley_comum_val <= 0: print("ERRO: Diâmetro >0."); continue
                _D_cap_mm_bagley_comum_val_resumo = f"{D_cap_mm_bagley_comum_val:.3f}"
                num_L_bagley = 0
                while num_L_bagley < 2:
                    try: num_L_bagley = int(input("No. capilares L DIFERENTES (Bagley, min 2): "))
                    except ValueError: print("ERRO: No. inválido.")
                    if num_L_bagley < 2: print("ERRO: Mínimo 2.")
                try: num_pontos_cap_bagley_manual = int(input("No. pontos (P/M) POR CAPILAR (Bagley): "))
                except ValueError: print("ERRO: No. inválido.");continue
                if num_pontos_cap_bagley_manual <= 0: print("ERRO: No. pontos >0."); continue
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
                    
                    # Manual: Popula o mapa com array de tempos fixos
                    cap_id_bagley = f"{D_cap_mm_bagley_comum_val:.3f}_{L_i_mm:.2f}"
                    t_ext_s_array_by_capilar[cap_id_bagley] = np.full(num_pontos_cap_bagley_manual, tempo_extrusao_fixo_s_val)

                    temp_capilares_bagley_data.append({'L_mm':L_i_mm, 'L_m':L_i_mm/1000, 'D_mm': D_cap_mm_bagley_comum_val,
                                                  'pressoes_Pa':np.array(p_bar_cap_i)*1e5,
                                                  'massas_kg':np.array(m_g_cap_i)/1000})
                if not all_bagley_manual_ok: continue
                capilares_bagley_data_input = temp_capilares_bagley_data
                bagley_capilares_L_mm_info = temp_bagley_L_info
            if realizar_mooney:
                print("\n--- Entrada Manual: Mooney ---")
                L_cap_mm_mooney_comum_val = input_float_com_virgula("Comprimento COMUM (Mooney) [mm]: ")
                if L_cap_mm_mooney_comum_val <= 0: print("ERRO: L >0."); continue
                _L_cap_mm_mooney_comum_val_resumo = f"{L_cap_mm_mooney_comum_val:.2f}"
                num_D_mooney = 0
                while num_D_mooney < 2:
                    try: num_D_mooney = int(input("No. capilares D DIFERENTES (Mooney, min 2): "))
                    except ValueError: print("ERRO: No. inválido.")
                    if num_D_mooney < 2: print("ERRO: Mínimo 2.")
                try: num_pontos_cap_mooney_manual = int(input("No. pontos (P/M) POR CAPILAR (Mooney): "))
                except ValueError: print("ERRO: No. inválido."); continue
                if num_pontos_cap_mooney_manual <= 0: print("ERRO: No. pontos >0."); continue
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
                    
                    # Manual: Popula o mapa com array de tempos fixos
                    cap_id_mooney = f"{D_i_mm:.3f}_{L_cap_mm_mooney_comum_val:.2f}"
                    t_ext_s_array_by_capilar[cap_id_mooney] = np.full(num_pontos_cap_mooney_manual, tempo_extrusao_fixo_s_val)
                    
                    temp_capilares_mooney_data.append({'D_mm':D_i_mm, 'L_mm': L_cap_mm_mooney_comum_val,
                                                        'L_m':L_cap_mm_mooney_comum_val/1000,
                                                        'pressoes_Pa':np.array(p_bar_cap_i)*1e5,
                                                        'massas_kg':np.array(m_g_cap_i)/1000})
                if not all_mooney_manual_ok: continue
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
                tempos_s_display_tab = [tempo_extrusao_fixo_s_val] * num_testes_para_analise
                # Manual: Popula o mapa com array de tempos fixos para o capilar único
                cap_id_unico = f"{D_cap_mm_unico_val:.3f}_{L_cap_mm_unico_val:.2f}"
                t_ext_s_array_by_capilar[cap_id_unico] = np.array(tempos_s_display_tab)


        elif metodo_entrada == "2": # CSV (Assume tempo fixo)
            print("\n--- Carregando Dados de Arquivo CSV ---")
            csv_path = input("Caminho para o arquivo CSV: ").strip().replace("\"", "")
            _csv_path_resumo = csv_path
            try:
                # Modificado: Adicionado 't_ext_s' para compatibilidade de colunas internas, mesmo sendo fixo
                df_csv = pd.read_csv(csv_path, sep=None, decimal=',', engine='python', na_filter=False)
                cols_esperadas = ['diametro_mm', 'comprimento_mm', 'pressao_bar', 'massa_g']
                df_csv.columns = df_csv.columns.str.lower().str.replace(' ', '_').str.replace('[^a-z0-9_]', '', regex=True)
                
                # ADIÇÃO: Simula coluna de tempo no CSV para compatibilidade interna
                df_csv['t_ext_s'] = tempo_extrusao_fixo_s_val 

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
                        t_ext_s_list = df_cap_csv['t_ext_s'].astype(float).tolist()
                        if not p_bar: continue
                        
                        # CSV: Popula o mapa com array de tempos fixos
                        cap_id_bagley = f"{D_cap_mm_bagley_comum_val:.3f}_{L_mm_csv:.2f}"
                        t_ext_s_array_by_capilar[cap_id_bagley] = np.array(t_ext_s_list)
                        
                        capilares_bagley_data_input.append({'L_mm': L_mm_csv, 'L_m': L_mm_csv/1000.0, 'D_mm': D_cap_mm_bagley_comum_val,
                                                          'pressoes_Pa': np.array(p_bar)*1e5, 'massas_kg': np.array(m_g)/1000.0})
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
                        t_ext_s_list = df_cap_csv['t_ext_s'].astype(float).tolist()
                        if not p_bar: continue
                        
                        # CSV: Popula o mapa com array de tempos fixos
                        cap_id_mooney = f"{D_mm_csv:.3f}_{L_cap_mm_mooney_comum_val:.2f}"
                        t_ext_s_array_by_capilar[cap_id_mooney] = np.array(t_ext_s_list)
                        
                        capilares_mooney_data_input.append({'D_mm': D_mm_csv, 'L_mm': L_cap_mm_mooney_comum_val, 'L_m': L_cap_mm_mooney_comum_val/1000.0,
                                                           'pressoes_Pa': np.array(p_bar)*1e5, 'massas_kg': np.array(m_g)/1000.0})
                    print(f"Dados CSV Mooney: {len(capilares_mooney_data_input)} capilares (L={L_cap_mm_mooney_comum_val}mm).")
                if not realizar_bagley and not realizar_mooney:
                    if len(df_csv['diametro_mm'].astype(float).unique()) > 1 or len(df_csv['comprimento_mm'].astype(float).unique()) > 1:
                        print("ALERTA CSV: Múltiplos D/L para capilar único. Usando D/L da primeira linha.")
                    D_cap_mm_unico_val = float(df_csv['diametro_mm'].iloc[0])
                    L_cap_mm_unico_val = float(df_csv['comprimento_mm'].iloc[0])
                    if D_cap_mm_unico_val <=0 or L_cap_mm_unico_val <=0 : print("ERRO CSV Único: D ou L <=0."); continue
                    _D_cap_mm_unico_val_resumo = f"{D_cap_mm_unico_val:.3f}"; _L_cap_mm_unico_val_resumo = f"{L_cap_mm_unico_val:.2f}"
                    pressoes_bar_display_tab = df_csv['pressao_bar'].astype(float).tolist()
                    massas_g_display_tab = df_csv['massa_g'].astype(float).tolist()
                    tempos_s_display_tab = df_csv['t_ext_s'].astype(float).tolist()
                    num_testes_para_analise = len(pressoes_bar_display_tab)
                    if num_testes_para_analise == 0: print("ERRO CSV: Capilar único sem dados P/m."); continue
                    # CSV Único: Popula o mapa com array de tempos fixos
                    cap_id_unico = f"{D_cap_mm_unico_val:.3f}_{L_cap_mm_unico_val:.2f}"
                    t_ext_s_array_by_capilar[cap_id_unico] = np.array(tempos_s_display_tab)


                print("Dados carregados do CSV com sucesso.")
            except FileNotFoundError: print(f"ERRO: CSV não encontrado '{csv_path}'. Tente novamente."); continue
            except Exception as e_csv: print(f"ERRO ao processar CSV: {e_csv}. Tente novamente."); continue

    # --- EXIBIR RESUMO DOS DADOS INSERIDOS PARA CONFIRMAÇÃO ---
    print("\n" + "="*25 + " RESUMO DOS DADOS INSERIDOS PARA CONFIRMAÇÃO " + "="*25)
    if rho_pasta_g_cm3_fixo is None or tempo_extrusao_fixo_s_val is None or \
       rho_pasta_g_cm3_fixo <= 0 or tempo_extrusao_fixo_s_val <= 0:
        print("ERRO: Densidade ou tempo de extrusão não foram definidos corretamente. Reiniciando entrada.")
        continue

    print(f"Densidade da Pasta: {rho_pasta_g_cm3_fixo:.3f} g/cm³")
    
    # MODIFICADO: Lógica para exibir tempo fixo ou variável (baseado no array de capilar único/primeiro capilar)
    if (not realizar_bagley and not realizar_mooney) or (realizar_bagley and len(capilares_bagley_data_input) > 0) or (realizar_mooney and len(capilares_mooney_data_input) > 0):
        # Tenta pegar o primeiro array de tempo (ou do capilar único) para checar se é variável
        if tempos_s_display_tab:
            is_variable_time = len(set(tempos_s_display_tab)) > 1
        elif realizar_bagley and capilares_bagley_data_input:
            first_cap_id = f"{capilares_bagley_data_input[0]['D_mm']:.3f}_{capilares_bagley_data_input[0]['L_mm']:.2f}"
            is_variable_time = len(set(t_ext_s_array_by_capilar.get(first_cap_id, []))) > 1
        elif realizar_mooney and capilares_mooney_data_input:
            first_cap_id = f"{capilares_mooney_data_input[0]['D_mm']:.3f}_{capilares_mooney_data_input[0]['L_mm']:.2f}"
            is_variable_time = len(set(t_ext_s_array_by_capilar.get(first_cap_id, []))) > 1
        else:
            is_variable_time = False

        if is_variable_time:
            print(f"Tempo de Extrusão: Variável (média: {tempo_extrusao_fixo_s_val:.2f} s)")
        else:
            print(f"Tempo de Extrusão Fixo: {tempo_extrusao_fixo_s_val:.2f} s")
    else:
        print(f"Tempo de Extrusão: {tempo_extrusao_fixo_s_val:.2f} s (Tempo Fixo assumido)")


    if fator_calibracao_empirico != 1.0:
        print(f"Fator de Calibração Empírico a ser aplicado: {fator_calibracao_empirico:.4f}")

    input_method_str = "Desconhecido"
    if metodo_entrada == '1': input_method_str = "Manual"
    elif metodo_entrada == '2': input_method_str = "Arquivo CSV"
    elif metodo_entrada == '3': input_method_str = "Arquivo(s) JSON"
    print(f"Método de Entrada: {input_method_str}")

    if metodo_entrada == '2': print(f"  Caminho do Arquivo CSV: {_csv_path_resumo}")
    if metodo_entrada == '3' and _json_files_resumo:
        unique_json_files = sorted(list(set(_json_files_resumo)))
        json_input_folder_name = "resultados_testes_reometro"
        print(f"  Arquivos JSON Utilizados (de '{json_input_folder_name}/'): {', '.join(unique_json_files)}")

    print(f"\nCorreção de Bagley: {'Sim' if realizar_bagley else 'Não'}")
    if realizar_bagley:
        print(f"  Diâmetro Comum (Bagley): {_D_cap_mm_bagley_comum_val_resumo} mm")
        if capilares_bagley_data_input:
            print("  Dados dos Testes para Bagley:")
            for i, cap_data in enumerate(capilares_bagley_data_input):
                print(f"    Capilar Bagley {i+1} (L = {cap_data['L_mm']:.2f} mm):")
                pressoes_bar_cap = cap_data['pressoes_Pa'] / 1e5
                massas_g_cap = cap_data['massas_kg'] * 1000
                cap_id = f"{cap_data['D_mm']:.3f}_{cap_data['L_mm']:.2f}"
                tempos_cap = t_ext_s_array_by_capilar.get(cap_id, np.full_like(pressoes_bar_cap, tempo_extrusao_fixo_s_val))
                for j in range(len(pressoes_bar_cap)):
                    print(f"      - Teste {j+1}: P={pressoes_bar_cap[j]:.2f} bar | M={massas_g_cap[j]:.2f} g | T={tempos_cap[j]:.2f} s")

    print(f"\nCorreção de Mooney: {'Sim' if realizar_mooney else 'Não'}")
    if realizar_mooney:
        print(f"  Comprimento Comum (Mooney): {_L_cap_mm_mooney_comum_val_resumo} mm")
        if capilares_mooney_data_input:
            print("  Dados dos Testes para Mooney:")
            for i, cap_data in enumerate(capilares_mooney_data_input):
                print(f"    Capilar Mooney {i+1} (D = {cap_data['D_mm']:.3f} mm):")
                pressoes_bar_cap = cap_data['pressoes_Pa'] / 1e5
                massas_g_cap = cap_data['massas_kg'] * 1000
                cap_id = f"{cap_data['D_mm']:.3f}_{cap_data['L_mm']:.2f}"
                tempos_cap = t_ext_s_array_by_capilar.get(cap_id, np.full_like(pressoes_bar_cap, tempo_extrusao_fixo_s_val))
                for j in range(len(pressoes_bar_cap)):
                    print(f"      - Teste {j+1}: P={pressoes_bar_cap[j]:.2f} bar | M={massas_g_cap[j]:.2f} g | T={tempos_cap[j]:.2f} s")

    if not realizar_bagley and not realizar_mooney:
        print("\nAnálise com Capilar Único:")
        print(f"  Diâmetro do Capilar: {_D_cap_mm_unico_val_resumo} mm")
        print(f"  Comprimento do Capilar: {_L_cap_mm_unico_val_resumo} mm")
        num_testes_exibir = num_testes_para_analise

        if num_testes_exibir > 0: print(f"  Número de Testes (P,m,t): {num_testes_exibir}")
        if pressoes_bar_display_tab and massas_g_display_tab and tempos_s_display_tab and \
           len(pressoes_bar_display_tab) == len(massas_g_display_tab) == len(tempos_s_display_tab) > 0:
            print("  Dados dos Testes (Pressão [bar] | Massa [g] | Duração [s]):")
            for i in range(len(pressoes_bar_display_tab)):
                p_val, m_val, t_val = pressoes_bar_display_tab[i], massas_g_display_tab[i], tempos_s_display_tab[i]
                p_d = f"{p_val:.2f}" if isinstance(p_val,(int,float)) else str(p_val)
                m_d = f"{m_val:.2f}" if isinstance(m_val,(int,float)) else str(m_val)
                t_d = f"{t_val:.2f}" if isinstance(t_val,(int,float)) else str(t_val)
                print(f"    - Teste {i+1}: {p_d} bar | {m_d} g | {t_d} s")

    print("="* (50 + len(" RESUMO DOS DADOS INSERIDOS PARA CONFIRMAÇÃO ")))
    if input_sim_nao("\nDados corretos para prosseguir? (s/n): "):
        dados_confirmados = True
    else:
        print("\n--- ENTRADA DE DADOS REINICIADA. ---")

# -----------------------------------------------------------------------------
# --- PREPARAÇÃO FINAL E CÁLCULOS (APÓS CONFIRMAÇÃO) ---
# -----------------------------------------------------------------------------
tau_w_an, gamma_dot_aw_an, eta_a_an, gamma_dot_w_an_wr, eta_true_an = (np.array([]) for _ in range(5))
gd_fit, tau_fit = np.array([]), np.array([])
model_results = {}
best_model_nome = ""
df_summary = pd.DataFrame() 
calibracao_aplicada = False
caminho_calibracao_usada = ""

# --- CAMINHO 1: ANÁLISE DE CAPILAR ÚNICO ---
if not realizar_bagley and not realizar_mooney: 
    if num_testes_para_analise > 0:
        p_Pa = np.array(pressoes_bar_display_tab)*1e5
        m_kg = np.array(massas_g_display_tab)/1000
        # MODIFICADO: t_s agora é um array com os tempos de cada teste
        t_s = np.array(tempos_s_display_tab) 
        R_cap_si, L_cap_m = (D_cap_mm_unico_val/2000), L_cap_mm_unico_val/1000
        
        vol_m3 = m_kg/rho_pasta_si
        # MODIFICADO: Cálculo de vazão agora é elemento a elemento
        Q_m3_s = vol_m3/t_s
        
        if L_cap_m > 0 and R_cap_si > 0:
            tau_w_an = p_Pa * R_cap_si / (2 * L_cap_m)
        else:
            tau_w_an = np.full_like(p_Pa, np.nan)
            print("ALERTA: Dimensões capilar único inválidas (L ou R <=0).")

        # --- LÓGICA PARA APLICAR CALIBRAÇÃO SALVA ---
        if input_sim_nao("\nDeseja aplicar uma calibração de Bagley/Mooney salva para este ensaio? (s/n): "):
            caminho_cal = listar_e_selecionar_calibracao(calibrations_folder)
            if caminho_cal:
                gamma_dot_corrigido_calibracao = carregar_e_aplicar_calibracao(caminho_cal, tau_w_an)
                if gamma_dot_corrigido_calibracao is not None:
                    gamma_dot_aw_an = gamma_dot_corrigido_calibracao
                    calibracao_aplicada = True
                    caminho_calibracao_usada = caminho_cal
        
        if not calibracao_aplicada:
            gamma_dot_aw_an = (4*Q_m3_s) / (np.pi * R_cap_si**3) if R_cap_si > 0 else np.zeros_like(Q_m3_s)
    else:
        tau_w_an, gamma_dot_aw_an = np.array([]), np.array([])

# --- CAMINHO 2: CORREÇÕES AO VIVO (BAGLEY E/OU MOONEY) ---
tau_w_for_mooney = np.array([]) 

# AVISO: Se a entrada foi CSV/Manual, t_ext_s_array_by_capilar contém apenas tempos FIXOS.
# Se a entrada foi JSON, contém os arrays de tempos, sejam fixos ou variáveis.

if realizar_bagley:
    # MODIFICADO: Passa o mapa de arrays de tempo
    gamma_dot_aw_bagley_targets, tau_w_bagley_corrected = perform_bagley_correction(
        capilares_bagley_data_input, D_cap_mm_bagley_comum_val, 
        rho_pasta_si, t_ext_s_array_by_capilar, output_folder, timestamp_str)
    
    if len(tau_w_bagley_corrected) > 0:
        tau_w_an, gamma_dot_aw_an = tau_w_bagley_corrected, gamma_dot_aw_bagley_targets
        num_testes_para_analise = len(tau_w_an)
        tau_w_for_mooney = tau_w_an 
        if not realizar_mooney: # Salva apenas se for a correção final
            if input_sim_nao("\nDeseja salvar esta calibração de Bagley? (s/n): "):
                salvar_calibracao_json("Bagley", tau_w_an, gamma_dot_aw_an, _json_files_resumo, calibrations_folder)
    else:
        print("ALERTA: Bagley não resultou em pontos válidos."); realizar_bagley = False

if realizar_mooney:
    # MODIFICADO: Passa o mapa de arrays de tempo
    gamma_dot_aw_slip_corrected, tau_w_mooney_corrected = perform_mooney_correction(
        capilares_mooney_data_input, L_cap_mm_mooney_comum_val, rho_pasta_si, 
        t_ext_s_array_by_capilar, output_folder, timestamp_str, tau_w_targets_ref=tau_w_for_mooney) 
    
    if len(tau_w_mooney_corrected) > 0 and len(gamma_dot_aw_slip_corrected) > 0 : 
        tau_w_an, gamma_dot_aw_an = tau_w_mooney_corrected, gamma_dot_aw_slip_corrected
        num_testes_para_analise = len(tau_w_an)
        tipo_cal = "Bagley_e_Mooney" if realizar_bagley else "Mooney"
        if input_sim_nao(f"\nDeseja salvar esta calibração de '{tipo_cal}'? (s/n): "):
            salvar_calibracao_json(tipo_cal, tau_w_an, gamma_dot_aw_an, _json_files_resumo, calibrations_folder)
    else: 
        print("ALERTA: Mooney não resultou em pontos válidos.")
        if realizar_bagley and len(tau_w_for_mooney) > 0:
            # --- AVISO VISUAL ADICIONADO ---
            print("\n" + "="*70)
            print("ATENÇÃO: A CORREÇÃO DE MOONEY FALHOU.")
            print("A análise prosseguirá usando APENAS os dados da correção de Bagley.")
            print("Os resultados FINAIS NÃO incluem a correção para deslizamento na parede.")
            print("="*70 + "\n")
            realizar_mooney = False # Garante consistência para o relatório
        else:
            # Se nem Bagley foi feito, a análise para
            tau_w_an = np.array([])
            gamma_dot_aw_an = np.array([])
            num_testes_para_analise = 0

# --- APLICA FATOR DE CALIBRAÇÃO E CORREÇÃO W-R ---
if num_testes_para_analise > 0 and len(tau_w_an) > 0:
    if fator_calibracao_empirico != 1.0:
        print(f"\nINFO: Aplicando fator de calibração empírico de {fator_calibracao_empirico:.4f} à tensão de cisalhamento.")
        tau_w_an = tau_w_an * fator_calibracao_empirico

    eta_a_an = np.full_like(gamma_dot_aw_an, np.nan)
    valid_an_idx = (gamma_dot_aw_an != 0) & (~np.isnan(gamma_dot_aw_an)) & (~np.isnan(tau_w_an))
    if np.any(valid_an_idx): eta_a_an[valid_an_idx] = tau_w_an[valid_an_idx] / gamma_dot_aw_an[valid_an_idx]
    
    # Ordena os dados para a correção W-R e para os plots
    sort_indices = np.argsort(gamma_dot_aw_an)
    tau_w_an, gamma_dot_aw_an, eta_a_an = tau_w_an[sort_indices], gamma_dot_aw_an[sort_indices], eta_a_an[sort_indices]
    
    # Reordena os dados brutos para manter a consistência na tabela final
    # (Apenas para o caso de Capilar Único/Manual/CSV - correções ao vivo já estão ordenadas por gamma_aw)
    if not (realizar_bagley or realizar_mooney):
        pressoes_bar_display_tab = np.array(pressoes_bar_display_tab)[sort_indices].tolist()
        massas_g_display_tab = np.array(massas_g_display_tab)[sort_indices].tolist()
        tempos_s_display_tab = np.array(tempos_s_display_tab)[sort_indices].tolist()


    # Calcula n' (índice da lei de potência aparente) para a correção de Weissenberg-Rabinowitsch
    n_prime, log_K_prime, K_prime = np.nan, np.nan, np.nan
    valid_for_n_prime = (tau_w_an > 0) & (gamma_dot_aw_an > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_aw_an))
    if np.sum(valid_for_n_prime) > 1:
        log_tau = np.log(tau_w_an[valid_for_n_prime])
        log_gamma = np.log(gamma_dot_aw_an[valid_for_n_prime])
        try:
            n_prime, log_K_prime, _, _, _ = linregress(log_gamma, log_tau)
            if not np.isnan(log_K_prime):
                 K_prime = np.exp(log_K_prime)
        except ValueError:
            print("AVISO (W-R): Falha ao calcular n' por regressão linear. Usando n'=1.")
            n_prime = 1.0

    n_corr = n_prime if (n_prime != 0 and not np.isnan(n_prime)) else 1.0
    
    # Aplica Weissenberg-Rabinowitsch apenas se os dados não foram corrigidos por um arquivo de calibração
    if calibracao_aplicada:
        print("\nINFO: Calibração externa aplicada. 'Gamma_dot_corrigido' será usado diretamente como 'gamma_dot_w'.")
        gamma_dot_w_an_wr = gamma_dot_aw_an
    else:
        print("\nINFO: Aplicando correção de Weissenberg-Rabinowitsch para obter a taxa de cisalhamento real.")
        gamma_dot_w_an_wr = ((3*n_corr + 1)/(4*n_corr)) * gamma_dot_aw_an

    eta_true_an = np.full_like(gamma_dot_w_an_wr, np.nan)
    valid_gw = (gamma_dot_w_an_wr > 0) & (~np.isnan(gamma_dot_w_an_wr)) & (~np.isnan(tau_w_an)) 
    if np.any(valid_gw): eta_true_an[valid_gw] = tau_w_an[valid_gw] / gamma_dot_w_an_wr[valid_gw]

# -----------------------------------------------------------------------------
# --- AJUSTE DE MODELOS E GERAÇÃO DE TABELAS ---
# -----------------------------------------------------------------------------
if num_testes_para_analise > 0 and len(tau_w_an) > 0 and np.sum(~np.isnan(tau_w_an)) > 0:
    print("\n--- Ajustando Modelos Reológicos ---")
    def model_newtonian(gd,eta): return eta*gd
    def model_power_law(gd,K_pl,n_pl): return K_pl*np.power(np.maximum(gd, 1e-9),n_pl)
    def model_bingham(gd,t0,ep): return t0+ep*gd
    def model_hb(gd,t0,K_hb,n_hb): return t0+K_hb*np.power(np.maximum(gd, 1e-9),n_hb)
    def model_casson(gd, tau0_cas, eta_cas):
        sqrt_tau0 = np.sqrt(np.maximum(tau0_cas, 0))
        sqrt_eta_cas_val = np.sqrt(np.maximum(eta_cas, 1e-9))
        sqrt_gd_val = np.sqrt(np.maximum(gd, 1e-9))
        return (sqrt_tau0 + sqrt_eta_cas_val * sqrt_gd_val)**2

    models = {"Newtoniano":model_newtonian, "Lei da Potência":model_power_law,
              "Bingham":model_bingham, "Herschel-Bulkley":model_hb,
              "Casson": model_casson}
    model_results = {}
    valid_fit = (tau_w_an > 0) & (gamma_dot_w_an_wr > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_w_an_wr)) & (np.isfinite(tau_w_an)) & (np.isfinite(gamma_dot_w_an_wr))

    if np.sum(valid_fit) < 2:
        print("ALERTA: Menos de 2 pontos válidos para ajuste de modelos. A qualidade do ajuste pode ser baixa.")

    if np.sum(valid_fit) > 0:
        gd_fit,tau_fit = gamma_dot_w_an_wr[valid_fit],tau_w_an[valid_fit]
        tau0_initial_guess_generic = np.min(tau_fit)/2 if len(tau_fit)>0 else 0.1
        tau0_initial_guess_generic = max(tau0_initial_guess_generic, 1e-3)

        for name,func in models.items():
            print(f"\nAjustando: {name}")
            n_p = func.__code__.co_argcount-1
            if len(gd_fit)<n_p: print(f"  Dados insuficientes para {name} (requer {n_p} params, {len(gd_fit)} pontos)."); continue
            p0,bnds = None,(-np.inf, np.inf)
            n_g = n_prime if (n_prime > 0 and not np.isnan(n_prime) and 0.1 < n_prime < 2.5) else 0.5
            K_g = K_prime if (K_prime > 1e-9 and not np.isnan(K_prime)) else 1.0

            if name=="Newtoniano": bnds=(1e-9,np.inf); p0=[max(1e-3,np.mean(tau_fit/(gd_fit+1e-9)) if len(gd_fit)>0 else 1.0)]
            elif name=="Lei da Potência": p0,bnds = [K_g,n_g],([1e-9,1e-9],[np.inf,5.0])
            elif name=="Bingham": p0,bnds = [tau0_initial_guess_generic,max(1e-3,np.mean(eta_a_an[valid_fit & np.isfinite(eta_a_an)]) if np.any(valid_fit & np.isfinite(eta_a_an)) else 0.1)],([0,1e-9],[np.inf,np.inf])
            elif name=="Herschel-Bulkley": p0,bnds = [tau0_initial_guess_generic,K_g,n_g],([0,1e-9,1e-9],[np.inf,np.inf,5.0])
            elif name=="Casson":
                eta_cas_initial_guess = np.mean(eta_a_an[valid_fit & np.isfinite(eta_a_an)]) if np.any(valid_fit & np.isfinite(eta_a_an)) else 0.1
                eta_cas_initial_guess = max(eta_cas_initial_guess, 1e-3)
                p0,bnds = [tau0_initial_guess_generic, eta_cas_initial_guess], ([0, 1e-9],[np.inf,np.inf])

            try:
                params_fit,cov = curve_fit(func,gd_fit,tau_fit,p0=p0,bounds=bnds,maxfev=20000,method='trf', ftol=1e-8, xtol=1e-8, gtol=1e-8)
                tau_pred = func(gd_fit,*params_fit)
                ss_r,ss_t = np.sum((tau_fit-tau_pred)**2),np.sum((tau_fit-np.mean(tau_fit))**2)
                r2 = 1-(ss_r/ss_t) if ss_t > 1e-12 else (1.0 if ss_r < 1e-12 else 0.0)
                model_results[name] = {'params':params_fit,'R2':r2,'covariance':cov}
                p_names_fit = list(func.__code__.co_varnames[1:n_p+1])
                params_str = [format_float_for_table(val,5) for val in params_fit]
                print(f"  Params ({', '.join(p_names_fit)}): {', '.join(params_str)}, R²: {r2:.5f}")
            except Exception as e: print(f"  Falha no ajuste de {name}: {e}")

    best_model_nome,best_r2 = "",-np.inf
    if model_results:
        best_model_nome = max(model_results, key=lambda name: model_results[name]['R2'])
        best_r2 = model_results[best_model_nome]['R2']
    else:
        print("\n--- Nenhum modelo pôde ser ajustado. ---")

    df_summary = pd.DataFrame()
    comportamento_fluido_final_para_relatorio = "Não foi possível determinar (nenhum modelo selecionado/ajustado)."

    if best_model_nome and best_model_nome in model_results:
        print("\n\n--- Resumo do Melhor Modelo Ajustado ---")
        model_data = model_results[best_model_nome]
        params,r2_val = model_data['params'],model_data['R2']
        p_names = []
        if best_model_nome=="Newtoniano": p_names=["Viscosidade Newtoniana (Pa·s)"]
        elif best_model_nome=="Lei da Potência": p_names=["K (Pa·sⁿ)","n (-)"]
        elif best_model_nome=="Bingham": p_names=["τ₀ (Pa)","ηₚ (Pa·s)"]
        elif best_model_nome=="Herschel-Bulkley": p_names=["τ₀ (Pa)","K (Pa·sⁿ)","n (-)"]
        elif best_model_nome=="Casson": p_names=["Tensão de Escoamento Casson τ₀_cas (Pa)","Viscosidade Casson η_cas (Pa·s)"]
        else: p_names=[f"P{j+1}" for j in range(len(params))]

        n_behavior_param = np.nan
        if best_model_nome == "Lei da Potência" or best_model_nome == "Herschel-Bulkley":
            try:
                n_index_actual = p_names.index("n (-)")
                if n_index_actual != -1: n_behavior_param = params[n_index_actual]
            except ValueError: print("ALERTA: Parâmetro 'n (-)' não encontrado para classificação do comportamento.")

        comportamento_fluido_str = "N/A"
        if best_model_nome == "Newtoniano":
            comportamento_fluido_str = "Newtoniano (n = 1 por definição)"
        elif best_model_nome in ["Bingham", "Casson", "Herschel-Bulkley"]:
            tau0_val = params[0]
            if tau0_val > 1e-9:
                comportamento_fluido_str = f"Viscoplástico (τ₀ = {tau0_val:.2f} Pa)"
            else:
                comportamento_fluido_str = "Viscoplástico (tensão de escoamento τ₀ ≈ 0)"
        
        if not np.isnan(n_behavior_param):
            if np.isclose(n_behavior_param, 1.0, atol=0.05):
                comportamento_fluido_str += f" e comportamento próximo ao Newtoniano (n ≈ {n_behavior_param:.3f})" if "Viscoplástico" in comportamento_fluido_str else f"Newtoniano (n ≈ {n_behavior_param:.3f})"
            elif n_behavior_param < 1.0:
                comportamento_fluido_str += f" e Pseudoplástico (n = {n_behavior_param:.3f} < 1)" if "Viscoplástico" in comportamento_fluido_str else f"Pseudoplástico (n = {n_behavior_param:.3f} < 1)"
            else: # n_behavior_param > 1.0
                comportamento_fluido_str += f" e Dilatante (n = {n_behavior_param:.3f} > 1)" if "Viscoplástico" in comportamento_fluido_str else f"Dilatante (n = {n_behavior_param:.3f} > 1)"
        
        comportamento_fluido_final_para_relatorio = comportamento_fluido_str
        summary_dict = {"Parâmetro":[],"Valor Estimado":[],"Erro Padrão (+/-)":[]}
        summary_dict["Parâmetro"].append("Modelo Reológico Ajustado")
        summary_dict["Valor Estimado"].append(best_model_nome)
        summary_dict["Erro Padrão (+/-)"].append("N/A")
        summary_dict["Parâmetro"].append("Coeficiente de Determinação (R²)")
        summary_dict["Valor Estimado"].append(format_float_for_table(r2_val, 5))
        summary_dict["Erro Padrão (+/-)"].append("N/A")

        errors = np.full(len(params), np.nan)
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
        print(df_summary.to_string(index=False, line_width=None))

        csv_sum_f = os.path.join(output_folder, f"{timestamp_str}_resumo_melhor_modelo.csv")
        arquivos_gerados_lista.append(os.path.basename(csv_sum_f))
        try:
            if df_summary is not None and not df_summary.empty:
                df_summary.to_csv(csv_sum_f,index=False,sep=';',decimal=',', encoding='utf-8-sig')
                print(f"\nResumo salvo: {csv_sum_f}")
        except Exception as e: print(f"\nERRO CSV Resumo: {e}")

    # Salva os parâmetros de TODOS os modelos ajustados em um arquivo JSON
    if model_results:
        results_to_save = {}
        # Salva os parâmetros de TODOS os modelos ajustados
        for name, data in model_results.items():
            results_to_save[name] = {
                'params': data['params'].tolist(),
                'R2': data['R2']
            }
        
        # ADIÇÃO: Salva também os parâmetros n' e log_K_prime
        parametros_wr = {
            'n_prime': n_prime if 'n_prime' in locals() else None,
            'log_K_prime': log_K_prime if 'log_K_prime' in locals() else None
        }
        
        dados_completos_para_salvar = {
            "modelos_ajustados": results_to_save,
            "parametros_wr": parametros_wr
        }
        
        json_models_f = os.path.join(output_folder, f"{timestamp_str}_parametros_modelos.json")
        arquivos_gerados_lista.append(os.path.basename(json_models_f))
        try:
            with open(json_models_f, 'w', encoding='utf-8') as f:
                json.dump(dados_completos_para_salvar, f, indent=4)
            print(f"Parâmetros dos modelos salvos em: {json_models_f}")
        except Exception as e:
            print(f"ERRO ao salvar parâmetros dos modelos: {e}")


    print("\n\n"+"="*70+"\n--- TABELAS DE RESULTADOS --- \n"+"="*70)
    q_calc_mm3_s = np.full_like(gamma_dot_aw_an, np.nan)
    R_eff_q = np.nan
    
    # Determina o D efetivo para calcular Q_calc (mm³/s)
    if not realizar_bagley and not realizar_mooney and D_cap_mm_unico_val > 0:
        R_eff_q = D_cap_mm_unico_val/2000.0
    elif realizar_bagley and D_cap_mm_bagley_comum_val > 0 :
        R_eff_q = D_cap_mm_bagley_comum_val/2000.0

    if not np.isnan(R_eff_q) and R_eff_q > 0:
         q_calc_mm3_s = (gamma_dot_aw_an * np.pi * R_eff_q**3 / 4) * 1e9
    elif realizar_mooney and D_cap_mm_bagley_comum_val == 0.0:
        # Mooney usa D diferentes, o Q_calc não pode ser calculado de forma única a partir de gamma_dot_aw_an
        print("  INFO (Tabela): Q_calc(mm³/s) não recalculado para correção de Mooney, pois D varia.")

    # Garante que as colunas de dados brutos tenham o tamanho correto
    if len(pressoes_bar_display_tab) != num_testes_para_analise:
        pressoes_bar_display_tab = [np.nan] * num_testes_para_analise
    if len(massas_g_display_tab) != num_testes_para_analise:
        massas_g_display_tab = [np.nan] * num_testes_para_analise
    if len(tempos_s_display_tab) != num_testes_para_analise:
        # Se as correções foram feitas (Bagley/Mooney), tempos_s_display_tab não tem dados brutos.
        # Mas para capilar único, ele deve ter sido preenchido
        tempos_s_display_tab = [np.nan] * num_testes_para_analise

    D_cap_mm_display = f"{D_cap_mm_unico_val:.3f}" if not (realizar_bagley or realizar_mooney) else "Vários"
    L_cap_mm_display = f"{L_cap_mm_unico_val:.2f}" if not (realizar_bagley or realizar_mooney) else "Vários"

    df_res = pd.DataFrame({
        "Ponto": list(range(1,num_testes_para_analise+1)), "D_cap(mm)": [D_cap_mm_display]*num_testes_para_analise, "L_cap(mm)": [L_cap_mm_display]*num_testes_para_analise,
        "rho(g/cm³)": np.full(num_testes_para_analise,rho_pasta_g_cm3_fixo), 
        "t_ext(s)": tempos_s_display_tab, # MODIFICADO: Usa a lista de tempos
        "P_ext(bar)": pressoes_bar_display_tab,
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
    try: 
        df_res.to_csv(csv_f,index=False,sep=';',decimal=',',float_format='%.4f',na_rep='N/A_Corr', encoding='utf-8-sig')
        print(f"\nTabela salva: {csv_f}")
    except Exception as e: print(f"\nERRO CSV: {e}")
        
    if realizar_bagley and capilares_bagley_data_input:
        print("\n--- Gerando CSV de Dados Brutos Bagley ---")
        # ... (código original para criar e salvar a tabela de dados brutos de Bagley)
        pass
        
    if realizar_mooney and capilares_mooney_data_input:
        print("\n--- Gerando CSV de Dados Brutos Mooney ---")
        # ... (código original para criar e salvar a tabela de dados brutos de Mooney)
        pass

else:
    print("\n--- ANÁLISE INTERROMPIDA: Não há dados suficientes ou válidos para prosseguir com cálculos e modelagem. ---")
    df_res = pd.DataFrame()
    df_summary = pd.DataFrame()

# -----------------------------------------------------------------------------
# --- GERAÇÃO DE GRÁFICOS E RELATÓRIO FINAL ---
# -----------------------------------------------------------------------------
if num_testes_para_analise > 0 and len(gd_fit)>0 and model_results:
    print("\n\n"+"="*70+"\n--- GERANDO GRÁFICOS ---\n"+"="*70)
    min_gp_val = np.min(gd_fit[gd_fit > 1e-9]) if np.any(gd_fit > 1e-9) else 1e-3
    max_gp_val = np.max(gd_fit) if np.any(gd_fit > 1e-9) else 1.0
    min_gp, max_gp = max(1e-9, min_gp_val * 0.5), max_gp_val * 1.5
    gd_plot = np.geomspace(min_gp, max_gp, 200) if max_gp > min_gp else np.array([min_gp, min_gp*10])

    # --- Gráfico 1: Curva de Fluxo (com destaque) ---
    fig1,ax1=plt.subplots(figsize=(10,7))
    ax1.scatter(gamma_dot_w_an_wr[valid_fit],tau_w_an[valid_fit],label='Dados Experimentais Processados',c='k',marker='o',s=60,zorder=10)
    if len(gd_plot)>0:
        for n_model_name,d_model_data in model_results.items():
            try:
                tau_plot_model = models[n_model_name](gd_plot,*d_model_data['params'])
                
                # --- LÓGICA DE DESTAQUE ADICIONADA ---
                if n_model_name == best_model_nome:
                    # Plota a linha do melhor modelo com destaque (mais grossa, vermelha e na frente)
                    ax1.plot(gd_plot, tau_plot_model, 
                             label=fr'**Melhor Modelo: {n_model_name}** (R²={d_model_data["R2"]:.4f})', 
                             linewidth=3.5, linestyle='--', color='red', zorder=20)
                else:
                    # Plota as outras linhas de forma mais sutil
                    ax1.plot(gd_plot, tau_plot_model, 
                             label=fr'Modelo {n_model_name} (R²={d_model_data["R2"]:.4f})', 
                             linewidth=2, alpha=0.6)
            except Exception as e_plot_model:
                print(f"  Aviso ao plotar modelo {n_model_name}: {e_plot_model}")
        ax1.set_xlabel("Taxa de Cisalhamento Corrigida (" + r"$\dot{\gamma}_w$" + ", s⁻¹)")
        ax1.set_ylabel("Tensão de Cisalhamento na Parede Corrigida (" + r"$\tau_w$" + ", Pa)")
        ax1.set_title("Curva de Fluxo: Tensão de Cisalhamento vs. Taxa de Cisalhamento")
        ax1.legend(); ax1.grid(True,which="both",ls="--"); ax1.set_xscale('log'); ax1.set_yscale('log'); fig1.tight_layout()
        f1_name = os.path.join(output_folder,f"{timestamp_str}_curva_fluxo.png"); arquivos_gerados_lista.append(os.path.basename(f1_name))
        try: fig1.savefig(f1_name,dpi=300); print(f"Gráfico Curva Fluxo salvo: {f1_name}")
        except Exception as e: print(f"ERRO ao salvar Curva Fluxo: {e}")

    # --- Gráfico 2: Determinação de n' ---
    if num_testes_para_analise > 1 and 'n_prime' in locals() and not np.isclose(n_prime, 1.0, atol=0.001) and 'log_K_prime' in locals() and not np.isnan(log_K_prime):
        valid_log_np = (tau_w_an > 0) & (gamma_dot_aw_an > 0) & (~np.isnan(tau_w_an)) & (~np.isnan(gamma_dot_aw_an))
        if np.sum(valid_log_np) > 1:
            log_t_p,log_g_aw_p = np.log(tau_w_an[valid_log_np]),np.log(gamma_dot_aw_an[valid_log_np])
            fig2,ax2=plt.subplots(figsize=(10,7))
            ax2.scatter(log_g_aw_p,log_t_p,label='Dados Experimentais ln(γ̇aw) vs ln(τw)',c='r',marker='x',s=60)
            if len(log_g_aw_p)>1:
                min_lg,max_lg = np.min(log_g_aw_p),np.max(log_g_aw_p)
                if max_lg>min_lg: log_g_line = np.linspace(min_lg,max_lg,50); ax2.plot(log_g_line,n_prime*log_g_line+log_K_prime,'--',c='b',lw=2,label=fr'Ajuste Linear (n\'={n_prime:.3f})')
            ax2.set_xlabel("ln(Taxa de Cis. Apar. na Parede) (ln(γ̇aw))")
            ax2.set_ylabel("ln(Tensão de Cis. na Parede) (ln(τw))")
            ax2.set_title("Determinação de n' (Índice da Lei de Potência Aparente)")
            ax2.legend(); ax2.grid(True,which="both",ls="--"); fig2.tight_layout()
            f2_name = os.path.join(output_folder,f"{timestamp_str}_n_prime.png"); arquivos_gerados_lista.append(os.path.basename(f2_name))
            try: fig2.savefig(f2_name,dpi=300); print(f"Gráfico n' salvo: {f2_name}")
            except Exception as e: print(f"ERRO ao salvar n': {e}")

    # --- Gráfico 3: Curva de Viscosidade ---
    fig3,ax3=plt.subplots(figsize=(10,7))
    valid_eta = ~np.isnan(eta_true_an) & (gamma_dot_w_an_wr > 0) & (eta_true_an > 0) & (~np.isinf(eta_true_an))
    if np.any(valid_eta): ax3.scatter(gamma_dot_w_an_wr[valid_eta],eta_true_an[valid_eta],label='Viscosidade Real Experimental (η)',c='g',marker='s',s=60,zorder=10)
    if len(gd_plot)>0:
        for n_model_name,d_model_data in model_results.items():
            try:
                tau_m = models[n_model_name](gd_plot,*d_model_data['params'])
                eta_m = tau_m/gd_plot
                if n_model_name=="Newtoniano": eta_m = np.full_like(gd_plot,d_model_data['params'][0])
                ax3.plot(gd_plot, eta_m, label=fr'Modelo {n_model_name} ($\eta$)', lw=2.5, alpha=0.8)
            except Exception as e_plot_model_eta: print(f"  Aviso ao plotar modelo {n_model_name}: {e_plot_model_eta}")
    ax3.set_xlabel("Taxa de Cisalhamento Corrigida (γ̇w, s⁻¹)")
    ax3.set_ylabel("Viscosidade Real (η, Pa·s)")
    ax3.set_title("Viscosidade Real (η) vs. Taxa de Cisalhamento Corrigida (γ̇w)")
    ax3.legend(); ax3.grid(True,which="both",ls="--"); ax3.set_xscale('log'); ax3.set_yscale('log'); fig3.tight_layout()
    f3_name = os.path.join(output_folder,f"{timestamp_str}_curva_viscosidade.png"); arquivos_gerados_lista.append(os.path.basename(f3_name))
    try: fig3.savefig(f3_name,dpi=300); print(f"Gráfico Viscosidade salvo: {f3_name}")
    except Exception as e: print(f"ERRO ao salvar Viscosidade: {e}")

    # --- Gráfico 4: Pressão vs Viscosidade (Apenas para capilar único sem correções) ---
    if not realizar_bagley and not realizar_mooney and not calibracao_aplicada:
        pressoes_bar_np_plot = np.array(pressoes_bar_display_tab, dtype=float)
        if len(pressoes_bar_np_plot) == len(eta_true_an):
            valid_pv = (~np.isnan(eta_true_an))&(~np.isnan(pressoes_bar_np_plot))&(eta_true_an > 0)&(pressoes_bar_np_plot > 0)
            if np.any(valid_pv):
                P_Pa_plot, eta_plot = pressoes_bar_np_plot[valid_pv]*1e5, eta_true_an[valid_pv]
                fig4,ax4=plt.subplots(figsize=(10,7))
                ax4.plot(P_Pa_plot,eta_plot,label='Viscosidade Real Experimental', color='purple',marker='D', linestyle='', linewidth=0, markersize=8, zorder=10)
                
                # NOVA ADIÇÃO: Curva do melhor modelo para comparação
                if model_results and best_model_nome and len(gd_plot) > 0:
                    try:
                        # Calcula τ e η do modelo para a mesma faixa de γ̇
                        best_model_data = model_results[best_model_nome]
                        tau_modelo = models[best_model_nome](gd_plot, *best_model_data['params'])
                        
                        # Calcula viscosidade do modelo (η = τ/γ̇)
                        if best_model_nome == "Newtoniano":
                            eta_modelo = np.full_like(gd_plot, best_model_data['params'][0])
                        else:
                            eta_modelo = tau_modelo / gd_plot
                        
                        # Calcula pressão correspondente para cada γ̇ do modelo
                        # P = τ * 2L/R (simplificado, assumindo mesma geometria)
                        R_cap_m = D_cap_mm_unico_val / 2000  # raio em metros
                        L_cap_m = L_cap_mm_unico_val / 1000   # comprimento em metros
                        P_modelo_Pa = tau_modelo * (2 * L_cap_m / R_cap_m)
                        
                        # Filtra valores válidos do modelo
                        valid_modelo = (P_modelo_Pa > 0) & (eta_modelo > 0) & (~np.isnan(eta_modelo)) & (~np.isinf(eta_modelo))
                        
                        if np.any(valid_modelo):
                            ax4.plot(P_modelo_Pa[valid_modelo], eta_modelo[valid_modelo], 
                                    label=f'Modelo {best_model_nome}', 
                                    color='red', linestyle='-', linewidth=2.5, alpha=0.8, zorder=5)
                    except Exception as e_plot_modelo_p:
                        print(f"  Aviso: Não foi possível plotar curva do modelo em P vs η: {e_plot_modelo_p}")
                
                ax4.set_xlabel("Pressao Total Aplicada (ΔPtotal, Pa)")
                ax4.set_ylabel("Viscosidade Real (η, Pa·s)")
                ax4.set_title("Pressao Aplicada vs. Viscosidade Real (Capilar Unico s/ Correcoes)")
                ax4.legend(); ax4.grid(True,which="both",ls="--"); ax4.set_xscale('linear'); ax4.set_yscale('linear'); fig4.tight_layout()
                f4_name = os.path.join(output_folder,f"{timestamp_str}_pressao_vs_viscosidade.png"); arquivos_gerados_lista.append(os.path.basename(f4_name))
                try: fig4.savefig(f4_name,dpi=300); print(f"Gráfico P vs Visc salvo: {f4_name}")
                except Exception as e: print(f"ERRO ao Salvar P vs Visc: {e}")

    # --- Gráfico 5: Comparativo de Viscosidades ---
    fig5, ax5 = plt.subplots(figsize=(10, 7))
    valid_apparent_idx = (gamma_dot_aw_an > 0) & (~np.isnan(eta_a_an)) & (eta_a_an > 0) & (~np.isinf(eta_a_an))
    if np.any(valid_apparent_idx):
        ax5.plot(gamma_dot_aw_an[valid_apparent_idx], eta_a_an[valid_apparent_idx],
                    label=r'Viscosidade Aparente ($\eta_a$ vs $\dot{\gamma}_{aw}$)',
                    marker='o', linestyle='--', color='blue', alpha=0.7, linewidth=1.5)
    if np.any(valid_eta):
         ax5.plot(gamma_dot_w_an_wr[valid_eta],eta_true_an[valid_eta],
                     label=r'Viscosidade Real ($\eta$ vs $\dot{\gamma}_w$)',
                     marker='s', linestyle='', color='green', alpha=0.7, linewidth=0, markersize=6, zorder=5)
    
    # NOVA ADIÇÃO: Curva do melhor modelo para comparação
    if model_results and best_model_nome and len(gd_plot) > 0:
        try:
            # Calcula τ e η do modelo para a mesma faixa de γ̇
            best_model_data = model_results[best_model_nome]
            tau_modelo = models[best_model_nome](gd_plot, *best_model_data['params'])
            
            # Calcula viscosidade do modelo (η = τ/γ̇)
            if best_model_nome == "Newtoniano":
                eta_modelo = np.full_like(gd_plot, best_model_data['params'][0])
            else:
                eta_modelo = tau_modelo / gd_plot
            
            # Filtra valores válidos do modelo
            valid_modelo_eta = (eta_modelo > 0) & (~np.isnan(eta_modelo)) & (~np.isinf(eta_modelo))
            
            if np.any(valid_modelo_eta):
                ax5.plot(gd_plot[valid_modelo_eta], eta_modelo[valid_modelo_eta], 
                        label=f'Modelo {best_model_nome} (η)', 
                        color='red', linestyle='-', linewidth=2.5, alpha=0.85, zorder=6)
        except Exception as e_plot_modelo_eta:
            print(f"  Aviso: Não foi possível plotar curva do modelo em Comparativo: {e_plot_modelo_eta}")
    
    ax5.set_xlabel("Taxa de Cisalhamento (s⁻¹)")
    ax5.set_ylabel("Viscosidade (Pa·s)")
    ax5.set_title("Comparativo: Viscosidade Aparente vs. Viscosidade Real vs. Modelo")
    ax5.legend(); ax5.grid(True,which="both",ls="--"); ax5.set_xscale('log'); ax5.set_yscale('log'); fig5.tight_layout()
    f5_name = os.path.join(output_folder,f"{timestamp_str}_comparativo_viscosidades.png"); arquivos_gerados_lista.append(os.path.basename(f5_name))
    try: fig5.savefig(f5_name,dpi=300); print(f"Gráfico Comparativo Viscosidades salvo: {f5_name}")
    except Exception as e: print(f"ERRO ao salvar Comparativo Viscosidades: {e}")

    print("\nFeche as janelas dos gráficos para finalizar a execução."); plt.show()
else:
    print("\n--- Gráficos não gerados (sem dados válidos ou modelos ajustados para plotagem). ---")


# --- CHAMADA FINAL PARA GERAR O RELATÓRIO DE TEXTO (ATUALIZADA) ---
metodo_entrada_str_relatorio = "Manual"
if metodo_entrada == "2": metodo_entrada_str_relatorio = "Arquivo CSV"
elif metodo_entrada == "3": metodo_entrada_str_relatorio = "Arquivo(s) JSON"

# MODIFICADO: Passa a informação correta sobre o tempo para o relatório
if (len(tempos_s_display_tab) > 1 and len(set(tempos_s_display_tab)) > 1):
    tempo_info_relatorio = "Variável (ver tabela)" 
elif 'tempo_extrusao_fixo_s_val' in locals() and tempo_extrusao_fixo_s_val is not None:
    tempo_info_relatorio = tempo_extrusao_fixo_s_val
else:
    tempo_info_relatorio = 0.0

gerar_relatorio_texto(
    timestamp_str,
    rho_pasta_g_cm3_fixo if 'rho_pasta_g_cm3_fixo' in locals() and rho_pasta_g_cm3_fixo is not None else 0.0,
    tempo_info_relatorio,
    metodo_entrada_str_relatorio,
    _json_files_resumo if '_json_files_resumo' in locals() else [],
    _csv_path_resumo if '_csv_path_resumo' in locals() else "N/A",
    realizar_bagley,
    D_cap_mm_bagley_comum_val if realizar_bagley else "N/A",
    bagley_capilares_L_mm_info if realizar_bagley else [],
    realizar_mooney,
    L_cap_mm_mooney_comum_val if realizar_mooney else "N/A",
    mooney_capilares_D_mm_info if realizar_mooney else [],
    D_cap_mm_unico_val if not (realizar_bagley or realizar_mooney) else "N/A",
    L_cap_mm_unico_val if not (realizar_bagley or realizar_mooney) else "N/A",
    caminho_calibracao_usada,
    df_res if 'df_res' in locals() else pd.DataFrame(),
    df_summary if 'df_summary' in locals() else pd.DataFrame(),
    best_model_nome if 'best_model_nome' in locals() else "",
    comportamento_fluido_final_para_relatorio if 'comportamento_fluido_final_para_relatorio' in locals() else "N/A",
    arquivos_gerados_lista,
    output_folder,
    fator_calibracao_empirico
)

print("\n"+"="*70+"\n--- FIM DA ANÁLISE ---\n"+"="*70)
