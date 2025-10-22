# -----------------------------------------------------------------------------
# SCRIPT 3.VISUALIZAR_RESULTADOS.PY (Versão Corrigida FINAL e Robusta)
# Permite visualizar o conjunto completo de gráficos de dados individuais ou a 
# curva média com barras de erro (Estatístico).
# -----------------------------------------------------------------------------

import os
import glob
import json
import numpy as np
import pandas as pd
import matplotlib
import re
try:
    # Tenta usar um backend mais moderno para melhor performance de visualização
    matplotlib.use('QtAgg') 
except ImportError:
    print("Aviso: Backend QtAgg não encontrado, usando o padrão do sistema.")
import matplotlib.pyplot as plt

# --- Definições dos Modelos Reológicos ---
def model_newtonian(gd,eta): return eta*gd
def model_power_law(gd,K_pl,n_pl): return K_pl*np.power(np.maximum(gd, 1e-9),n_pl)
def model_bingham(gd,t0,ep): return t0+ep*gd
def model_hb(gd,t0,K_hb,n_hb): return t0+K_hb*np.power(np.maximum(gd, 1e-9),n_hb)
def model_casson(gd, tau0_cas, eta_cas): 
    sqrt_tau0 = np.sqrt(np.maximum(tau0_cas, 0))
    sqrt_eta_cas_val = np.sqrt(np.maximum(eta_cas, 1e-9))
    sqrt_gd_val = np.sqrt(np.maximum(gd, 1e-9))
    return (sqrt_tau0 + sqrt_eta_cas_val * sqrt_gd_val)**2

models = {
    "Newtoniano": model_newtonian, "Lei da Potência": model_power_law, 
    "Bingham": model_bingham, "Herschel-Bulkley": model_hb, "Casson": model_casson
}

# --- Definição de Cores Otimizadas (tab10) ---
# Usaremos cores sólidas e contrastantes
CORES = plt.get_cmap('tab10')
COR_DADOS_FLUXO = CORES(0) # Azul Escuro
COR_DADOS_VISCOSIDADE = CORES(2) # Verde Sólido
COR_ERRO = CORES(7) # Cinza Chumbo ou Magenta (para contraste)
COR_RESIDUO = CORES(4) # Roxo
COR_MELHOR_MODELO = 'red' 

# --- Função Auxiliar para Adicionar Texto ---
def adicionar_texto_explicativo(fig, texto):
    fig.subplots_adjust(bottom=0.25)
    fig.text(0.5, 0.01, texto, ha='center', va='bottom', fontsize=9, wrap=True,
             bbox=dict(boxstyle='round,pad=0.5', fc='wheat', alpha=0.5))

def verificar_arquivos_na_sessao(caminho_sessao):
    """Verifica se a sessão contém algum CSV de resultados individual ou estatístico, usando busca recursiva."""
    # Busca por arquivos CSV em qualquer nível de subpasta (busca recursiva)
    search_pattern_indiv = os.path.join(caminho_sessao, '**', '*_resultados_reologicos.csv')
    arquivos_indiv = glob.glob(search_pattern_indiv, recursive=True)
    
    search_pattern_stat = os.path.join(caminho_sessao, '**', '*_resultados_estatisticos.csv')
    arquivos_stat = glob.glob(search_pattern_stat, recursive=True)
    
    return arquivos_indiv, arquivos_stat

