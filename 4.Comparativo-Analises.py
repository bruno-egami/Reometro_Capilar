# -----------------------------------------------------------------------------
# SCRIPT PARA COMPARAÇÃO E ANÁLISE DE DADOS REOLÓGICOS (MODIFICADO)
# --- VERSÃO COM AJUSTE AUTOMÁTICO DE MODELOS E SUPORTE A DADOS ESTATÍSTICOS ---
# --- NOVIDADE: CÁLCULO DE FATOR DE CALIBRAÇÃO EMPÍRICO ENTRE DUAS AMOSTRAS ---
# --- SUPORTE: PLOTAGEM OTIMIZADA (SEM BARRAS DE ERRO, USO DE CORES TAB10) ---
# --- ATUALIZAÇÃO: NOMES PERSONALIZADOS E RELATÓRIOS COMPLETOS (DADOS E MODELOS) ---
# -----------------------------------------------------------------------------

import os
import glob
import json
import re
import inspect # <--- ADICIONADO
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from scipy.interpolate import interp1d
from scipy.stats import linregress 

# Tenta importar as bibliotecas necessárias para o ajuste de curvas.
try:
    from scipy.optimize import curve_fit
    from sklearn.metrics import r2_score
    MODEL_FITTING_ENABLED = True
except ImportError:
    MODEL_FITTING_ENABLED = False
    print("AVISO: Bibliotecas 'scipy' e 'scikit-learn' não encontradas.")
    print("       O script não poderá ajustar novos modelos para os dados importados.")


# --- CONFIGURAÇÃO DE PASTAS ---
CAMINHO_BASE_INDIVIDUAL = "resultados_analise_reologica"
CAMINHO_BASE_ESTATISTICO = "resultados_analise_estatistica"
CAMINHO_BASE_COMPARATIVOS = "comparativo_analises"
CAMINHO_BASE_ROTACIONAL = "resultados_processados_interativo"

# --- PADRÕES DE NOMES DE ARQUIVOS ---
STATISTICAL_CSV_PATTERN = '*_resultados_estatisticos.csv'
INDIVIDUAL_CSV_PATTERN = '*_resultados_reologicos.csv'
PARAM_JSON_PATTERN = '*_parametros_modelos.json'
ROTACIONAL_CSV_PATTERN = '*_processado.csv'


# -----------------------------------------------------------------------------
# --- DEFINIÇÕES DOS MODELOS REOLÓGICOS (Consistentes com o Script 2) ---
# -----------------------------------------------------------------------------

def model_newtonian(gd, eta): return eta * gd
def model_power_law(gd, K_pl, n_pl): return K_pl * np.power(np.maximum(gd, 1e-9), n_pl)
def model_bingham(gd, t0, ep): return t0 + ep * gd
def model_hb(gd, t0, K_hb, n_hb): return t0 + K_hb * np.power(np.maximum(gd, 1e-9), n_hb)
def model_casson(gd, tau0_cas, eta_cas):
    sqrt_tau0 = np.sqrt(np.maximum(tau0_cas, 0))
    sqrt_eta_cas_val = np.sqrt(np.maximum(eta_cas, 1e-9))
    sqrt_gd_val = np.sqrt(np.maximum(gd, 1e-9))
    return (sqrt_tau0 + sqrt_eta_cas_val * sqrt_gd_val)**2

MODELS = {
    "Newtoniano": (model_newtonian, ([1e-9], [np.inf])),
    "Lei da Potência": (model_power_law, ([1e-9, 1e-9], [np.inf, 5.0])),
    "Bingham": (model_bingham, ([0, 1e-9], [np.inf, np.inf])),
    "Herschel-Bulkley": (model_hb, ([0, 1e-9, 1e-9], [np.inf, np.inf, 5.0])),
    "Casson": (model_casson, ([0, 1e-9], [np.inf, np.inf]))
}

# (NOVO) Mapeamento de nomes de parâmetros para o relatório de modelos
PARAM_NAMES_MAP = {
    "Newtoniano": ["eta (Pa.s)"],
    "Lei da Potência": ["K (Pa.s^n)", "n (-)"],
    "Bingham": ["t0 (Pa)", "ep (Pa.s)"],
    "Herschel-Bulkley": ["t0 (Pa)", "K (Pa.s^n)", "n (-)"],
    "Casson": ["t0 (Pa)", "eta_cas (Pa.s)"]
}


# -----------------------------------------------------------------------------
# --- FUNÇÕES DE CARREGAMENTO, SELEÇÃO E AJUSTE ---
# -----------------------------------------------------------------------------

def selecionar_pastas_analise(caminho_base_indiv, caminho_base_stat, caminho_base_rotacional):
    """
    Lista as análises disponíveis em todos os diretórios de resultados e solicita ao usuário.
    """
    print("="*70)
    print("--- SELECIONAR ANÁLISES PARA COMPARAÇÃO ---")
    print("="*70)
    
    pastas_disponiveis = {}
    
    # 1. Carrega sessões de Reômetro Capilar (Estatístico/Individual)
    def listar_e_mapear_capilar(caminho_base, tipo):
        if not os.path.exists(caminho_base): return
        pastas = sorted([d for d in os.listdir(caminho_base) if os.path.isdir(os.path.join(caminho_base, d))])
        for pasta in pastas:
            # Garante que a pasta tem um CSV de resultados
            search_pattern = STATISTICAL_CSV_PATTERN if tipo == 'Estatístico' else INDIVIDUAL_CSV_PATTERN
            arquivos = glob.glob(os.path.join(caminho_base, pasta, search_pattern))
            if arquivos:
                if pasta not in pastas_disponiveis or tipo == 'Estatístico': # Prioriza estatístico se houver duplicidade
                     pastas_disponiveis[pasta] = {'caminho': os.path.join(caminho_base, pasta), 'tipo': tipo}

    listar_e_mapear_capilar(caminho_base_stat, 'Estatístico')
    listar_e_mapear_capilar(caminho_base_indiv, 'Individual')

    # 2. Carrega arquivos do Reômetro Rotacional (Script 5)
    if os.path.exists(CAMINHO_BASE_ROTACIONAL):
        arquivos_rot = glob.glob(os.path.join(CAMINHO_BASE_ROTACIONAL, ROTACIONAL_CSV_PATTERN))
        for arq_caminho in arquivos_rot:
            # O nome da sessão Rotacional é o nome do arquivo CSV sem a extensão
            nome_arq_base = os.path.basename(arq_caminho).replace(ROTACIONAL_CSV_PATTERN.replace('*', ''), '').replace('.csv', '')
            session_name = f"ROTACIONAL_{nome_arq_base}"
            # O caminho aqui é o CAMINHO DO ARQUIVO CSV, não da pasta
            pastas_disponiveis[session_name] = {'caminho': arq_caminho, 'tipo': 'Rotacional'}


    if not pastas_disponiveis:
        print(f"ERRO: Nenhuma análise encontrada em nenhuma pasta de resultados.")
        return None, None

    pastas_ordenadas = sorted(pastas_disponiveis.keys(), reverse=True)
    
    print("Análises disponíveis:")
    for i, nome_sessao in enumerate(pastas_ordenadas):
        origem = pastas_disponiveis[nome_sessao]['tipo']
        # Mostra o nome do arquivo/pasta para facilitar a escolha
        print(f"  {i+1}: {nome_sessao} (Origem: {origem})")
    
    pastas_selecionadas = []
    nomes_selecionados = []
    
    while True:
        try:
            escolha_str = input("\nDigite os NÚMEROS das análises a comparar, separados por vírgula (ex: 1, 3, 4): ")
            indices_escolhidos = [int(i.strip()) - 1 for i in escolha_str.split(',') if i.strip().isdigit()]
            
            if not indices_escolhidos:
                 print("ERRO: Nenhuma análise foi selecionada.")
                 continue

            if any(i < 0 or i >= len(pastas_ordenadas) for i in indices_escolhidos):
                raise ValueError("Um ou mais números estão fora do intervalo válido.")
                
            for i in indices_escolhidos:
                nome_sessao = pastas_ordenadas[i]
                info = pastas_disponiveis[nome_sessao]
                pastas_selecionadas.append(info) # Passa o dicionário completo (caminho e tipo)
                nomes_selecionados.append(nome_sessao)
            
            break
            
        except ValueError as e:
            print(f"ERRO: Entrada inválida. ({e})")
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")
            return None, None
            
    print("\nAnálises selecionadas para comparação:")
    for nome in nomes_selecionados:
        print(f"  - {nome}")
            
    return pastas_selecionadas, nomes_selecionados

