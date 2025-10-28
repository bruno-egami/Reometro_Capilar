# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# SCRIPT 2B.TRATAMENTO_ESTATISTICO.PY (VERSÃO INCORPORADA COM ANÁLISE DE VARIAÇÃO)
# (Agrupa por Pressão Nominal e calcula Média/Desvio Padrão e Parecer Qualitativo)
# -----------------------------------------------------------------------------

# 1. Importação de Bibliotecas
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
from datetime import datetime
import os 
import glob
import re
import json

# Configura o backend para visualização
try:
    matplotlib.use('QtAgg') 
except ImportError:
    print("Aviso: Backend QtAgg não encontrado, usando o padrão do sistema.")


# -----------------------------------------------------------------------------
# --- CONFIGURAÇÃO INICIAL ---
# -----------------------------------------------------------------------------
# Pasta onde os resultados do 2.Analise_reologica.py (CSV) estão localizados
INPUT_BASE_FOLDER = "resultados_analise_reologica"
# Pasta onde os resultados estatísticos serão salvos
STATISTICAL_OUTPUT_FOLDER = "resultados_analise_estatistica"

# Cria a pasta de saída se não existir
if not os.path.exists(STATISTICAL_OUTPUT_FOLDER):
    os.makedirs(STATISTICAL_OUTPUT_FOLDER)

# -----------------------------------------------------------------------------
# --- FUNÇÕES AUXILIARES DE FORMATAÇÃO E SELEÇÃO ---
# -----------------------------------------------------------------------------
def format_float_for_table(value, decimal_places=4):
    """Formata um número float para exibição em tabelas, usando notação científica para valores muito pequenos."""
    if isinstance(value, (float, np.floating)):
        if np.isnan(value): return "NaN"
        if abs(value) < 10**(-decimal_places) and value != 0 and abs(value) > 1e-12 :
             return f"{value:.{max(1,decimal_places)}g}"
        return f"{value:.{decimal_places}f}"
    return str(value)

def selecionar_arquivo_csv(pasta_base):
    """Lista e permite ao usuário selecionar um arquivo CSV de resultados."""
    print("\n--- Seleção de Arquivo CSV de Resultados (Individual) ---")
    
    # Busca por CSVs de resultados na pasta base e em todas as suas subpastas
    caminho_busca = os.path.join(pasta_base, '**', '*_resultados_reologicos.csv')
    arquivos_csv = glob.glob(caminho_busca, recursive=True)
    
    if not arquivos_csv:
        print(f"ERRO: Nenhum arquivo '*_resultados_reologicos.csv' encontrado na pasta '{pasta_base}'.")
        print("Certifique-se de que o script '2.Analise_reologica.py' foi executado primeiro.")
        return None, None, None

    print("Arquivos de resultados disponíveis:")
    
    # Cria uma lista de exibição mais amigável, mostrando apenas o nome da pasta e o arquivo
    arquivos_para_selecao = []
    for i, caminho_completo in enumerate(arquivos_csv):
        # O nome da sessão é o nome da pasta pai
        nome_sessao = os.path.basename(os.path.dirname(caminho_completo))
        arquivos_para_selecao.append({'caminho': caminho_completo, 'nome': nome_sessao})
        print(f"  {i+1}: {nome_sessao}")

    while True:
        try:
            escolha_str = input("\nDigite o NÚMERO da sessão (pasta) que contém o CSV que deseja analisar: ")
            if escolha_str == '0':
                return None, None, None
            
            escolha = int(escolha_str)
            if 1 <= escolha <= len(arquivos_para_selecao):
                caminho_selecionado = arquivos_para_selecao[escolha - 1]['caminho']
                nome_base = arquivos_para_selecao[escolha - 1]['nome']
                
                # O caminho de saída é a pasta de estatística + o nome da sessão base
                sessao_output_folder = os.path.join(STATISTICAL_OUTPUT_FOLDER, nome_base)
                if not os.path.exists(sessao_output_folder):
                    os.makedirs(sessao_output_folder)
                
                return caminho_selecionado, nome_base, sessao_output_folder
            else:
                print("ERRO: Escolha inválida.")
        except ValueError:
            print("ERRO: Entrada inválida. Digite um número.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")
            return None, None, None