def ler_e_preparar_dados(caminho_csv, tipo_arquivo):
    """Lê o CSV, identifica o tipo de dado e prepara as variáveis."""
    
    is_statistical = (tipo_arquivo == 'Estatístico') # Define o flag booleano corretamente
    
    try:
        # Tenta a codificação comum primeiro
        df_res = pd.read_csv(caminho_csv, sep=';', decimal=',')
    except Exception:
        # Tenta codificação sig (para CSVs gerados pelo Python com sep=; e decimal=,)
        df_res = pd.read_csv(caminho_csv, sep=';', decimal=',', encoding='utf-8-sig')
        
    # --- Colunas de Dados ---
    if is_statistical:
        print("INFO: Modo Estatístico ativado (plotando médias com barras de erro).")
        # Colunas Médias
        tau_col = 'τw_MEDIA(Pa)'
        gd_col = 'γ̇w_MEDIA(s⁻¹)'
        eta_col = 'η_MEDIA(Pa·s)'
        # Colunas de Erro
        tau_std_col = 'STD_τw (Pa)'
        gd_std_col = 'STD_γ̇w (s⁻¹)'
        
        # Extração de dados (STD = 0 se não houver coluna de STD)
        tau_data = df_res[tau_col].values
        gamma_dot_data = df_res[gd_col].values
        eta_data = df_res[eta_col].values
        tau_std = df_res.get(tau_std_col, np.zeros_like(tau_data)).values
        gd_std = df_res.get(gd_std_col, np.zeros_like(gamma_dot_data)).values
        
        titulo_sufixo = " (Dados Estatísticos: Média $\\pm$ $\\sigma$)"
        plot_type = 'errorbar'
        
    else: # Modo Individual
        print("INFO: Modo Individual ativado (plotando pontos brutos processados).")
        # Colunas Individuais
        tau_col = 'τw (Pa)'
        gd_col = 'γ̇w (s⁻¹)'
        eta_col = 'η (Pa·s)'
        
        # Correção do problema de Key Error: 
        # Acessa as colunas esperadas para o CSV individual.
        tau_data = df_res[tau_col].values
        gamma_dot_data = df_res[gd_col].values
        eta_data = df_res[eta_col].values
        tau_std, gd_std = None, None # Desvio padrão não se aplica
        
        titulo_sufixo = " (Dados Individuais Processados)"
        plot_type = 'scatter'
        
    # --- Carregamento dos Parâmetros do Modelo ---
    
    # Nomes base dos arquivos de parâmetros (sem a extensão csv)
    arquivo_base_nome = os.path.basename(caminho_csv).replace('.csv', '').replace('_resultados_reologicos', '').replace('_resultados_estatisticos', '')
    
    # Busca por JSON de parâmetros na mesma pasta do CSV (seja indiv ou stat)
    pasta_do_csv = os.path.dirname(caminho_csv)
    path_parametros = os.path.join(pasta_do_csv, f"{arquivo_base_nome}_parametros_modelos.json")
    
    dados_modelos_completos = {}
    if os.path.exists(path_parametros):
        try:
            # Tenta ler com a codificação correta
            with open(path_parametros, 'r', encoding='utf-8') as f:
                dados_modelos_completos = json.load(f)
            print(f"INFO: Parâmetros do modelo carregados de: {os.path.basename(path_parametros)}")
        except Exception as e:
            print(f"AVISO: Falha ao carregar parâmetros do modelo: {e}")
            
    model_results = dados_modelos_completos.get("modelos_ajustados", {})
    
    # Retorna o status 'is_statistical' junto com os dados
    return tau_data, gamma_dot_data, eta_data, tau_std, gd_std, model_results, titulo_sufixo, plot_type, df_res, is_statistical