def ajustar_modelos_reologicos(df, col_gamma, col_tau):
    """
    Ajusta todos os modelos reológicos aos dados, usando limites para garantir
    parâmetros fisicamente realistas. Retorna os resultados e o melhor modelo.
    """
    if not MODEL_FITTING_ENABLED:
        return None, None

    x_data = df[col_gamma].values
    y_data = df[col_tau].values
    
    modelos_ajustados = {}
    
    for name, (model_func, bounds) in MODELS.items():
        try:
            import inspect
            param_names = list(inspect.signature(model_func).parameters.keys())[1:]
            
            # Chute inicial mais inteligente, para garantir estabilidade do ajuste
            p0 = [1.0] * len(param_names)
            tau0_g = max(1e-3, np.min(y_data) / 2) if len(y_data) > 0 else 0.1
            eta_a_g = np.mean(y_data / x_data) if len(x_data) > 0 else 0.1
            n_g = 0.5 # Chute inicial para n
            
            if name=="Newtoniano": p0=[eta_a_g]
            elif name=="Lei da Potência": p0 = [eta_a_g, n_g] 
            elif name=="Bingham": p0 = [tau0_g, eta_a_g]
            elif name=="Herschel-Bulkley": p0 = [tau0_g, eta_a_g, n_g]
            elif name=="Casson": p0 = [tau0_g, eta_a_g]

            # Usa limites (bounds) para forçar parâmetros positivos e mais estáveis.
            params, _ = curve_fit(model_func, x_data, y_data, p0=p0, bounds=bounds, maxfev=10000)
            
            y_pred = model_func(x_data, *params)
            r2 = r2_score(y_data, y_pred)
            
            if r2 < 0:
                continue

            modelos_ajustados[name] = {
                'params': list(params),
                'param_names': param_names, # Salva os nomes dos parâmetros
                'R2': r2
            }

        except Exception as e:
            pass

    if not modelos_ajustados:
        return None, None

    best_model_name = max(modelos_ajustados, key=lambda name: modelos_ajustados[name]['R2'])
    
    modelo_info = {
        "name": best_model_name,
        "params": modelos_ajustados[best_model_name]['params']
    }
    
    # Retorna TODOS os modelos ajustados, e a info do MELHOR
    return modelos_ajustados, modelo_info

def carregar_csv_rotacional(caminho_arquivo_csv):
    """
    Carrega e padroniza o CSV gerado pelo script 5 (Reômetro Rotacional).
    Retorna o DataFrame padronizado.
    """
    try:
        df = pd.read_csv(caminho_arquivo_csv, sep=';', decimal=',', encoding='utf-8-sig')
        df.columns = df.columns.str.strip()
        
        # Garante que as colunas existam e sejam renomeadas para o padrão
        df = df.rename(columns={
            'Taxa de Cisalhamento (s-1)': 'γ̇w (s⁻¹)',
            'Tensao de Cisalhamento (Pa)': 'τw (Pa)',
            'Viscosidade (Pa.s)': 'η (Pa·s)'
        })
        
        # Remove NaN e valores nulos
        df.dropna(subset=['γ̇w (s⁻¹)', 'τw (Pa)', 'η (Pa·s)'], inplace=True)
        df = df[(df['γ̇w (s⁻¹)'] > 0) & (df['τw (Pa)'] > 0)]
        
        # Rotacional não possui STD
        df['STD_τw (Pa)'] = 0.0
        df['STD_γ̇w (s⁻¹)'] = 0.0
        
        return df

    except Exception as e:
        print(f"ERRO ao ler o arquivo Rotacional '{os.path.basename(caminho_arquivo_csv)}': {e}")
        return None