# -----------------------------------------------------------------------------
# --- DEFINIÇÕES DOS MODELOS REOLÓGICOS (Consistentes com 2.Analise_reologica.py) ---
# -----------------------------------------------------------------------------
def model_newtonian(gd,eta): return eta*gd
def model_power_law(gd,K_pl,n_pl): return K_pl*np.power(np.maximum(gd, 1e-9),n_pl)
def model_bingham(gd,t0,ep): return t0+ep*gd
def model_hb(gd,t0,K_hb,n_hb): return t0+K_hb*np.power(np.maximum(gd, 1e-9),n_hb)
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

# -----------------------------------------------------------------------------
# --- FUNÇÕES DE ANÁLISE DE VARIAÇÃO E RELATÓRIO (INTEGRADO DO SCRIPT 2C) ---
# -----------------------------------------------------------------------------
def calcular_metricas(df):
    """Calcula Coeficiente de Variação (CV) e outras métricas estatísticas."""
    
    tau_mean = 'τw_MEDIA(Pa)'
    gd_mean = 'γ̇w_MEDIA(s⁻¹)'
    eta_mean = 'η_MEDIA(Pa·s)'
    tau_std = 'STD_τw (Pa)'
    gd_std = 'STD_γ̇w (s⁻¹)'
    
    df_metricas = df[[tau_mean, gd_mean, eta_mean]].copy()
    
    # Cálculo do Coeficiente de Variação (CV = (STD / Média) * 100)
    df_metricas['CV_τw(%)'] = (df[tau_std] / df[tau_mean]) * 100
    df_metricas['CV_γ̇w(%)'] = (df[gd_std] / df[gd_mean]) * 100

    # CV da Viscosidade (Propagação de Erro)
    df_metricas['CV_η_PROPAGADO(%)'] = np.sqrt(df_metricas['CV_τw(%)']**2 + df_metricas['CV_γ̇w(%)']**2)
    
    # Cálculo do CV Médio Ponderado, onde o peso é a própria Média de τw (pressão)
    total_tau = df[tau_mean].sum()
    if total_tau > 0:
        peso_tau = df[tau_mean] / total_tau
        CV_medio_ponderado_tau = (df_metricas['CV_τw(%)'] * peso_tau).sum()
        CV_medio_ponderado_gd = (df_metricas['CV_γ̇w(%)'] * peso_tau).sum()
        CV_medio_ponderado_eta = (df_metricas['CV_η_PROPAGADO(%)'] * peso_tau).sum()
    else:
        CV_medio_ponderado_tau, CV_medio_ponderado_gd, CV_medio_ponderado_eta = np.nan, np.nan, np.nan
        
    metricas_resumo = {
        'CV_τw_Medio_Ponderado(%)': CV_medio_ponderado_tau,
        'CV_γ̇w_Medio_Ponderado(%)': CV_medio_ponderado_gd,
        'CV_η_Propagado_Medio_Pond(%)': CV_medio_ponderado_eta,
        'Max_CV_τw(%)': df_metricas['CV_τw(%)'].max(),
        'Max_CV_γ̇w(%)': df_metricas['CV_γ̇w(%)'].max(),
        'Pontos_Totais': len(df)
    }
    
    return df_metricas, metricas_resumo