def visualizador_principal():
    base_folder = "resultados_analise_reologica"
    base_folder_stat = "resultados_analise_estatistica"

    # Garante que as pastas existam
    if not os.path.exists(base_folder): os.makedirs(base_folder)
    if not os.path.exists(base_folder_stat): os.makedirs(base_folder_stat)

    # Dicionário para mapear o nome da sessão para o caminho e tipo
    sessoes_validas = {}

    # --- 1. Busca e Valida Sessões Individuais ---
    sessoes_indiv = sorted([d for d in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, d))], reverse=True)
    for nome_sessao in sessoes_indiv:
        caminho_sessao = os.path.join(base_folder, nome_sessao)
        arquivos_indiv, _ = verificar_arquivos_na_sessao(caminho_sessao)
        if arquivos_indiv:
             if nome_sessao not in sessoes_validas:
                 sessoes_validas[nome_sessao] = {'caminho': caminho_sessao, 'tipo': 'Individual'}
    
    # --- 2. Busca e Valida Sessões Estatísticas ---
    sessoes_stat = sorted([d for d in os.listdir(base_folder_stat) if os.path.isdir(os.path.join(base_folder_stat, d))], reverse=True)
    for nome_sessao in sessoes_stat:
        caminho_sessao = os.path.join(base_folder_stat, nome_sessao)
        _, arquivos_stat = verificar_arquivos_na_sessao(caminho_sessao)
        if arquivos_stat:
             sessoes_validas[nome_sessao] = {'caminho': caminho_sessao, 'tipo': 'Estatístico'}

    sessoes_ordenadas = sorted(sessoes_validas.keys(), reverse=True)
    
    if not sessoes_ordenadas:
        print(f"Nenhuma sessão de análise (com arquivos CSV) encontrada nas pastas '{base_folder}' ou '{base_folder_stat}'."); return

    print("\n--- Sessões de Análise Disponíveis ---")
    for i, nome_sessao in enumerate(sessoes_ordenadas): 
        tipo = sessoes_validas[nome_sessao]['tipo']
        print(f"  {i+1}: {nome_sessao} ({tipo})")

    escolha_sessao = -1
    while escolha_sessao < 1 or escolha_sessao > len(sessoes_ordenadas):
        try:
            escolha_sessao = int(input(f"Escolha o número da sessão que deseja visualizar (1-{len(sessoes_ordenadas)}): "))
        except ValueError: print("Entrada inválida.")
    
    nome_sessao = sessoes_ordenadas[escolha_sessao - 1]
    
    # 3. Busca os arquivos CSV disponíveis na sessão selecionada
    arquivos_disponiveis = []
    
    # Extrai o prefixo do projeto (tudo antes do último timestamp, ex: '19-10-25_Caulim40H2OCap3x64')
    project_prefix = nome_sessao.rsplit('_202', 1)[0]
    
    # --- 1. Busca na pasta Estatística (prioridade) ---
    caminho_sessao_stat = os.path.join(base_folder_stat, nome_sessao)
    _, arquivos_stat = verificar_arquivos_na_sessao(caminho_sessao_stat)
    for arq in arquivos_stat:
        arquivos_disponiveis.append({'caminho': arq, 'nome': os.path.basename(arq), 'tipo': 'Estatístico'})
    
    # --- 2. Busca na pasta Individual (BUSCA AMPLA POR PREFIXO) ---
    
    # Caminho de busca ampla: procura em qualquer pasta em 'resultados_analise_reologica' 
    # que comece com o prefixo do projeto
    search_pattern_broad = os.path.join(base_folder, f"{project_prefix}*", '**', '*_resultados_reologicos.csv')
    arquivos_indiv_broad = glob.glob(search_pattern_broad, recursive=True)
    
    for arq in arquivos_indiv_broad:
        # Garante que não sejam duplicatas (o nome do arquivo individual não deve ser listado como estatístico)
        if not any(a['caminho'] == arq for a in arquivos_disponiveis):
            arquivos_disponiveis.append({'caminho': arq, 'nome': os.path.basename(arq), 'tipo': 'Individual'})

    # Garante que não haja duplicatas
    arquivos_disponiveis = list({v['caminho']:v for v in arquivos_disponiveis}.values())
        
    if not arquivos_disponiveis:
        print(f"ERRO: Nenhum arquivo CSV de resultados encontrado na sessão '{nome_sessao}'."); return

    print("\n--- Arquivos de Resultados Disponíveis na Sessão ---")
    for i, arq in enumerate(arquivos_disponiveis):
        print(f"  {i+1}: {arq['nome']} (Tipo: {arq['tipo']})")
        
    escolha_csv = -1
    while escolha_csv < 1 or escolha_csv > len(arquivos_disponiveis):
        try:
            escolha_csv = int(input(f"Escolha o número do arquivo para plotagem (1-{len(arquivos_disponiveis)}): "))
        except ValueError: print("Entrada inválida.")

    # 4. Carrega e prepara os dados
    # A variável is_statistical é o 10º item retornado
    arquivo_selecionado = arquivos_disponiveis[escolha_csv - 1]
    
    tau_w_data, gamma_dot_data, eta_true_data, tau_std, gd_std, model_results, titulo_sufixo, plot_type, df_res, is_statistical = \
        ler_e_preparar_dados(arquivo_selecionado['caminho'], arquivo_selecionado['tipo'])

    if tau_w_data is None: return

    # 5. Preparação Final
    best_model_nome = ""
    if model_results:
        best_model_nome = max(model_results, key=lambda name: model_results[name]['R2'])
    
    valid_fit = ~np.isnan(tau_w_data) & ~np.isnan(gamma_dot_data) & (gamma_dot_data > 0)
    gd_fit = gamma_dot_data[valid_fit]
    if len(gd_fit) == 0: print("Não há dados válidos para gerar gráficos."); return

    print("Gerando e SALVANDO gráficos...") # Alerta de que salvará
    
    # --- DEFINIÇÃO DOS NOMES DE ARQUIVO E PASTA DE SAÍDA ---
    caminho_csv_completo = arquivo_selecionado['caminho']
    pasta_saida_graficos = os.path.dirname(caminho_csv_completo)
    nome_base_arquivo = os.path.basename(caminho_csv_completo).replace('.csv', '')
    
    min_gp_val = np.min(gd_fit) if np.any(gd_fit) else 1e-3
    max_gp_val = np.max(gd_fit) if np.any(gd_fit) else 1.0
    min_gp, max_gp = max(1e-9, min_gp_val * 0.5), max_gp_val * 1.5
    gd_plot = np.geomspace(min_gp, max_gp, 200)

    # --- INÍCIO DA GERAÇÃO DAS FIGURAS (ESTRUTURA COMPLETA) ---

    # --- Figura 1: Curva de Fluxo (Todos Modelos) ---
    fig1, ax1 = plt.subplots(figsize=(10, 7))

    # Plota os dados com ou sem barra de erro
    if plot_type == 'errorbar':
         # CORES ALTERADAS: COR_DADOS_FLUXO (Azul), COR_ERRO (Cinza Chumbo)
         ax1.errorbar(gamma_dot_data[valid_fit], tau_w_data[valid_fit], 
                           yerr=tau_std[valid_fit], xerr=gd_std[valid_fit], 
                           fmt='o', color=COR_DADOS_FLUXO, ecolor=COR_ERRO, capsize=5, elinewidth=1.5,
                           label='Dados Médios $\\pm$ $\\sigma$', zorder=10)
    else:
        ax1.scatter(gamma_dot_data[valid_fit], tau_w_data[valid_fit], c=COR_DADOS_FLUXO, marker='o', label='Dados Processados', s=60, zorder=10)

    # Plota todos os modelos (destacando o melhor)
    model_keys = list(models.keys())
    for idx, n_model_name in enumerate(model_keys):
        d_model_data = model_results.get(n_model_name)
        if d_model_data:
            try:
                tau_plot_model = models[n_model_name](gd_plot, *d_model_data['params'])
                
                line_style = '--'
                line_width = 2
                z_order = 5
                model_color = CORES(idx % 10) # Usa cores sequenciais do tab10 para modelos
                
                if n_model_name == best_model_nome:
                    line_style = '-'
                    line_width = 3.5
                    z_order = 20
                    model_color = COR_MELHOR_MODELO # Red
                    label = fr'**Melhor Modelo: {n_model_name}** (R²={d_model_data["R2"]:.4f})'
                else:
                    label = fr'Modelo {n_model_name} (R²={d_model_data["R2"]:.4f})'
                    
                ax1.plot(gd_plot, tau_plot_model, 
                         label=label, 
                         linewidth=line_width, 
                         linestyle=line_style, 
                         color=model_color,
                         alpha=0.8,
                         zorder=z_order)
            except Exception as e:
                print(f"  Aviso ao plotar modelo {n_model_name} na Fig 1: {e}")

    ax1.set_title(f"Curva de Fluxo (Comparativo de Modelos){titulo_sufixo}\nSessão: {nome_sessao}")
    ax1.set_xlabel(r"Taxa de Cisalhamento Corrigida ($\dot{\gamma}_w$, s⁻¹)"); ax1.set_ylabel(r"Tensão de Cisalhamento ($\tau_w$, Pa)")
    ax1.legend(); ax1.grid(True,which="both",ls="--"); ax1.set_xscale('log'); ax1.set_yscale('log')
    fig1.tight_layout()
    # --- SALVAMENTO FIGURA 1 ---
    filename_fig1 = os.path.join(pasta_saida_graficos, f"{nome_base_arquivo}_curva_fluxo.png")
    try:
        fig1.savefig(filename_fig1, dpi=300, bbox_inches='tight')
        print(f"-> Salvo: {os.path.basename(filename_fig1)}")
    except Exception as e:
        print(f"ERRO ao salvar {os.path.basename(filename_fig1)}: {e}")


    # --- Figura 2: Curva de Viscosidade (Todos Modelos) ---
    fig2, ax2 = plt.subplots(figsize=(10, 7))
    valid_eta = ~np.isnan(eta_true_data) & (gamma_dot_data > 0) & (eta_true_data > 0)
    
    # Plota os dados com ou sem barra de erro
    if plot_type == 'errorbar' and tau_std is not None and gd_std is not None:
         # *** INICIALIZAÇÃO CORRIGIDA ***
         std_eta = np.zeros_like(eta_true_data)
         
         # Estimativa simplificada do erro de viscosidade (usando a aproximação diferencial)
         valid_std = (gamma_dot_data > 1e-9) & (tau_std >= 0) & (gd_std >= 0)
         if np.any(valid_std):
            std_tau_valid = tau_std[valid_std]
            std_gd_valid = gd_std[valid_std]
            eta_valid = eta_true_data[valid_std]
            tau_w_valid = tau_w_data[valid_std]
            gd_valid = gamma_dot_data[valid_std]
            
            # Cálculo de propagação de erro para Viscosidade
            std_eta_calc = eta_valid * np.sqrt(
                        (std_tau_valid / tau_w_valid)**2 + 
                        (std_gd_valid / gd_valid)**2
                    )
            std_eta[valid_std] = std_eta_calc # A linha que causava o NameError

            # --- PREPARAÇÃO DAS BARRAS DE ERRO ASSIMÉTRICAS (CLIPPING) ---
            # y_err_pos: distância do ponto (y_data) até o limite superior (y_data + std_eta)
            y_data_valid = eta_true_data[valid_eta]
            std_eta_valid = std_eta[valid_eta]
            
            # Garante que o erro negativo não seja plotado abaixo de 1e-9 (limite log)
            y_err_neg = np.clip(std_eta_valid, 0, y_data_valid - 1e-9) 
            y_err_pos = std_eta_valid 
            
            y_err_plot = np.array([y_err_neg, y_err_pos])
            x_err = gd_std[valid_eta]

         # Plotagem com cor otimizada (COR_DADOS_VISCOSIDADE e COR_ERRO)
         ax2.errorbar(gamma_dot_data[valid_eta], eta_true_data[valid_eta], 
                          yerr=y_err_plot, xerr=x_err, 
                          fmt='s', color=COR_DADOS_VISCOSIDADE, ecolor=COR_ERRO, capsize=5, elinewidth=1.5,
                          label='Viscosidade Média $\\pm$ $\\sigma$', zorder=10)
    else:
        ax2.scatter(gamma_dot_data[valid_eta], eta_true_data[valid_eta], label='Viscosidade Real (η)', c=COR_DADOS_VISCOSIDADE, marker='s', s=60, zorder=10)

    # Plota os modelos (cor sequencial do tab10)
    for idx, n_model_name in enumerate(model_keys):
        d_model_data = model_results.get(n_model_name)
        if d_model_data:
            try:
                tau_m = models[n_model_name](gd_plot, *d_model_data['params'])
                eta_m = tau_m / gd_plot
                
                line_style = '--'
                line_width = 2
                model_color = CORES(idx % 10)
                
                if n_model_name == best_model_nome:
                    line_style = '-'
                    line_width = 3.5
                    model_color = COR_MELHOR_MODELO # Red
                    
                # Aplicar clipping visual para HB/Bingham/Casson
                if n_model_name in ["Herschel-Bulkley", "Bingham", "Casson"]:
                    min_gd_data = gamma_dot_data[valid_fit].min()
                    clip_start_gamma = max(1e-4, min_gd_data * 0.1) 
                    clip_start_index_safe = np.argmin(np.abs(gd_plot - clip_start_gamma))
                    gd_plot_safe = gd_plot[clip_start_index_safe:]
                    eta_m_safe = eta_m[clip_start_index_safe:]

                    ax2.plot(gd_plot_safe, eta_m_safe, 
                             label=fr'Modelo {n_model_name} ($\eta$)', 
                             lw=line_width, 
                             alpha=0.8, 
                             linestyle=line_style,
                             color=model_color)
                else:
                    if n_model_name=="Newtoniano": eta_m = np.full_like(gd_plot, d_model_data['params'][0])
                    ax2.plot(gd_plot, eta_m, 
                             label=fr'Modelo {n_model_name} ($\eta$)', 
                             lw=line_width, 
                             alpha=0.8, 
                             linestyle=line_style,
                             color=model_color)
                             
            except Exception as e: 
                print(f"  Aviso ao plotar modelo {n_model_name} na Fig 2: {e}")

    ax2.set_title(f"Curva de Viscosidade (Comparativo de Modelos){titulo_sufixo}\nSessão: {nome_sessao}")
    ax2.set_xlabel(r"Taxa de Cisalhamento Corrigida ($\dot{\gamma}_w$, s⁻¹)"); ax2.set_ylabel(r"Viscosidade Real ($\eta$, Pa·s)")
    ax2.legend(); ax2.grid(True,which="both",ls="--"); ax2.set_xscale('log'); ax2.set_yscale('log')
    fig2.tight_layout()
    # --- SALVAMENTO FIGURA 2 ---
    filename_fig2 = os.path.join(pasta_saida_graficos, f"{nome_base_arquivo}_curva_viscosidade.png")
    try:
        fig2.savefig(filename_fig2, dpi=300, bbox_inches='tight')
        print(f"-> Salvo: {os.path.basename(filename_fig2)}")
    except Exception as e:
        print(f"ERRO ao salvar {os.path.basename(filename_fig2)}: {e}")

    # --- Figura 3: Comparativo de Viscosidades Aparente vs. Real (SOMENTE INDIVIDUAL) ---
    fig_aparente, ax_aparente = None, None
    if not is_statistical:
        fig_aparente, ax_aparente = plt.subplots(figsize=(10, 7))
        valid_apparent_idx = ~np.isnan(df_res['ηa (Pa·s)'].values)
        if np.any(valid_apparent_idx):
            ax_aparente.plot(df_res['γ̇aw (s⁻¹)'][valid_apparent_idx], df_res['ηa (Pa·s)'][valid_apparent_idx], 
                         label=r'Aparente ($\eta_a$ vs $\dot{\gamma}_{aw}$)', marker='o', linestyle='--', color=CORES(6)) # Cor Magenta
            
            # Real (corrigida)
            ax_aparente.plot(gamma_dot_data[valid_eta], eta_true_data[valid_eta], 
                         label=r'Real ($\eta$ vs $\dot{\gamma}_w$)', marker='s', linestyle='-', color=COR_DADOS_VISCOSIDADE) # Cor Verde Sólido

            ax_aparente.set_title(f"Comparativo de Viscosidades (Aparente vs. Real)\nSessão: {nome_sessao}")
            ax_aparente.set_xlabel(r"Taxa de Cisalhamento ($\dot{\gamma}$, s⁻¹)"); ax_aparente.set_ylabel(r"Viscosidade ($\eta$, Pa·s)")
            ax_aparente.legend(); ax_aparente.grid(True, which="both", ls="--"); ax_aparente.set_xscale('log'); ax_aparente.set_yscale('log')
            fig_aparente.tight_layout()
            
            # --- SALVAMENTO FIGURA 3 ---
            filename_fig3 = os.path.join(pasta_saida_graficos, f"{nome_base_arquivo}_comparativo_viscosidades.png")
            try:
                fig_aparente.savefig(filename_fig3, dpi=300, bbox_inches='tight')
                print(f"-> Salvo: {os.path.basename(filename_fig3)}")
            except Exception as e:
                print(f"ERRO ao salvar {os.path.basename(filename_fig3)}: {e}")

    # --- Figura 4: Gráfico de Resíduos (Melhor Modelo) ---
    fig4, ax4 = None, None
    if best_model_nome and model_results:
        fig4, ax4 = plt.subplots(figsize=(10, 7))
        tau_w_exp_fit = tau_w_data[valid_fit]
        tau_w_predito = models[best_model_nome](gd_fit, *model_results[best_model_nome]['params'])
        residuos = tau_w_exp_fit - tau_w_predito
        ax4.scatter(gd_fit, residuos, c=COR_RESIDUO, marker='x') # Cor Roxo Sólido
        ax4.axhline(y=0, color='k', linestyle='--')
        ax4.set_title(f"Gráfico de Resíduos do Melhor Modelo ({best_model_nome}){titulo_sufixo}\nSessão: {nome_sessao}")
        ax4.set_xlabel(r"Taxa de Cisalhamento Corrigida ($\dot{\gamma}_w$, s⁻¹)"); ax4.set_ylabel(r"Resíduo ($\tau_{exp} - \tau_{mod}$) [Pa]")
        ax4.set_xscale('log'); ax4.grid(True)
        fig4.tight_layout()
        
        # --- SALVAMENTO FIGURA 4 (GRÁFICO DE RESÍDUOS) ---
        filename_fig4 = os.path.join(pasta_saida_graficos, f"{nome_base_arquivo}_grafico_residuos.png")
        try:
            fig4.savefig(filename_fig4, dpi=300, bbox_inches='tight')
            print(f"-> Salvo: {os.path.basename(filename_fig4)}")
        except Exception as e:
            print(f"ERRO ao salvar {os.path.basename(filename_fig4)}: {e}")
        
    # --- Figura 5: P vs. Viscosidade (CONDICIONAL - SOMENTE Capilar Único/Individual) ---
    fig5, ax5 = None, None
    # Verifica se a sessão está no modo Individual e se D/L são únicos (Capilar Único)
    if not is_statistical and df_res['D_cap(mm)'].astype(str).unique().size == 1 and df_res['L_cap(mm)'].astype(str).unique().size == 1:
        # Filtra NaNs e valores não positivos, e converte para float
        p_bar_plot = pd.to_numeric(df_res['P_ext(bar)'], errors='coerce')
        eta_plot = df_res['η (Pa·s)']
        
        valid_pv = (~p_bar_plot.isna()) & (~eta_plot.isna()) & (eta_plot > 0) & (p_bar_plot > 0)
        
        if np.any(valid_pv):
            fig5, ax5 = plt.subplots(figsize=(10, 7))
            
            ax5.plot(p_bar_plot[valid_pv], eta_plot[valid_pv], 
                     label='Viscosidade Real vs Pressão', 
                     color=CORES(8), marker='D', linestyle='-', # Cor Marrom Sólida
                     linewidth=1.5, markersize=7)
            
            ax5.set_xlabel("Pressão Total Aplicada (bar)")
            ax5.set_ylabel(r"Viscosidade Real ($\eta$, Pa·s)")
            ax5.set_title(f"Pressão Aplicada vs. Viscosidade Real (Capilar Único)\nSessão: {nome_sessao}")
            ax5.legend(); ax5.grid(True, which="both", ls="--"); ax5.set_xscale('linear'); ax5.set_yscale('linear')
            fig5.tight_layout()
            
            # --- SALVAMENTO FIGURA 5 ---
            filename_fig5 = os.path.join(pasta_saida_graficos, f"{nome_base_arquivo}_pressao_vs_viscosidade.png")
            try:
                fig5.savefig(filename_fig5, dpi=300, bbox_inches='tight')
                print(f"-> Salvo: {os.path.basename(filename_fig5)}")
            except Exception as e:
                print(f"ERRO ao salvar {os.path.basename(filename_fig5)}: {e}")


    # --- EXIBIÇÃO ---
    print("\nVisualização pronta. Feche as janelas dos gráficos para encerrar.")
    plt.show()

if __name__ == "__main__":
    visualizador_principal()