def carregar_dados_completos(info_analise):
    """
    Carrega dados de uma análise (Capilar ou Rotacional) e padroniza o DataFrame.
    (MODIFICADO) Retorna: (df, modelo_info_best, modelos_ajustados_all)
    """
    caminho_pasta_ou_arquivo = info_analise['caminho']
    tipo = info_analise['tipo']
    
    df = None
    modelo_info_best = None
    modelos_ajustados_all = None

    if tipo == 'Rotacional':
        df = carregar_csv_rotacional(caminho_pasta_ou_arquivo)
    
    # Lógica de carregamento Capilar (Individual ou Estatístico)
    elif tipo in ['Individual', 'Estatístico']:
        caminho_csv_usado = None
        
        # Colunas de STD (para carregar se estiverem presentes)
        col_std_tau = 'STD_τw (Pa)'
        col_std_gamma = 'STD_γ̇w (s⁻¹)'
        
        if tipo == 'Estatístico':
            arquivos_stat = glob.glob(os.path.join(caminho_pasta_ou_arquivo, STATISTICAL_CSV_PATTERN))
            if arquivos_stat:
                caminho_csv_usado = arquivos_stat[0]
                col_gamma, col_tau, col_eta = 'γ̇w_MEDIA(s⁻¹)', 'τw_MEDIA(Pa)', 'η_MEDIA(Pa·s)'
        
        if caminho_csv_usado is None:
            arquivos_indiv = glob.glob(os.path.join(caminho_pasta_ou_arquivo, INDIVIDUAL_CSV_PATTERN))
            if arquivos_indiv:
                caminho_csv_usado = arquivos_indiv[0]
                col_gamma, col_tau, col_eta = 'γ̇w (s⁻¹)', 'τw (Pa)', 'η (Pa·s)'
                # No modo Individual, o STD é 0
                col_std_tau = 'STD_τw (Pa)' # Coluna dummy
                col_std_gamma = 'STD_γ̇w (s⁻¹)' # Coluna dummy


        if not caminho_csv_usado:
            return None, None, None
        
        # Carregamento do CSV Capilar
        try:
            df = pd.read_csv(caminho_csv_usado, sep=';', decimal=',', encoding='utf-8-sig')
            df.columns = df.columns.str.strip()
            
            # (NOVO) Preserva todas as colunas, mas garante as principais
            colunas_principais = [col_gamma, col_tau, col_eta]
            
            for col in colunas_principais:
                if col not in df.columns:
                    if col == col_tau and col_eta in df.columns and col_gamma in df.columns:
                        df[col_tau] = df[col_eta] * df[col_gamma]
                    else:
                        raise KeyError(f"O CSV capilar deve conter as colunas '{col_gamma}', '{col_tau}' e '{col_eta}'.")
            
            # Converte apenas as colunas principais para numérico
            for col in colunas_principais:
                if pd.api.types.is_string_dtype(df[col]):
                    df[col] = df[col].str.replace(',', '.', regex=False).astype(float)
                else:
                    df[col] = pd.to_numeric(df[col])
            
            # Tenta carregar as colunas STD se elas existirem (caso estatístico)
            if col_std_tau in df.columns:
                df['STD_τw (Pa)'] = df[col_std_tau]
                df['STD_γ̇w (s⁻¹)'] = df[col_std_gamma]
            else:
                # Se não for estatístico (Individual), o STD é zero
                df['STD_τw (Pa)'] = 0.0
                df['STD_γ̇w (s⁻¹)'] = 0.0

            # Renomeia para o padrão (criando novas colunas)
            df['γ̇w (s⁻¹)'], df['τw (Pa)'], df['η (Pa·s)'] = df[col_gamma], df[col_tau], df[col_eta]
            df.dropna(subset=['γ̇w (s⁻¹)', 'τw (Pa)', 'η (Pa·s)'], inplace=True)
            df = df[df['γ̇w (s⁻¹)'] > 0]
            
        except Exception as e:
            print(f"ERRO ao ler o arquivo CSV capilar '{os.path.basename(caminho_csv_usado)}': {e}")
            return None, None, None
    
    # --- Ajuste de Modelo (Comum para todos os tipos de dados) ---
    if df is not None and not df.empty:
        # Carregamento do Modelo Capilar (apenas se for uma pasta Capilar)
        if tipo in ['Individual', 'Estatístico']:
             padrao_json = os.path.join(caminho_pasta_ou_arquivo, PARAM_JSON_PATTERN)
             arquivos_json = glob.glob(padrao_json)
             if arquivos_json:
                 try:
                    with open(arquivos_json[0], 'r', encoding='utf-8') as f:
                        params_data = json.load(f)

                    # (MODIFICADO) Carrega TODOS os modelos
                    modelos_ajustados_all = params_data.get("modelos_ajustados", {})
                    
                    if modelos_ajustados_all:
                        # Identifica o melhor modelo
                        best_model_name = max(modelos_ajustados_all, key=lambda name: modelos_ajustados_all[name].get('R2', 0))
                        
                        # (NOVO) Garante 'param_names' se não veio do JSON
                        for name, details in modelos_ajustados_all.items():
                            if 'param_names' not in details:
                                # Inferir nomes de parâmetros (necessário para compatibilidade com JSONs antigos)
                                sig = list(inspect.signature(MODELS[name][0]).parameters.keys())[1:]
                                modelos_ajustados_all[name]['param_names'] = sig


                        modelo_info_best = { 
                            "name": best_model_name, 
                            "params": modelos_ajustados_all[best_model_name]['params'] 
                        }
                 except Exception as e:
                     print(f"Aviso: Não foi possível carregar o JSON de parâmetros: {e}")
                     pass # Continua para tentar o ajuste ao vivo

        # Se falhou (JSON não existe) ou se for Rotacional, tenta ajustar ao vivo
        if modelos_ajustados_all is None and MODEL_FITTING_ENABLED:
            modelos_ajustados_all, modelo_info_best = ajustar_modelos_reologicos(df, 'γ̇w (s⁻¹)', 'τw (Pa)')
            
    return df, modelo_info_best, modelos_ajustados_all


def criar_nome_curto(nome_completo_pasta):
    """Cria um nome mais curto e limpo para a legenda do gráfico."""
    # Remove prefixos
    nome = re.sub(r'_(?:ROTACIONAL)_.+', '', nome_completo_pasta)
    # Remove timestamp
    nome = re.sub(r'_\d{8}_\d{6}$', '', nome)
    return nome

# -----------------------------------------------------------------------------
# --- FUNÇÃO DE PLOTAGEM ---
# -----------------------------------------------------------------------------

