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

# --- CONFIGURAÇÃO DE PASTAS ---
INPUT_BASE_FOLDER = utils_reologia.CONSTANTS['INPUT_BASE_FOLDER']
# Pasta correta para salvar comparativos
OUTPUT_FOLDER = utils_reologia.CONSTANTS.get('CAMINHO_BASE_COMPARATIVOS', "comparativo_analises")

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
                    
                    # Carrega e processa
                    df = reologia_io.carregar_csv_resultados(caminho_csv)
                    if df is not None:
                        df.columns = [c.lower() for c in df.columns]
                        
                        # Mapeamento Estendido (incluindo Rotacional)
                        mapa_colunas = {
                            # Real / Corrigido
                            'taxa de cisalhamento corrigida (s-1)': 'γ̇w (s⁻¹)',
                            'tensao de cisalhamento (pa)': 'τw (Pa)',
                            'viscosidade real (pa.s)': 'η (Pa·s)',
                            'gamma_dot_w_mean': 'γ̇w (s⁻¹)',
                            'tau_w_mean': 'τw (Pa)',
                            'eta_true_mean': 'η (Pa·s)',
                            'γ̇w (s⁻¹)': 'γ̇w (s⁻¹)',
                            'τw (pa)': 'τw (Pa)',
                            'η (pa·s)': 'η (Pa·s)',
                            
                            # Rotacional (Script 5)
                            'taxa de cisalhamento (s-1)': 'γ̇w (s⁻¹)',
                            'tensao de cisalhamento (pa)': 'τw (Pa)',
                            'viscosidade (pa.s)': 'η (Pa·s)',
                            # Para n', usamos a taxa real como aparente (já que não há correção de Rabinowitsch para rotacional da mesma forma)
                            # Isso permite que o gráfico de n' seja gerado
                            'taxa de cisalhamento (s-1)': 'γ̇aw (s⁻¹)', 
                            
                            # Aparente (para n')
                            'taxa de cisalhamento aparente (s-1)': 'γ̇aw (s⁻¹)',
                            'viscosidade aparente (pa.s)': 'η_a (Pa·s)',
                            'gamma_dot_aw_mean': 'γ̇aw (s⁻¹)',
                            'eta_a_mean': 'η_a (Pa·s)',
                            
                            # Pressão (para P vs Eta)
                            'pressao (bar)': 'P (bar)',
                            'pressao_mean_bar': 'P (bar)',
                            'p_ext(bar)': 'P (bar)'
                        }
                        df.rename(columns=mapa_colunas, inplace=True)
                        
                        # CORREÇÃO PÓS-RENAME:
                        # Se for rotacional, 'taxa de cisalhamento (s-1)' foi renomeada para 'γ̇aw (s⁻¹)' (última chave vence no dict se duplicada?)
                        # Não, dict não permite chaves duplicadas. A definição acima sobrescreve.
                        # Precisamos garantir que tenhamos AMBAS: γ̇w (s⁻¹) e γ̇aw (s⁻¹)
                        
                        # Recarrega colunas originais para garantir
                        cols_orig = [c.lower() for c in reologia_io.carregar_csv_resultados(caminho_csv).columns]
                        
                        # Se for arquivo do Script 5
                        if 'taxa de cisalhamento (s-1)' in cols_orig:
                            df['γ̇w (s⁻¹)'] = df['γ̇aw (s⁻¹)'] # Duplica para ter as duas
                        
                        # Guarda caminho original para referência futura (se precisar)
                        df.attrs['path_source'] = caminho_csv
                        
                        if 'γ̇w (s⁻¹)' in df.columns and 'τw (Pa)' in df.columns:
                            dados_analises[nome_legenda] = df
                            print(f"  '{nome_legenda}' adicionado.")
                            
                            # Tenta carregar modelo associado (JSON ou CSV)
                            pasta_arquivo = os.path.dirname(caminho_csv)
                            nome_base = os.path.splitext(os.path.basename(caminho_csv))[0]
                            
                            # 1. Tenta JSON (Script 5 e Script 2B)
                            possiveis_jsons = [
                                # Script 5 (Rotacional)
                                os.path.join(pasta_arquivo, f"{nome_base}_parametros_modelos.json"),
                                os.path.join(pasta_arquivo, f"{nome_base.replace('_processado', '')}_parametros_modelos.json"),
                                # Script 2B (Estatísticas)
                                os.path.join(pasta_arquivo, f"{nome_base}_parametros_modelos.json"),
                                # Padrão com "_estatisticas_" no meio
                                os.path.join(pasta_arquivo, f"{nome_base.replace('_estatisticas_', '_estatisticas_X_')}_parametros_modelos.json".replace('_X_', '_'))
                            ]
                            
                            json_carregado = False
                            for json_path in possiveis_jsons:
                                if os.path.exists(json_path):
                                    try:
                                        with open(json_path, 'r', encoding='utf-8') as f:
                                            dados_json = json.load(f)
                                            if "Melhor Modelo" in dados_json and "Parametros" in dados_json:
                                                modelos_dict[nome_legenda] = dados_json
                                                print(f"    -> Modelo (JSON) '{dados_json['Melhor Modelo']}' carregado.")
                                                json_carregado = True
                                                break
                                    except Exception as e:
                                        print(f"    -> Erro ao ler JSON: {e}")
                            
                            # 2. Tenta CSV (Script 2) se JSON não encontrado
                            if not json_carregado:
                                possiveis_csvs_modelo = [
                                    os.path.join(pasta_arquivo, f"{nome_base}_resumo_melhor_modelo.csv"),
                                    os.path.join(pasta_arquivo, f"{nome_base.replace('_resultados_reologicos', '')}_resumo_melhor_modelo.csv")
                                ]
                                
                                for csv_model_path in possiveis_csvs_modelo:
                                    if os.path.exists(csv_model_path):
                                        try:
                                            df_mod = pd.read_csv(csv_model_path, sep=';', encoding='latin-1')
                                            if not df_mod.empty:
                                                # Extrai nome do modelo
                                                row_model = df_mod[df_mod.iloc[:, 0].astype(str).str.contains("Modelo Reológico", case=False, na=False)]
                                                if not row_model.empty:
                                                    nome_modelo = row_model.iloc[0, 1]
                                                    
                                                    # Extrai R2
                                                    r2 = 0.0
                                                    row_r2 = df_mod[df_mod.iloc[:, 0].astype(str).str.contains("R²", case=False, na=False)]
                                                    if not row_r2.empty:
                                                        try: r2 = float(row_r2.iloc[0, 1].replace(',', '.'))
                                                        except: pass
                                                    
                                                    # Extrai Parâmetros
                                                    params = []
                                                    # Mapeia ordem dos parâmetros conforme modelos_reologicos.py
                                                    from modelos_reologicos import MODELS
                                                    if nome_modelo in MODELS:
                                                        param_names_expected = MODELS[nome_modelo][1] # ex: ["tau0", "K", "n"]
                                                        
                                                        for p_name in param_names_expected:
                                                            # Busca linha que contém o nome do parâmetro (simplificado)
                                                            # Mapeamento de busca
                                                            search_term = p_name
                                                            if p_name == "tau0": search_term = "τ₀"
                                                            elif p_name == "eta": search_term = "η"
                                                            elif p_name == "eta_p": search_term = "η_p"
                                                            elif p_name == "eta_c": search_term = "η_c"
                                                            
                                                            # Busca parcial
                                                            row_p = df_mod[df_mod.iloc[:, 0].astype(str).str.contains(search_term, regex=False, na=False)]
                                                            # Se não achar, tenta busca genérica pelo nome da variável
                                                            if row_p.empty:
                                                                 row_p = df_mod[df_mod.iloc[:, 0].astype(str).str.contains(p_name, case=False, na=False)]
                                                            
                                                            if not row_p.empty:
                                                                val_str = str(row_p.iloc[0, 1]).replace(',', '.')
                                                                try: params.append(float(val_str))
                                                                except: params.append(0.0)
                                                            else:
                                                                params.append(0.0) # Valor default se não achar
                                                        
                                                        modelos_dict[nome_legenda] = {
                                                            "Melhor Modelo": nome_modelo,
                                                            "R2": r2,
                                                            "Parametros": params
                                                        }
                                                        print(f"    -> Modelo (CSV) '{nome_modelo}' carregado.")
                                                        break
                                        except Exception as e:
                                            print(f"    -> Erro ao ler CSV de modelo: {e}")

                        else:
                            print("  ERRO: Colunas essenciais não encontradas.")

            
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
    
    # 1. Curva de Fluxo (Tensão vs Taxa)
    reologia_plot.plotar_comparativo_multiplo(
        dados_analises, 'γ̇w (s⁻¹)', 'τw (Pa)', 
        "Comparativo: Curva de Fluxo", "Taxa de Cisalhamento (s⁻¹)", "Tensão de Cisalhamento (Pa)",
        pasta_saida, timestamp, show_plots=True, modelos_dict=modelos_dict
    )
    
    # 2. Viscosidade (Visc vs Taxa)
    reologia_plot.plotar_comparativo_multiplo(
        dados_analises, 'γ̇w (s⁻¹)', 'η (Pa·s)', 
        "Comparativo: Viscosidade Real", "Taxa de Cisalhamento (s⁻¹)", "Viscosidade Real (Pa·s)",
        pasta_saida, timestamp, show_plots=True, modelos_dict=modelos_dict
    )
    
    # 3. Determinação de n' (ln(tau) vs ln(gamma_ap)) - NOVO
    # Precisa criar colunas de log temporárias ou passar log=False para o plotador e passar os dados já logaritimizados?
    # O plotador 'plotar_comparativo_multiplo' plota X vs Y. Se passarmos log(X) e log(Y), ele plota.
    # Mas ele tem 'usar_log=True' que seta a escala do eixo para log.
    # Para n', queremos eixos lineares mas com valores logarítmicos, OU eixos log-log dos valores originais?
    # O gráfico de n' original é linear nos eixos, mas os dados são log.
    # Vamos criar colunas ln temporárias nos dataframes.
    
    dados_n_prime = {}
    for nome, df in dados_analises.items():
        if 'γ̇aw (s⁻¹)' in df.columns and 'τw (Pa)' in df.columns:
            df_n = df.copy()
            # Filtra valores válidos para log
            valid = (df_n['γ̇aw (s⁻¹)'] > 0) & (df_n['τw (Pa)'] > 0)
            df_n = df_n[valid]
            if not df_n.empty:
                df_n['ln_gamma_aw'] = np.log(df_n['γ̇aw (s⁻¹)'])
                df_n['ln_tau_w'] = np.log(df_n['τw (Pa)'])
                dados_n_prime[nome] = df_n
    
    if dados_n_prime:
        reologia_plot.plotar_comparativo_multiplo(
            dados_n_prime, 'ln_gamma_aw', 'ln_tau_w',
            "Comparativo: Determinação de n'", "ln(Taxa de Cisalhamento Aparente)", "ln(Tensão de Cisalhamento)",
            pasta_saida, timestamp, usar_log=False, show_plots=True # Eixos lineares pois os dados já são log
        )
        
    # 4. Pressão vs Viscosidade (NOVO)
    dados_pressao = {}
    for nome, df in dados_analises.items():
        if 'P (bar)' in df.columns and 'η (Pa·s)' in df.columns:
            df_p = df.copy()
            df_p['P (Pa)'] = df_p['P (bar)'] * 1e5
            dados_pressao[nome] = df_p
            
    if dados_pressao:
        reologia_plot.plotar_comparativo_multiplo(
            dados_pressao, 'P (Pa)', 'η (Pa·s)',
            "Comparativo: Pressão vs Viscosidade", "Pressão (Pa)", "Viscosidade Real (Pa·s)",
            pasta_saida, timestamp, usar_log=False, show_plots=True # Geralmente linear ou log? Script 2 usa linear.
        )

    # 2. Análise MAPE (Opcional)
    analise_mape(dados_analises, pasta_saida, timestamp)
    
    # 3. Relatório Texto
    reologia_report.gerar_relatorio_comparativo(dados_analises, pasta_saida, timestamp)
    
    print("\nProcesso concluído!")

if __name__ == "__main__":
    main()
