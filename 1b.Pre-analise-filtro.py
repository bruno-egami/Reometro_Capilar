# -*- coding: utf-8 -*-
"""
SCRIPT 2X.PRE_ANALISE_E_LIMPEZA.PY
(Fusão de JSONs, Cálculo de CV e Remoção Automática de Outliers para Limpeza de Dados)
-----------------------------------------------------------------------------
"""

# 1. Importação de Bibliotecas
import numpy as np
import pandas as pd
from datetime import datetime
import os 
import glob
import re
import json
from scipy.stats import linregress

# --- CONFIGURAÇÃO DE PASTAS ---
JSON_INPUT_DIR = "resultados_testes_reometro"
STATISTICAL_OUTPUT_FOLDER = "resultados_analise_estatistica"

# Cria as pastas se não existirem
if not os.path.exists(STATISTICAL_OUTPUT_FOLDER):
    os.makedirs(STATISTICAL_OUTPUT_FOLDER)
if not os.path.exists(JSON_INPUT_DIR):
    os.makedirs(JSON_INPUT_DIR)


# -----------------------------------------------------------------------------
# --- FUNÇÕES AUXILIARES ---
# -----------------------------------------------------------------------------

def input_float_com_virgula(mensagem_prompt, permitir_vazio=False):
    """Pede um número float ao usuário, aceitando ',' como decimal."""
    while True:
        entrada = input(mensagem_prompt).strip()
        if permitir_vazio and entrada == "":
            return None
        try:
            return float(entrada.replace(',', '.'))
        except ValueError:
            print("ERRO: Entrada inválida. Insira um número.")

def format_float_for_table(value, decimal_places=4):
    """Formata um número float para exibição em tabelas."""
    if isinstance(value, (float, np.floating)):
        if np.isnan(value): return "NaN"
        return f"{value:.{decimal_places}f}"
    return str(value)

def ler_dados_json(json_filepath):
    """Lê dados de um arquivo JSON, retornando o dicionário completo."""
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e: 
        print(f"ERRO ao ler JSON '{os.path.basename(json_filepath)}': {e}"); return None

def listar_arquivos_json_numerados(pasta_json):
    """Lista todos os arquivos .json na pasta de testes."""
    arquivos = sorted([f for f in os.listdir(pasta_json) if f.endswith('.json') and os.path.isfile(os.path.join(pasta_json, f))])
    if not arquivos:
        print(f"Nenhum arquivo .json encontrado na pasta '{pasta_json}'.")
    else:
        print(f"\nArquivos JSON disponíveis em '{pasta_json}':")
        for i, arq in enumerate(arquivos):
            print(f"  {i+1}: {arq}")
    return arquivos

def selecionar_multiplos_json(pasta_json, mensagem_prompt):
    """Permite selecionar múltiplos JSONs por número ou '0' para seleção manual."""
    arquivos_disponiveis = listar_arquivos_json_numerados(pasta_json)
    if not arquivos_disponiveis: return [] 
    
    while True:
        try:
            escolha_str = input(f"{mensagem_prompt} (Números separados por vírgula, ex: 1, 3): ").strip()
            if not escolha_str: continue

            indices_escolhidos = [int(i.strip()) - 1 for i in escolha_str.split(',') if i.strip().isdigit()]
            
            if any(i < 0 or i >= len(arquivos_disponiveis) for i in indices_escolhidos):
                print("ERRO: Um ou mais números estão fora do intervalo válido.")
                continue

            caminhos_selecionados = [os.path.join(pasta_json, arquivos_disponiveis[i]) for i in indices_escolhidos]
            nomes_selecionados = [arquivos_disponiveis[i] for i in indices_escolhidos]
            
            print(f"Selecionados ({len(caminhos_selecionados)}): {', '.join(nomes_selecionados)}")
            return caminhos_selecionados
            
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite números separados por vírgula.")

