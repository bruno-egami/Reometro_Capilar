# -*- coding: utf-8 -*-
"""
SCRIPT 2C.FILTRO_RESIDUOS_MODELO.PY
(Filtra outliers comparando dados experimentais corrigidos com o melhor modelo ajustado)
"""
import os
import pandas as pd
import numpy as np
import utils_reologia
import reologia_io
import reologia_fitting
import reologia_plot

# --- CONFIGURAÇÃO DE PASTAS ---
INPUT_BASE_FOLDER = utils_reologia.CONSTANTS['INPUT_BASE_FOLDER']
JSON_INPUT_DIR = utils_reologia.CONSTANTS['JSON_INPUT_DIR']

def main():
    print("\n--- FILTRO DE OUTLIERS POR RESÍDUOS (MODULARIZADO) ---")
    
    # 1. Seleciona Sessão (CSV de Resultados)
    caminho_csv = utils_reologia.selecionar_arquivo(INPUT_BASE_FOLDER, "*resultados_reologicos.csv", "Selecione o CSV de Resultados", recursivo=True)
    if not caminho_csv: return

    nome_base = os.path.splitext(os.path.basename(caminho_csv))[0]
    pasta_saida = os.path.dirname(caminho_csv) # Salva na mesma pasta da análise original
    
    # 2. Carrega Dados
    df = reologia_io.carregar_csv_resultados(caminho_csv)
    if df is None: return
    
    # Padroniza colunas (usa apenas a coluna corrigida)
    # Normaliza nomes de colunas (lowercase) antes de mapear
    df.columns = [c.lower() for c in df.columns]
    
    # Seleciona e renomeia apenas as colunas que precisamos
    # Tenta diferentes variações de nomes de colunas para compatibilidade
    colunas_necessarias = [
        ('taxa de cisalhamento corrigida (s-1)', 'γ̇w (s⁻¹)'),
        ('γ̇w (s⁻¹)', 'γ̇w (s⁻¹)'),  # Se já existe
        ('tensao de cisalhamento (pa)', 'τw (Pa)'),
        ('τw (pa)', 'τw (Pa)'),  # Se já existe
    ]
    
    # Encontra quais colunas existem
    colunas_encontradas = {}
    col_gamma = None
    col_tau = None
    
    for old_name, new_name in colunas_necessarias:
        if old_name in df.columns:
            if new_name == 'γ̇w (s⁻¹)' and col_gamma is None:
                col_gamma = old_name
                colunas_encontradas[old_name] = new_name
            elif new_name == 'τw (Pa)' and col_tau is None:
                col_tau = old_name
                colunas_encontradas[old_name] = new_name
    
    if len(colunas_encontradas) < 2:
        print(f"ERRO: Colunas necessárias não encontradas. Colunas disponíveis: {list(df.columns)}")
        return
    
    # Seleciona apenas as colunas encontradas e renomeia
    df = df[list(colunas_encontradas.keys())].copy()
    df.rename(columns=colunas_encontradas, inplace=True)

    # 3. Reajusta Modelos (para garantir consistência)
    print("  Reajustando modelos...")
    model_results, best_model_nome, _ = reologia_fitting.ajustar_modelos(
        df['γ̇w (s⁻¹)'].values, df['τw (Pa)'].values
    )
    
    if not best_model_nome:
        print("ERRO: Não foi possível ajustar modelos.")
        return
        
    print(f"  Melhor modelo: {best_model_nome}")
    
    # 4. Calcula Resíduos
    # Predição do modelo
    func_modelo = reologia_fitting.MODELS[best_model_nome][0]
    params = model_results[best_model_nome]['params']
    
    df['τw_pred'] = func_modelo(df['γ̇w (s⁻¹)'].values, *params)
    
    # Resíduo Relativo (%)
    df['Residuo (%)'] = ((df['τw (Pa)'] - df['τw_pred']) / df['τw_pred']) * 100
    
    # 5. Filtra Outliers (> 20% de erro, por exemplo)
    LIMITE_ERRO = 20.0
    df_filtrado = df[df['Residuo (%)'].abs() <= LIMITE_ERRO].copy()
    n_removidos = len(df) - len(df_filtrado)
    
    print(f"  Pontos removidos (Erro > {LIMITE_ERRO}%): {n_removidos}")
    
    if n_removidos > 0:
        # Salva Novo CSV Filtrado
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{nome_base}_FILTRADO_{timestamp}.csv"
        caminho_novo = os.path.join(pasta_saida, novo_nome)
        df_filtrado.to_csv(caminho_novo, sep=';', decimal=',', index=False)
        print(f"  Novo CSV salvo: {novo_nome}")
        
        # Plota Resíduos (Opcional - usando matplotlib direto ou adicionar func no reologia_plot)
        # Por simplicidade, vamos pular o plot específico de resíduos aqui ou usar o genérico se tiver.
    else:
        print("  Nenhum outlier significativo encontrado.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRO: {e}")
