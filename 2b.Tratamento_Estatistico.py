# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
from scipy.stats import linregress
import glob
import json
import warnings

# Importa módulos do projeto
import utils_reologia
import reologia_io
import reologia_fitting
import reologia_plot

def processar_estatisticamente(caminho_csv, nome_base, output_folder):
    """Processa estatisticamente um arquivo CSV de resultados."""
    
    print(f"\nProcessando: {nome_base}")
    
    # 1. Carrega CSV
    df = reologia_io.carregar_csv_resultados(caminho_csv)
    if df is None: return
    
    # IMPORTANTE: Salva coluna de pressão ANTES de normalizar nomes
    pressao_original = None
    if 'Pressao (bar)' in df.columns:
        pressao_original = df['Pressao (bar)'].copy()
    
    # Normaliza nomes de colunas (lowercase)
    df.columns = [c.lower() for c in df.columns]
    
    # Mapeamento de colunas necessárias
    col_map = {
        'gamma_dot_w': ['taxa de cisalhamento corrigida (s-1)', 'gamma_dot_w (s-1)', 'γ̇w (s⁻¹)', 'taxa de cisalhamento corrigida'],
        'tau_w': ['tensao de cisalhamento na parede (pa)', 'tau_w (pa)', 'τw (pa)', 'tensao de cisalhamento (pa)'],
        'eta_true': ['viscosidade real (pa.s)', 'eta_true (pa.s)', 'η (pa·s)', 'viscosidade real'],
        'gamma_dot_aw': ['taxa de cisalhamento aparente (s-1)', 'gamma_dot_aw (s-1)', 'γ̇aw (s⁻¹)', 'taxa de cisalhamento aparente'],
        'eta_a': ['viscosidade aparente (pa.s)', 'eta_a (pa.s)', 'viscosidade aparente']
    }
    
    data = {}
    for key, candidates in col_map.items():
        found = False
        for cand in candidates:
            if cand.lower() in df.columns:
                data[key] = df[cand.lower()].values
                found = True
                break
        if not found:
            print(f"  AVISO: Coluna para '{key}' não encontrada. Tentando continuar...")
            data[key] = np.full(len(df), np.nan)

    # Adiciona pressão se existir
    if pressao_original is not None:
        data['pressao'] = pressao_original.values
    else:
        data['pressao'] = np.full(len(df), np.nan)

    # Cria DataFrame temporário para agrupamento
    df_temp = pd.DataFrame(data)
    
    # Remove linhas inválidas (NaN ou <= 0 para log)
    valid_mask = (df_temp['gamma_dot_w'] > 0) & (df_temp['tau_w'] > 0)
    df_temp = df_temp[valid_mask].copy()
    
    if df_temp.empty:
        print("  ERRO: Sem dados válidos para processamento estatístico.")
        return

    # Agrupamento por Taxa de Cisalhamento (usando log para agrupar valores próximos)
    # Arredonda log10 da taxa para 1 casa decimal para agrupar (tolerância robusta)
    df_temp['log_gd'] = np.round(np.log10(df_temp['gamma_dot_w']), 1)
    
    # Calcula médias e desvios padrão
    grouped = df_temp.groupby('log_gd')
    
    gamma_dot_w_mean = grouped['gamma_dot_w'].mean().values
    tau_w_mean = grouped['tau_w'].mean().values
    tau_w_std = grouped['tau_w'].std().values
    eta_true_mean = grouped['eta_true'].mean().values
    eta_true_std = grouped['eta_true'].std().values
    gamma_dot_aw_mean = grouped['gamma_dot_aw'].mean().values
    eta_a_mean = grouped['eta_a'].mean().values
    pressao_mean = grouped['pressao'].mean().values
    
    # Substitui NaNs no desvio padrão por 0 (caso de ponto único)
    tau_w_std = np.nan_to_num(tau_w_std)
    eta_true_std = np.nan_to_num(eta_true_std)

    # --- Carrega Geometria do Capilar (JSON) ---
    # Procura JSON recursivamente a partir da raiz do projeto
    project_root = os.path.dirname(os.path.abspath(__file__)) # Assume script na raiz ou próximo
    json_files = glob.glob(os.path.join(project_root, "**", "*.json"), recursive=True)
    
    D_cap_mm = 0.0
    L_cap_mm = 0.0
    
    # Tenta encontrar JSON correspondente ao nome_base ou pega o primeiro encontrado que tenha geometria
    # Estratégia simples: procurar JSON na mesma pasta do CSV primeiro
    csv_dir = os.path.dirname(caminho_csv)
    local_jsons = glob.glob(os.path.join(csv_dir, "*.json"))
    
    # Filtra arquivos de calibração para evitar carregar geometria errada (D=0)
    local_jsons = [f for f in local_jsons if "calibracao_" not in os.path.basename(f)]
    
    target_json = None
    # Prioriza arquivos que terminam com _parametros_modelos.json
    for f in local_jsons:
        if "_parametros_modelos.json" in f:
            target_json = f
            break
            
    if not target_json and local_jsons:
        target_json = local_jsons[0]
    elif not target_json and json_files:
        # Fallback global (mas evita calibração também)
        valid_global = [f for f in json_files if "calibracao_" not in os.path.basename(f)]
        if valid_global:
            target_json = valid_global[0]
        
    if target_json:
        try:
            with open(target_json, 'r', encoding='utf-8') as f:
                info = json.load(f)
                D_cap_mm = float(info.get('diametro_capilar_mm', 0))
                L_cap_mm = float(info.get('comprimento_capilar_mm', 0))
                print(f"  Geometria carregada de {os.path.basename(target_json)}: D={D_cap_mm}mm, L={L_cap_mm}mm")
        except Exception as e:
            print(f"  Erro ao ler JSON de geometria: {e}")

    # --- Ajuste de Modelos ---
    print("  Ajustando modelos reológicos às médias...")
    model_results, best_model_nome, _ = reologia_fitting.ajustar_modelos(gamma_dot_w_mean, tau_w_mean)
    
    # --- Cálculo de n' (Lei de Potência) ---
    # ln(tau) vs ln(gamma_ap)
    valid_n = (gamma_dot_aw_mean > 0) & (tau_w_mean > 0)
    if np.sum(valid_n) > 1:
        log_g_aw = np.log(gamma_dot_aw_mean[valid_n])
        log_t = np.log(tau_w_mean[valid_n])
        slope, intercept, _, _, _ = linregress(log_g_aw, log_t)
        n_prime = slope
        log_K_prime = intercept
    else:
        n_prime = 1.0
        log_K_prime = 0.0

    # --- Geração dos Gráficos ---
    timestamp = utils_reologia.gerar_timestamp()
    
    # Cria subpasta para os resultados deste ensaio específico
    pasta_resultados_ensaio = os.path.join(output_folder, f"{nome_base}_{timestamp}")
    if not os.path.exists(pasta_resultados_ensaio):
        os.makedirs(pasta_resultados_ensaio)
    
    print(f"  Gerando gráficos estatísticos em: {pasta_resultados_ensaio}")
    reologia_plot.gerar_graficos_finais(
        pasta_resultados_ensaio, timestamp,
        gamma_dot_aw_mean, tau_w_mean,
        gamma_dot_w_mean, eta_true_mean, eta_a_mean,
        n_prime, log_K_prime,
        model_results, best_model_nome,
        pressao_mean, D_cap_mm, L_cap_mm,
        False, False, False, # Flags de correções (já aplicadas ou irrelevantes aqui)
        only_show=False,
        std_tau_w=tau_w_std,
        std_eta=eta_true_std,
        show_plots=True
    )
    
    # Salva CSV estatístico
    df_stats = pd.DataFrame({
        'gamma_dot_w_mean': gamma_dot_w_mean,
        'tau_w_mean': tau_w_mean,
        'tau_w_std': tau_w_std,
        'eta_true_mean': eta_true_mean,
        'eta_true_std': eta_true_std,
        'gamma_dot_aw_mean': gamma_dot_aw_mean,
        'eta_a_mean': eta_a_mean,
        'pressao_mean_bar': pressao_mean
    })
    f_csv_stats = os.path.join(pasta_resultados_ensaio, f"{timestamp}_estatisticas_{nome_base}.csv")
    df_stats.to_csv(f_csv_stats, index=False)
    print(f"  Dados estatísticos salvos em: {os.path.basename(f_csv_stats)}")
    
    # --- NOVO: Salva Parâmetros dos Modelos em JSON ---
    if model_results and best_model_nome:
        json_params_name = os.path.join(pasta_resultados_ensaio, f"{timestamp}_estatisticas_{nome_base}_parametros_modelos.json")
        
        # Extrai parâmetros do melhor modelo
        best_model_data = model_results.get(best_model_nome, {})
        params_list = best_model_data.get('params', [])
        r2_value = best_model_data.get('R2', 0.0)
        
        dados_json_export = {
            "Melhor Modelo": best_model_nome,
            "R2": r2_value,
            "Parametros": params_list,
            "Modelos_Testados": model_results
        }
        
        try:
            with open(json_params_name, 'w', encoding='utf-8') as f:
                json.dump(dados_json_export, f, indent=4)
            print(f"  Parâmetros do modelo '{best_model_nome}' salvos em: {os.path.basename(json_params_name)}")
        except Exception as e:
            print(f"  ERRO ao salvar JSON de parâmetros: {e}")



