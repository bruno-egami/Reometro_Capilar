# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# SCRIPT 4.COMPARATIVO_ANALISES.PY (MODULARIZADO)
# -----------------------------------------------------------------------------
import os
import json
import pandas as pd
import numpy as np
import glob
import utils_reologia
import reologia_io
import reologia_fitting
import reologia_plot
import reologia_report
import reologia_report_pdf

# --- CONFIGURAÇÃO DE PASTAS ---
INPUT_BASE_FOLDER = utils_reologia.CONSTANTS['INPUT_BASE_FOLDER']
# Pasta correta para salvar comparativos
OUTPUT_FOLDER = utils_reologia.CONSTANTS.get('CAMINHO_BASE_COMPARATIVOS', "comparativo_analises")

# =============================================================================
# FUNÇÕES AUXILIARES PARA CARREGAMENTO E NORMALIZAÇÃO
# =============================================================================

def mapear_colunas_para_padrao(df, cols_originais):
    """
    Mapeia colunas de diferentes formatos para o padrão unificado.
    
    Detecta automaticamente o tipo de arquivo e mapeia as colunas
    sem usar chaves duplicadas no dicionário.
    
    Args:
        df: DataFrame pandas com dados
        cols_originais: Lista de nomes de colunas originais (lowercase)
    
    Returns:
        tuple: (DataFrame com colunas padronizadas, tipo_arquivo)
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
            'eta_true_mean': 'η (Pa·s)',
            'eta_true_std': 'η_std (Pa·s)',
            'eta_a_mean': 'η_a (Pa·s)',
            'pressao_mean_bar': 'P (bar)',
            'tempo_mean': 'tempo_s',
            'massa_mean': 'massa_g'
        })
        
    elif tipo_arquivo == 'estatistico_antigo':
        df_result = df_result.rename(columns={
            'mean_gamma': 'γ̇w (s⁻¹)',
            'mean_tau_w': 'τw (Pa)',
            'std_tau_w': 'τw_std (Pa)'
        })
        
    elif tipo_arquivo == 'ja_padronizado':
        # Garante que as colunas (que estão em lowercase) sejam renomeadas para o padrão MixedCase
        # Isso corrige o erro onde 'τw (pa)' não era reconhecido como 'τw (Pa)'
        df_result = df_result.rename(columns={
            'γ̇w (s⁻¹)': 'γ̇w (s⁻¹)',
            'τw (pa)': 'τw (Pa)',
            'η (pa·s)': 'η (Pa·s)',
            'γ̇aw (s⁻¹)': 'γ̇aw (s⁻¹)',
            'η_a (pa·s)': 'η_a (Pa·s)',
            'η_a (pa·s)': 'η_a (Pa·s)',
            'p (bar)': 'P (bar)',
            'duracao_real_s': 'tempo_s',
            'massa_g': 'massa_g'
        })
        
        # Fallback para nomes antigos
        if 'tempo_extrusao_s' in df_result.columns and 'tempo_s' not in df_result.columns:
             df_result = df_result.rename(columns={'tempo_extrusao_s': 'tempo_s'})
    
    return df_result, tipo_arquivo


def carregar_modelo_associado(caminho_csv):
    """
    Carrega modelo associado a um arquivo CSV de resultados.
    
    Busca apenas arquivos JSON (mais confiável que parsing de CSV).
    
    Args:
        caminho_csv: Caminho completo do arquivo CSV
    
    Returns:
        dict: Dados do modelo {'Melhor Modelo': str, 'Parametros': list, 'R2': float}
              ou None se não encontrar
    """
    pasta = os.path.dirname(caminho_csv)
    nome_base = os.path.splitext(os.path.basename(caminho_csv))[0]
    
    # Remove sufixos comuns para tentar encontrar o JSON
    nome_base_limpo = nome_base
    nome_base_limpo = nome_base_limpo.replace('_resultados_reologicos', '')
    nome_base_limpo = nome_base_limpo.replace('_estatisticas_', '_')
    nome_base_limpo = nome_base_limpo.replace('_processado', '')
    
    # Lista de possíveis caminhos JSON
    possiveis_jsons = [
        os.path.join(pasta, f"{nome_base}_parametros_modelos.json"),
        os.path.join(pasta, f"{nome_base_limpo}_parametros_modelos.json"),
    ]
    
    # Tenta carregar JSON
    for json_path in possiveis_jsons:
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Valida estrutura mínima
                if "Melhor Modelo" in data and "Parametros" in data:
                    return data
                    
            except Exception as e:
                print(f"    ⚠️ Aviso: Erro ao ler modelo JSON '{os.path.basename(json_path)}': {e}")
    
    # --- FALLBACK: Tenta carregar CSV (para compatibilidade com Script 2 antigo) ---
    possiveis_csvs = [
        os.path.join(pasta, f"{nome_base}_resumo_melhor_modelo.csv"),
        os.path.join(pasta, f"{nome_base_limpo}_resumo_melhor_modelo.csv")
    ]
    
    for csv_path in possiveis_csvs:
        if os.path.exists(csv_path):
            try:
                # Tenta ler CSV com encoding latin-1 (comum no Excel/Script 2)
                df_mod = pd.read_csv(csv_path, sep=';', encoding='latin-1')
                if not df_mod.empty:
                    # Lógica de extração do CSV (adaptada do código original)
                    nome_modelo = None
                    r2 = 0.0
                    params = []
                    
                    # Busca nome do modelo
                    row_model = df_mod[df_mod.iloc[:, 0].astype(str).str.contains("Modelo Reológico", case=False, na=False)]
                    if not row_model.empty:
                        nome_modelo = str(row_model.iloc[0, 1]).strip()
                    
                    # Busca R2
                    row_r2 = df_mod[df_mod.iloc[:, 0].astype(str).str.contains("R²", case=False, na=False)]
                    if not row_r2.empty:
                        try: r2 = float(str(row_r2.iloc[0, 1]).replace(',', '.'))
                        except: pass
                        
                    # Se achou modelo, tenta extrair parâmetros
                    if nome_modelo:
                        # Importa definições de modelos para saber quais parâmetros buscar
                        from modelos_reologicos import MODELS
                        if nome_modelo in MODELS:
                            param_names = MODELS[nome_modelo][1]
                            
                            for p_name in param_names:
                                # Mapeia nomes comuns
                                search_term = p_name
                                if p_name == "tau0": search_term = "τ₀"
                                elif p_name == "eta": search_term = "η"
                                
                                # Busca no CSV
                                row_p = df_mod[df_mod.iloc[:, 0].astype(str).str.contains(search_term, regex=False, na=False)]
                                if row_p.empty: # Tenta nome exato se falhar
                                    row_p = df_mod[df_mod.iloc[:, 0].astype(str).str.contains(p_name, case=False, na=False)]
                                    
                                if not row_p.empty:
                                    try: params.append(float(str(row_p.iloc[0, 1]).replace(',', '.')))
                                    except: params.append(0.0)
                                else:
                                    params.append(0.0)
                            
                            return {
                                "Melhor Modelo": nome_modelo,
                                "R2": r2,
                                "Parametros": params
                            }
            except Exception as e:
                print(f"    ⚠️ Aviso: Erro ao ler modelo CSV '{os.path.basename(csv_path)}': {e}")

    # Não encontrou modelo
    print(f"    ℹ️ Modelo não encontrado para '{os.path.basename(caminho_csv)}'")
    return None



def calcular_mape(y_true, y_pred):
    """Calcula o Mean Absolute Percentage Error."""
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    # Evita divisão por zero
    mask = (y_true != 0)
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

def analise_mape(dados_analises, pasta_saida, timestamp):
    """
    Realiza análise MAPE comparando um dataset de referência com os demais.
    """
    print("\n--- ANÁLISE MAPE (Erro Percentual Absoluto Médio) ---")
    print("Selecione o dataset de REFERÊNCIA (os outros serão comparados a este):")
    
    nomes = list(dados_analises.keys())
    for i, nome in enumerate(nomes):
        print(f"  {i+1}: {nome}")
        
    try:
        idx = int(input("Digite o número da referência: ")) - 1
        if not (0 <= idx < len(nomes)):
            print("Seleção inválida. Pulando MAPE.")
            return
    except ValueError:
        print("Entrada inválida. Pulando MAPE.")
        return
        
    ref_nome = nomes[idx]
    df_ref = dados_analises[ref_nome]
    
    # Colunas padrão (já renomeadas na carga)
    col_x = 'γ̇w (s⁻¹)'
    col_y = 'η (Pa·s)' # Compara viscosidade
    
    if col_x not in df_ref.columns or col_y not in df_ref.columns:
        print(f"Erro: Colunas {col_x} ou {col_y} não encontradas na referência.")
        return
        
    x_ref = df_ref[col_x].values
    y_ref = df_ref[col_y].values
    
    # Ordena referência para interpolação
    sort_idx = np.argsort(x_ref)
    x_ref = x_ref[sort_idx]
    y_ref = y_ref[sort_idx]
    
    resultados_mape = []
    
    print(f"\nCalculando MAPE em relação a '{ref_nome}':")
    
    for nome, df in dados_analises.items():
        if nome == ref_nome: continue
        
        if col_x not in df.columns or col_y not in df.columns:
            print(f"  Pular '{nome}': colunas ausentes.")
            continue
            
        x_comp = df[col_x].values
        y_comp = df[col_y].values
        
        # Interpolação: Estima o valor da referência nas taxas de cisalhamento do comparado
        # (Ou vice-versa? Geralmente queremos saber o erro do modelo/teste em relação à referência nos pontos da referência ou nos pontos comuns)
        # Vamos interpolar a REFERÊNCIA para as taxas do COMPARADO (se o comparado for um modelo ou outro teste)
        # OU interpolar o COMPARADO para as taxas da REFERÊNCIA.
        # Se a referência é o "Real", queremos saber o erro do "Teste" nos pontos onde o "Teste" foi medido?
        # Vamos interpolar a REFERÊNCIA nas taxas de cisalhamento do COMPARADO, desde que estejam dentro do range.
        
        # Filtra pontos do comparado que estão dentro do range da referência
        mask_range = (x_comp >= x_ref.min()) & (x_comp <= x_ref.max())
        
        if np.sum(mask_range) < 2:
            print(f"  Pular '{nome}': sem sobreposição suficiente de taxas de cisalhamento.")
            mape = np.nan
        else:
            x_eval = x_comp[mask_range]
            y_eval_true = np.interp(x_eval, x_ref, y_ref) # Valor da referência interpolado
            y_eval_pred = y_comp[mask_range] # Valor do comparado
            
            mape = calcular_mape(y_eval_true, y_eval_pred)
            print(f"  {nome}: MAPE = {mape:.2f}%")
            
        resultados_mape.append({
            'Comparado': nome,
            'Referencia': ref_nome,
            'MAPE (%)': mape,
            'Pontos_Sobrepostos': np.sum(mask_range)
        })
        
    if resultados_mape:
        df_mape = pd.DataFrame(resultados_mape)
        f_csv = os.path.join(pasta_saida, f"{timestamp}_analise_mape.csv")
        df_mape.to_csv(f_csv, index=False)
        print(f"\nRelatório MAPE salvo em: {os.path.basename(f_csv)}")

def main():
    print("\n--- COMPARATIVO DE ANÁLISES REOLÓGICAS (MODULARIZADO) ---")
    
    # Busca arquivos disponíveis (Individual, Estatístico e Rotacional)
    print("Buscando arquivos...")
    search_patterns = [
        (utils_reologia.CONSTANTS['INPUT_BASE_FOLDER'], "**/*resultados*.csv"),
        ("resultados_estatisticos", "**/*estatisticas*.csv"),
        (utils_reologia.CONSTANTS['CAMINHO_BASE_ROTACIONAL'], "**/*processado.csv")
    ]
    all_files = []
    project_root = os.path.dirname(os.path.abspath(__file__))
    for folder, pattern in search_patterns:
        found = glob.glob(os.path.join(project_root, folder, pattern), recursive=True)
        all_files.extend(found)
    all_files = sorted(list(set(all_files)), key=os.path.getmtime, reverse=True)
    
    if not all_files:
        print("Nenhum arquivo encontrado.")
        return

    # --- Seleção de Arquivos (Listagem Agrupada) ---
    dados_analises = {} # {nome_legenda: df}
    modelos_dict = {}   # {nome_legenda: {model_data}}
    
    while True:
        print(f"\n--- Seleção de Arquivos (Selecionados: {len(dados_analises)}) ---")
        
        # Separa arquivos para exibição
        files_stat = []
        files_rot = []
        files_indiv = []
        
        for f in all_files:
            fname = os.path.basename(f)
            if "estatisticas" in fname: files_stat.append(f)
            elif "processado" in fname: files_rot.append(f)
            else: files_indiv.append(f)
            
        current_idx = 1
        mapa_indices = {} # {idx_exibicao: indice_real_all_files}
        
        if files_stat:
            print("\n[RESULTADOS ESTATÍSTICOS (MÉDIAS)]")
            for f in files_stat:
                real_idx = all_files.index(f)
                parent = os.path.basename(os.path.dirname(f))
                fname = os.path.basename(f)
                display = fname.replace("_estatisticas_", " -> ").replace(".csv", "")
                print(f"  {current_idx}: {display} ({parent})")
                mapa_indices[current_idx] = real_idx
                current_idx += 1

        if files_rot:
            print("\n[RESULTADOS ROTACIONAL (SCRIPT 5)]")
            for f in files_rot:
                real_idx = all_files.index(f)
                parent = os.path.basename(os.path.dirname(f))
                fname = os.path.basename(f)
                display = fname.replace("_processado", "").replace(".csv", "")
                print(f"  {current_idx}: {display} ({parent})")
                mapa_indices[current_idx] = real_idx
                current_idx += 1
                
        if files_indiv:
            print("\n[RESULTADOS INDIVIDUAIS]")
            for f in files_indiv:
                real_idx = all_files.index(f)
                parent = os.path.basename(os.path.dirname(f))
                fname = os.path.basename(f)
                display = fname.replace("_resultados_reologicos", "").replace(".csv", "")
                print(f"  {current_idx}: {display} ({parent})")
                mapa_indices[current_idx] = real_idx
                current_idx += 1
            
        print("\nOpções:")
        print("  Digite os números dos arquivos separados por vírgula (ex: 1, 3, 5)")
        print("  'c': Continuar para geração dos gráficos")
        print("  '0': Sair")
        
        entrada = input("Escolha: ").strip().lower()
        
        if entrada == '0': return
        if entrada == 'c': 
            if len(dados_analises) > 0: break
            else: print("Selecione pelo menos um arquivo."); continue
            
        try:
            indices_selecionados = [int(x.strip()) for x in entrada.split(',') if x.strip().isdigit()]
            
            for idx_sel in indices_selecionados:
                if idx_sel in mapa_indices:
                    real_idx = mapa_indices[idx_sel]
                    caminho_csv = all_files[real_idx]
                    
                    # Pede nome para legenda
                    nome_padrao = os.path.splitext(os.path.basename(caminho_csv))[0].replace("_resultados_reologicos", "").replace("_estatisticas_", "_").replace("_processado", "")
                    
                    print(f"\nCarregando: {nome_padrao}")
                    nome_legenda = input(f"  Nome para legenda (Enter='{nome_padrao}'): ").strip()
                    if not nome_legenda: nome_legenda = nome_padrao
                    
                    # === INÍCIO DA CORREÇÃO ===
                    # Carrega CSV uma única vez
                    df = reologia_io.carregar_csv_resultados(caminho_csv)
                    if df is None:
                        print(f"  ❌ ERRO: Não foi possível carregar '{os.path.basename(caminho_csv)}'")
                        continue
                    
                    # Normaliza nomes das colunas (lowercase)
                    df.columns = [c.lower() for c in df.columns]
                    cols_originais = df.columns.tolist()  # SALVA ANTES de modificar
                    
                    # Usa função nova para mapear colunas (SEM duplicatas!)
                    df, tipo_arquivo = mapear_colunas_para_padrao(df, cols_originais)
                    
                    print(f"  📄 Tipo detectado: {tipo_arquivo}")
                    
                    # === VALIDAÇÃO DETALHADA ===
                    colunas_necessarias = ['γ̇w (s⁻¹)', 'τw (Pa)']
                    colunas_presentes = [col for col in colunas_necessarias if col in df.columns]
                    
                    if len(colunas_presentes) == len(colunas_necessarias):
                        # Sucesso! Adiciona aos dados
                        dados_analises[nome_legenda] = df
                        print(f"  ✅ '{nome_legenda}' adicionado com sucesso")
                        print(f"     Colunas disponíveis: {sorted(df.columns.tolist())[:8]}...")
                        
                        # === CARREGA MODELO ASSOCIADO ===
                        modelo = carregar_modelo_associado(caminho_csv)
                        if modelo:
                            modelos_dict[nome_legenda] = modelo
                            print(f"    📊 Modelo '{modelo['Melhor Modelo']}' carregado (R²={modelo.get('R2', 'N/A')})")
                    
                    else:
                        # ERRO: Colunas faltando
                        faltantes = set(colunas_necessarias) - set(colunas_presentes)
                        print(f"  ❌ ERRO: '{os.path.basename(caminho_csv)}' não possui colunas essenciais")
                        print(f"     Faltando: {faltantes}")
                        print(f"     Presentes: {df.columns.tolist()[:10]}...")
                        print(f"     Tipo detectado: {tipo_arquivo}")
                    # === FIM DA CORREÇÃO ===

            
        except ValueError:
            print("Entrada inválida.")

    # --- Configuração de Saída ---
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    nome_pasta_user = input(f"\nNome da pasta de saída (Enter para 'Comparativo_{timestamp}'): ").strip()
    if not nome_pasta_user:
        nome_pasta_user = f"Comparativo_{timestamp}"
        
    pasta_saida = os.path.join(OUTPUT_FOLDER, nome_pasta_user)
    if not os.path.exists(pasta_saida): os.makedirs(pasta_saida)
    
    print(f"\nGerando comparativos em: {pasta_saida}")
    
    # DEBUG: Mostra quais modelos foram carregados
    print(f"\n[DEBUG] Modelos carregados: {list(modelos_dict.keys()) if modelos_dict else 'Nenhum'}")
    for nome_leg, modelo_data in modelos_dict.items():
        print(f"  - {nome_leg}: {modelo_data.get('Melhor Modelo', 'N/A')}")
    
    # --- Geração dos Gráficos ---
    
    # --- Geração dos Gráficos ---
    
    # Lógica Híbrida: 
    # - Se apenas 1 arquivo: Gera gráficos detalhados (estilo Script 3)
    # - Se múltiplos arquivos: Gera gráficos comparativos (estilo Script 4)
    
    # Lista para armazenar imagens geradas
    lista_imgs_geradas = []

    if len(dados_analises) == 1:
        print("\n--- Modo Detalhado (Arquivo Único) ---")
        nome_unico = list(dados_analises.keys())[0]
        df_unico = dados_analises[nome_unico]
        
        # Prepara dados para gerar_graficos_finais (Script 3)
        # Extrai colunas necessárias
        gamma_dot_aw = df_unico.get('γ̇aw (s⁻¹)', df_unico['γ̇w (s⁻¹)']).values # Fallback para real se não tiver aparente
        tau_w = df_unico['τw (Pa)'].values
        gamma_dot_w = df_unico['γ̇w (s⁻¹)'].values
        eta_true = df_unico['η (Pa·s)'].values
        
        # Opcionais
        eta_a = df_unico.get('η_a (Pa·s)', tau_w / gamma_dot_aw).values
        std_tau = df_unico.get('τw_std (Pa)', None)
        std_tau = std_tau.values if std_tau is not None else None
        std_eta = df_unico.get('η_std (Pa·s)', None)
        std_eta = std_eta.values if std_eta is not None else None
        
        # Calcula n' e K' on-the-fly para visualização
        from scipy.stats import linregress
        valid_log = (gamma_dot_aw > 0) & (tau_w > 0)
        if np.sum(valid_log) > 1:
            slope, intercept, _, _, _ = linregress(np.log(gamma_dot_aw[valid_log]), np.log(tau_w[valid_log]))
            n_prime, log_K_prime = slope, intercept
        else:
            n_prime, log_K_prime = 1.0, 0.0
            
        # Pega modelo se existir
        modelo_data = modelos_dict.get(nome_unico, {})
        best_model_nome = modelo_data.get('Melhor Modelo', 'Nenhum')
        model_results = {}
        if best_model_nome != 'Nenhum':
            model_results[best_model_nome] = {
                'params': modelo_data['Parametros'],
                'R2': modelo_data.get('R2', 0.0)
            }
            
        print(f"  Gerando 5 gráficos detalhados para '{nome_unico}'...")
        imgs = reologia_plot.gerar_graficos_finais(
            pasta_saida, timestamp,
            gamma_dot_aw, tau_w,
            gamma_dot_w, eta_true, eta_a,
            n_prime, log_K_prime,
            model_results, best_model_nome,
            [], 0.0, 0.0, # Sem dados de pressão/geometria específicos
            False, False, False,
            only_show=False, # Salva arquivos
            std_tau_w=std_tau,
            std_eta=std_eta,
            show_plots=True
        )
        lista_imgs_geradas.extend(imgs)
        
        # Gera PDF Detalhado (reusa função do script 2)
        # Cria DF resumo
        df_res_pdf = pd.DataFrame({
            'Taxa de Cisalhamento Corrigida (s-1)': gamma_dot_w,
            'Tensao de Cisalhamento (Pa)': tau_w,
            'Viscosidade Real (Pa.s)': eta_true
        })
        
        # Adiciona opcionais se existirem
        if 'tempo_s' in df_unico.columns:
            df_res_pdf['duracao_real_s'] = df_unico['tempo_s'].values
        if 'massa_g' in df_unico.columns:
            df_res_pdf['massa_g'] = df_unico['massa_g'].values
        if 'P (bar)' in df_unico.columns:
            df_res_pdf['Pressao (bar)'] = df_unico['P (bar)'].values
        reologia_report_pdf.gerar_pdf(
            timestamp, 0.0, "N/A", "Comparativo Único", [nome_unico], "N/A",
            False, 0, [], False, 0, [], 0, 0, None,
            df_res_pdf, pd.DataFrame(), best_model_nome, "N/A",
            lista_imgs_geradas, pasta_saida, 1.0
        )
        
    else:
        print(f"\n--- Modo Comparativo ({len(dados_analises)} Arquivos) ---")
        
        # 1. Curva de Fluxo (Tensão vs Taxa)
        f1 = reologia_plot.plotar_comparativo_multiplo(
            dados_analises, 'γ̇w (s⁻¹)', 'τw (Pa)', 
            "Comparativo: Curva de Fluxo", "Taxa de Cisalhamento (s⁻¹)", "Tensão de Cisalhamento (Pa)",
            pasta_saida, timestamp, show_plots=True, modelos_dict=modelos_dict
        )
        if f1: lista_imgs_geradas.append(os.path.basename(f1))
        
        # 2. Viscosidade (Visc vs Taxa)
        f2 = reologia_plot.plotar_comparativo_multiplo(
            dados_analises, 'γ̇w (s⁻¹)', 'η (Pa·s)', 
            "Comparativo: Viscosidade Real", "Taxa de Cisalhamento (s⁻¹)", "Viscosidade Real (Pa·s)",
            pasta_saida, timestamp, show_plots=True, modelos_dict=modelos_dict
        )
        if f2: lista_imgs_geradas.append(os.path.basename(f2))
        
        # 3. Determinação de n' (ln(tau) vs ln(gamma_ap))
        dados_n_prime = {}
        for nome, df in dados_analises.items():
            if 'γ̇aw (s⁻¹)' in df.columns and 'τw (Pa)' in df.columns:
                df_n = df.copy()
                valid = (df_n['γ̇aw (s⁻¹)'] > 0) & (df_n['τw (Pa)'] > 0)
                df_n = df_n[valid]
                if not df_n.empty:
                    df_n['ln_gamma_aw'] = np.log(df_n['γ̇aw (s⁻¹)'])
                    df_n['ln_tau_w'] = np.log(df_n['τw (Pa)'])
                    dados_n_prime[nome] = df_n
        
        if dados_n_prime:
            f3 = reologia_plot.plotar_comparativo_multiplo(
                dados_n_prime, 'ln_gamma_aw', 'ln_tau_w',
                "Comparativo: Determinação de n'", "ln(Taxa de Cisalhamento Aparente)", "ln(Tensão de Cisalhamento)",
                pasta_saida, timestamp, usar_log=False, show_plots=True
            )
            if f3: lista_imgs_geradas.append(os.path.basename(f3))
            
        # 4. Pressão vs Viscosidade
        dados_pressao = {}
        for nome, df in dados_analises.items():
            if 'P (bar)' in df.columns and 'η (Pa·s)' in df.columns:
                df_p = df.copy()
                df_p['P (Pa)'] = df_p['P (bar)'] * 1e5
                dados_pressao[nome] = df_p
                
        if dados_pressao:
            f4 = reologia_plot.plotar_comparativo_multiplo(
                dados_pressao, 'P (Pa)', 'η (Pa·s)',
                "Comparativo: Pressão vs Viscosidade", "Pressão (Pa)", "Viscosidade Real (Pa·s)",
                pasta_saida, timestamp, usar_log=False, show_plots=True
            )
            if f4: lista_imgs_geradas.append(os.path.basename(f4))

        # 2. Análise MAPE (Opcional)
        # Precisa capturar o DF de MAPE se gerado. A função analise_mape original não retornava o DF.
        # Vou modificar a chamada para ler o CSV gerado se existir, ou modificar a função analise_mape?
        # A função analise_mape salva um CSV. Posso ler esse CSV.
        analise_mape(dados_analises, pasta_saida, timestamp)
        
        df_mape = None
        csv_mape = os.path.join(pasta_saida, f"{timestamp}_analise_mape.csv")
        if os.path.exists(csv_mape):
            try: df_mape = pd.read_csv(csv_mape)
            except: pass
            
        # 3. Relatório Texto
        reologia_report.gerar_relatorio_comparativo(dados_analises, pasta_saida, timestamp)
        
        # 4. Relatório PDF Comparativo
        reologia_report_pdf.gerar_pdf_comparativo(pasta_saida, timestamp, dados_analises, lista_imgs_geradas, df_mape)
    
    print("\nProcesso concluído!")

if __name__ == "__main__":
    main()
