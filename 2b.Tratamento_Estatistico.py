# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# SCRIPT 2B.TRATAMENTO_ESTATISTICO_ROBUSTO.PY 
# (VERSÃO COM FILTRO AUTOMÁTICO DE OUTLIERS)
# -----------------------------------------------------------------------------

# 1. Importação de Bibliotecas
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress
import matplotlib.pyplot as plt
import matplotlib # <-- CORREÇÃO: Esta linha foi readicionada
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
# Pasta onde os JSONs de origem (do script 1a) estão
JSON_COMPANHEIRO_DIR = "resultados_testes_reometro" 

# --- NOVO: Fator de agrupamento de pressão ---
# Altere este valor para agrupar os pontos.
# 0.1 = agrupa a cada 0.1 bar (ex: 1.0, 1.1, 1.2...)
# 0.25 = agrupa a cada 0.25 bar (ex: 1.0, 1.25, 1.5...)
# 0.5 = agrupa a cada 0.5 bar (ex: 1.0, 1.5, 2.0...)
FATOR_AGRUPAMENTO_BAR = 0.1

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
def calcular_metricas(df_estatistico):
    """Calcula Coeficiente de Variação (CV) e outras métricas estatísticas."""
    
    tau_mean = 'τw_MEDIA(Pa)'
    gd_mean = 'γ̇w_MEDIA(s⁻¹)'
    eta_mean = 'η_MEDIA(Pa·s)'
    tau_std = 'STD_τw (Pa)'
    gd_std = 'STD_γ̇w (s⁻¹)'
    
    df_metricas = df_estatistico.copy() # <-- MUDANÇA: Copia o DF inteiro
    
    # Cálculo do Coeficiente de Variação (CV = (STD / Média) * 100)
    # Adiciona 1e-9 para evitar divisão por zero se a média for 0
    df_metricas['CV_τw(%)'] = (df_metricas[tau_std] / (df_metricas[tau_mean] + 1e-9)) * 100
    df_metricas['CV_γ̇w(%)'] = (df_metricas[gd_std] / (df_metricas[gd_mean] + 1e-9)) * 100

    # CV da Viscosidade (Propagação de Erro)
    df_metricas['CV_η_PROPAGADO(%)'] = np.sqrt(df_metricas['CV_τw(%)']**2 + df_metricas['CV_γ̇w(%)']**2)
    
    # Cálculo do CV Médio Ponderado, onde o peso é a própria Média de τw (pressão)
    total_tau = df_metricas[tau_mean].sum()
    if total_tau > 0:
        peso_tau = df_metricas[tau_mean] / total_tau
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
        'Pontos_Totais': len(df_metricas)
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
    parecer.append(f"NOTA: Agrupamento por {FATOR_AGRUPAMENTO_BAR} bar. Filtro automático de outliers (baseado em >2σ de γ̇w) foi aplicado.")
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
        parecer.append("  * CONCLUSÃO QUALITATIVA: O volume/massa extrudado(a) no tempo de ensaio se manteve relativamente constante para os diferentes testes (após remoção de outliers).")
    else: # cv_gd > 15.0
        parecer.append(f"  * RESULTADO: Alta Variação ({cv_gd:.2f}%). Variação excessiva (mesmo após o filtro).")
        parecer.append("  * CONCLUSÃO QUALITATIVA: Este alto CV de vazão indica grande variabilidade na massa extrudada. Isso pode ser um sinal de 'wall slip' (deslizamento de parede), entupimento, ou que a amostra é altamente sensível à pressão/história de cisalhamento.")

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
        parecer.append("  * RECOMENDAÇÃO: Mesmo após o filtro, a variação é alta. Refazer o ensaio com maior controle da preparação da amostra (homogeneização) e verificar o desempenho do sistema.")
    elif cv_eta is not None and cv_eta > 15.0:
        parecer.append("  * RECOMENDAÇÃO: A variação é moderada, mas os dados são utilizáveis. O filtro automático removeu os piores pontos. Prossiga com cautela.")
    else:
        parecer.append("  * RECOMENDAÇÃO: Os dados são estatisticamente robustos (após o filtro). Prossiga com a modelagem e comparação com outras amostras (Scripts 3 e 4).")
        
    return "\n".join(parecer)