def validar_e_combinar_jsons(caminhos_jsons):
    """Carrega, valida parâmetros globais e combina a lista de testes."""
    if not caminhos_jsons: return None

    dados_base = ler_dados_json(caminhos_jsons[0])
    if not dados_base: return None

    todos_testes = dados_base.get('testes', [])
    
    # 1. Validação de Compatibilidade
    params_base = {k: dados_base.get(k) for k in ['diametro_capilar_mm', 'comprimento_capilar_mm', 'densidade_pasta_g_cm3']}
    if any(p is None for p in params_base.values()):
        print("ERRO: JSON base está incompleto (D, L, ou rho ausente).")
        return None

    for i, caminho in enumerate(caminhos_jsons[1:]):
        dados = ler_dados_json(caminho)
        if not dados: continue
        
        # Compara parâmetros globais com tolerância
        if not (np.isclose(dados.get('diametro_capilar_mm', 0), params_base['diametro_capilar_mm']) and
                np.isclose(dados.get('comprimento_capilar_mm', 0), params_base['comprimento_capilar_mm']) and
                np.isclose(dados.get('densidade_pasta_g_cm3', 0), params_base['densidade_pasta_g_cm3'])):
            print(f"ALERTA: JSON {os.path.basename(caminho)} tem parâmetros globais divergentes. Ignorando este arquivo.")
            continue
        
        todos_testes.extend(dados.get('testes', []))

    if not todos_testes:
        print("ERRO: Nenhuma lista de testes válida foi combinada.")
        return None

    # 2. Ordenação e Renumeração Final
    # Ordena por Pressão para garantir a curva correta
    todos_testes = sorted(todos_testes, key=lambda t: t.get('media_pressao_final_ponto_bar', 0))
    
    # Renumera os pontos sequencialmente
    for i, teste in enumerate(todos_testes):
        teste['ponto_n'] = i + 1

    dados_base['testes'] = todos_testes
    
    return dados_base

# -----------------------------------------------------------------------------
# --- FUNÇÕES DE CÁLCULO E TRATAMENTO (NOVO NÚCLEO) ---
# -----------------------------------------------------------------------------

def calcular_dados_reologicos_brutos(df_testes, rho_g_cm3, D_mm, L_mm):
    """Calcula Tau_w, Gamma_aw e Taxa de Fluxo de Massa para cada ponto bruto."""
    rho_si = rho_g_cm3 * 1000
    R_cap_si, L_cap_m = (D_mm / 2000), L_mm / 1000
    
    df_testes['P_Pa'] = df_testes['media_pressao_final_ponto_bar'] * 1e5
    df_testes['M_kg'] = df_testes['massa_g_registrada'] / 1000
    
    # Filtra dados de duração zero (evita Divisão por Zero)
    df_testes = df_testes[df_testes['duracao_real_s'] > 0].copy()
    
    # Cálculos reológicos básicos
    df_testes['τw (Pa)'] = df_testes['P_Pa'] * R_cap_si / (2 * L_cap_m)
    df_testes['Q_m3_s'] = (df_testes['M_kg'] / rho_si) / df_testes['duracao_real_s']
    df_testes['γ̇aw (s⁻¹)'] = (4 * df_testes['Q_m3_s']) / (np.pi * R_cap_si**3)
    
    # Taxa de fluxo de massa (para cálculo de CV)
    df_testes['mass_flow_rate_g_s'] = df_testes['massa_g_registrada'] / df_testes['duracao_real_s']
    
    return df_testes

def calcular_estatisticas_e_cv(df_testes):
    """Agrupa por pressão nominal e calcula estatísticas, incluindo CV."""
    
    # Arredonda a pressão para agrupamento (2 casas decimais é razoável para a precisão do transdutor)
    df_testes['P_NOMINAL_AGRUPADA'] = df_testes['media_pressao_final_ponto_bar'].round(2)
    
    # Colunas para calcular estatísticas (Taxa de Fluxo de Massa como proxy de Vazão)
    cols_to_group = ['τw (Pa)', 'γ̇aw (s⁻¹)', 'mass_flow_rate_g_s']

    # Calcular Média e Desvio Padrão
    df_mean = df_testes.groupby('P_NOMINAL_AGRUPADA')[cols_to_group].mean().reset_index()
    df_std = df_testes.groupby('P_NOMINAL_AGRUPADA')[cols_to_group].std().reset_index()
    df_count = df_testes.groupby('P_NOMINAL_AGRUPADA').size().reset_index(name='N')

    # Renomear para juntar
    df_mean.columns = ['P_NOMINAL_AGRUPADA', 'mu_tau_w', 'mu_gamma_aw', 'mu_mass_flow']
    df_std.columns = ['P_NOMINAL_AGRUPADA', 'std_tau_w', 'std_gamma_aw', 'std_mass_flow']

    # Juntar e calcular CV
    df_stats = pd.merge(df_mean, df_std, on='P_NOMINAL_AGRUPADA')
    df_stats = pd.merge(df_stats, df_count, on='P_NOMINAL_AGRUPADA')
    
    # Filtro: Apenas grupos com N >= 2 para CV
    df_stats = df_stats[df_stats['N'] >= 2].copy()
    
    # Garante que não haja divisão por zero no CV
    df_stats = df_stats[df_stats['mu_mass_flow'] > 1e-9].copy()

    # Cálculo do CV (Coefficient of Variation)
    df_stats['CV_τw(%)'] = (df_stats['std_tau_w'] / df_stats['mu_tau_w']) * 100
    df_stats['CV_γ̇aw(%)'] = (df_stats['std_gamma_aw'] / df_stats['mu_gamma_aw']) * 100

    return df_stats

