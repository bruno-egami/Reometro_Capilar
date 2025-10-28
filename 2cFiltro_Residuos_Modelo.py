# -*- coding: utf-8 -*-
"""
SCRIPT 1D.FILTRO_RESIDUOS_MODELO.PY
(Filtra outliers comparando dados experimentais corrigidos com o melhor modelo ajustado)
-----------------------------------------------------------------------------
"""

# 1. Importação de Bibliotecas
import numpy as np
import pandas as pd
from datetime import datetime
import os 
import glob
import json
import inspect 
import re 
from scipy.stats import linregress
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score


# --- CONFIGURAÇÃO DE PASTAS ---
OUTPUT_BASE_FOLDER = "resultados_analise_reologica"
JSON_INPUT_DIR = "resultados_testes_reometro"


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
    "Newtoniano": model_newtonian, 
    "Lei da Potência": model_power_law, 
    "Bingham": model_bingham, 
    "Herschel-Bulkley": model_hb, 
    "Casson": model_casson
}

# -----------------------------------------------------------------------------
# --- FUNÇÕES AUXILIARES DE CARREGAMENTO E INPUT ---
# -----------------------------------------------------------------------------

def input_float_com_virgula(mensagem_prompt, permitir_vazio=False):
    """Pede um número float ao usuário, aceitando ',' como decimal."""
    while True:
        entrada = input(mensagem_prompt).strip()
        if permitir_vazio and entrada == "":
            return None
        try:
            val = float(entrada.replace(',', '.'))
            if val < 0: raise ValueError
            return val
        except ValueError:
            print("ERRO: Insira um número não negativo (use ponto ou vírgula).")
            
def input_sim_nao(mensagem_prompt):
    """Pede uma entrada do usuário e valida se é 'sim' ou 'não'."""
    while True:
        resposta = input(mensagem_prompt).strip().lower()
        if resposta in ['s', 'sim']: return True
        elif resposta in ['n', 'nao', 'não']: return False
        else: print("ERRO: Resposta inválida. Digite 's' ou 'n'.")

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

def selecionar_arquivo_json(pasta_json, mensagem_prompt):
    """Gerencia o menu para o usuário escolher um arquivo JSON da lista."""
    arquivos_disponiveis = listar_arquivos_json_numerados(pasta_json)
    if not arquivos_disponiveis:
        return None 
    while True:
        try:
            escolha_str = input(f"{mensagem_prompt} (digite o número): ").strip()
            if not escolha_str.isdigit():
                 print("ERRO: Entrada inválida. Digite o número do arquivo.")
                 continue
            
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_disponiveis):
                arquivo_selecionado = arquivos_disponiveis[escolha_num - 1]
                print(f"  Selecionado: {arquivo_selecionado}")
                return arquivo_selecionado
            else:
                print(f"ERRO: Escolha inválida. Digite um número entre 1 e {len(arquivos_disponiveis)}.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado na seleção: {e}")
            return None