# --- NOVO: Função para Analisar Resíduos ---
def analisar_residuos(residuos, gd_mean, best_model_nome):
    """Gera uma análise qualitativa do gráfico de resíduos."""
    if residuos is None or len(residuos) == 0:
        return "N/A: Resíduos não disponíveis para análise."

    analise = []
    analise.append(f"--- ANÁLISE DO GRÁFICO DE RESÍDUOS (Modelo: {best_model_nome}) ---")
    
    # Métrica básica: Resíduo médio
    mean_residual = np.mean(residuos)
    analise.append(f"Resíduo Médio: {mean_residual:.3f} Pa")
    
    # Análise qualitativa da distribuição
    # Verifica se os resíduos estão mais ou menos centrados em zero
    if abs(mean_residual) < np.std(residuos) * 0.5: # Critério arbitrário, pode ser ajustado
        analise.append("* Distribuição: Os resíduos parecem estar razoavelmente centrados em torno de zero, o que é um bom sinal.")
    else:
        analise.append("* Distribuição: Há um viés nos resíduos (média diferente de zero), sugerindo que o modelo pode estar sistematicamente superestimando ou subestimando os dados.")

    # Tenta detectar tendências (correlação com a taxa de cisalhamento)
    try:
        # Usa regressão linear simples nos resíduos vs log(taxa de cisalhamento)
        slope, _, r_value, _, _ = linregress(np.log(gd_mean), residuos)
        
        # Um R² baixo indica falta de tendência linear clara
        if r_value**2 < 0.3: # Critério arbitrário
            analise.append("* Tendência: Não há uma tendência linear clara nos resíduos em relação à taxa de cisalhamento (log). Isso indica que o modelo captura bem a forma da curva.")
        else:
            if slope > 0:
                analise.append("* Tendência: Observa-se uma tendência de aumento dos resíduos com a taxa de cisalhamento. O modelo pode estar subestimando a curvatura em altas taxas.")
            else:
                analise.append("* Tendência: Observa-se uma tendência de diminuição dos resíduos com a taxa de cisalhamento. O modelo pode estar superestimando a curvatura em altas taxas.")
    except Exception:
        analise.append("* Tendência: Não foi possível avaliar a tendência (poucos pontos ou erro no cálculo).")

    # Avaliação geral
    analise.append("* Avaliação Geral: Verifique o gráfico de resíduos visualmente. Uma distribuição aleatória e sem padrões claros em torno da linha zero indica um bom ajuste do modelo aos dados.")
    
    return "\n".join(analise)
# --- FIM NOVO ---

