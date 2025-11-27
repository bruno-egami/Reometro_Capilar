# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# SCRIPT 3.VISUALIZAR_RESULTADOS.PY (MODULARIZADO)
# -----------------------------------------------------------------------------
import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import utils_reologia
import reologia_io
import reologia_fitting
import reologia_plot

import json

# --- CONFIGURAÇÃO DE PASTAS ---
INPUT_BASE_FOLDER = utils_reologia.CONSTANTS['INPUT_BASE_FOLDER']

# =============================================================================
# FUNÇÕES AUXILIARES (Portadas do Script 4)
# =============================================================================

def mapear_colunas_para_padrao(df, cols_originais):
    """
    Mapeia colunas de diferentes formatos para o padrão unificado.
    """
    # Detecta tipo de arquivo baseado nas colunas presentes
    tipo_arquivo = None
    
    if 'gamma_dot_w_mean' in cols_originais:
        tipo_arquivo = 'estatistico_novo'
    elif 'mean_gamma' in cols_originais:
        tipo_arquivo = 'estatistico_antigo'
    elif 'taxa de cisalhamento corrigida (s-1)' in cols_originais:
        tipo_arquivo = 'individual'
    elif 'taxa de cisalhamento (s-1)' in cols_originais:
        tipo_arquivo = 'rotacional'
    elif 'γ̇w (s⁻¹)' in cols_originais:
        tipo_arquivo = 'ja_padronizado'
    else:
        tipo_arquivo = 'desconhecido'
    
    # Cria cópia para não modificar df original durante detecção
    df_result = df.copy()
    
    # Mapeia baseado no tipo (SEM DUPLICATAS!)
    if tipo_arquivo == 'rotacional':
        # Para rotacional, taxa é tanto real quanto aparente
        df_result = df_result.rename(columns={
            'taxa de cisalhamento (s-1)': 'γ̇w (s⁻¹)',
            'tensao de cisalhamento (pa)': 'τw (Pa)',
            'viscosidade (pa.s)': 'η (Pa·s)'
        })
        # Cria coluna aparente como cópia (para gráfico de n')
        if 'γ̇w (s⁻¹)' in df_result.columns:
            df_result['γ̇aw (s⁻¹)'] = df_result['γ̇w (s⁻¹)']
        # Pressão (se disponível)
        if 'tensao_std (pa)' in df_result.columns:
            df_result = df_result.rename(columns={'tensao_std (pa)': 'τw_std (Pa)'})
        if 'viscosity_std (pa.s)' in df_result.columns:
            df_result = df_result.rename(columns={'viscosity_std (pa.s)': 'η_std (Pa·s)'})
            
    elif tipo_arquivo == 'individual':
        df_result = df_result.rename(columns={
            'taxa de cisalhamento corrigida (s-1)': 'γ̇w (s⁻¹)',
            'taxa de cisalhamento aparente (s-1)': 'γ̇aw (s⁻¹)',
            'tensao de cisalhamento (pa)': 'τw (Pa)',
            'viscosidade real (pa.s)': 'η (Pa·s)',
            'viscosidade aparente (pa.s)': 'η_a (Pa·s)',
            'pressao (bar)': 'P (bar)'
        })
        
    elif tipo_arquivo == 'estatistico_novo':
        df_result = df_result.rename(columns={
            'gamma_dot_w_mean': 'γ̇w (s⁻¹)',
            'gamma_dot_aw_mean': 'γ̇aw (s⁻¹)',
            'tau_w_mean': 'τw (Pa)',
            'tau_w_std': 'τw_std (Pa)',
            'eta_true_mean': 'η (Pa·s)',
            'eta_true_std': 'η_std (Pa·s)',
            'eta_a_mean': 'η_a (Pa·s)',
            'pressao_mean_bar': 'P (bar)'
        })
        
    elif tipo_arquivo == 'estatistico_antigo':
        df_result = df_result.rename(columns={
            'mean_gamma': 'γ̇w (s⁻¹)',
            'mean_tau_w': 'τw (Pa)',
            'std_tau_w': 'τw_std (Pa)'
        })
        
    elif tipo_arquivo == 'ja_padronizado':
        # Garante que as colunas (que estão em lowercase) sejam renomeadas para o padrão MixedCase
        df_result = df_result.rename(columns={
            'γ̇w (s⁻¹)': 'γ̇w (s⁻¹)',
            'τw (pa)': 'τw (Pa)',
            'η (pa·s)': 'η (Pa·s)',
            'γ̇aw (s⁻¹)': 'γ̇aw (s⁻¹)',
            'η_a (pa·s)': 'η_a (Pa·s)',
            'p (bar)': 'P (bar)'
        })
    
    return df_result, tipo_arquivo