def selecionar_arquivos_analise():
    """Lista e permite selecionar a sessão de análise (pasta) para carregar os resultados."""
    print("="*70); print("--- SELECIONAR SESSÃO DE ANÁLISE PARA FILTRO POR RESÍDUOS ---"); print("="*70)
    
    # 1. Lista as pastas de resultados de análise
    if not os.path.exists(OUTPUT_BASE_FOLDER):
        print(f"ERRO: Pasta de resultados '{OUTPUT_BASE_FOLDER}' não encontrada.")
        return None, None, None

    pastas_disponiveis = sorted([d for d in os.listdir(OUTPUT_BASE_FOLDER) if os.path.isdir(os.path.join(OUTPUT_BASE_FOLDER, d))], reverse=True)
    if not pastas_disponiveis:
        print(f"Nenhuma sessão de análise encontrada em '{OUTPUT_BASE_FOLDER}'.")
        return None, None, None

    print("Sessões de Análise disponíveis:")
    for i, pasta in enumerate(pastas_disponiveis):
        print(f"  {i+1}: {pasta}")

    while True:
        try:
            escolha_str = input("\nDigite o NÚMERO da sessão (pasta) cujos dados você deseja filtrar: ").strip()
            if not escolha_str.isdigit(): continue
            escolha = int(escolha_str) - 1
            if 0 <= escolha < len(pastas_disponiveis):
                nome_sessao = pastas_disponiveis[escolha]
                caminho_sessao = os.path.join(OUTPUT_BASE_FOLDER, nome_sessao)
                
                # 2. Busca os arquivos necessários dentro da sessão
                csv_path = glob.glob(os.path.join(caminho_sessao, '*_resultados_reologicos.csv'))
                json_params_path = glob.glob(os.path.join(caminho_sessao, '*_parametros_modelos.json'))
                
                if not csv_path:
                    print(f"ERRO: Arquivo CSV de resultados não encontrado na sessão '{nome_sessao}'.")
                    continue
                if not json_params_path:
                    print(f"ERRO: Arquivo JSON de parâmetros de modelo não encontrado na sessão '{nome_sessao}'.")
                    continue
                    
                # 3. Tenta encontrar o JSON BRUTO original (Busca inteligente e robusta)
                match = re.search(r'([A-Za-z0-9%_-]+)_20\d{6}_\d{6}', nome_sessao)
                if match:
                    # Extrai o ID da amostra da pasta, removendo tags de limpeza intermediárias
                    nome_base_id = match.group(1).split('_ANALISE_LIMPA')[0].split('_ANALISE_LIMPA')[0].split('_ANALISE_LIMPA')[0]
                    
                    # 3.1. Pesquisa por TODOS os JSONs na pasta de testes que contêm o ID
                    json_caminhos = glob.glob(os.path.join(JSON_INPUT_DIR, f"*{nome_base_id}*.json"))
                    
                    # 3.2. Filtra para remover arquivos que definitivamente não são a fonte (ex: parâmetros de outros scripts)
                    json_caminhos = [p for p in json_caminhos if 'parametros_modelos' not in os.path.basename(p)]
                    
                    if not json_caminhos:
                        print(f"AVISO: JSON Bruto original não encontrado em '{JSON_INPUT_DIR}' com o ID '{nome_base_id}'.")
                        return None, None, None
                    
                    # 3.3. Seleciona o JSON: prioriza a versão MAIS RECENTE como a fonte de dados mais atualizada.
                    json_caminhos.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    json_bruto_caminho = json_caminhos[0]
                    
                    print(f"INFO: JSON de referência encontrado: {os.path.basename(json_bruto_caminho)}")
                    return csv_path[0], json_params_path[0], json_bruto_caminho
                else:
                    print("ERRO: Não foi possível inferir o nome do JSON bruto a partir da pasta de análise. Verifique o formato do nome da pasta.")
                    return None, None, None
            else:
                print("ERRO: Escolha inválida.")
        except Exception as e:
            print(f"Ocorreu um erro: {e}")
            return None, None, None