def plotar_comparativo_com_modelo(dados_analises, coluna_y, coluna_x, titulo, ylabel, xlabel, usar_escala_log=True, fcal_info=None):
    """
    Cria e retorna uma figura do Matplotlib com a comparação de múltiplas análises.
    (MODIFICADO) Usa 'modelo_best' do dicionário 'dados_analises'
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    plt.style.use('seaborn-v0_8-whitegrid')
    
    cores = plt.get_cmap('tab10') 
    marcadores = ['o', 's', '^', 'D', 'v', 'P', '*', 'X']
    
    min_x_vis, max_x_vis = [], []
    min_y_vis, max_y_vis = [], []
    all_y_points_linear = []

    # 'dados_analises' agora contém os nomes personalizados como chaves
    for i, (nome_analise, dados) in enumerate(dados_analises.items()):
        df = dados.get('df') # Usa .get() para segurança
        modelo = dados.get('modelo_best') # <-- MUDANÇA AQUI
        cor = cores(i % 10) 
        
        # (NOVO) Destaque para a curva média
        is_media = "Média" in nome_analise
        
        if df is None or df.empty:
            continue
        has_std_tau = 'STD_τw (Pa)' in df.columns and np.any(df['STD_τw (Pa)'] > 1e-9)
        has_std_gamma = 'STD_γ̇w (s⁻¹)' in df.columns and np.any(df['STD_γ̇w (s⁻¹)'] > 1e-9)
        
        
        if df is not None and not df.empty:
            
            x_data, y_data = df[coluna_x].values, df[coluna_y].values
            
            x_data, y_data = df[coluna_x].values, df[coluna_y].values
            # --- FIM DA CORREÇÃO ---
            
            if is_media:
                 # Plota a média com destaque
                 ax.plot(x_data, y_data, linestyle='--', color='black', alpha=1.0, linewidth=3, label=nome_analise, zorder=15)
            else:
                # Plota pontos de dados normais
                ax.scatter(x_data, y_data, marker=marcadores[i % len(marcadores)], color=cor, label=nome_analise, s=50, zorder=10, alpha=0.9)
                ax.plot(x_data, y_data, linestyle='-', color=cor, alpha=0.7, linewidth=2)

            if (has_std_tau or has_std_gamma) and not is_media: # Não plota STD para a média (já é 0)
                
                if coluna_y == 'η (Pa·s)':
                    std_tau = df['STD_τw (Pa)'].values
                    # --- CORREÇÃO DE BUG (SyntaxError) ---
                    std_gamma = df['STD_γ̇w (s⁻¹)'].values 
                    # --- FIM DA CORREÇÃO ---
                    eta = df['η (Pa·s)'].values
                    
                    std_eta = np.zeros_like(eta)
                    valid_calc = (x_data > 1e-9) & (y_data > 1e-9) & (std_tau >= 0) & (std_gamma >= 0)
                    
                    if np.any(valid_calc):
                        std_eta[valid_calc] = eta[valid_calc] * np.sqrt(
                            (std_tau[valid_calc] / y_data[valid_calc])**2 + 
                            (std_gamma[valid_calc] / x_data[valid_calc])**2
                        )
                    y_err = std_eta
                    x_err = std_gamma
                    
                else: # Curva de Fluxo
                    y_err = df['STD_τw (Pa)'].values
                    x_err = df['STD_γ̇w (s⁻¹)'].values
                
                pass # Plotagem de barras de erro desativada
            
            # Plota a Curva do Modelo (Linha Pontilhada)
            if modelo:
                nome_modelo = modelo['name']
                params = modelo['params']
                
                min_gd_data = df[coluna_x].min()
                max_gd_data = df[coluna_x].max()
                gd_plot = np.geomspace(max(1e-9, min_gd_data * 0.5), max_gd_data * 1.5, 100)

                if nome_modelo in MODELS:
                    model_func = MODELS[nome_modelo][0]
                    try:
                        y_pred_model = model_func(gd_plot, *params)
                        
                        if coluna_y == 'η (Pa·s)':
                            eta_m = y_pred_model / np.maximum(gd_plot, 1e-9)
                            
                            if nome_modelo in ["Herschel-Bulkley", "Bingham", "Casson"]:
                                clip_start_gamma = max(1e-4, min_gd_data * 0.1) 
                                clip_start_index_safe = np.argmin(np.abs(gd_plot - clip_start_gamma))
                                gd_plot_safe = gd_plot[clip_start_index_safe:]
                                eta_m_safe = eta_m[clip_start_index_safe:]
                                
                                ax.plot(gd_plot_safe, eta_m_safe, 
                                        color=cor, 
                                        linestyle=':', 
                                        linewidth=2.5, 
                                        alpha=0.9,
                                        label=f"Modelo {nome_modelo} ({nome_analise})", 
                                        zorder=5)
                                
                            else: 
                                valid_eta = np.isfinite(eta_m)
                                ax.plot(gd_plot[valid_eta], eta_m[valid_eta], 
                                        color=cor if not is_media else 'black',
                                        linestyle=':', 
                                        linewidth=2.5, 
                                        alpha=0.9,
                                        label=f"Modelo {nome_modelo} ({nome_analise})", 
                                        zorder=5)
                        
                        else: # Se for o gráfico de Curva de Fluxo (Tau vs Gamma)
                            gd_plot_safe = gd_plot[gd_plot >= 1e-4]
                            y_pred_model_safe = model_func(gd_plot_safe, *params)

                            ax.plot(gd_plot_safe, y_pred_model_safe, 
                                    color=cor, 
                                    linestyle=':', 
                                    linewidth=2.5, 
                                    alpha=0.9,
                                    label=f"Modelo {nome_modelo} ({nome_analise})", 
                                    zorder=5)
                        
                    except Exception as e:
                        pass


            min_x_vis.append(df[coluna_x].min())
            max_x_vis.append(df[coluna_x].max())
            min_y_vis.append(df[coluna_y].min())
            max_y_vis.append(df[coluna_y].max())
            if not usar_escala_log:
                all_y_points_linear.extend(df[coluna_y].tolist())

    if not min_x_vis:
        plt.close(fig)
        return None

    if fcal_info and fcal_info.get('fcal_valor'):
        titulo += f"\n(Fator de Calibração (Fcal) = {fcal_info['fcal_valor']:.4f} aplicado à amostra {fcal_info['amostra_nome']})"

    ax.set_title(titulo, fontsize=16, weight='bold')
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_xlabel(xlabel, fontsize=12)
    
    if usar_escala_log:
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlim(max(1e-9, min(min_x_vis) * 0.8), max(max_x_vis) * 1.2)
    else:
        ax.set_xscale('linear')
        ax.set_yscale('linear')
        ax.set_xlim(left=0, right=max(max_x_vis) * 1.05)
        
        if all_y_points_linear:
            p98 = np.percentile(all_y_points_linear, 98)
            ax.set_ylim(bottom=0, top=p98 * 1.2)
        else:
            ax.set_ylim(bottom=0, top=max(max_y_vis) * 1.05)
        
    ax.legend(title="Amostras e Modelos", fontsize=10, loc='best')
    fig.tight_layout()
    
    return fig


# -----------------------------------------------------------------------------
# --- FUNÇÃO DE CÁLCULO DE FATOR DE CALIBRAÇÃO EMPÍRICO (NOVO) ---
# -----------------------------------------------------------------------------

def analisar_fator_calibracao(dados_completos, pasta_salvamento):
    """
    Calcula o fator de calibração empírico (Fcal) entre duas amostras de mesma formulação.
    Fcal = tau_ref / tau_amostra (para a mesma taxa de cisalhamento).
    'dados_completos' já deve conter os nomes personalizados.
    """
    
    print("\n" + "="*70)
    print("--- CÁLCULO DE FATOR DE CALIBRAÇÃO EMPÍRICO (FCAL) ---")
    print("="*70)
    
    if len(dados_completos) != 2:
        print("ERRO: O Fator de Calibração Empírico só pode ser calculado com EXATAMENTE 2 amostras.")
        return

    # Os nomes das amostras já são os nomes personalizados
    nomes_amostras = list(dados_completos.keys())
    
    # 1. Seleção da Amostra de Referência
    print("Selecione a amostra de REFERÊNCIA (curva que será mantida):")
    for i, nome in enumerate(nomes_amostras):
        print(f"  {i+1}: {nome}")
    
    while True:
        try:
            escolha_ref_str = input("Digite o NÚMERO da amostra de referência: ")
            indice_ref = int(escolha_ref_str.strip()) - 1
            if 0 <= indice_ref < 2:
                break
            else:
                print("ERRO: Escolha inválida.")
        except ValueError:
            print("ERRO: Entrada inválida. Digite 1 ou 2.")
    
    ref_nome = nomes_amostras[indice_ref]
    amostra_nome = nomes_amostras[1 - indice_ref] # A outra amostra
    
    ref_df = dados_completos[ref_nome]['df']
    amostra_df = dados_completos[amostra_nome]['df']
    
    if ref_df.empty or amostra_df.empty:
        print("ERRO: Dados de ambas as amostras estão vazios ou incompletos.")
        return
        
    # 2. Definição da Faixa Comum de Cisalhamento
    
    # Ordena os dados de referência (essencial para interpolação)
    ref_df = ref_df.sort_values('γ̇w (s⁻¹)')
    amostra_df = amostra_df.sort_values('γ̇w (s⁻¹)')
    
    min_gamma_ref, max_gamma_ref = ref_df['γ̇w (s⁻¹)'].min(), ref_df['γ̇w (s⁻¹)'].max()
    min_gamma_amostra, max_gamma_amostra = amostra_df['γ̇w (s⁻¹)'].min(), amostra_df['γ̇w (s⁻¹)'].max()
    
    gamma_min_comum = max(min_gamma_ref, min_gamma_amostra)
    gamma_max_comum = min(max_gamma_ref, max_gamma_amostra)
    
    if gamma_min_comum >= gamma_max_comum:
        print("ERRO: As faixas de taxa de cisalhamento das amostras não se sobrepõem.")
        print(f"  Ref: [{min_gamma_ref:.2f}, {max_gamma_ref:.2f}], Amostra: [{min_gamma_amostra:.2f}, {max_gamma_amostra:.2f}]")
        return
        
    # Gera 20 pontos para interpolação dentro da faixa comum
    gamma_comum = np.geomspace(gamma_min_comum, gamma_max_comum, 20)
    
    print(f"\n--- Análise ---")
    print(f"Referência (Ref): {ref_nome}")
    print(f"Amostra a Calibrar (Amostra): {amostra_nome}")
    print(f"Faixa de comparação (γ̇w): {gamma_min_comum:.2f} a {gamma_max_comum:.2f} 1/s")
    
    # 3. Interpolação e Cálculo dos Fatores Pontuais
    
    # Cria funções de interpolação para ambas as amostras
    ref_tau_interp = interp1d(ref_df['γ̇w (s⁻¹)'], ref_df['τw (Pa)'], kind='linear', fill_value="extrapolate")
    amostra_tau_interp = interp1d(amostra_df['γ̇w (s⁻¹)'], amostra_df['τw (Pa)'], kind='linear', fill_value="extrapolate")
    
    # Interpola os valores de tau
    tau_ref_interp = ref_tau_interp(gamma_comum)
    tau_amostra_interp = amostra_tau_interp(gamma_comum)
    
    # Calcula Fcal para cada ponto
    fcal_pontual = tau_ref_interp / tau_amostra_interp
    
    # 4. Cálculo do Fator de Calibração Final (Média Ponderada)
    
    # Ponderação pela Tensão de Cisalhamento da Amostra (dá mais peso aos pontos de maior pressão/qualidade)
    pesos = tau_amostra_interp / np.sum(tau_amostra_interp)
    fcal_final = np.sum(fcal_pontual * pesos)
    
    # 5. Geração do Relatório e Resultados
    
    print("\n" + "-"*35 + " RESULTADO FCAL " + "-"*35)
    print(f"Fator de Calibração (Fcal) Média Ponderada: {fcal_final:.4f}")
    print(f"A ser aplicado a: {amostra_nome}")
    print(f"Fórmula: τ_calibrado = τ_original * {fcal_final:.4f}")
    print("-" * 80)
    
    # Cria um DataFrame de resultados detalhados
    df_fcal_detalhe = pd.DataFrame({
        'Gamma_w (s-1)': gamma_comum,
        f'Tau_w_Ref ({ref_nome}) (Pa)': tau_ref_interp,
        f'Tau_w_Amostra ({amostra_nome}) (Pa)': tau_amostra_interp,
        'Fcal_Pontual (Ref/Amostra)': fcal_pontual
    })
    
    # Salva o relatório detalhado
    nome_arquivo_csv = os.path.join(pasta_salvamento, "Fator_Calibracao_Empirico.csv")
    try:
        # Salva o arquivo com o formato do português (Ponto e Vírgula e Vírgula)
        df_fcal_detalhe.to_csv(nome_arquivo_csv, index=False, sep=';', decimal=',', float_format='%.4f')
        print(f"\nResultados detalhados salvos em: {os.path.basename(nome_arquivo_csv)}")
    except Exception as e:
        print(f"ERRO ao salvar o arquivo de Fcal: {e}")
        
    return fcal_final, amostra_nome # Retorna o Fcal e o nome da amostra que deve ser ajustada


# -----------------------------------------------------------------------------
# --- FUNÇÃO DE ANÁLISE DE DISCREPÂNCIA ---
# -----------------------------------------------------------------------------

def analisar_discrepancia(dados_completos, nome_referencia, pasta_salvamento):
    """
    (MODIFICADO) Usa 'modelo_best'
    """
    print("\n" + "="*70)
    print("--- ANÁLISE DE DISCREPÂNCIA QUANTITATIVA ---")
    print("="*70)

    # (MODIFICADO) Checa 'modelo_best'
    if nome_referencia not in dados_completos or 'modelo_best' not in dados_completos[nome_referencia] or dados_completos[nome_referencia]['modelo_best'] is None:
        print(f"ERRO: A análise de referência '{nome_referencia}' não possui um modelo ajustado válido.")
        return

    ref_data = dados_completos[nome_referencia]
    ref_model_func = MODELS[ref_data['modelo_best']['name']][0]
    ref_params = ref_data['modelo_best']['params']

    faixas_individuais = {}
    for nome, dados in dados_completos.items():
        if dados.get('df') is not None and not dados['df'].empty and dados.get('modelo_best') is not None:
            min_gamma = dados['df']['γ̇w (s⁻¹)'].min()
            max_gamma = dados['df']['γ̇w (s⁻¹)'].max()
            faixas_individuais[nome] = (min_gamma, max_gamma)
    
    if len(faixas_individuais) < 2:
        print("ERRO: É necessário ter pelo menos duas amostras com modelos e dados válidos para comparar.")
        return

    min_gammas = [v[0] for v in faixas_individuais.values()]
    max_gammas = [v[1] for v in faixas_individuais.values()]
    
    gamma_min_comum = max(min_gammas)
    gamma_max_comum = min(max_gammas)

    if gamma_min_comum >= gamma_max_comum:
        print("AVISO: Análise de discrepância não pode ser executada.")
        print("       Não há uma faixa de sobreposição de taxas de cisalhamento entre todas as amostras válidas.")
        return

    print(f"Análise de Referência: {nome_referencia}")
    print(f"Faixa de comparação (γ̇): {gamma_min_comum:.2f} a {gamma_max_comum:.2f} 1/s")

    gamma_comum = np.logspace(np.log10(gamma_min_comum), np.log10(gamma_max_comum), 200)
    tau_ref = ref_model_func(gamma_comum, *ref_params)
    eta_ref = tau_ref / np.maximum(gamma_comum, 1e-9)
    
    resultados_discrepancia = []

    for nome_analise, dados_analise in dados_completos.items():
        if nome_analise == nome_referencia or nome_analise not in faixas_individuais:
            continue
            
        model_func = MODELS[dados_analise['modelo_best']['name']][0]
        params = dados_analise['modelo_best']['params']
        tau_comp = model_func(gamma_comum, *params)
        eta_comp = tau_comp / np.maximum(gamma_comum, 1e-9)

        mape_tau = 100 * np.mean(np.abs((tau_comp - tau_ref) / tau_ref))
        mape_eta = 100 * np.mean(np.abs((eta_comp - eta_ref) / eta_ref))
        
        resultados_discrepancia.append({
            "Amostra Comparada": nome_analise,
            "Referência": nome_referencia,
            "Modelo Comparado": dados_analise['modelo_best']['name'],
            "MAPE τw (%)": f"{mape_tau:.2f}",
            "MAPE η (%)": f"{mape_eta:.2f}"
        })

    if not resultados_discrepancia:
        print("Nenhuma outra amostra com modelo válido para comparar.")
        return

    df_discrepancia = pd.DataFrame(resultados_discrepancia)
    print("\nResultados da Análise de Discrepância (MAPE %):")
    
    df_discrepancia_display = df_discrepancia.copy()
    df_discrepancia_display['MAPE τw (%)'] = df_discrepancia_display['MAPE τw (%)'].astype(str).str.replace('.', ',', regex=False)
    df_discrepancia_display['MAPE η (%)'] = df_discrepancia_display['MAPE η (%)'].astype(str).str.replace('.', ',', regex=False)

    print(df_discrepancia_display.to_string(index=False))

    nome_arquivo_csv = os.path.join(pasta_salvamento, "Analise_Discrepancia.csv")
    try:
        df_discrepancia['MAPE τw (%)'] = df_discrepancia['MAPE τw (%)'].astype(str).str.replace('.', ',', regex=False)
        df_discrepancia['MAPE η (%)'] = df_discrepancia['MAPE η (%)'].astype(str).str.replace('.', ',', regex=False)

        df_discrepancia.to_csv(nome_arquivo_csv, index=False, sep=';', decimal=',', encoding='utf-8-sig')
        print(f"\nResultados da discrepância salvos em: {os.path.basename(nome_arquivo_csv)}")
    except Exception as e:
        print(f"ERRO ao salvar o arquivo de discrepância: {e}")


# -----------------------------------------------------------------------------
# --- (FUNÇÃO ATUALIZADA) GERAR RELATÓRIO COMPILADO DE DADOS ---
# -----------------------------------------------------------------------------

def gerar_relatorio_compilado_dados(dados_renomeados, pasta_salvamento):
    """
    (MODIFICADO) Compila os DataFrames de todas as análises (com nomes personalizados)
    em um único arquivo CSV longo, mantendo TODAS as colunas originais.
    """
    print("\n" + "="*70)
    print("--- GERANDO RELATÓRIO COMPILADO (DADOS COMPLETOS) ---")
    print("=" * 70)

    lista_dfs_compilados = []
    todas_colunas = set()
    dfs_para_compilar = []

    # 1. Coleta todos os DFs e nomes de colunas
    for nome_amostra, dados in dados_renomeados.items():
        if 'df' in dados and dados['df'] is not None and not dados['df'].empty:
            df_copia = dados['df'].copy()
            df_copia['Amostra'] = nome_amostra
            dfs_para_compilar.append(df_copia)
            todas_colunas.update(df_copia.columns.tolist())
    
    if not dfs_para_compilar:
        print("AVISO: Nenhum dado válido encontrado para gerar o relatório compilado de dados.")
        return

    try:
        # 2. Define a ordem preferencial das colunas (para ficar mais organizado)
        colunas_preferenciais = [
            'Amostra', 
            'γ̇w (s⁻¹)', 'τw (Pa)', 'η (Pa·s)', 
            'STD_τw (Pa)', 'STD_γ̇w (s⁻¹)', 
            'γ̇aw (s⁻¹)', 'ηa (Pa·s)',
            'P_ext(bar)', 'M_ext(g)', 'Q_calc(mm³/s)', 't_ext(s)',
            'Ponto', 'D_cap(mm)', 'L_cap(mm)', 'rho(g/cm³)'
        ]
        
        colunas_finais = []
        # Adiciona colunas preferenciais na ordem correta
        for col in colunas_preferenciais:
            if col in todas_colunas:
                colunas_finais.append(col)
                if col in todas_colunas:
                    todas_colunas.remove(col)
        
        # Adiciona o restante das colunas (ordenadas alfabeticamente)
        colunas_finais.extend(sorted(list(todas_colunas)))
        
        # 3. Concatena todos os DataFrames (pd.concat lida com colunas desalinhadas)
        df_final_compilado = pd.concat(dfs_para_compilar, ignore_index=True, sort=False)
        
        # 4. Reordena o DataFrame final para a ordem definida
        df_final_compilado = df_final_compilado[colunas_finais]

        # 5. Ordena os dados por Amostra e Taxa de Cisalhamento
        df_final_compilado = df_final_compilado.sort_values(by=['Amostra', 'γ̇w (s⁻¹)'])
        
        nome_arquivo_csv = os.path.join(pasta_salvamento, "Relatorio_Compilado_Dados.csv")
        
        # 6. Salva no formato PT-BR
        df_final_compilado.to_csv(nome_arquivo_csv, index=False, sep=';', decimal=',', encoding='utf-8-sig', float_format='%.6g')
        print(f"Relatório compilado de DADOS salvo em: {os.path.basename(nome_arquivo_csv)}")

    except Exception as e:
        print(f"ERRO ao gerar relatório compilado de dados: {e}")


# -----------------------------------------------------------------------------
# --- (NOVA FUNÇÃO) GERAR RELATÓRIO COMPILADO DE MODELOS ---
# -----------------------------------------------------------------------------

def gerar_relatorio_modelos(dados_renomeados, pasta_salvamento):
    """
    Compila os parâmetros e R2 de TODOS os modelos ajustados para todas
    as amostras comparadas em um único CSV "longo".
    """
    print("\n" + "="*70)
    print("--- GERANDO RELATÓRIO COMPILADO (PARÂMETROS DE MODELOS) ---")
    print("=" * 70)

    lista_resultados_modelos = []

    for nome_amostra, dados in dados_renomeados.items():
        
        modelos_all = dados.get('modelos_all')
        
        # --- CORREÇÃO DE BUG ---
        # Checa se 'modelo_best' não é None antes de tentar acessar seus dados
        modelo_best_data = dados.get('modelo_best') 
        melhor_modelo_nome = None
        if modelo_best_data: # Checa se não é None
            melhor_modelo_nome = modelo_best_data.get('name')
        # --- FIM DA CORREÇÃO ---
        
        if not modelos_all:
            print(f"Aviso: Amostra '{nome_amostra}' não possui dados de modelo para o relatório.")
            continue
            
        # Itera sobre todos os modelos ajustados para esta amostra
        for modelo_nome, detalhes in modelos_all.items():
            
            r2 = detalhes.get('R2')
            is_best = (modelo_nome == melhor_modelo_nome)
            param_vals = detalhes.get('params', [])
            
            # Busca os nomes dos parâmetros no nosso mapa
            param_names_map = PARAM_NAMES_MAP.get(modelo_nome, [])

            # Adiciona uma linha para cada parâmetro do modelo
            for j, val in enumerate(param_vals):
                try:
                    param_nome = param_names_map[j]
                except IndexError:
                    param_nome = f"parametro_{j+1}" # Fallback
                
                lista_resultados_modelos.append({
                    'Amostra': nome_amostra,
                    'Modelo': modelo_nome,
                    'Parametro': param_nome,
                    'Valor': val,
                    'R2': r2,
                    'Melhor_Modelo_Para_Amostra': is_best
                })
            
            # Adiciona também o R2 como uma "métrica" separada para facilitar a filtragem
            lista_resultados_modelos.append({
                'Amostra': nome_amostra,
                'Modelo': modelo_nome,
                'Parametro': 'R2',
                'Valor': r2,
                'R2': r2, # (propositalmente redundante para pivots)
                'Melhor_Modelo_Para_Amostra': is_best
            })

    if not lista_resultados_modelos:
        print("AVISO: Nenhum dado de modelo encontrado para gerar o relatório.")
        return

    try:
        df_modelos = pd.DataFrame(lista_resultados_modelos)
        
        # Ordena
        df_modelos = df_modelos.sort_values(by=['Amostra', 'Modelo', 'Parametro'])
        
        nome_arquivo_csv = os.path.join(pasta_salvamento, "Relatorio_Compilado_Modelos.csv")
        
        # Salva no formato PT-BR
        df_modelos.to_csv(nome_arquivo_csv, index=False, sep=';', decimal=',', encoding='utf-8-sig', float_format='%.6g')
        print(f"Relatório compilado de MODELOS salvo em: {os.path.basename(nome_arquivo_csv)}")

    except Exception as e:
        print(f"ERRO ao gerar relatório compilado de modelos: {e}")


# -----------------------------------------------------------------------------
# --- BLOCO PRINCIPAL DE EXECUÇÃO (Menu Atualizado) ---
# -----------------------------------------------------------------------------

def menu_principal_4():
    
    print("\n" + "="*70)
    print("--- MENU DE ANÁLISE COMPARATIVA ---")
    print("1. Comparar e Plotar Múltiplas Curvas (Padrão)")
    print("2. Calcular Fator de Calibração Empírico (Fcal)")
    print("3. Analisar Discrepância Quantitativa (MAPE)")
    print("0. Sair")
    print("="*70)
    
    escolha = input("Escolha uma opção (1, 2, 3 ou 0): ").strip()
    return escolha

if __name__ == "__main__":
    
    if not os.path.exists(CAMINHO_BASE_INDIVIDUAL):
        os.makedirs(CAMINHO_BASE_INDIVIDUAL)

    if not os.path.exists(CAMINHO_BASE_COMPARATIVOS):
        os.makedirs(CAMINHO_BASE_COMPARATIVOS)
        
    if not os.path.exists(CAMINHO_BASE_ROTACIONAL):
        os.makedirs(CAMINHO_BASE_ROTACIONAL)
    
    while True:
        
        escolha = menu_principal_4()
        
        if escolha == '0':
            print("\nEncerrando script.")
            break
        
        if escolha == '1' or escolha == '3' or escolha == '2':
            
            pastas_selecionadas_info, nomes_selecionados = selecionar_pastas_analise(CAMINHO_BASE_INDIVIDUAL, CAMINHO_BASE_ESTATISTICO, CAMINHO_BASE_ROTACIONAL)
            
            if pastas_selecionadas_info is None:
                continue

            if escolha == '2' and len(pastas_selecionadas_info) != 2:
                print("\nERRO: Para o Cálculo de Fcal, você deve selecionar EXATAMENTE 2 amostras.")
                continue

            # --- PREPARAÇÃO PARA SALVAMENTO ---
            nomes_curtos_analises = [criar_nome_curto(nome) for nome in nomes_selecionados]
            
            # Gera nome sugerido automaticamente baseado no tipo de comparação
            if escolha == '2':
                 nome_sugerido = f"FCAL_ENTRE_{nomes_curtos_analises[0]}_E_{nomes_curtos_analises[1]}"
            elif escolha == '4':
                 nome_sugerido = f"COMPARATIVO_COM_MEDIA_{nomes_curtos_analises[0]}_e_Outros"
            else:
                 nome_sugerido = "+".join(sorted(list(set(nomes_curtos_analises))))
            
            # --- SOLICITA NOME PERSONALIZADO PARA O COMPARATIVO ---
            print("\n" + "="*70)
            print("NOME DO COMPARATIVO")
            print("="*70)
            print(f"Nome automático sugerido: '{nome_sugerido}'")
            print("Você pode fornecer um nome personalizado ou pressionar ENTER para usar a sugestão.")
            print("="*70)
            
            while True:
                nome_input = input("\nNome personalizado do comparativo (ou ENTER para sugestão): ").strip()
                
                if nome_input:
                    # Valida o nome (remove caracteres inválidos)
                    nome_personalizado = "".join(c for c in nome_input if c.isalnum() or c in (' ', '_', '-')).strip()
                    if nome_personalizado:
                        nome_comparativo = nome_personalizado.replace(' ', '_')
                        print(f"\n✓ Nome personalizado aceito: '{nome_comparativo}'")
                        break
                    else:
                        print("ERRO: Nome inválido. Use apenas letras, números, espaços, '-' ou '_'.")
                else:
                    # Usa o nome sugerido
                    nome_comparativo = nome_sugerido
                    print(f"\n✓ Usando nome sugerido: '{nome_comparativo}'")
                    break
            
            timestamp_comparativo = datetime.now().strftime("%Y%m%d_%H%M%S")
            pasta_salvamento = os.path.join(CAMINHO_BASE_COMPARATIVOS, f"{nome_comparativo}_{timestamp_comparativo}")
            
            if not os.path.exists(pasta_salvamento):
                os.makedirs(pasta_salvamento)
            
            print(f"\n📁 Os resultados serão salvos em: {os.path.basename(pasta_salvamento)}\n")

            # --- CARREGAMENTO DOS DADOS ---
            # (MODIFICADO) 'dados_completos' agora armazena a estrutura completa
            dados_completos = {}
            for i, info_analise in enumerate(pastas_selecionadas_info):
                nome_base_sessao = nomes_selecionados[i]
                sufixo = 1
                nome_final = nome_base_sessao
                
                while nome_final in dados_completos:
                    sufixo += 1
                    nome_final = f"{nome_base_sessao}_{sufixo}"

                # (MODIFICADO) Carrega df, o melhor modelo, e todos os modelos
                df_analise, modelo_best, modelos_all = carregar_dados_completos(info_analise)
                
                if df_analise is not None and not df_analise.empty:
                    dados_completos[nome_final] = {
                        'df': df_analise, 
                        'modelo': modelo_info
                    }
                else:
                    print(f"AVISO: A análise '{nome_base_sessao}' foi descartada por falta de dados válidos.")

            
            if not dados_completos:
                print("\nERRO: Nenhuma análise válida foi carregada. Retornando ao menu.")
                continue

            # -----------------------------------------------------------------
            # --- SOLICITAR NOMES PERSONALIZADOS PARA PLOTAGEM ---
            # -----------------------------------------------------------------
            print("\n" + "="*70)
            print("--- DEFINIR NOMES PARA LEGENDA E RELATÓRIOS ---")
            print("Forneça nomes curtos para cada análise (pressione Enter para usar a sugestão).")
            print("=" * 70)
            
            dados_completos_renomeados = {}
            chaves_originais = list(dados_completos.keys())
            
            for nome_original in chaves_originais:
                nome_sugerido = criar_nome_curto(nome_original)
                
                while True:
                    novo_nome_input = input(f"Nome para '{nome_original}' (sugestão: '{nome_sugerido}'): ").strip()
                    novo_nome = novo_nome_input if novo_nome_input else nome_sugerido
                    
                    if novo_nome in dados_completos_renomeados:
                        print(f"ERRO: O nome '{novo_nome}' já foi usado. Tente novamente.")
                    elif not novo_nome:
                         print(f"ERRO: O nome não pode ficar em branco.")
                    else:
                        dados_completos_renomeados[novo_nome] = dados_completos[nome_original]
                        print(f" -> '{nome_original}' será chamado de '{novo_nome}'")
                        break
            
            print("=" * 70)
            
            # -----------------------------------------------------------------
            # --- (NOVOS) GERAR RELATÓRIOS COMPILADOS ---
            # -----------------------------------------------------------------
            # 1. Gera o relatório com os dados brutos/calculados de todas as amostras
            gerar_relatorio_compilado_dados(dados_completos_renomeados, pasta_salvamento)
            
            # 2. Gera o relatório com todos os parâmetros de modelo
            gerar_relatorio_modelos(dados_completos_renomeados, pasta_salvamento)
            
            
            # --- EXECUTAR MODO FCAL (Opção 2) ---
            if escolha == '2':
                # Usa o dicionário RENOMEADO para a análise
                fcal_valor, amostra_nome = analisar_fator_calibracao(dados_completos_renomeados, pasta_salvamento)
                
                if fcal_valor is not None:
                    df_ajustado = dados_completos_renomeados[amostra_nome]['df'].copy()
                    df_ajustado['τw (Pa)'] = df_ajustado['τw (Pa)'] * fcal_valor
                    df_ajustado['η (Pa·s)'] = df_ajustado['η (Pa·s)'] * fcal_valor
                    
                    dados_plot_fcal = dados_completos_renomeados.copy()
                    # (MODIFICADO) Adiciona a curva corrigida com a estrutura de dados completa
                    dados_plot_fcal[f"{amostra_nome} (FCAL={fcal_valor:.4f})"] = {
                        'df': df_ajustado, 
                        'modelo_best': None, 
                        'modelos_all': None
                    }
                    
                    fcal_info_plot = {'fcal_valor': fcal_valor, 'amostra_nome': amostra_nome}

                    print("\n--- Gerando e Salvando Gráficos (FCAL Aplicado) ---")
                    plot_configs = [
                        {'col_y': 'τw (Pa)', 'col_x': 'γ̇w (s⁻¹)', 'title': 'Curvas de Fluxo (FCAL Aplicado)', 'ylabel': r'Tensão de Cisalhamento ($\tau_w$, Pa)', 'xlabel': r'Taxa de Cisalhamento ($\dot{\gamma}_w$, 1/s)', 'log': True, 'fname': 'FCAL_Comparativo_Fluxo_Log.png'},
                        {'col_y': 'η (Pa·s)', 'col_x': 'γ̇w (s⁻¹)', 'title': 'Curvas de Viscosidade (FCAL Aplicado)', 'ylabel': r'Viscosidade ($\eta$, Pa·s)', 'xlabel': r'Taxa de Cisalhamento ($\dot{\gamma}_w$, 1/s)', 'log': True, 'fname': 'FCAL_Comparativo_Viscosidade_Log.png'}
                    ]
                    
                    figures = []
                    for config in plot_configs:
                        fig = plotar_comparativo_com_modelo(dados_plot_fcal, config['col_y'], config['col_x'], config['title'], config['ylabel'], config['xlabel'], usar_escala_log=config['log'], fcal_info=fcal_info_plot)
                        
                        if fig:
                            try:
                                caminho_completo = os.path.join(pasta_salvamento, config['fname'])
                                fig.savefig(caminho_completo, dpi=300, bbox_inches='tight')
                                print(f"Gráfico salvo em: {config['fname']}")
                                figures.append(fig)
                            except Exception as e:
                                print(f"ERRO ao salvar o gráfico '{config['fname']}': {e}")
                                
                    try:
                        if figures and plt.get_backend():
                            print("\nExibindo gráficos... Feche as janelas para finalizar o script.")
                            plt.show()
                        elif figures:
                            for fig in figures:
                                plt.close(fig)
                    except Exception as e:
                        print(f"\nNão foi possível exibir os gráficos interativamente ({e}). Eles já foram salvos na pasta de resultados.")
                        
                
            # --- EXECUTAR MODO COMPARAÇÃO PADRÃO (Opção 1) ---
            elif escolha == '1':
                print("\n--- Gerando e Salvando Gráficos Comparativos (Padrão) ---")
                
                plot_configs = [
                    {'col_y': 'τw (Pa)', 'col_x': 'γ̇w (s⁻¹)', 'title': 'Comparativo de Curvas de Fluxo (Escala Log)', 'ylabel': r'Tensão de Cisalhamento ($\tau_w$, Pa)', 'xlabel': r'Taxa de Cisalhamento ($\dot{\gamma}_w$, 1/s)', 'log': True, 'fname': 'Comparativo_Fluxo_Log.png'},
                    {'col_y': 'η (Pa·s)', 'col_x': 'γ̇w (s⁻¹)', 'title': 'Comparativo de Curvas de Viscosidade (Escala Log)', 'ylabel': r'Viscosidade ($\eta$, Pa·s)', 'xlabel': r'Taxa de Cisalhamento ($\dot{\gamma}_w$, 1/s)', 'log': True, 'fname': 'Comparativo_Viscosidade_Log.png'},
                    {'col_y': 'τw (Pa)', 'col_x': 'γ̇w (s⁻¹)', 'title': 'Comparativo de Curvas de Fluxo (Escala Linear)', 'ylabel': r'Tensão de Cisalhamento ($\tau_w$, Pa)', 'xlabel': r'Taxa de Cisalhamento ($\dot{\gamma}_w$, 1/s)', 'log': False, 'fname': 'Comparativo_Fluxo_Linear.png'},
                    {'col_y': 'η (Pa·s)', 'col_x': 'γ̇w (s⁻¹)', 'title': 'Comparativo de Curvas de Viscosidade (Escala Linear)', 'ylabel': r'Viscosidade ($\eta$, Pa·s)', 'xlabel': r'Taxa de Cisalhamento ($\dot{\gamma}_w$, 1/s)', 'log': False, 'fname': 'Comparativo_Viscosidade_Linear.png'}
                ]

                figures = []
                for config in plot_configs:
                    # Passa o dicionário RENOMEADO para a plotagem
                    fig = plotar_comparativo_com_modelo(dados_completos_renomeados, config['col_y'], config['col_x'], config['title'], config['ylabel'], config['xlabel'], usar_escala_log=config['log'])
                    
                    if fig:
                        try:
                            caminho_completo = os.path.join(pasta_salvamento, config['fname'])
                            fig.savefig(caminho_completo, dpi=300, bbox_inches='tight')
                            print(f"Gráfico salvo em: {config['fname']}")
                            figures.append(fig)
                        except Exception as e:
                            print(f"ERRO ao salvar o gráfico '{config['fname']}': {e}")
                            
                try:
                    if figures and plt.get_backend():
                        print("\nExibindo gráficos... Feche as janelas para finalizar o script.")
                        plt.show()
                    elif figures:
                        for fig in figures:
                            plt.close(fig)
                except Exception as e:
                    print(f"\nNão foi possível exibir os gráficos interativamente ({e}). Eles já foram salvos na pasta de resultados.")
                    
            # --- EXECUTAR MODO DISCREPÂNCIA (Opção 3) ---
            elif escolha == '3':
                if len(dados_completos_renomeados) > 1:
                    print("\nSelecione a análise de REFERÊNCIA para a comparação de discrepância:")
                    # (MODIFICADO) Usa 'modelo_best'
                    lista_nomes_validos = [nome for nome, dados in dados_completos_renomeados.items() if 'modelo_best' in dados and dados['modelo_best']]
                    
                    if len(lista_nomes_validos) < 2:
                        print("ERRO: É necessário ter pelo menos duas amostras com modelos ajustados para realizar a comparação.")
                    else:
                        for i, nome in enumerate(lista_nomes_validos):
                            print(f"  {i+1}: {nome}")
                        
                        try:
                            escolha_ref_str = input("Digite o NÚMERO da amostra de referência: ")
                            indice_ref = int(escolha_ref_str.strip()) - 1
                            if 0 <= indice_ref < len(lista_nomes_validos):
                                nome_referencia = lista_nomes_validos[indice_ref]
                                analisar_discrepancia(dados_completos_renomeados, nome_referencia, pasta_salvamento)
                            else:
                                print("ERRO: Escolha inválida.")
                        except (ValueError, IndexError):
                            print("ERRO: Entrada inválida. A análise de discrepância não será executada.")
                else:
                    print("ERRO: Selecione mais de uma amostra para a análise de discrepância.")
            
        else:
            print("Opção inválida. Tente novamente.")

    print("\n--- FIM DA COMPARAÇÃO ---")