def carregar_modelo_associado(caminho_csv):
    """
    Carrega modelo associado a um arquivo CSV de resultados (JSON ou CSV).
    """
    pasta = os.path.dirname(caminho_csv)
    nome_base = os.path.splitext(os.path.basename(caminho_csv))[0]
    
    # Remove sufixos comuns
    nome_base_limpo = nome_base
    nome_base_limpo = nome_base_limpo.replace('_resultados_reologicos', '')
    nome_base_limpo = nome_base_limpo.replace('_estatisticas_', '_')
    nome_base_limpo = nome_base_limpo.replace('_processado', '')
    
    # 1. Tenta carregar JSON
    possiveis_jsons = [
        os.path.join(pasta, f"{nome_base}_parametros_modelos.json"),
        os.path.join(pasta, f"{nome_base_limpo}_parametros_modelos.json"),
    ]
    
    for json_path in possiveis_jsons:
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if "Melhor Modelo" in data and "Parametros" in data:
                    return data
            except Exception as e:
                print(f"    ⚠️ Aviso: Erro ao ler modelo JSON '{os.path.basename(json_path)}': {e}")

    # 2. Fallback: Tenta carregar CSV (Script 2 antigo)
    possiveis_csvs = [
        os.path.join(pasta, f"{nome_base}_resumo_melhor_modelo.csv"),
        os.path.join(pasta, f"{nome_base_limpo}_resumo_melhor_modelo.csv")
    ]
    
    for csv_path in possiveis_csvs:
        if os.path.exists(csv_path):
            try:
                df_mod = pd.read_csv(csv_path, sep=';', encoding='latin-1')
                if not df_mod.empty:
                    nome_modelo = None
                    r2 = 0.0
                    params = []
                    
                    row_model = df_mod[df_mod.iloc[:, 0].astype(str).str.contains("Modelo Reológico", case=False, na=False)]
                    if not row_model.empty: nome_modelo = str(row_model.iloc[0, 1]).strip()
                    
                    row_r2 = df_mod[df_mod.iloc[:, 0].astype(str).str.contains("R²", case=False, na=False)]
                    if not row_r2.empty:
                        try: r2 = float(str(row_r2.iloc[0, 1]).replace(',', '.'))
                        except: pass
                        
                    if nome_modelo:
                        from modelos_reologicos import MODELS
                        if nome_modelo in MODELS:
                            param_names = MODELS[nome_modelo][1]
                            for p_name in param_names:
                                search_term = "τ₀" if p_name == "tau0" else ("η" if p_name == "eta" else p_name)
                                row_p = df_mod[df_mod.iloc[:, 0].astype(str).str.contains(search_term, regex=False, na=False)]
                                if row_p.empty: row_p = df_mod[df_mod.iloc[:, 0].astype(str).str.contains(p_name, case=False, na=False)]
                                if not row_p.empty:
                                    try: params.append(float(str(row_p.iloc[0, 1]).replace(',', '.')))
                                    except: params.append(0.0)
                                else: params.append(0.0)
                            
                            return {"Melhor Modelo": nome_modelo, "R2": r2, "Parametros": params}
            except Exception as e:
                print(f"    ⚠️ Aviso: Erro ao ler modelo CSV '{os.path.basename(csv_path)}': {e}")
    
    return None