def carregar_resultados(csv_path, json_params_path):
    """Carrega CSV de resultados e parâmetros do melhor modelo."""
    
    # Carregar CSV (resultados processados)
    try:
        df_res = pd.read_csv(csv_path, sep=';', decimal=',', encoding='utf-8-sig')
        df_res.columns = df_res.columns.str.strip()
        
        # Converte as colunas essenciais (corrigidas) para float
        df_res['τw (Pa)'] = pd.to_numeric(df_res['τw (Pa)'], errors='coerce')
        df_res['γ̇w (s⁻¹)'] = pd.to_numeric(df_res['γ̇w (s⁻¹)'], errors='coerce')
        df_res['Ponto'] = pd.to_numeric(df_res['Ponto'], errors='coerce')


        df_res.dropna(subset=['τw (Pa)', 'γ̇w (s⁻¹)', 'Ponto'], inplace=True)
        df_res = df_res[(df_res['τw (Pa)'] > 0) & (df_res['γ̇w (s⁻¹)'] > 0)].copy().reset_index(drop=True)
        
    except Exception as e:
        print(f"ERRO ao carregar CSV de resultados: {e}")
        return None, None

    # Carregar Parâmetros do Modelo
    try:
        params_data = ler_dados_json(json_params_path)
        modelos = params_data.get("modelos_ajustados", {})
        
        if not modelos:
            print("ERRO: JSON de parâmetros está vazio ou inválido.")
            return None, None
            
        best_model_name = max(modelos, key=lambda name: modelos[name].get('R2', -np.inf))
        
        # Obtém o R² do modelo selecionado
        best_r2 = modelos[best_model_name].get('R2', 0.0)

        if best_model_name not in MODELS:
            print(f"AVISO: O melhor modelo ('{best_model_name}') não foi encontrado na definição de modelos. Abortando.")
            return None, None
            
        best_model_func = MODELS[best_model_name]
        best_model_params = modelos[best_model_name]['params']
        
    except Exception as e:
        print(f"ERRO ao carregar ou processar JSON de parâmetros: {e}")
        return None, None
        
    return df_res, {'name': best_model_name, 'func': best_model_func, 'params': best_model_params, 'R2': best_r2}


# -----------------------------------------------------------------------------
# --- FUNÇÃO PRINCIPAL DE FILTRO INTERATIVO ---
# -----------------------------------------------------------------------------