def gerar_parecer_qualitativo(metricas_resumo):
    """Gera um parecer de texto interpretando os resultados do CV."""
    
    cv_tau = metricas_resumo['CV_τw_Medio_Ponderado(%)']
    cv_gd = metricas_resumo['CV_γ̇w_Medio_Ponderado(%)']
    cv_eta = metricas_resumo['CV_η_Propagado_Medio_Pond(%)']
    
    parecer = []
    
    parecer.append("--- PARECER GERAL DA VARIAÇÃO ESTATÍSTICA (QUALI-QUANTITATIVO) ---")
    parecer.append(f"Análise baseada em {metricas_resumo['Pontos_Totais']} níveis de Pressão Nominal (P_ext) distintos.")
    parecer.append("")
    
    # 1. Análise da Reprodutibilidade da Tensão de Cisalhamento (τw)
    parecer.append("1. REPRODUTIBILIDADE DA TENSÃO DE CISALHAMENTO (τw - Pressão):")
    
    if cv_tau is None or np.isnan(cv_tau):
        parecer.append("  * ALERTA: Não foi possível calcular o CV médio. Verifique os dados.")
    elif cv_tau <= 5.0:
        parecer.append(f"  * RESULTADO: Excelente ({cv_tau:.2f}%). Indica uma alta reprodutibilidade da pressão aplicada e, consequentemente, da tensão de cisalhamento (τw).")
        parecer.append("  * CONCLUSÃO QUALITATIVA: O equipamento e o procedimento de ensaio demonstram ser altamente estáveis e controláveis.")
    elif 5.0 < cv_tau <= 10.0:
        parecer.append(f"  * RESULTADO: Boa ({cv_tau:.2f}%). Aceitável para a maioria dos materiais não-ideais (pastas, concretos).")
        parecer.append("  * CONCLUSÃO QUALITATIVA: Reprodutibilidade satisfatória. Pequenas variações podem estar ligadas à não-homogeneidade da amostra ou a flutuações no sistema de pressurização.")
    else: # cv_tau > 10.0
        parecer.append(f"  * RESULTADO: Moderada/Baixa ({cv_tau:.2f}%). CV alto, sugerindo variação significativa.")
        parecer.append("  * CONCLUSÃO QUALITATIVA: Recomenda-se investigar a origem da variação. Possíveis causas: segregação/desmistura da amostra, instabilidade da bomba, ou entupimento parcial do capilar.")

    # 2. Análise da Reprodutibilidade da Taxa de Cisalhamento (γ̇w - Vazão)
    parecer.append("\n2. REPRODUTIBILIDADE DA TAXA DE CISALHAMENTO (γ̇w - Vazão):")
    
    if cv_gd is None or np.isnan(cv_gd):
        parecer.append("  * ALERTA: Não foi possível calcular o CV de taxa de cisalhamento. Verifique os dados.")
    elif cv_gd <= 15.0:
        parecer.append(f"  * RESULTADO: Aceitável ({cv_gd:.2f}%). Variação esperada, já que γ̇w depende da vazão e da geometria do capilar.")
        parecer.append("  * CONCLUSÃO QUALITATIVA: O volume/massa extrudado(a) no tempo de ensaio se manteve relativamente constante para os diferentes testes.")
    else: # cv_gd > 15.0
        parecer.append(f"  * RESULTADO: Alta Variação ({cv_gd:.2f}%). Variação excessiva.")
        parecer.append("  * CONCLUSÃO QUALITATIVA: Este alto CV de vazão indica grande variabilidade na massa extrudada por repetição. Isso pode ser um sinal de 'wall slip' (deslizamento de parede), entupimento, ou que a amostra é altamente sensível à pressão/história de cisalhamento.")

    # 3. Análise da Estabilidade da Viscosidade (η)
    parecer.append("\n3. ESTABILIDADE ESTATÍSTICA DA VISCOSIDADE (η - Propagação de Erro):")

    if cv_eta is None or np.isnan(cv_eta):
        parecer.append("  * ALERTA: Não foi possível calcular a variação da Viscosidade.")
    elif cv_eta <= 10.0:
        parecer.append(f"  * RESULTADO: Estabilidade Alta ({cv_eta:.2f}%).")
        parecer.append("  * CONCLUSÃO QUALITATIVA: A variabilidade nos parâmetros fundamentais (τw e γ̇w) não resulta em uma incerteza excessiva no resultado final da viscosidade, reforçando a validade dos dados reológicos.")
    elif 10.0 < cv_eta <= 20.0:
        parecer.append(f"  * RESULTADO: Estabilidade Moderada ({cv_eta:.2f}%).")
        parecer.append("  * CONCLUSÃO QUALITATIVA: A viscosidade é consistente. O CV moderado sugere que os desvios padrão (τw e γ̇w) são relevantes e devem ser reportados junto com os valores médios.")
    else: # cv_eta > 20.0
        parecer.append(f"  * RESULTADO: Estabilidade Baixa/Incerteza Alta ({cv_eta:.2f}%).")
        parecer.append("  * CONCLUSÃO QUALITATIVA: A alta incerteza na viscosidade final indica que a combinação dos desvios de τw e γ̇w está comprometendo a precisão da curva de fluxo. O produto pode ser inerentemente não-reprodutível, ou o método requer melhor controle (temperatura, tempo de repouso).")

    # 4. Recomendações (Qualitativas)
    parecer.append("\n4. RECOMENDAÇÕES FINAIS (Qualitativas):")
    if (cv_tau is not None and cv_tau > 10.0) or (cv_gd is not None and cv_gd > 20.0):
        parecer.append("  * RECOMENDAÇÃO: Refazer o ensaio com maior controle da preparação da amostra (homogeneização) e verificar o desempenho do sistema de pressurização/coleta de massa.")
    elif cv_eta is not None and cv_eta > 15.0:
        parecer.append("  * RECOMENDAÇÃO: Avaliar a curva de viscosidade ponto a ponto. Pontos com CV alto devem ser excluídos no pré-tratamento do JSON (Script 1a) antes de reprocessar a análise estatística (Script 2b).")
    else:
        parecer.append("  * RECOMENDAÇÃO: Os dados são estatisticamente robustos. Prossiga com a modelagem e comparação com outras amostras (Scripts 3 e 4).")
        
    return "\n".join(parecer)