def main():
    # Configuração
    input_folder = "resultados_csv" # Pasta onde script 2 salva
    output_folder = "resultados_estatisticos"
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    # Encontra arquivos CSV gerados pelo script 2
    # Padrão esperado: "*_resultados_finais.csv" ou "*_resultados_reologicos.csv"
    csv_files = glob.glob(os.path.join(input_folder, "*_resultados_reologicos.csv"))
    if not csv_files:
        csv_files = glob.glob(os.path.join(input_folder, "*_resultados_finais.csv"))
    
    if not csv_files:
        # Tenta procurar em qualquer subpasta ou na raiz se não achar
        csv_files = glob.glob("**/*_resultados_reologicos.csv", recursive=True)
        if not csv_files:
            csv_files = glob.glob("**/*_resultados_finais.csv", recursive=True)
        
    if not csv_files:
        print("Nenhum arquivo CSV de resultados encontrado. Execute o script 2 primeiro.")
        return
        
    # Ordena arquivos por data de modificação (mais recente primeiro)
    csv_files.sort(key=os.path.getmtime, reverse=True)
    
    print(f"\nEncontrados {len(csv_files)} arquivos de resultados:")
    for i, f in enumerate(csv_files):
        # Mostra pasta pai e nome do arquivo para facilitar identificação
        parent_folder = os.path.basename(os.path.dirname(f))
        filename = os.path.basename(f)
        print(f"  {i+1}: {parent_folder}/{filename}")
        
    print("\nOpções:")
    print("  0: Sair")
    print("  Digite o número do arquivo para processar")
    
    escolha = input("\nEscolha uma opção: ").strip().lower()
    
    if escolha == '0':
        return
    else:
        try:
            idx = int(escolha) - 1
            if 0 <= idx < len(csv_files):
                files_to_process = [csv_files[idx]]
            else:
                print("Opção inválida.")
                return
        except ValueError:
            print("Opção inválida.")
            return

    for csv_path in files_to_process:
        nome_base = os.path.splitext(os.path.basename(csv_path))[0].replace("_resultados_finais", "").replace("_resultados_reologicos", "")
        processar_estatisticamente(csv_path, nome_base, output_folder)

if __name__ == "__main__":
    main()