def executar_filtro_por_residuos():
    
    # 1. Seleção e Carregamento de Arquivos
    csv_path, json_params_path, json_bruto_path = selecionar_arquivos_analise()
    
    if not csv_path: return
    
    df_res, best_model_info = carregar_resultados(csv_path, json_params_path)
    if df_res is None: return

    print("\n" + "="*70)
    print("--- INICIANDO FILTRO POR RESÍDUOS DO MODELO ---")
    print(f"Modelo de Referência: {best_model_info['name']} (R²={best_model_info['R2']:.4f})")
    print("="*70)

    x_data = df_res['γ̇w (s⁻¹)'].values 
    y_data = df_res['τw (Pa)'].values 
    
    # 2. Cálculo dos Resíduos e Desvio Padrão Global
    try:
        y_pred_best = best_model_info['func'](x_data, *best_model_info['params'])
        residuals = y_data - y_pred_best
        std_residuals = np.std(residuals)
        
    except Exception as e:
        print(f"ERRO no cálculo de resíduos ou ajuste do modelo: {e}. Abortando.")
        return
        
    # --- LOOP INTERATIVO DE FILTRAGEM ---
    
    filtro_aplicado = False
    pontos_removidos = 0
    df_filtrado_final = df_res.copy()
    
    # 2.1. Pergunta inicial pelo limite
    limite_multiplicador = input_float_com_virgula("\nQual o limite de resíduos (Multiplicador de STD)? (Sugestão: 3.0): ", permitir_vazio=True)
    if limite_multiplicador is None: limite_multiplicador = 3.0

    
    while not filtro_aplicado:
        
        threshold = limite_multiplicador * std_residuals
        
        # Identifica os outliers com o limite atual
        outlier_indices_local = np.where(np.abs(residuals) > threshold)[0]
        pontos_a_remover = len(outlier_indices_local)
        
        print("\n" + "-"*70)
        print(f"ANÁLISE DE RESÍDUOS (Multiplicador Atual: {limite_multiplicador:.2f} x STD)")
        print(f"  -> STD dos Resíduos: {std_residuals:.2f} Pa")
        print(f"  -> Limite Absoluto: {threshold:.2f} Pa")
        print("-" * 70)
        
        if pontos_a_remover == 0:
            print("  -> Nenhum ponto excede este limite. Dados considerados limpos.")
            filtro_aplicado = True
            pontos_removidos = 0
            df_filtrado_final = df_res.copy()
            break
            
        else:
            print(f"  -> PONTOS A SEREM REMOVIDOS: {pontos_a_remover} de {len(df_res)} pontos totais.")
            
            # Exibe os pontos que serão removidos
            df_res['Resíduo'] = residuals # Adiciona Resíduo para exibição
            outlier_points_data = df_res.iloc[outlier_indices_local].copy()
            
            print("\nPontos que excedem o limite:")
            print(f"{'Ponto No.':<10} | {'τw (Pa)':<10} | {'Resíduo (Pa)':<15}")
            print("-" * 37)
            
            for index, row in outlier_points_data.iterrows():
                 print(f"{int(row['Ponto']):<10} | {row['τw (Pa)']:.2f} | {row['Resíduo']:.2f}")
            print("-" * 37)

            # 3. Pedido de Confirmação
            if input_sim_nao("\nCONFIRMA a remoção desses pontos com o limite atual? (s/n): "):
                
                # Aplica o filtro final e sai do loop
                df_filtrado_final = df_res.drop(outlier_indices_local).reset_index(drop=True)
                pontos_removidos = pontos_a_remover
                filtro_aplicado = True
                
            else:
                # Permite reajustar o limite
                print("\nLimite Negado. Digite um novo multiplicador para recalcular.")
                novo_limite = input_float_com_virgula(f"Novo Multiplicador (ex: {limite_multiplicador:.2f}): ")
                if novo_limite is not None and novo_limite > 0:
                    limite_multiplicador = novo_limite
                else:
                    print("Multiplicador inválido. Reiniciando com o limite atual.")


    # 4. Geração do Novo JSON Limpo
    
    if len(df_filtrado_final) < 5:
        print("ALERTA: Após a filtragem, restam menos de 5 pontos. O resultado final pode ser instável.")

    # Abre o JSON BRUTO original para obter os metadados (D, L, rho, etc.) e a lista completa de testes
    dados_brutos_orig = ler_dados_json(json_bruto_path)
    if not dados_brutos_orig: return

    # A chave para recriar o JSON é usar os índices dos pontos MANTIDOS no DataFrame
    pontos_mantidos_do_csv = df_filtrado_final['Ponto'].tolist()
    
    testes_limpos_json = []
    
    # Percorre o JSON original e verifica se o Ponto No. está na lista dos mantidos
    for teste in dados_brutos_orig.get("testes", []):
        if teste.get('ponto_n') in pontos_mantidos_do_csv:
            testes_limpos_json.append(teste)
            
    # Renumera os pontos sequencialmente para o novo JSON
    for i, teste in enumerate(testes_limpos_json):
        teste['ponto_n'] = i + 1

    # Atualiza o objeto JSON
    dados_brutos_orig['testes'] = testes_limpos_json
    
    nome_sessao_base = dados_brutos_orig['id_amostra']
    json_limpo_filename = f"limpo_residuos_{nome_sessao_base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    caminho_json_limpo = os.path.join(JSON_INPUT_DIR, json_limpo_filename)

    # Adiciona observação de limpeza
    dados_brutos_orig['data_hora_filtragem_residuos'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dados_brutos_orig['observacoes_filtragem'] = f"Filtro por Resíduos ({limite_multiplicador:.1f} * STD). {pontos_removidos} ponto(s) removido(s) do total ({len(df_res)} pontos)."


    try:
        with open(caminho_json_limpo, 'w', encoding='utf-8') as f:
            json.dump(dados_brutos_orig, f, indent=4, ensure_ascii=False)
        print(f"\nSUCESSO: JSON de Teste (FILTRADO POR RESÍDUOS) salvo em: {os.path.basename(caminho_json_limpo)}")
        print("\nPRÓXIMO PASSO: Execute o Script 2.Analise_reologica.py.")
        print(f"Use o modo 'JSON' e selecione '{os.path.basename(caminho_json_limpo)}' para a análise final e geração de gráficos limpos.")
    except Exception as e:
        print(f"ERRO ao salvar JSON limpo: {e}")

# -----------------------------------------------------------------------------
# --- INÍCIO DA EXECUÇÃO ---
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    executar_filtro_por_residuos()
    print("\n--- FIM DO SCRIPT DE FILTRAGEM POR RESÍDUOS ---")