def remover_outliers_por_cv(df_testes, df_stats_atual, cv_limite_pct=10):
    """
    Identifica e remove pontos outliers cuja taxa de fluxo de massa esteja
    fora de 2 desvios padrão da média do seu grupo, SE o CV do grupo exceder o limite.
    
    Retorna o DataFrame limpo e o DataFrame de estatísticas recalculado.
    """
    
    df_stats_map = df_stats_atual[['P_NOMINAL_AGRUPADA', 'mu_mass_flow', 'std_mass_flow', 'CV_γ̇aw(%)']].set_index('P_NOMINAL_AGRUPADA').to_dict('index')

    indices_para_remover = set()
    pontos_removidos_total = 0
    
    # Itera sobre cada ponto no DataFrame original de testes
    for index, row in df_testes.iterrows():
        p_nominal = row['P_NOMINAL_AGRUPADA']
        
        if p_nominal in df_stats_map:
            stats = df_stats_map[p_nominal]
            
            cv_do_grupo = stats['CV_γ̇aw(%)']
            fluxo_atual = row['mass_flow_rate_g_s']
            
            # Condição de remoção: Se o CV do grupo está alto E o ponto está fora de 2*STD
            if cv_do_grupo > cv_limite_pct:
                limite_superior = stats['mu_mass_flow'] + 2 * stats['std_mass_flow']
                limite_inferior = stats['mu_mass_flow'] - 2 * stats['std_mass_flow']
                
                if (fluxo_atual > limite_superior) or (fluxo_atual < limite_inferior):
                    indices_para_remover.add(index)
                    pontos_removidos_total += 1
                    
    df_limpo = df_testes.drop(indices_para_remover).copy()
    
    if pontos_removidos_total > 0:
        print(f"-> Removidos {pontos_removidos_total} ponto(s) (Outlier de Vazão/CV > {cv_limite_pct:.1f}%)")
        # Re-calcula estatísticas para a amostra limpa
        return df_limpo, calcular_estatisticas_e_cv(df_limpo)
    
    return df_limpo, df_stats_atual

# -----------------------------------------------------------------------------
# --- FUNÇÃO PRINCIPAL DE PRÉ-ANÁLISE ---
# -----------------------------------------------------------------------------