def salvar_relatorio_analise(nome_sessao, df_metricas, metricas_resumo, parecer_texto, output_folder):
    """Salva a tabela de CV e o parecer qualitativo em um arquivo TXT."""
    
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo_base = f"{nome_sessao}_{timestamp_str}_relatorio_variacao_estatistica"
    caminho_txt = os.path.join(output_folder, f"{nome_arquivo_base}.txt")
    
    # Formatação da tabela de CV
    df_metricas_display = df_metricas[[
        'τw_MEDIA(Pa)', 'CV_τw(%)', 
        'γ̇w_MEDIA(s⁻¹)', 'CV_γ̇w(%)', 
        'CV_η_PROPAGADO(%)'
    ]].copy()
    
    # Formata a tabela para o relatório
    fmt_stats = {col: (lambda x, dp=4: f"{x:.2f}") for col in df_metricas_display.columns if 'CV' in col or 'MEDIA' in col}
    tabela_cv_str = df_metricas_display.to_string(index=False, formatters=fmt_stats, na_rep='N/A')
    
    # Cria o conteúdo do relatório
    conteudo_relatorio = "="*80 + "\n"
    conteudo_relatorio += f"RELATÓRIO DE VARIAÇÃO ESTATÍSTICA APROFUNDADA\n"
    conteudo_relatorio += f"Sessão Base: {nome_sessao}\n"
    conteudo_relatorio += f"Data de Análise: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    conteudo_relatorio += "="*80 + "\n\n"
    
    conteudo_relatorio += "--- TABELA DE COEFICIENTE DE VARIAÇÃO (CV) POR PONTO ---\n"
    conteudo_relatorio += f"CV = (Desvio Padrão / Média) * 100\n"
    conteudo_relatorio += f"CV_η_PROPAGADO é uma estimativa de erro da viscosidade.\n\n"
    conteudo_relatorio += tabela_cv_str + "\n\n"
    
    conteudo_relatorio += "="*80 + "\n"
    conteudo_relatorio += f"--- RESUMO DAS MÉTRICAS GLOBAIS (Ponderado por τw) ---\n"
    conteudo_relatorio += f"CV Médio Ponderado de τw: {metricas_resumo['CV_τw_Medio_Ponderado(%)']:.2f} %\n"
    conteudo_relatorio += f"CV Médio Ponderado de γ̇w: {metricas_resumo['CV_γ̇w_Medio_Ponderado(%)']:.2f} %\n"
    conteudo_relatorio += f"CV Médio Ponderado de η:  {metricas_resumo['CV_η_Propagado_Medio_Pond(%)']:.2f} %\n"
    conteudo_relatorio += f"CV Máximo de τw (Pior Ponto): {metricas_resumo['Max_CV_τw(%)']:.2f} %\n"
    conteudo_relatorio += f"Pontos Analisados: {metricas_resumo['Pontos_Totais']}\n"
    conteudo_relatorio += "="*80 + "\n\n"
    
    conteudo_relatorio += parecer_texto
    conteudo_relatorio += "\n\n" + "="*80 + "\nFIM DO RELATÓRIO\n" + "="*80 + "\n"

    # Salvar
    try:
        with open(caminho_txt, 'w', encoding='utf-8') as f:
            f.write(conteudo_relatorio)
        print(f"\nSUCESSO: Relatório de variação estatística salvo em: {caminho_txt}")
    except Exception as e:
        print(f"\nERRO ao salvar o relatório TXT: {e}")

