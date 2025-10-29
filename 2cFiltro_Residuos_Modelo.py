# -*- coding: utf-8 -*-
"""
SCRIPT 2C.FILTRO_RESIDUOS_MODELO.PY
(Filtra outliers comparando dados experimentais corrigidos com o melhor modelo ajustado)
-----------------------------------------------------------------------------

Versão revisada (corrigida em 2025-10-29):
- Corrige compatibilidade com JSONs que usam "ponto_n" em vez de "id_ponto".
- Ajusta a lógica de remoção para JSONs cujo array principal é diretamente 'testes'.
- Mantém compatibilidade com estruturas antigas ('pontos_medidos').

-----------------------------------------------------------------------------

"""

# 1. Importação de Bibliotecas
import numpy as np
import pandas as pd
from datetime import datetime
import os
import glob
import json
import re
from sklearn.metrics import r2_score


# --- CONFIGURAÇÃO DE PASTAS ---
OUTPUT_BASE_FOLDER = "resultados_analise_reologica"
JSON_INPUT_DIR = "resultados_testes_reometro"


# -----------------------------------------------------------------------------
# --- DEFINIÇÕES DOS MODELOS REOLÓGICOS ---
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


# -----------------------------------------------------------------------------
# --- FUNÇÕES AUXILIARES ---
# -----------------------------------------------------------------------------

def selecionar_sessao(caminho_base):
    print("=" * 70)
    print("--- SELECIONAR SESSÃO DE ANÁLISE PARA FILTRO POR RESÍDUOS ---")
    print("=" * 70)

    try:
        pastas = sorted(
            [d for d in os.listdir(caminho_base) if os.path.isdir(os.path.join(caminho_base, d))],
            key=lambda x: (os.path.getmtime(os.path.join(caminho_base, x))),
            reverse=True
        )
    except FileNotFoundError:
        print(f"ERRO: A pasta base '{caminho_base}' não foi encontrada.")
        return None, None

    if not pastas:
        print(f"ERRO: Nenhuma sessão de análise encontrada em '{caminho_base}'.")
        return None, None

    print("Sessões de Análise disponíveis:")
    for i, nome_sessao in enumerate(pastas):
        print(f"  {i + 1}: {nome_sessao}")

    while True:
        try:
            escolha = input(f"\nDigite o NÚMERO da sessão (pasta) cujos dados você deseja filtrar: ")
            indice = int(escolha) - 1
            if 0 <= indice < len(pastas):
                nome_sessao = pastas[indice]
                caminho_sessao = os.path.join(caminho_base, nome_sessao)
                return caminho_sessao, nome_sessao
            else:
                print("ERRO: Número fora do intervalo. Tente novamente.")
        except ValueError:
            print("ERRO: Entrada inválida. Digite apenas o número.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")
            return None, None


def carregar_dados_sessao(caminho_sessao):
    try:
        csv_pattern = os.path.join(caminho_sessao, '*_resultados_reologicos.csv')
        csv_files = glob.glob(csv_pattern)
        if not csv_files:
            csv_pattern = os.path.join(caminho_sessao, '*_resultados_estatisticos.csv')
            csv_files = glob.glob(csv_pattern)
            if csv_files:
                print("Aviso: Usando dados estatísticos. O filtro de resíduos é idealmente feito em dados 'individuais'.")
            else:
                print(f"ERRO: Nenhum arquivo CSV encontrado em '{os.path.basename(caminho_sessao)}'.")
                return None, None

        df_reologico = pd.read_csv(csv_files[0], sep=';', decimal=',', encoding='utf-8-sig')

        json_pattern = os.path.join(caminho_sessao, '*_parametros_modelos.json')
        json_files = glob.glob(json_pattern)
        if not json_files:
            print(f"ERRO: Nenhum arquivo JSON de parâmetros encontrado em '{os.path.basename(caminho_sessao)}'.")
            return None, None

        with open(json_files[0], 'r', encoding='utf-8') as f:
            dados_modelos = json.load(f)

        return df_reologico, dados_modelos

    except Exception as e:
        print(f"ERRO ao carregar arquivos da sessão '{os.path.basename(caminho_sessao)}': {e}")
        return None, None


def encontrar_json_bruto(id_sessao_base, json_dir):
    if not os.path.exists(json_dir):
        return None

    arquivos_json = glob.glob(os.path.join(json_dir, f"*{id_sessao_base}.json"))
    if not arquivos_json:
        arquivos_json = glob.glob(os.path.join(json_dir, f"*{id_sessao_base}*.json"))

    arquivos_validos = [f for f in arquivos_json if not os.path.basename(f).startswith('limpo_')]
    if arquivos_validos:
        edit_files = [f for f in arquivos_validos if os.path.basename(f).startswith('edit_')]
        if edit_files:
            return edit_files[0]
        dados_files = [f for f in arquivos_validos if os.path.basename(f).startswith('dados_')]
        if dados_files:
            return dados_files[0]
        return arquivos_validos[0]
    return None