def executar_pre_analise_e_limpeza():
    """Gerencia a seleção de JSONs, a limpeza interativa e a geração do CSV e JSON final."""
    
    print("="*70); print("--- FUSÃO, LIMPEZA E PRÉ-TRATAMENTO ESTATÍSTICO (2X) ---"); print("="*70)
    
    # 1. Fusão e Combinação de JSONs
    caminhos_jsons = selecionar_multiplos_json(JSON_INPUT_DIR, "Selecione os JSONs de teste a serem combinados")
    if not caminhos_jsons: return
    
    dados_combinados = validar_e_combinar_jsons(caminhos_jsons)
    if not dados_combinados: return
    
    nome_sessao_base = dados_combinados['id_amostra']
    D_mm = dados_combinados['diametro_capilar_mm']
    L_mm = dados_combinados['comprimento_capilar_mm']
    rho_g_cm3 = dados_combinados['densidade_pasta_g_cm3']

    # 2. Carrega para DataFrame e Calcula Dados Brutos
    df_testes = pd.DataFrame(dados_combinados['testes'])
    df_testes = calcular_dados_reologicos_brutos(df_testes, rho_g_cm3, D_mm, L_mm)
    
    # Limpa valores óbvios (Q ou Tau zero)
    df_testes.dropna(subset=['τw (Pa)', 'γ̇aw (s⁻¹)'], inplace=True)
    df_testes = df_testes[(df_testes['τw (Pa)'] > 1e-9) & (df_testes['γ̇aw (s⁻¹)'] > 1e-9)].copy()
    
    if len(df_testes) < 2:
        print("\nERRO: Menos de 2 pontos válidos após a limpeza inicial (Duração ou Pressão zero).")
        return

    # 3. Processamento Iterativo de Outliers
    
    df_limpo = df_testes.copy()
    
    # Exibe estatísticas iniciais
    df_stats_inicial = calcular_estatisticas_e_cv(df_limpo)
    if df_stats_inicial.empty:
        print("\nERRO: Nenhuma repetição (N >= 2) encontrada para calcular o CV. Continue com o Script 2.")
        return
        
    print("\n--- VISUALIZAÇÃO ESTATÍSTICA INICIAL (N>=2) ---")
    df_stats_display = df_stats_inicial[['P_NOMINAL_AGRUPADA', 'N', 'CV_γ̇aw(%)']].copy()
    df_stats_display.columns = ['P_Nominal', 'N', 'CV Vazão (%)']
    
    # CORREÇÃO: Usa 'formatters' em vez de 'floatfmt' (compatibilidade)
    fmt_display = {'P_Nominal': lambda x: format_float_for_table(x, 2),
                   'N': lambda x: str(int(x)) if pd.notna(x) else 'N/A',
                   'CV Vazão (%)': lambda x: format_float_for_table(x, 2)}
    
    print(df_stats_display.to_string(index=False, formatters=fmt_display))
    
    
    # Pergunta o limite de CV para a remoção
    cv_limite = input_float_com_virgula("\nLimite de CV (%) para remoção automática de outliers (Sugestão: 10): ")
    if cv_limite is None or cv_limite <= 0: cv_limite = 10.0

    print(f"\n--- INICIANDO LIMPEZA ITERATIVA COM CV={cv_limite:.1f}% ---")
    
    df_stats_atual = df_stats_inicial
    total_pontos_orig = len(df_limpo)
    
    # Loop de repetição para remover outliers e recalcular as estatísticas
    while True:
        pontos_antes = len(df_limpo)
        
        # Remove outliers usando o CV e 2*STD
        df_limpo, df_stats_recalc = remover_outliers_por_cv(df_limpo, df_stats_atual, cv_limite)
        
        pontos_depois = len(df_limpo)
        
        if pontos_depois == pontos_antes:
            print("\nSUCESSO: Nenhuma remoção adicional de outliers necessária.")
            break
        
        df_stats_atual = df_stats_recalc
        print(f"  -> Limpeza resultou em {pontos_antes - pontos_depois} remoções. Novo ciclo de verificação...")
        
        if pontos_depois < 4:
            print("AVISO: Restaram menos de 4 pontos válidos. Abortando limpeza.")
            break

    # 4. Exibe o resultado final da limpeza
    
    df_stats_final = df_stats_recalc
    
    print("\n" + "="*70)
    print("--- RESULTADO FINAL DO TRATAMENTO ESTATÍSTICO (PRONTO PARA O SCRIPT 2) ---")
    print(f"Pontos Originais: {total_pontos_orig}. Pontos Finais: {len(df_limpo)}.")
    
    if not df_stats_final.empty:
        # Formata para exibição
        df_stats_display = df_stats_final.copy()
        df_stats_display = df_stats_display[['P_NOMINAL_AGRUPADA', 'N', 'mu_tau_w', 'std_tau_w', 'CV_τw(%)', 'mu_gamma_aw', 'CV_γ̇aw(%)']]
        df_stats_display.columns = ['P_Nominal', 'N', 'Média τw (Pa)', 'STD τw (Pa)', 'CV τw (%)', 'Média γ̇aw (s⁻¹)', 'CV γ̇aw (%)']
        
        # Define os formatters para os dados de saída final
        fmt = {'P_Nominal': lambda x: format_float_for_table(x, 2),
               'N': lambda x: str(int(x)) if pd.notna(x) else 'N/A',
               'Média τw (Pa)': lambda x: format_float_for_table(x, 3),
               'STD τw (Pa)': lambda x: format_float_for_table(x, 3),
               'CV τw (%)': lambda x: format_float_for_table(x, 2),
               'Média γ̇aw (s⁻¹)': lambda x: format_float_for_table(x, 3),
               'CV γ̇aw (%)': lambda x: format_float_for_table(x, 2)}
               
        print(df_stats_display.to_string(index=False, formatters=fmt))
    else:
        print("AVISO: Não restaram pontos com repetições (N>=2) para cálculo estatístico.")

    # 5. GERA O ARQUIVO JSON LIMPO (Mantendo a estrutura do Script 1)
    
    # 5.1. Mapeia colunas do df_limpo de volta para a estrutura de lista de dicionários do JSON
    testes_limpos_json = []
    
    # As colunas `media_pressao_final_ponto_bar`, `massa_g_registrada`, `duracao_real_s`, etc.,
    # são as colunas originais que o Script 1 espera dentro da lista 'testes'.
    # O Ponto_n é a numeração sequencial após a ordenação/limpeza.
    
    for i, row in df_limpo.reset_index(drop=True).iterrows():
        testes_limpos_json.append({
            "ponto_n": i + 1, # Renumeração final após a limpeza
            "massa_g_registrada": row['massa_g_registrada'],
            "duracao_real_s": row['duracao_real_s'],
            "media_tensao_final_ponto_V": row['media_tensao_final_ponto_V'], # Mantém o valor original lido
            "media_pressao_final_ponto_bar": row['media_pressao_final_ponto_bar']
            # Omissão de 'leituras_pressao_detalhadas_bar' para simplificar o JSON
        })

    # 5.2. Cria o novo objeto JSON
    dados_combinados['testes'] = testes_limpos_json
    dados_combinados['data_hora_limpeza'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dados_combinados['observacoes_limpeza'] = f"Combinado(s) de {len(caminhos_jsons)} arquivo(s). {total_pontos_orig - len(df_limpo)} ponto(s) removido(s) automaticamente (CV > {cv_limite:.1f}%)."
    
    # 5.3. Salva o JSON na pasta de testes
    json_limpo_filename = f"limpo_{nome_sessao_base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    caminho_json_limpo = os.path.join(JSON_INPUT_DIR, json_limpo_filename)
    
    try:
        with open(caminho_json_limpo, 'w', encoding='utf-8') as f:
            json.dump(dados_combinados, f, indent=4, ensure_ascii=False)
        print(f"\nSUCESSO: JSON de Teste (Limpo) salvo em: {caminho_json_limpo}")
    except Exception as e:
        print(f"ERRO ao salvar JSON limpo: {e}")
        
    # 6. Gera o CSV de Resultados para o Script 2 (Como alternativa)
    
    # Mapeia colunas do df_limpo para o formato do Script 2
    df_saida_individual = df_limpo.rename(columns={
        'media_pressao_final_ponto_bar': 'P_ext(bar)',
        'massa_g_registrada': 'M_ext(g)',
        'duracao_real_s': 't_ext(s)',
    })
    
    df_saida_individual['D_cap(mm)'] = D_mm
    df_saida_individual['L_cap(mm)'] = L_mm
    df_saida_individual['rho(g/cm³)'] = rho_g_cm3
    df_saida_individual['τw (Pa)'] = df_saida_individual['τw (Pa)'] 
    df_saida_individual['γ̇w (s⁻¹)'] = df_saida_individual['γ̇aw (s⁻¹)']
    df_saida_individual['η (Pa·s)'] = df_saida_individual['τw (Pa)'] / df_saida_individual['γ̇w (s⁻¹)'].replace(0, np.nan)
    
    colunas_finais = ['P_ext(bar)', 'M_ext(g)', 't_ext(s)', 'D_cap(mm)', 'L_cap(mm)', 'rho(g/cm³)', 'τw (Pa)', 'γ̇w (s⁻¹)', 'η (Pa·s)']
    df_saida_individual = df_saida_individual[colunas_finais]
    
    nome_pasta_analise = f"{nome_sessao_base}_ANALISE_LIMPA_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    caminho_pasta_individual = os.path.join("resultados_analise_reologica", nome_pasta_analise)
    if not os.path.exists(caminho_pasta_individual):
        os.makedirs(caminho_pasta_individual)

    csv_individual_filename = f"limpo_{nome_pasta_analise}_resultados_reologicos.csv"
    caminho_csv_individual = os.path.join(caminho_pasta_individual, csv_individual_filename)
    
    try:
        df_saida_individual.to_csv(caminho_csv_individual, index=False, sep=';', decimal=',', float_format='%.4f', encoding='utf-8-sig')
        print(f"\nSUCESSO: CSV de Análise (Limpo) salvo em: {caminho_csv_individual}")
        print(f"\nPRÓXIMO PASSO: Execute o Script 2.Analise_reologica.py.")
        print(f"Use o modo 'JSON' e selecione '{json_limpo_filename}' ou o modo 'CSV' com o arquivo CSV salvo acima.")
        
    except Exception as e:
        print(f"ERRO ao salvar CSV de análise: {e}")
        
# -----------------------------------------------------------------------------
# --- INÍCIO DA EXECUÇÃO --
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    executar_pre_analise_e_limpeza()
    print("\n--- FIM DO SCRIPT DE PRÉ-ANÁLISE E LIMPEZA ---")