def salvar_relatorio_analise(nome_sessao, df_metricas, metricas_resumo, parecer_texto, output_folder, relatorio_agrupamento, metadados_ensaio, analise_residuos_texto): # <-- NOVO: Adiciona parâmetro
    """Salva a tabela de CV e o parecer qualitativo em um arquivo TXT."""
    
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo_base = f"{nome_sessao}_{timestamp_str}_relatorio_variacao_estatistica_ROBUSTO"
    caminho_txt = os.path.join(output_folder, f"{nome_arquivo_base}.txt")
    
    # Formatação da tabela de CV
    df_metricas_display = df_metricas[[
        'P_NOMINAL_AGRUPADA',
        'N_Repeticoes',
        'τw_MEDIA(Pa)', 'CV_τw(%)', 
        'γ̇w_MEDIA(s⁻¹)', 'CV_γ̇w(%)', 
        'CV_η_PROPAGADO(%)'
    ]].copy()
    
    # Formata a tabela para o relatório
    fmt_stats = {
        'P_NOMINAL_AGRUPADA': (lambda x, dp=2: f"{x:.2f}"),
        'N_Repeticoes': (lambda x: f"{x:.0f}"),
        'τw_MEDIA(Pa)': (lambda x, dp=2: f"{x:.2f}"),
        'γ̇w_MEDIA(s⁻¹)': (lambda x, dp=2: f"{x:.2f}"),
    }
    # Adiciona formatação para todas as colunas de CV
    fmt_stats.update({col: (lambda x, dp=2: f"{x:.2f}") for col in df_metricas_display.columns if 'CV' in col})
    
    # Renomeia colunas para a tabela ficar mais bonita
    df_metricas_display.rename(columns={
        'P_NOMINAL_AGRUPADA': 'P_Nominal (bar)',
        'N_Repeticoes': 'N (Final)',
        'τw_MEDIA(Pa)': 'τw Média (Pa)',
        'CV_τw(%)': 'CV τw (%)',
        'γ̇w_MEDIA(s⁻¹)': 'γ̇w Média (s⁻¹)',
        'CV_γ̇w(%)': 'CV γ̇w (%)',
        'CV_η_PROPAGADO(%)': 'CV η (Prop.) (%)'
    }, inplace=True)

    tabela_cv_str = df_metricas_display.to_string(index=False, formatters=fmt_stats, na_rep='N/A')
    
    # Cria o conteúdo do relatório
    conteudo_relatorio = "="*80 + "\n"
    conteudo_relatorio += f"RELATÓRIO DE VARIAÇÃO ESTATÍSTICA ROBUSTA (COM FILTRO DE OUTLIERS)\n"
    conteudo_relatorio += f"Sessão Base: {nome_sessao}\n"
    conteudo_relatorio += f"Data de Análise: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    # --- NOVO: Resumo dos Metadados ---
    if metadados_ensaio.get('encontrado', False):
        conteudo_relatorio += "="*80 + "\n"
        conteudo_relatorio += f"RESUMO DO ENSAIO (Dados de: {metadados_ensaio.get('arquivo_json_origem', 'N/A')})\n"
        conteudo_relatorio += "-"*80 + "\n"
        conteudo_relatorio += f"ID/Formulação: {metadados_ensaio.get('id_amostra', 'N/A')}\n"
        conteudo_relatorio += f"Descrição:     {metadados_ensaio.get('descricao', 'N/A')}\n"
        conteudo_relatorio += f"Capilar:       {metadados_ensaio.get('diametro_capilar_mm', 'N/A')} mm x {metadados_ensaio.get('comprimento_capilar_mm', 'N/A')} mm (D x L)\n"
        conteudo_relatorio += f"Densidade:     {metadados_ensaio.get('densidade_pasta_g_cm3', 'N/A')} g/cm³\n"
        
        # Adiciona o relatório de união do script 1a, se existir
        relatorio_uniao = metadados_ensaio.get('relatorio_uniao', {})
        if relatorio_uniao:
            arquivos_unidos = relatorio_uniao.get('arquivos_unidos', [])
            stats_limpeza = relatorio_uniao.get('estatisticas_limpeza', {})
            if arquivos_unidos:
                conteudo_relatorio += f"\nArquivos de Origem Unidos ({len(arquivos_unidos)}):\n"
                for arq in arquivos_unidos:
                    conteudo_relatorio += f"  - {arq}\n"
                conteudo_relatorio += f"  Pontos (Massa 0g removidos): {stats_limpeza.get('pontos_massa_zero_removidos', 'N/A')}\n"
                conteudo_relatorio += f"  Pontos (Duplicados removidos): {stats_limpeza.get('pontos_duplicados_removidos', 'N/A')}\n"
    # --- FIM Resumo Metadados ---
            
    conteudo_relatorio += "="*80 + "\n\n"
    
    # --- NOVO: Resumo do Filtro de Outliers ---
    if relatorio_agrupamento:
        conteudo_relatorio += "--- DETALHAMENTO DO AGRUPAMENTO E FILTRO DE OUTLIERS ---\n"
        conteudo_relatorio += f"Fator de Agrupamento: {FATOR_AGRUPAMENTO_BAR} bar\n"
        conteudo_relatorio += "Filtro aplicado: > 2.0 desvios padrão da média de γ̇w (s⁻¹) (grupos com N < 3 são ignorados)\n"
        
        # Cabeçalho da tabela
        header = f"{'P_Nominal (bar)':<18} | {'N (Bruto)':<10} | {'N (Removidos)':<13} | {'N (Final)':<10}"
        conteudo_relatorio += header + "\n"
        conteudo_relatorio += "-" * len(header) + "\n"
        
        total_bruto = 0
        total_removidos_filtro = 0
        total_final_filtro = 0
        
        # Ordena os grupos pela pressão (chave do dict)
        for p_nominal, dados in sorted(relatorio_agrupamento.items()):
            linha = f"{p_nominal:<18.2f} | {dados['n_bruto']:<10} | {dados['n_removidos']:<13} | {dados['n_final']:<10}"
            conteudo_relatorio += linha + "\n"
            total_bruto += dados['n_bruto']
            total_removidos_filtro += dados['n_removidos']
            total_final_filtro += dados['n_final']
        
        # Rodapé da tabela
        conteudo_relatorio += "-" * len(header) + "\n"
        linha_total = f"{'Total':<18} | {total_bruto:<10} | {total_removidos_filtro:<13} | {total_final_filtro:<10}"
        conteudo_relatorio += linha_total + "\n\n"
    # --- FIM Resumo Filtro ---

    conteudo_relatorio += "--- TABELA DE COEFICIENTE DE VARIAÇÃO (CV) POR PONTO (PÓS-FILTRO) ---\n"
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
    conteudo_relatorio += "\n\n" + "="*80 + "\n" # <-- NOVO: Divisor
    
    # --- NOVO: Adiciona Análise de Resíduos ---
    conteudo_relatorio += analise_residuos_texto
    # --- FIM ---
    
    conteudo_relatorio += "\n\n" + "="*80 + "\nFIM DO RELATÓRIO\n" + "="*80 + "\n"

    # Salvar
    try:
        with open(caminho_txt, 'w', encoding='utf-8') as f:
            f.write(conteudo_relatorio)
        print(f"\nSUCESSO: Relatório de variação estatística salvo em: {caminho_txt}")
    except Exception as e:
        print(f"\nERRO ao salvar o relatório TXT: {e}")

