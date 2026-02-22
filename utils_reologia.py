import os
import glob
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from datetime import datetime

# -----------------------------------------------------------------------------
# --- CONSTANTES GERAIS ---
# -----------------------------------------------------------------------------
CONSTANTS = {
    'INPUT_BASE_FOLDER': "resultados_analise_reologica",
    'STATISTICAL_OUTPUT_FOLDER': "resultados_analise_estatistica",
    'JSON_COMPANHEIRO_DIR': "resultados_testes_reometro",
    'CAMINHO_BASE_COMPARATIVOS': "comparativo_analises",
    'CAMINHO_BASE_ROTACIONAL': "resultados_processados_interativo",
    'JSON_INPUT_DIR': "resultados_testes_reometro", # Usado em scripts de coleta/filtro
    'RESULTS_JSON_DIR': "resultados_testes_reometro", # Alias comum
    'CALIBRATIONS_FOLDER': "correcoes_bagley_mooney"
}

# -----------------------------------------------------------------------------
# --- CONFIGURAÇÃO DE PLOTAGEM ---
# -----------------------------------------------------------------------------
def setup_graficos():
    """DEPRECATED: mantida para compatibilidade com scripts em legacy/.
    A GUI principal usa apply_dark_style() de reologia_plot_style.py."""
    pass

def gerar_timestamp():
    """Gera uma string de timestamp atual (YYYYMMDD_HHMMSS)."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

# -----------------------------------------------------------------------------
# --- FORMATAÇÃO ---
# -----------------------------------------------------------------------------
def format_float_for_table(value, decimal_places=4):
    """Formata um número float para exibição em tabelas, usando notação científica para valores muito pequenos."""
    if isinstance(value, (float, np.floating)):
        if np.isnan(value): return "NaN"
        if abs(value) < 10**(-decimal_places) and value != 0 and abs(value) > 1e-12 :
             return f"{value:.{max(1,decimal_places)}g}"
        return f"{value:.{decimal_places}f}"
    return str(value)

# -----------------------------------------------------------------------------
# --- SELEÇÃO DE ARQUIVOS ---
# -----------------------------------------------------------------------------
def selecionar_arquivo(diretorio_base, padrao_busca="*", mensagem_prompt="Selecione um arquivo", extensao_filtro=None, recursivo=False):
    """
    Lista e permite ao usuário selecionar um arquivo de um diretório.
    
    Args:
        diretorio_base (str): Caminho da pasta para buscar.
        padrao_busca (str): Padrão glob para busca (ex: '*.json', '*_resultados.csv').
        mensagem_prompt (str): Mensagem para exibir ao usuário.
        extensao_filtro (str, opcional): Extensão obrigatória para validação manual (ex: '.json').
        recursivo (bool): Se True, busca em subpastas.
    
    Returns:
        str: Caminho completo do arquivo selecionado, ou None se cancelado.
    """
    if not os.path.exists(diretorio_base):
        print(f"ERRO: Diretório não encontrado: {diretorio_base}")
        return None

    caminho_busca = os.path.join(diretorio_base, '**', padrao_busca) if recursivo else os.path.join(diretorio_base, padrao_busca)
    arquivos = glob.glob(caminho_busca, recursive=recursivo)
    
    # Ordena por data de modificação (mais recente primeiro)
    arquivos.sort(key=os.path.getmtime, reverse=True)

    if not arquivos:
        print(f"Nenhum arquivo encontrado com o padrão '{padrao_busca}' em '{diretorio_base}'.")
        return None

    print(f"\n--- {mensagem_prompt} ---")
    arquivos_exibicao = []
    for i, caminho_completo in enumerate(arquivos):
        nome_arquivo = os.path.basename(caminho_completo)
        # Se for recursivo, mostra a pasta pai para contexto
        if recursivo:
            pasta_pai = os.path.basename(os.path.dirname(caminho_completo))
            display_name = f"{pasta_pai}/{nome_arquivo}"
        else:
            display_name = nome_arquivo
            
        arquivos_exibicao.append(caminho_completo)
        print(f"  {i+1}: {display_name}")

    while True:
        try:
            escolha_str = input(f"\nDigite o NÚMERO do arquivo (ou '0' para cancelar/manual): ").strip()
            if escolha_str == '0':
                # Opção de entrada manual (útil se o arquivo não for listado ou para criar novos em alguns contextos)
                # Mas para seleção estrita, pode ser apenas cancelar. 
                # Vamos manter a lógica de cancelar por padrão, mas permitir manual se solicitado explicitamente no prompt?
                # Para simplificar e unificar, '0' cancela ou pede nome manual dependendo da implementação original.
                # Vou implementar uma verificação simples:
                print("  1. Cancelar")
                print("  2. Digitar nome manualmente")
                sub_escolha = input("  Opção: ").strip()
                if sub_escolha == '1': return None
                if sub_escolha == '2':
                    nome_manual = input(f"  Digite o nome do arquivo (deve estar em {diretorio_base}): ").strip()
                    if extensao_filtro and not nome_manual.lower().endswith(extensao_filtro.lower()):
                         nome_manual += extensao_filtro
                    
                    caminho_manual = os.path.join(diretorio_base, nome_manual)
                    if os.path.exists(caminho_manual):
                        return caminho_manual
                    else:
                        print(f"  ERRO: Arquivo '{nome_manual}' não encontrado.")
                        continue
                return None
            
            escolha = int(escolha_str)
            if 1 <= escolha <= len(arquivos_exibicao):
                return arquivos_exibicao[escolha - 1]
            else:
                print("ERRO: Escolha inválida.")
        except ValueError:
            print("ERRO: Entrada inválida. Digite um número.")

# -----------------------------------------------------------------------------
# --- LEITURA DE DADOS DE REFERÊNCIA (ROTACIONAL) ---
# -----------------------------------------------------------------------------
def read_reference_csv(filepath):
    """
    Lê um arquivo CSV exportado de reômetros rotacionais (ex: Anton Paar MCR)
    e retorna um dicionário com arrays numpy (Taxa, Tensão, Viscosidade).
    """
    import pandas as pd
    try:
        df = pd.read_csv(filepath, sep=';', decimal=',', encoding='utf-8')
        df.columns = [str(c).strip() for c in df.columns]
        if len(df.columns) < 3: return None
            
        col_gd, col_tau, col_eta = df.columns[0], df.columns[1], df.columns[2]
        
        for col in [col_gd, col_tau, col_eta]:
            if df[col].dtype == 'O':
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        df = df.dropna(subset=[col_gd, col_tau, col_eta])
        if len(df) == 0: return None
        
        return {
            'nome': os.path.basename(filepath),
            'gd': df[col_gd].values,
            'tau': df[col_tau].values,
            'eta': df[col_eta].values
        }
    except Exception as e:
        print(f"Erro referência: {e}")
        return None