def visualizador_principal():
    print("\n--- VISUALIZADOR DE RESULTADOS REOLÓGICOS (MODULARIZADO) ---")
    
    # 1. Seleciona Arquivo (Busca em múltiplas pastas)
    print("Buscando arquivos de resultados...")
    
    # Define padrões de busca
    search_patterns = [
        (utils_reologia.CONSTANTS['INPUT_BASE_FOLDER'], "**/*resultados*.csv"),
        ("resultados_estatisticos", "**/*estatisticas*.csv"),
        (utils_reologia.CONSTANTS['CAMINHO_BASE_ROTACIONAL'], "**/*processado.csv")
    ]
    
    all_files = []
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    for folder, pattern in search_patterns:
        search_path = os.path.join(project_root, folder, pattern)
        found = glob.glob(search_path, recursive=True)
        all_files.extend(found)
        
    # Remove duplicatas e ordena
    all_files = sorted(list(set(all_files)), key=os.path.getmtime, reverse=True)
    
    if not all_files:
        print("Nenhum arquivo de resultados encontrado.")
        return

    # Separa em grupos para exibição
    files_stat = []
    files_rot = []
    files_indiv = []
    
    for f in all_files:
        fname = os.path.basename(f)
        if "estatisticas" in fname:
            files_stat.append(f)
        elif "processado" in fname:
            files_rot.append(f)
        else:
            files_indiv.append(f)
            
    print(f"\n--- Selecione um arquivo de resultados ---")
    
    current_idx = 1
    mapa_escolha = {}
    
    if files_stat:
        print("\n[RESULTADOS ESTATÍSTICOS (MÉDIAS)]")
        for f in files_stat:
            parent = os.path.basename(os.path.dirname(f))
            fname = os.path.basename(f)
            # Tenta simplificar o nome exibido
            display_name = fname.replace("_estatisticas_", " -> ").replace(".csv", "")
            print(f"  {current_idx}: {display_name}  (Pasta: {parent})")
            mapa_escolha[current_idx] = f
            current_idx += 1

    if files_rot:
        print("\n[RESULTADOS ROTACIONAL (SCRIPT 5)]")
        for f in files_rot:
            parent = os.path.basename(os.path.dirname(f))
            fname = os.path.basename(f)
            display_name = fname.replace("_processado", "").replace(".csv", "")
            print(f"  {current_idx}: {display_name}  (Pasta: {parent})")
            mapa_escolha[current_idx] = f
            current_idx += 1
            
    if files_indiv:
        print("\n[RESULTADOS INDIVIDUAIS (BRUTOS/PROCESSADOS)]")
        for f in files_indiv:
            parent = os.path.basename(os.path.dirname(f))
            fname = os.path.basename(f)
            display_name = fname.replace("_resultados_reologicos", "").replace(".csv", "")
            print(f"  {current_idx}: {display_name}  (Pasta: {parent})")
            mapa_escolha[current_idx] = f
            current_idx += 1
        
    try:
        entrada = input("\nDigite o número do arquivo (ou lista ex: 1, 3, 5): ").strip()
        if not entrada: return
        
        # Parseia entrada (suporta múltiplos índices)
        indices_selecionados = []
        partes = entrada.split(',')
        for p in partes:
            if p.strip().isdigit():
                idx = int(p.strip())
                if idx in mapa_escolha:
                    indices_selecionados.append(idx)
        
        if not indices_selecionados:
            print("Nenhuma opção válida selecionada.")
            return
            
    except ValueError:
        return

    # --- PROCESSAMENTO DOS ARQUIVOS SELECIONADOS ---
    dados_analises = {}
    modelos_dict = {}
    
    print(f"\nProcessando {len(indices_selecionados)} arquivo(s)...")
    
    for idx in indices_selecionados:
        caminho_arquivo = mapa_escolha[idx]
        nome_arquivo = os.path.basename(caminho_arquivo)
        
        # Nome para legenda (simplificado)
        nome_legenda = os.path.splitext(nome_arquivo)[0]
        nome_legenda = nome_legenda.replace("_resultados_reologicos", "").replace("_estatisticas_", "_").replace("_processado", "")
        
        print(f"\nCarregando: {nome_legenda}")
        
        # Carrega CSV
        df = reologia_io.carregar_csv_resultados(caminho_arquivo)
        if df is None: continue
        
        # Normaliza e Mapeia Colunas
        df.columns = [c.lower() for c in df.columns]
        cols_originais = df.columns.tolist()
        df, tipo_arquivo = mapear_colunas_para_padrao(df, cols_originais)
        
        # Valida Colunas Essenciais
        colunas_necessarias = ['γ̇w (s⁻¹)', 'τw (Pa)']
        colunas_presentes = [col for col in colunas_necessarias if col in df.columns]
        
        if len(colunas_presentes) == len(colunas_necessarias):
            dados_analises[nome_legenda] = df
            print(f"  ✅ Dados carregados (Tipo: {tipo_arquivo})")
            
            # Carrega Modelo Associado
            modelo = carregar_modelo_associado(caminho_arquivo)
            if modelo:
                modelos_dict[nome_legenda] = modelo
                print(f"  📊 Modelo carregado: {modelo['Melhor Modelo']}")
            else:
                # Tenta ajustar on-the-fly se não tiver modelo salvo (apenas para visualização)
                print("  ⚠️ Modelo não encontrado. Ajustando on-the-fly para visualização...")
                try:
                    gamma = df['γ̇w (s⁻¹)'].values
                    tau = df['τw (Pa)'].values
                    m_results, best_name, _ = reologia_fitting.ajustar_modelos(gamma, tau)
                    if best_name:
                        modelos_dict[nome_legenda] = {
                            "Melhor Modelo": best_name,
                            "Parametros": m_results[best_name]['params'],
                            "R2": m_results[best_name]['R2']
                        }
                        print(f"  ✨ Modelo ajustado: {best_name}")
                except Exception as e:
                    print(f"  Erro ao ajustar modelo: {e}")
        else:
            print(f"  ❌ ERRO: Colunas faltando em '{nome_arquivo}'")

    if not dados_analises:
        print("\nNenhum dado válido para visualizar.")
        return

    # --- LÓGICA DE PLOTAGEM HÍBRIDA ---
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_saida = os.path.dirname(mapa_escolha[indices_selecionados[0]]) # Salva na pasta do primeiro arquivo
    
    # MODO 1: ARQUIVO ÚNICO (Detalhado - Estilo Script 3 Original)
    if len(dados_analises) == 1:
        print("\n--- MODO DETALHADO (Arquivo Único) ---")
        nome_unico = list(dados_analises.keys())[0]
        df_unico = dados_analises[nome_unico]
        modelo_data = modelos_dict.get(nome_unico, {})
        
        # Prepara dados para gerar_graficos_finais
        gamma_dot_aw = df_unico.get('γ̇aw (s⁻¹)', df_unico['γ̇w (s⁻¹)']).values
        tau_w = df_unico['τw (Pa)'].values
        gamma_dot_w = df_unico['γ̇w (s⁻¹)'].values
        eta_true = df_unico['η (Pa·s)'].values
        eta_a = df_unico.get('η_a (Pa·s)', tau_w / gamma_dot_aw).values
        
        std_tau = df_unico.get('τw_std (Pa)', None)
        std_tau = std_tau.values if std_tau is not None else None
        std_eta = df_unico.get('η_std (Pa·s)', None)
        std_eta = std_eta.values if std_eta is not None else None
        
        # Calcula n' e K'
        from scipy.stats import linregress
        valid_log = (gamma_dot_aw > 0) & (tau_w > 0)
        if np.sum(valid_log) > 1:
            slope, intercept, _, _, _ = linregress(np.log(gamma_dot_aw[valid_log]), np.log(tau_w[valid_log]))
            n_prime, log_K_prime = slope, intercept
        else:
            n_prime, log_K_prime = 1.0, 0.0
            
        # Formata modelo para função de plotagem
        best_model_nome = modelo_data.get('Melhor Modelo', 'Nenhum')
        model_results = {}
        if best_model_nome != 'Nenhum':
            model_results[best_model_nome] = {
                'params': modelo_data['Parametros'],
                'R2': modelo_data.get('R2', 0.0)
            }
            
        reologia_plot.gerar_graficos_finais(
            pasta_saida, timestamp,
            gamma_dot_aw, tau_w,
            gamma_dot_w, eta_true, eta_a,
            n_prime, log_K_prime,
            model_results, best_model_nome,
            [], 0.0, 0.0,
            False, False, False,
            only_show=True, # Apenas mostra na tela (não salva PNG para não poluir)
            std_tau_w=std_tau,
            std_eta=std_eta,
            show_plots=True
        )
        
    # MODO 2: MÚLTIPLOS ARQUIVOS (Comparativo - Estilo Script 4)
    else:
        print(f"\n--- MODO COMPARATIVO ({len(dados_analises)} Arquivos) ---")
        
        # Cria pasta específica para comparativos se não existir
        pasta_comp = os.path.join(utils_reologia.CONSTANTS.get('CAMINHO_BASE_COMPARATIVOS', "comparativo_analises"), f"Comparativo_{timestamp}")
        if not os.path.exists(pasta_comp): os.makedirs(pasta_comp)
        
        print(f"Gerando gráficos comparativos em: {pasta_comp}")
        
        # 1. Curva de Fluxo
        reologia_plot.plotar_comparativo_multiplo(
            dados_analises, 'γ̇w (s⁻¹)', 'τw (Pa)', 
            "Comparativo: Curva de Fluxo", "Taxa de Cisalhamento (s⁻¹)", "Tensão de Cisalhamento (Pa)",
            pasta_comp, timestamp, show_plots=True, modelos_dict=modelos_dict
        )
        
        # 2. Viscosidade
        reologia_plot.plotar_comparativo_multiplo(
            dados_analises, 'γ̇w (s⁻¹)', 'η (Pa·s)', 
            "Comparativo: Viscosidade Real", "Taxa de Cisalhamento (s⁻¹)", "Viscosidade Real (Pa·s)",
            pasta_comp, timestamp, show_plots=True, modelos_dict=modelos_dict
        )
        
        # 3. n' (ln vs ln)
        dados_n = {}
        for nome, df in dados_analises.items():
            if 'γ̇aw (s⁻¹)' in df.columns and 'τw (Pa)' in df.columns:
                df_n = df.copy()
                valid = (df_n['γ̇aw (s⁻¹)'] > 0) & (df_n['τw (Pa)'] > 0)
                df_n = df_n[valid]
                if not df_n.empty:
                    df_n['ln_gamma'] = np.log(df_n['γ̇aw (s⁻¹)'])
                    df_n['ln_tau'] = np.log(df_n['τw (Pa)'])
                    dados_n[nome] = df_n
        
        if dados_n:
            reologia_plot.plotar_comparativo_multiplo(
                dados_n, 'ln_gamma', 'ln_tau',
                "Comparativo: Determinação de n'", "ln(Taxa Aparente)", "ln(Tensão)",
                pasta_comp, timestamp, usar_log=False, show_plots=True
            )
            
        # 4. Pressão vs Viscosidade
        dados_p = {}
        for nome, df in dados_analises.items():
            if 'P (bar)' in df.columns and 'η (Pa·s)' in df.columns:
                df_p = df.copy()
                df_p['P (Pa)'] = df_p['P (bar)'] * 1e5
                dados_p[nome] = df_p
                
        if dados_p:
            reologia_plot.plotar_comparativo_multiplo(
                dados_p, 'P (Pa)', 'η (Pa·s)',
                "Comparativo: Pressão vs Viscosidade", "Pressão (Pa)", "Viscosidade Real (Pa·s)",
                pasta_comp, timestamp, usar_log=False, show_plots=True
            )

        # 5. Viscosidade Real vs Aparente (Novo Gráfico)
        reologia_plot.plotar_comparativo_real_vs_aparente(
            dados_analises, pasta_comp, timestamp, show_plots=True
        )


if __name__ == "__main__":
    visualizador_principal()