# -----------------------------------------------------------------------------
# --- FUNÇÃO DE FILTRAGEM (NOVA) ---
# -----------------------------------------------------------------------------
def filtrar_outliers_std(df_grupo, coluna_filtro='γ̇w (s⁻¹)', num_std=2.0):
    """
    Filtra outliers de um sub-dataframe (grupo) com base em N desvios padrão.
    A coluna 'coluna_filtro' (ex: γ̇w) é usada para decidir quem é outlier.
    """
    # Não filtra grupos com poucas repetições (precisamos de pelo menos 3 para std)
    if len(df_grupo) < 3: 
        return df_grupo, 0
    
    media = df_grupo[coluna_filtro].mean()
    std = df_grupo[coluna_filtro].std()
    
    # Não filtra se não houver variação (std=0) ou se std for NaN
    if std == 0 or np.isnan(std):
        return df_grupo, 0
        
    # Define os limites (thresholds)
    limite_superior = media + (num_std * std)
    limite_inferior = media - (num_std * std)
    
    # Filtra o dataframe
    df_filtrado = df_grupo[
        (df_grupo[coluna_filtro] >= limite_inferior) & 
        (df_grupo[coluna_filtro] <= limite_superior)
    ]
    
    removidos = len(df_grupo) - len(df_filtrado)
    return df_filtrado, removidos