# -----------------------------------------------------------------------------
# --- FUNÇÃO PRINCIPAL ---
# -----------------------------------------------------------------------------
def processar_estatisticamente(caminho_csv, nome_base_sessao, output_folder):
    """Realiza o agrupamento, cálculo estatístico, ajuste de modelo, análise de CV e plotagem."""
    print("\n" + "="*60)
    print("--- INICIANDO TRATAMENTO ESTATÍSTICO ---")
    print("="*60)

    try:
        # Tenta a codificação comum primeiro
        df = pd.read_csv(caminho_csv, sep=';', decimal=',', encoding='utf-8')
    except Exception:
        # Tenta codificação sig (para CSVs gerados pelo Python com sep=; e decimal=,)
        df = pd.read_csv(caminho_csv, sep=';', decimal=',', encoding='utf-8-sig')
        
    print(f"Arquivo '{os.path.basename(caminho_csv)}' carregado com sucesso. {len(df)} pontos brutos.")

    # --- CORREÇÃO DE ERRO CRÍTICO (TypeError) ---
    # Garante que as colunas críticas para o cálculo estatístico sejam numéricas
    cols_para_stats = ['P_ext(bar)', 'τw (Pa)', 'γ̇w (s⁻¹)', 'η (Pa·s)']
    for col in cols_para_stats:
        if col in df.columns:
            # errors='coerce' transforma strings não numéricas em NaN, permitindo o cálculo da média
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # --- FIM CORREÇÃO ---

    # Extrai o timestamp do nome do arquivo original para nomear os resultados
    match = re.search(r'(\d{8}_\d{6})', os.path.basename(caminho_csv))
    timestamp_arquivo = match.group(0) if match else datetime.now().strftime("%Y%m%d_%H%M%S")


    # --- 1. Agrupamento de Dados ---
    df.dropna(subset=['P_ext(bar)'], inplace=True)
    df['P_NOMINAL_AGRUPADA'] = df['P_ext(bar)'].round(1)
    
    contagem_repeticoes = df.groupby('P_NOMINAL_AGRUPADA').size()
    print("\nContagem de repetições por nível de Pressão Nominal Agrupada:")
    print(contagem_repeticoes)

    # Colunas para cálculo estatístico
    # cols_para_stats já está definida no bloco de correção
    
    # Calcula Média e Desvio Padrão por grupo de pressão
    df_mean = df.groupby('P_NOMINAL_AGRUPADA')[cols_para_stats].mean().reset_index()
    df_std = df.groupby('P_NOMINAL_AGRUPADA')[cols_para_stats].std().reset_index()
    
    # Renomeia as colunas de desvio padrão
    df_std.columns = ['P_NOMINAL_AGRUPADA'] + [f'STD_{col}' for col in cols_para_stats]

    # Junta os DataFrames de média e desvio padrão
    df_estatistico = pd.merge(df_mean, df_std, on='P_NOMINAL_AGRUPADA')
    
    # Renomeia as colunas de média para serem mais claras no resultado final
    df_estatistico.rename(columns={'P_ext(bar)': 'P_ext_MEDIA(bar)',
                                   'τw (Pa)': 'τw_MEDIA(Pa)',
                                   'γ̇w (s⁻¹)': 'γ̇w_MEDIA(s⁻¹)',
                                   'η (Pa·s)': 'η_MEDIA(Pa·s)'}, inplace=True)

    # Remove linhas onde as médias são NaN ou infinitas (ex: divisão por zero no cálculo W-R)
    df_estatistico.dropna(subset=['τw_MEDIA(Pa)', 'γ̇w_MEDIA(s⁻¹)'], inplace=True)
    df_estatistico = df_estatistico[df_estatistico['γ̇w_MEDIA(s⁻¹)'] > 0].reset_index(drop=True)

    if df_estatistico.empty:
        print("\nERRO: Nenhum ponto estatístico válido encontrado após o agrupamento e limpeza.")
        return

    # --- Salvamento do CSV Estatístico ---
    # O nome do arquivo CSV estatístico deve seguir o padrão do arquivo original
    csv_stat_filename = os.path.basename(caminho_csv).replace('_resultados_reologicos.csv', '_resultados_estatisticos.csv')
    csv_stat_f = os.path.join(output_folder, csv_stat_filename)
    
    print("\n--- Tabela de Resultados Estatísticos (Médias e Desvios Padrão) ---")
    fmt_stats = {col: (lambda x, dp=4: format_float_for_table(x, dp)) for col in df_estatistico.columns}
    print(df_estatistico.to_string(index=False, formatters=fmt_stats, na_rep='N/A'))
    
    
    try:
        # Salva o arquivo CSV estatístico com ponto e vírgula e vírgula como decimal
        df_estatistico.to_csv(csv_stat_f, index=False, sep=';', decimal=',', float_format='%.5f', encoding='utf-8-sig')
        print(f"\nResultados estatísticos salvos em: {csv_stat_f}")
    except Exception as e:
        print(f"ERRO ao salvar CSV estatístico: {e}")
        
    # =========================================================================
    # --- 2. ANÁLISE DE VARIAÇÃO E PARECER QUALITATIVO (NOVO PASSO INTEGRADO) ---
    # =========================================================================
    print("\n" + "-"*60)
    print("--- 2. ANÁLISE DE VARIAÇÃO E GERAÇÃO DE PARECER ---")
    print("-" * 60)
    
    try:
        df_metricas, metricas_resumo = calcular_metricas(df_estatistico)
        parecer_texto = gerar_parecer_qualitativo(metricas_resumo)
        salvar_relatorio_analise(nome_base_sessao, df_metricas, metricas_resumo, parecer_texto, output_folder)
    except Exception as e:
        print(f"ALERTA: Falha na Análise de Variação e Geração do Parecer. Erro: {e}")
        
    # =========================================================================
    # --- 3. Ajuste de Modelos na Curva Média ---
    # =========================================================================
    # --- CORREÇÃO DE SINTAXE (SyntaxWarning) ---
    print(r"\n--- 3. Ajustando Modelos Reológicos na Curva Média ($\mu(\tau_w)$ vs $\mu(\dot{\gamma}_{w})$) ---")
    
    # Prepara dados para ajuste
    gd_fit_mean = df_estatistico['γ̇w_MEDIA(s⁻¹)'].values
    tau_fit_mean = df_estatistico['τw_MEDIA(Pa)'].values
    model_results = {}
    best_model_nome = ""

    if len(gd_fit_mean) >= 2:
        valid_log_n_prime = (tau_fit_mean > 0) & (gd_fit_mean > 0)
        n_prime, log_K_prime = 1.0, 0.0
        if np.sum(valid_log_n_prime) > 1:
            log_tau, log_gamma = np.log(tau_fit_mean[valid_log_n_prime]), np.log(gd_fit_mean[valid_log_n_prime])
            try:
                n_prime, log_K_prime, _, _, _ = linregress(log_gamma, log_tau)
            except: pass

        for name, (func, bounds) in MODELS.items():
            n_p = func.__code__.co_argcount - 1
            if len(gd_fit_mean) < n_p: continue
            
            p0 = [1.0] * n_p
            # Chutes iniciais mais inteligentes, consistentes com 2.Analise_reologica.py
            tau0_g = max(1e-3, np.min(tau_fit_mean) / 2) if len(tau_fit_mean) > 0 else 0.1
            eta_a_mean_g = np.mean(tau_fit_mean / gd_fit_mean) if len(gd_fit_mean) > 0 else 0.1
            K_g = np.exp(log_K_prime) if not np.isnan(log_K_prime) else 1.0
            n_g = n_prime if (n_prime > 0 and not np.isnan(n_prime) and 0.1 < n_prime < 5.0) else 0.5
            
            if name=="Newtoniano": p0=[eta_a_mean_g]
            elif name=="Lei da Potência": p0 = [K_g, n_g]
            elif name=="Bingham": p0 = [tau0_g, eta_a_mean_g]
            elif name=="Herschel-Bulkley": p0 = [tau0_g, K_g, n_g]
            elif name=="Casson": p0 = [tau0_g, eta_a_mean_g]

            try:
                params_fit, cov = curve_fit(func, gd_fit_mean, tau_fit_mean, p0=p0, bounds=bounds, maxfev=20000, method='trf')
                tau_pred = func(gd_fit_mean, *params_fit)
                ss_r, ss_t = np.sum((tau_fit_mean - tau_pred)**2), np.sum((tau_fit_mean - np.mean(tau_fit_mean))**2)
                r2 = 1 - (ss_r / ss_t) if ss_t > 1e-12 else (1.0 if ss_r < 1e-12 else 0.0)
                model_results[name] = {'params': params_fit, 'R2': r2}
            except Exception as e:
                pass

        if model_results:
            best_model_nome = max(model_results, key=lambda name: model_results[name]['R2'])
            print(f"\nSUCESSO: Melhor modelo ajustado: {best_model_nome} (R²: {model_results[best_model_nome]['R2']:.4f})")
            
            # --- Geração do JSON de Parâmetros (NECESSÁRIO PARA SCRIPTS 3 e 4) ---
            results_to_save = {}
            for name, data in model_results.items():
                results_to_save[name] = {
                    'params': data['params'].tolist(),
                    'R2': data['R2']
                }

            dados_completos_para_salvar = {
                "modelos_ajustados": results_to_save,
                "parametros_wr": {"n_prime": None, "log_K_prime": None} 
            }
            
            # Garante que o nome do arquivo JSON siga o padrão
            json_models_filename = os.path.basename(caminho_csv).replace('_resultados_reologicos.csv', '_parametros_modelos.json')
            json_models_f = os.path.join(output_folder, json_models_filename)
            
            try:
                with open(json_models_f, 'w', encoding='utf-8') as f:
                    json.dump(dados_completos_para_salvar, f, indent=4)
                print(f"Parâmetros dos modelos MÉDIOS salvos em: {json_models_f}")
            except Exception as e:
                print(f"ERRO ao salvar parâmetros dos modelos estatísticos: {e}")

        else:
            print("\nAVISO: Nenhum modelo reológico pôde ser ajustado na curva média.")
    else:
        print("\nAVISO: Menos de 2 pontos médios válidos. Ajuste de modelos não realizado.")

    # --- 4. Plotagem da Curva de Fluxo com Barras de Erro ---
    print("\n--- 4. Gerando Gráfico de Curva de Fluxo com Erros ---")
    
    # Prepara os dados de erro
    tau_mean = df_estatistico['τw_MEDIA(Pa)'].values
    gd_mean = df_estatistico['γ̇w_MEDIA(s⁻¹)'].values
    tau_std = df_estatistico['STD_τw (Pa)'].values
    gd_std = df_estatistico['STD_γ̇w (s⁻¹)'].values
    
    tau_std = np.maximum(tau_std, 0)
    gd_std = np.maximum(gd_std, 0)

    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plota os pontos médios com barras de erro
    ax.errorbar(gd_mean, tau_mean, 
                yerr=tau_std, 
                xerr=gd_std,
                fmt='o', 
                color='k', 
                ecolor='gray', 
                capsize=5,
                elinewidth=1.5,
                label='Média $\\pm$ Desvio Padrão (N)',
                zorder=10)

    # Plota o melhor modelo ajustado
    if best_model_nome and best_model_nome in model_results:
        min_gd, max_gd = np.min(gd_mean) * 0.5, np.max(gd_mean) * 1.5
        gd_plot = np.geomspace(min_gd, max_gd, 200)
        
        best_model_func = MODELS[best_model_nome][0]
        best_model_params = model_results[best_model_nome]['params']
        tau_plot_model = best_model_func(gd_plot, *best_model_params)
        r2_val = model_results[best_model_nome]['R2']

        ax.plot(gd_plot, tau_plot_model, 
                color='red', 
                linestyle='--', 
                linewidth=3.5,
                label=f'Ajuste {best_model_nome} (R²={r2_val:.4f})', 
                zorder=20)

    ax.set_title(f"Curva de Fluxo Média com Tratamento Estatístico\nSessão Base: {nome_base_sessao}", fontsize=16)
    # --- CORREÇÃO DE SINTAXE (SyntaxWarning) ---
    ax.set_xlabel(r"Taxa de Cisalhamento Real Média ($\mu_{\dot{\gamma}_w}$, s⁻¹)", fontsize=12)
    ax.set_ylabel(r"Tensão de Cisalhamento Média ($\mu_{\tau_w}$, Pa)", fontsize=12)
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, which="both", ls="--", alpha=0.7)
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    fig.tight_layout()
    
    # O nome do PNG deve seguir o nome do arquivo estatístico
    png_filename = os.path.basename(csv_stat_f).replace('.csv', '.png')
    png_f = os.path.join(output_folder, png_filename)
    try:
        fig.savefig(png_f, dpi=300, bbox_inches='tight')
        print(f"Gráfico da curva de fluxo estatística salvo em: {png_f}")
    except Exception as e:
        print(f"ERRO ao salvar o gráfico: {e}")

    # Exibir o gráfico (necessário fechar para o script terminar)
    print("\nFeche a janela do gráfico para finalizar a execução.")
    plt.show()

# -----------------------------------------------------------------------------
# --- INÍCIO DA EXECUÇÃO ---
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    caminho_csv_input, nome_base, output_f = selecionar_arquivo_csv(INPUT_BASE_FOLDER)
    
    if caminho_csv_input:
        processar_estatisticamente(caminho_csv_input, nome_base, output_f)
    
    print("\n--- FIM DO SCRIPT DE TRATAMENTO ESTATÍSTICO ---")