def carregar_json_bruto(caminho_json_bruto):
    try:
        with open(caminho_json_bruto, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERRO ao ler o arquivo JSON bruto '{os.path.basename(caminho_json_bruto)}': {e}")
        return None


# -----------------------------------------------------------------------------
# --- FUNÇÃO PRINCIPAL ---
# -----------------------------------------------------------------------------

def main():
    caminho_sessao_selecionada, nome_sessao = selecionar_sessao(OUTPUT_BASE_FOLDER)
    if not caminho_sessao_selecionada:
        return

    nome_base_sem_ts = re.sub(r'_\d{8}_\d{6}$', '', nome_sessao)
    id_sessao_match = re.search(r'^(?:FC[\d\.]+-?)?(.*)', nome_base_sem_ts)
    if not id_sessao_match:
        print(f"ERRO: Não foi possível extrair o ID da sessão do nome '{nome_sessao}'.")
        return

    id_sessao = id_sessao_match.group(1)
    df_reologico, dados_modelos = carregar_dados_sessao(caminho_sessao_selecionada)
    if df_reologico is None:
        return

    caminho_json_bruto = encontrar_json_bruto(id_sessao, JSON_INPUT_DIR)
    if not caminho_json_bruto:
        print(f"AVISO: JSON Bruto original não encontrado em '{JSON_INPUT_DIR}' com ID '{id_sessao}'.")
        return

    dados_brutos_orig = carregar_json_bruto(caminho_json_bruto)
    if dados_brutos_orig is None:
        return

    print(f"\nSessão de análise selecionada: {nome_sessao}")
    print(f"ID da Sessão (JSON Base): {id_sessao}")
    print(f"JSON Bruto Original encontrado: {os.path.basename(caminho_json_bruto)}")

    # Obter o melhor modelo
    try:
        modelos_ajustados = dados_modelos['modelos_ajustados']
        melhor_modelo_nome = max(modelos_ajustados, key=lambda name: modelos_ajustados[name].get('R2', 0))
        melhor_modelo_params = modelos_ajustados[melhor_modelo_nome]['params']
        modelo_func = MODELS[melhor_modelo_nome][0]
        print(f"\nMelhor modelo: {melhor_modelo_nome} (R² = {modelos_ajustados[melhor_modelo_nome].get('R2', 0):.4f})")
    except Exception as e:
        print(f"ERRO ao extrair o melhor modelo: {e}")
        return

    col_gamma = 'γ̇w (s⁻¹)' if 'γ̇w (s⁻¹)' in df_reologico.columns else 'γ̇w_MEDIA(s⁻¹)'
    col_tau = 'τw (Pa)' if 'τw (Pa)' in df_reologico.columns else 'τw_MEDIA(Pa)'

    try:
        df_reologico['Ponto'] = df_reologico['Ponto'].astype(str)
        df_res = df_reologico[['Ponto', col_gamma, col_tau]].copy()
        df_res['τw_modelo (Pa)'] = modelo_func(df_res[col_gamma], *melhor_modelo_params)
        df_res['Residuo (Pa)'] = df_res[col_tau] - df_res['τw_modelo (Pa)']
        df_res['Residuo_Percentual (%)'] = 100 * (df_res['Residuo (Pa)'] / df_res[col_tau])
        df_res['Residuo_Abs'] = np.abs(df_res['Residuo (Pa)'])
    except Exception as e:
        print(f"ERRO ao calcular resíduos: {e}")
        return

    # --- Outliers ---
    limite_multiplicador = 2.0
    residuo_medio = df_res['Residuo (Pa)'].mean()
    residuo_std = df_res['Residuo (Pa)'].std()
    limite_sup = residuo_medio + limite_multiplicador * residuo_std
    limite_inf = residuo_medio - limite_multiplicador * residuo_std
    outliers = df_res[(df_res['Residuo (Pa)'] > limite_sup) | (df_res['Residuo (Pa)'] < limite_inf)]

    print("\n--- Análise de Resíduos ---")
    print(f"Resíduo Médio: {residuo_medio:.2f} Pa")
    print(f"Desvio Padrão: {residuo_std:.2f} Pa")
    print(f"Limite ±{limite_multiplicador:.1f}σ: [{limite_inf:.2f}, {limite_sup:.2f}]")

    if outliers.empty:
        print("\nNenhum outlier identificado.")
        return

    print(f"\n--- {len(outliers)} OUTLIERS IDENTIFICADOS ---")
    print(outliers.to_string(index=False, float_format="%.2f"))

    pontos_a_remover = set(outliers['Ponto'])
    pontos_removidos = 0

    # --- Correção principal: filtragem compatível ---
    if 'testes' not in dados_brutos_orig:
        print("ERRO: JSON não contém a chave 'testes'.")
        return

    testes_limpos = []
    for ponto_json in dados_brutos_orig['testes']:
        id_ponto_str = str(ponto_json.get('id_ponto', ponto_json.get('ponto_n')))
        if id_ponto_str not in pontos_a_remover:
            testes_limpos.append(ponto_json)
        else:
            pontos_removidos += 1

    if pontos_removidos != len(outliers):
        print(f"AVISO: {pontos_removidos} removidos, {len(outliers)} esperados.")
        print(f"Pontos a remover: {pontos_a_remover}")

    dados_brutos_orig['testes'] = testes_limpos
    dados_brutos_orig['data_hora_filtragem_residuos'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dados_brutos_orig['observacoes_filtragem'] = f"Filtro por resíduos ({limite_multiplicador:.1f} * STD). {pontos_removidos} ponto(s) removido(s)."

    nome_sessao_base = dados_brutos_orig.get('id_amostra', id_sessao)
    nome_saida = f"limpo_residuos_{nome_sessao_base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    caminho_saida = os.path.join(JSON_INPUT_DIR, nome_saida)

    with open(caminho_saida, 'w', encoding='utf-8') as f:
        json.dump(dados_brutos_orig, f, indent=4, ensure_ascii=False)

    print(f"\nSUCESSO: JSON limpo salvo em {nome_saida}")
    print("Execute o Script 2.Analise_reologica.py com este novo arquivo.")


# -----------------------------------------------------------------------------
# --- PONTO DE ENTRADA ---
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\nERRO INESPERADO: {e}")
        traceback.print_exc()

    print("\n--- FIM DO SCRIPT DE FILTRAGEM POR RESÍDUOS ---")