# -----------------------------------------------------------------------------
# --- FUNÇÃO PRINCIPAL ---
# -----------------------------------------------------------------------------
def processar_estatisticamente(caminho_csv, nome_base_sessao, output_folder):
    """Realiza o agrupamento, cálculo estatístico, ajuste de modelo, análise de CV e plotagem."""
    print("\n" + "="*60)
    print("--- INICIANDO TRATAMENTO ESTATÍSTICO (ROBUSTO) ---")
    print("="*60)

    try:
        # Tenta a codificação comum primeiro
        df = pd.read_csv(caminho_csv, sep=';', decimal=',', encoding='utf-8')
    except Exception:
        # Tenta codificação sig (para CSVs gerados pelo Python com sep=; e decimal=,)
        df = pd.read_csv(caminho_csv, sep=';', decimal=',', encoding='utf-8-sig')
        
    print(f"Arquivo '{os.path.basename(caminho_csv)}' carregado com sucesso. {len(df)} pontos brutos.")

    # Extrai o timestamp do nome do arquivo original para nomear os resultados
    match = re.search(r'(\d{8}_\d{6})', os.path.basename(caminho_csv))
    timestamp_arquivo = match.group(0) if match else datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- Tenta carregar metadados do JSON companheiro (criado pelo script 1a) ---
    metadados_ensaio = {'encontrado': False}
    # O nome_base_sessao (ex: 40%1.5x43mm_2025-10-29) deve ser o nome do JSON
    caminho_json_companheiro = os.path.join(JSON_COMPANHEIRO_DIR, nome_base_sessao + ".json")

    if os.path.exists(caminho_json_companheiro):
        try:
            with open(caminho_json_companheiro, 'r', encoding='utf-8') as f:
                data_json = json.load(f)
            metadados_ensaio = {
                'encontrado': True,
                'arquivo_json_origem': os.path.basename(caminho_json_companheiro),
                'id_amostra': data_json.get('id_amostra', 'N/A'),
                'descricao': data_json.get('descricao', 'N/A'),
                'diametro_capilar_mm': data_json.get('diametro_capilar_mm', 'N/A'),
                'comprimento_capilar_mm': data_json.get('comprimento_capilar_mm', 'N/A'),
                'densidade_pasta_g_cm3': data_json.get('densidade_pasta_g_cm3', 'N/A'),
                'relatorio_uniao': data_json.get('relatorio_uniao', {}) # Pega o relatório de união do script 1a
            }
            print(f"Info: Metadados carregados com sucesso do JSON: {caminho_json_companheiro}")
        except Exception as e:
            print(f"Aviso: Encontrado JSON companheiro ({caminho_json_companheiro}), mas falhou ao lê-lo: {e}")
    else:
        print(f"Aviso: Não foi possível encontrar o arquivo JSON companheiro em {caminho_json_companheiro} para extrair metadados.")
        

    # --- 1. Agrupamento de Dados (Preliminar) ---
    df.dropna(subset=['P_ext(bar)'], inplace=True)
    # --- MUDANÇA AQUI ---
    # Substitui .round(1) pela fórmula de agrupamento flexível
    df['P_NOMINAL_AGRUPADA'] = np.round(df['P_ext(bar)'] / FATOR_AGRUPAMENTO_BAR) * FATOR_AGRUPAMENTO_BAR
    # --- FIM DA MUDANÇA ---
    
    # =========================================================================
    # --- NOVO: 1b. Filtragem de Outliers ---
    # =========================================================================
    print(f"\n--- 1b. Aplicando Filtro de Outliers (baseado em > 2σ de γ̇w) ---")
    
    # Vamos agrupar, aplicar o filtro, e depois concatenar os resultados
    grupos = df.groupby('P_NOMINAL_AGRUPADA')
    dfs_filtrados = []
    total_removidos = 0
    relatorio_agrupamento = {} # <-- NOVA LINHA
    
    # Coluna principal para filtrar (causa da alta variação no relatório)
    coluna_alvo_filtro = 'γ̇w (s⁻¹)' 
    
    if coluna_alvo_filtro not in df.columns:
        print(f"AVISO: Coluna '{coluna_alvo_filtro}' não encontrada para filtragem. Pulando filtro.")
        df_filtrado_final = df
    else:
        for nome_grupo, grupo in grupos:
            grupo_filtrado, removidos = filtrar_outliers_std(grupo, coluna_filtro=coluna_alvo_filtro, num_std=2.0)
            dfs_filtrados.append(grupo_filtrado)
            
            # --- NOVO: Captura detalhes do agrupamento ---
            relatorio_agrupamento[nome_grupo] = {
                'n_bruto': len(grupo),
                'n_removidos': removidos,
                'n_final': len(grupo_filtrado)
            }
            # --- FIM ---

            if removidos > 0:
                print(f"  Grupo P_nominal={nome_grupo:.2f}: {removidos} ponto(s) outlier(s) removido(s).") # Ajuste no print
            total_removidos += removidos
            
        df_filtrado_final = pd.concat(dfs_filtrados)
        print(f"Total de {total_removidos} outliers removidos. {len(df_filtrado_final)} pontos válidos restantes.")
    
    # =========================================================================

    # --- 1c. Agrupamento Estatístico (Final, com dados limpos) ---
    
    # A partir daqui, usa df_filtrado_final ao invés de df
    contagem_repeticoes = df_filtrado_final.groupby('P_NOMINAL_AGRUPADA').size()
    print("\nContagem de repetições (pós-filtro) por nível de Pressão Nominal Agrupada:")
    print(contagem_repeticoes)
    
    # Converter contagem para DataFrame para o merge
    df_contagem = contagem_repeticoes.reset_index(name='N_Repeticoes')

    # Colunas para cálculo estatístico
    cols_para_stats = ['P_ext(bar)', 'τw (Pa)', 'γ̇w (s⁻¹)', 'η (Pa·s)']
    
    # Calcula Média e Desvio Padrão por grupo de pressão
    df_mean = df_filtrado_final.groupby('P_NOMINAL_AGRUPADA')[cols_para_stats].mean().reset_index()
    df_std = df_filtrado_final.groupby('P_NOMINAL_AGRUPADA')[cols_para_stats].std().reset_index()
    
    # Renomeia as colunas de desvio padrão
    df_std.columns = ['P_NOMINAL_AGRUPADA'] + [f'STD_{col}' for col in cols_para_stats]

    # Junta os DataFrames de média e desvio padrão
    df_estatistico = pd.merge(df_mean, df_std, on='P_NOMINAL_AGRUPADA')
    
    # Adiciona a contagem (N_Repeticoes) ao dataframe estatístico
    df_estatistico = pd.merge(df_estatistico, df_contagem, on='P_NOMINAL_AGRUPADA')
    
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
    csv_stat_filename = os.path.basename(caminho_csv).replace('_resultados_reologicos.csv', '_resultados_estatisticos_ROBUSTO.csv')
    csv_stat_f = os.path.join(output_folder, csv_stat_filename)
    
    print("\n--- Tabela de Resultados Estatísticos (Médias e Desvios Padrão PÓS-FILTRO) ---")
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
    print("--- 2. ANÁLISE DE VARIAÇÃO E GERAÇÃO DE PARECER (PÓS-FILTRO) ---")
    print("-" * 60)
    
    analise_residuos_texto = "N/A: Análise de resíduos não realizada (modelo não ajustado)." # Valor padrão
    try:
        df_metricas, metricas_resumo = calcular_metricas(df_estatistico)
        parecer_texto = gerar_parecer_qualitativo(metricas_resumo)
        # --- ATUALIZADO: Passa os novos dicionários E O TEXTO DOS RESÍDUOS ---
        # A variável analise_residuos_texto será atualizada após o ajuste do modelo
        # Por enquanto, passamos o valor padrão
        # salvar_relatorio_analise(nome_base_sessao, df_metricas, metricas_resumo, parecer_texto, output_folder, relatorio_agrupamento, metadados_ensaio, analise_residuos_texto) 
    except Exception as e:
        print(f"ALERTA: Falha na Análise de Variação ou Geração do Parecer inicial. Erro: {e}")
        # Define um valor padrão em caso de erro para evitar falha posterior
        df_metricas, metricas_resumo, parecer_texto = pd.DataFrame(), {}, "Erro na análise de variação."
        
    # =========================================================================
    # --- 3. Ajuste de Modelos na Curva Média ---
    # =========================================================================
    print(r"\n--- 3. Ajustando Modelos Reológicos na Curva Média ($\mu(\tau_w)$ vs $\mu(\dot{\gamma}_{w})$) ---") # <-- CORREÇÃO: Raw string
    
    # Prepara dados para ajuste
    gd_fit_mean = df_estatistico['γ̇w_MEDIA(s⁻¹)'].values
    tau_fit_mean = df_estatistico['τw_MEDIA(Pa)'].values
    model_results = {}
    best_model_nome = ""
    residuals = None # <-- NOVO: Armazena resíduos
    tau_pred_best_model = None # <-- NOVO: Armazena predições

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
                model_results[name] = {'params': params_fit, 'R2': r2, 'tau_pred': tau_pred} # <-- NOVO: Guarda predições
            except Exception as e:
                pass

        if model_results:
            best_model_nome = max(model_results, key=lambda name: model_results[name]['R2'])
            print(f"\nSUCESSO: Melhor modelo ajustado: {best_model_nome} (R²: {model_results[best_model_nome]['R2']:.4f})")
            
            # --- NOVO: Calcular Resíduos e Gerar Análise ---
            tau_pred_best_model = model_results[best_model_nome]['tau_pred']
            residuals = tau_fit_mean - tau_pred_best_model
            analise_residuos_texto = analisar_residuos(residuals, gd_fit_mean, best_model_nome) # <-- Chama a nova função
            # --- FIM ---

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
            json_models_filename = os.path.basename(caminho_csv).replace('_resultados_reologicos.csv', '_parametros_modelos_ROBUSTO.json')
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

    # --- Salva o relatório FINAL (agora com a análise de resíduos, se houver) ---
    try:
        salvar_relatorio_analise(nome_base_sessao, df_metricas, metricas_resumo, parecer_texto, output_folder, relatorio_agrupamento, metadados_ensaio, analise_residuos_texto)
    except Exception as e:
         print(f"ALERTA: Falha ao salvar o relatório final completo. Erro: {e}")


    # --- 4. Plotagem da Curva de Fluxo com Barras de Erro ---
    print("\n--- 4. Gerando Gráfico de Curva de Fluxo com Erros (PÓS-FILTRO) ---")
    
    # Prepara os dados de erro
    tau_mean = df_estatistico['τw_MEDIA(Pa)'].values
    gd_mean = df_estatistico['γ̇w_MEDIA(s⁻¹)'].values
    tau_std = df_estatistico['STD_τw (Pa)'].values
    gd_std = df_estatistico['STD_γ̇w (s⁻¹)'].values
    
    tau_std = np.maximum(tau_std, 0)
    gd_std = np.maximum(gd_std, 0)

    fig1, ax1 = plt.subplots(figsize=(12, 8)) # <-- MUDANÇA: fig1, ax1
    
    # Plota os pontos médios com barras de erro
    ax1.errorbar(gd_mean, tau_mean, 
                yerr=tau_std, 
                xerr=gd_std,
                fmt='o', 
                color='k', 
                ecolor='gray', 
                capsize=5,
                elinewidth=1.5,
                label=r'Média $\pm$ Desvio Padrão (Pós-Filtro)', # <-- CORREÇÃO: Raw string
                zorder=10)

    # Plota o melhor modelo ajustado
    if best_model_nome and best_model_nome in model_results:
        min_gd, max_gd = np.min(gd_mean) * 0.5, np.max(gd_mean) * 1.5
        gd_plot = np.geomspace(min_gd, max_gd, 200)
        
        best_model_func = MODELS[best_model_nome][0]
        best_model_params = model_results[best_model_nome]['params']
        tau_plot_model = best_model_func(gd_plot, *best_model_params)
        r2_val = model_results[best_model_nome]['R2']

        ax1.plot(gd_plot, tau_plot_model, 
                color='red', 
                linestyle='--', 
                linewidth=3.5,
                label=f'Ajuste {best_model_nome} (R²={r2_val:.4f})', 
                zorder=20)

    ax1.set_title(f"Curva de Fluxo Média (Tratamento Estatístico Robusto)\nSessão Base: {nome_base_sessao}", fontsize=16)
    ax1.set_xlabel(r"Taxa de Cisalhamento Real Média ($\mu_{\dot{\gamma}_w}$, s⁻¹)", fontsize=12) # <-- CORREÇÃO: Raw string
    ax1.set_ylabel(r"Tensão de Cisalhamento Média ($\mu_{\tau_w}$, Pa)", fontsize=12) # <-- CORREÇÃO: Raw string
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, which="both", ls="--", alpha=0.7)
    ax1.set_xscale('log')
    ax1.set_yscale('log')
    
    fig1.tight_layout()
    
    # O nome do PNG deve seguir o nome do arquivo estatístico
    png_filename = os.path.basename(csv_stat_f).replace('.csv', '.png')
    png_f = os.path.join(output_folder, png_filename)
    try:
        fig1.savefig(png_f, dpi=300, bbox_inches='tight')
        print(f"Gráfico da curva de fluxo estatística salvo em: {png_f}")
    except Exception as e:
        print(f"ERRO ao salvar o gráfico da curva de fluxo: {e}")

    # --- NOVO: 5. Plotagem do Gráfico de Resíduos ---
    if residuals is not None:
        print("\n--- 5. Gerando Gráfico de Resíduos ---")
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        
        # Plota resíduos vs. taxa de cisalhamento (log scale)
        ax2.scatter(gd_mean, residuals, color='blue', alpha=0.7, s=50, label='Resíduos')
        
        # Linha horizontal em y=0
        ax2.axhline(0, color='red', linestyle='--', linewidth=1.5, label='Ajuste Perfeito (Resíduo = 0)')
        
        ax2.set_title(f"Gráfico de Resíduos (Observado - Previsto por {best_model_nome})\nSessão Base: {nome_base_sessao}", fontsize=14)
        ax2.set_xlabel(r"Taxa de Cisalhamento Real Média ($\mu_{\dot{\gamma}_w}$, s⁻¹)", fontsize=12)
        ax2.set_ylabel("Resíduo da Tensão de Cisalhamento ($\mu_{\\tau_w} - \\tau_{predito}$, Pa)", fontsize=12)
        ax2.set_xscale('log') # Escala log para o eixo x é comum em resíduos reológicos
        ax2.grid(True, which="both", ls=":", alpha=0.6)
        ax2.legend(loc='best', fontsize=10)
        
        fig2.tight_layout()
        
        # Salva o gráfico de resíduos
        png_residuos_filename = png_filename.replace('.png', '_residuos.png')
        png_residuos_f = os.path.join(output_folder, png_residuos_filename)
        try:
            fig2.savefig(png_residuos_f, dpi=300, bbox_inches='tight')
            print(f"Gráfico de resíduos salvo em: {png_residuos_f}")
        except Exception as e:
            print(f"ERRO ao salvar o gráfico de resíduos: {e}")
    # --- FIM NOVO ---


    # Exibir o gráfico (necessário fechar para o script terminar)
    print("\nFeche as janelas dos gráficos para finalizar a execução.")
    plt.show()

# -----------------------------------------------------------------------------
# --- INÍCIO DA EXECUÇÃO ---
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    caminho_csv_input, nome_base, output_f = selecionar_arquivo_csv(INPUT_BASE_FOLDER)
    
    if caminho_csv_input:
        processar_estatisticamente(caminho_csv_input, nome_base, output_f)
    
    print("\n--- FIM DO SCRIPT DE TRATAMENTO ESTATÍSTICO ---")

" from the Canvas document above.

