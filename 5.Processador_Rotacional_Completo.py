# -----------------------------------------------------------------------------
# SCRIPT PARA PROCESSAMENTO INTERATIVO DE DADOS REOLÓGICOS
# -----------------------------------------------------------------------------
# Esta ferramenta permite selecionar um arquivo de dados,
# visualizar os pontos e remover outliers manualmente antes de salvar.
# AGORA COM SUPORTE A UNIFICAÇÃO E TRATAMENTO ESTATÍSTICO DE MÚLTIPLOS ARQUIVOS.
# -----------------------------------------------------------------------------

import os
import glob
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import utils_reologia
import reologia_fitting
from modelos_reologicos import MODELS

# --- Configurações ---
# Pasta onde os arquivos .txt de origem estão localizados.
PASTA_DADOS_BRUTOS = "dados_reometro_rotacional"
# Pasta onde os resultados processados (.csv) serão salvos.
PASTA_RESULTADOS = utils_reologia.CONSTANTS['CAMINHO_BASE_ROTACIONAL']

def processar_dados_iniciais(caminho_arquivo):
    """Lê e faz a limpeza inicial dos dados do arquivo de texto."""
    print(f"\nProcessando arquivo: {os.path.basename(caminho_arquivo)}...")
    try:
        col_names = ['Point No.', 'Shear Rate', 'Shear Stress', 'Viscosity', 'N1', 'N1_coeff', 'N1_Lodge', 'Torque', 'Status']
        df = pd.read_csv(caminho_arquivo, sep='\t', decimal=',', on_bad_lines='warn', 
                         encoding='latin-1', skiprows=3, header=None, names=col_names)
        
        colunas_necessarias = {'Shear Rate', 'Shear Stress'}
        if not colunas_necessarias.issubset(df.columns):
            print("ERRO: O arquivo não contém as colunas 'Shear Rate' e 'Shear Stress'.")
            return None
        
        for col in colunas_necessarias:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=colunas_necessarias, inplace=True)
        df = df[(df['Shear Stress'] > 0) & (df['Shear Rate'] > 0)].copy()
        
        if df.empty:
            print("ERRO: Nenhum dado válido encontrado após a limpeza.")
            return None
            
        df['Viscosity'] = df['Shear Stress'] / df['Shear Rate']
        print(f"-> Dados processados com sucesso. Encontrados {len(df)} pontos válidos.")
        return df[['Shear Rate', 'Shear Stress', 'Viscosity']].reset_index(drop=True)
    except Exception as e:
        print(f"Ocorreu um erro ao processar o arquivo: {e}")
        return None

def filtrar_dados_interativamente(df):
    """Mostra os dados ao usuário e permite que ele selecione os pontos a REMOVER."""
    if df is None:
        return None

    print("\n" + "-"*60)
    print("Passo 2: Filtragem de Dados Manual")
    print("-" * 60)
    
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(df['Shear Rate'], df['Shear Stress'], 'o-', label='Dados Válidos', markersize=5, markerfacecolor='red')
    for i, row in df.iterrows():
        ax.text(row['Shear Rate'], row['Shear Stress'], f' {i}', verticalalignment='bottom', fontsize=9, color='blue')
        
    ax.set_xlabel('Taxa de Cisalhamento (s⁻¹)')
    ax.set_ylabel('Tensão de Cisalhamento (Pa)')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_title('Visualização para Filtragem - Feche esta janela para continuar')
    ax.legend()
    ax.grid(True, which="both", ls="--")
    
    print("Abaixo estão os pontos de dados. Observe o gráfico que abriu.")
    with pd.option_context('display.max_rows', None):
        print(df.to_string())
    
    plt.show()

    while True:
        try:
            pontos_str = input("\nDigite os NÚMEROS dos pontos a REMOVER, separados por vírgula (ex: 0, 1, 15). Pressione Enter para não remover nenhum: ").strip()
            
            if not pontos_str:
                print("Nenhum ponto removido.")
                return df

            indices_para_remover = set()
            partes = pontos_str.replace(' ', '').split(',')
            for parte in partes:
                if '-' in parte:
                    inicio, fim = map(int, parte.split('-'))
                    indices_para_remover.update(range(inicio, fim + 1))
                elif parte:
                    indices_para_remover.add(int(parte))
            
            indices_validos = [idx for idx in indices_para_remover if idx in df.index]
            df_filtrado = df.drop(indices_validos).reset_index(drop=True)
            
            print(f"\nDados filtrados. {len(df_filtrado)} pontos mantidos.")
            return df_filtrado

        except (ValueError, KeyError):
            print("ERRO: Entrada inválida. Verifique os números dos pontos e o formato (ex: 0,1,18-22).")

def salvar_csv_final(df_processado, nome_base_saida, pasta_destino):
    """Salva o DataFrame processado em um arquivo CSV."""
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)

    # Prepara colunas para salvar
    data_to_save = {
        'Taxa de Cisalhamento (s-1)': df_processado['Shear Rate'],
        'Tensao de Cisalhamento (Pa)': df_processado['Shear Stress'],
        'Viscosity (Pa.s)': df_processado['Viscosity']
    }
    
    # Se tiver desvio padrão (modo estatístico), adiciona
    if 'Viscosity_std' in df_processado.columns:
        data_to_save['Viscosity_std (Pa.s)'] = df_processado['Viscosity_std']
        data_to_save['Tensao_std (Pa)'] = df_processado['Shear Stress_std']

    df_final_csv = pd.DataFrame(data_to_save)
    
    # Garante nomes corretos para o Script 4
    df_final_csv.rename(columns={'Viscosity (Pa.s)': 'Viscosidade (Pa.s)'}, inplace=True)
    
    caminho_csv = os.path.join(pasta_destino, f"{nome_base_saida}_processado.csv")
    
    try:
        df_final_csv.to_csv(caminho_csv, sep=';', decimal=',', index=False, float_format='%.4f')
        print(f"\n-> Arquivo de resultado salvo com sucesso em: {caminho_csv}")
    except Exception as e:
        print(f"-> ERRO ao salvar o arquivo CSV: {e}")

def salvar_json_parametros(nome_base_saida, pasta_destino, nome_modelo, params, r2=None):
    """Salva os parâmetros do modelo em JSON para uso no Script 3."""
    if not nome_modelo or params is None:
        return

    caminho_json = os.path.join(pasta_destino, f"{nome_base_saida}_parametros_modelos.json")
    
    # Estrutura compatível com o esperado pelos outros scripts
    dados_json = {
        "Melhor Modelo": nome_modelo,
        "R2": r2 if r2 else 0.0,
        "Parametros": list(params), # Converte numpy array para lista
        "Modelos_Testados": {
            nome_modelo: {
                "params": list(params),
                "R2": r2 if r2 else 0.0
            }
        }
    }
    
    try:
        with open(caminho_json, 'w', encoding='utf-8') as f:
            json.dump(dados_json, f, indent=4)
        print(f"-> Parâmetros do modelo salvos em: {caminho_json}")
    except Exception as e:
        print(f"-> ERRO ao salvar JSON de parâmetros: {e}")

# --- Novas Funções para Modo Múltiplos Arquivos ---

def filtrar_por_modelo(df_total, limite_erro=0.50):
    """
    Ajusta modelos aos dados brutos e remove pontos que desviam muito do melhor modelo.
    Retorna: df_filtrado, best_model_nome, model_params
    """
    print("\n  --- Filtragem Baseada em Modelo ---")
    print("  Ajustando modelos para identificar tendência global...")
    
    # Ajusta modelos
    gamma = df_total['Shear Rate'].values
    tau = df_total['Shear Stress'].values
    
    model_results, best_model_nome, _ = reologia_fitting.ajustar_modelos(gamma, tau)
    
    if not best_model_nome:
        print("  Aviso: Não foi possível ajustar modelos. Pulando filtragem por modelo.")
        return df_total, None, None
        
    print(f"  Melhor modelo identificado: {best_model_nome} (R2={model_results[best_model_nome]['R2']:.4f})")
    
    # Calcula previsão do modelo
    func_modelo = MODELS[best_model_nome][0]
    params = model_results[best_model_nome]['params']
    tau_pred = func_modelo(gamma, *params)
    
    # Calcula erro relativo: |(Medido - Modelo) / Modelo|
    # Evita divisão por zero
    tau_pred_safe = np.where(tau_pred == 0, 1e-9, tau_pred)
    erro_relativo = np.abs((tau - tau_pred) / tau_pred_safe)
    
    # Filtra
    mask_valid = erro_relativo <= limite_erro
    df_filtrado = df_total[mask_valid].copy()
    
    removidos = len(df_total) - len(df_filtrado)
    print(f"  Pontos removidos por desvio excessivo (> {limite_erro*100:.0f}%): {removidos} de {len(df_total)}")
    
    return df_filtrado, best_model_nome, params

def agrupar_e_tratar_estatisticamente(df_total):
    """
    Agrupa dados por taxa de cisalhamento, remove outliers e calcula médias.
    """
    print("  Agrupando dados por taxa de cisalhamento (log)...")
    # Cria coluna de log para agrupamento (binning)
    # Arredonda para 1 casa decimal no log para agrupar taxas próximas
    df_total['log_shear'] = np.round(np.log10(df_total['Shear Rate']), 1)
    
    grupos = df_total.groupby('log_shear')
    
    dados_limpos = []
    
    for log_s, grupo in grupos:
        grupo_valido = grupo.copy()
        
        # 1. Remoção Inicial por MAD (Robustez)
        if len(grupo_valido) >= 3:
            mediana_visc = grupo_valido['Viscosity'].median()
            mad_visc = np.median(np.abs(grupo_valido['Viscosity'] - mediana_visc))
            if mad_visc > 1e-9:
                limite = 2.5 * mad_visc
                mask = np.abs(grupo_valido['Viscosity'] - mediana_visc) <= limite
                grupo_valido = grupo_valido[mask]

        # 2. Refinamento por Coeficiente de Variação (CV)
        # Se o desvio padrão for > 20% da média, remove o ponto mais distante da mediana
        # Repete até CV <= 20% ou sobrar apenas 1 ponto
        MAX_CV = 0.20 # 20%
        
        while len(grupo_valido) > 1:
            media = grupo_valido['Viscosity'].mean()
            std = grupo_valido['Viscosity'].std()
            
            if media == 0: break
            cv = std / media
            
            if cv <= MAX_CV:
                break
            
            # Remove o ponto mais distante da mediana atual
            mediana = grupo_valido['Viscosity'].median()
            distancias = np.abs(grupo_valido['Viscosity'] - mediana)
            idx_rem = distancias.idxmax()
            grupo_valido = grupo_valido.drop(idx_rem)
            
        dados_limpos.append(grupo_valido)
        
    df_limpo = pd.concat(dados_limpos)
    
    # Recalcula médias finais por grupo
    grupos_finais = df_limpo.groupby('log_shear')
    
    resumo = grupos_finais.agg({
        'Shear Rate': ['mean', 'std'],
        'Shear Stress': ['mean', 'std'],
        'Viscosity': ['mean', 'std']
    })
    
    # Aplaina colunas
    resumo.columns = ['_'.join(col).strip() for col in resumo.columns.values]
    resumo = resumo.reset_index()
    
    # Renomeia para padrão interno
    df_final = pd.DataFrame({
        'Shear Rate': resumo['Shear Rate_mean'],
        'Shear Rate_std': resumo['Shear Rate_std'],
        'Shear Stress': resumo['Shear Stress_mean'],
        'Shear Stress_std': resumo['Shear Stress_std'],
        'Viscosity': resumo['Viscosity_mean'],
        'Viscosity_std': resumo['Viscosity_std']
    })
    
    # Ordenação CRÍTICA por Taxa de Cisalhamento
    df_final.sort_values('Shear Rate', inplace=True)
    
    return df_final, df_limpo

def modo_arquivo_unico():
    while True:
        caminho_arquivo = utils_reologia.selecionar_arquivo(PASTA_DADOS_BRUTOS, "*.txt", "Selecione o arquivo de dados brutos", ".txt")
        if not caminho_arquivo: break 
            
        nome_base = os.path.basename(caminho_arquivo).replace('.txt', '')
        df_bruto = processar_dados_iniciais(caminho_arquivo)
        
        if df_bruto is not None:
            df_filtrado = filtrar_dados_interativamente(df_bruto)
            if df_filtrado is not None and not df_filtrado.empty:
                confirm = input("\nDeseja salvar os dados filtrados? (s/n): ").lower()
                if confirm == 's':
                    salvar_csv_final(df_filtrado, nome_base, PASTA_RESULTADOS)
                else:
                    print("Operação cancelada.")
        
        print("\n" + "="*60)
        if input("Processar outro arquivo? (s/n): ").lower() != 's': break

def modo_multiplos_arquivos():
    print("\n--- MODO UNIFICAÇÃO DE MÚLTIPLOS ARQUIVOS ---")
    
    # Lista todos os arquivos disponíveis
    arquivos_disponiveis = glob.glob(os.path.join(PASTA_DADOS_BRUTOS, "*.txt"))
    # Ordena por nome ou data? Vamos por nome para facilitar
    arquivos_disponiveis.sort()
    
    if not arquivos_disponiveis:
        print(f"Nenhum arquivo .txt encontrado na pasta '{PASTA_DADOS_BRUTOS}'.")
        return

    print(f"Arquivos disponíveis em '{PASTA_DADOS_BRUTOS}':")
    for i, arq in enumerate(arquivos_disponiveis):
        print(f"  {i+1}: {os.path.basename(arq)}")
        
    print("\nDigite os números dos arquivos para unificar, separados por vírgula (ex: 1, 3, 5).")
    print("Ou '0' para cancelar.")
    
    entrada = input("Escolha: ").strip()
    
    if entrada == '0' or not entrada:
        print("Seleção cancelada.")
        return

    arquivos_selecionados = []
    try:
        indices = [int(x.strip()) - 1 for x in entrada.split(',') if x.strip().isdigit()]
        for idx in indices:
            if 0 <= idx < len(arquivos_disponiveis):
                arquivos_selecionados.append(arquivos_disponiveis[idx])
            else:
                print(f"Aviso: Índice {idx+1} inválido ignorado.")
    except ValueError:
        print("Entrada inválida.")
        return
        
    if not arquivos_selecionados:
        print("Nenhum arquivo válido selecionado.")
        return
        
    print(f"\nSelecionados {len(arquivos_selecionados)} arquivos:")
    for f in arquivos_selecionados:
        print(f" - {os.path.basename(f)}")
        
    print(f"\nIniciando processamento...")
    dfs = []
    for arq in arquivos_selecionados:
        df = processar_dados_iniciais(arq)
        if df is not None:
            dfs.append(df)
            
    if not dfs:
        print("Nenhum dado válido extraído.")
        return
        
    df_total = pd.concat(dfs, ignore_index=True)
    print(f"\nTotal de pontos combinados: {len(df_total)}")
    
    # 1. Filtragem por Modelo (NOVO)
    df_total, best_model, best_params = filtrar_por_modelo(df_total)
    
    # 2. Tratamento Estatístico (Agrupamento e Limpeza Fina)
    df_final, df_limpo = agrupar_e_tratar_estatisticamente(df_total)
    
    print(f"Pontos após limpeza de outliers: {len(df_limpo)}")
    print(f"Pontos na curva média final: {len(df_final)}")
    
    # Visualização
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plota pontos brutos (limpos) ao fundo
    ax.scatter(df_limpo['Shear Rate'], df_limpo['Viscosity'], color='gray', alpha=0.3, label='Pontos Individuais (Limpos)', s=10)
    
    # Plota média com erro
    ax.errorbar(df_final['Shear Rate'], df_final['Viscosity'], yerr=df_final['Viscosity_std'], 
                fmt='o-', color='blue', label='Média Estatística', capsize=5)
    
    # Plota Curva do Modelo (Se disponível)
    if best_model and best_params is not None:
        func_modelo = MODELS[best_model][0]
        # Gera pontos suaves para a curva
        gamma_smooth = np.logspace(np.log10(df_final['Shear Rate'].min()), np.log10(df_final['Shear Rate'].max()), 100)
        tau_smooth = func_modelo(gamma_smooth, *best_params)
        eta_smooth = tau_smooth / gamma_smooth
        
        ax.plot(gamma_smooth, eta_smooth, 'r--', linewidth=2, label=f'Modelo: {best_model}')
    
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_xlabel('Taxa de Cisalhamento (s⁻¹)')
    ax.set_ylabel('Viscosidade (Pa·s)')
    ax.set_title('Curva Unificada: Média Estatística + Modelo')
    ax.legend()
    ax.grid(True, which="both", ls="--")
    plt.show()
    
    # Salvar
    nome_sugerido = f"Unificado_{len(arquivos_selecionados)}arquivos"
    nome_saida = input(f"\nNome para salvar o arquivo unificado (Enter='{nome_sugerido}'): ").strip()
    if not nome_saida: nome_saida = nome_sugerido
    
    salvar_csv_final(df_final, nome_saida, PASTA_RESULTADOS)
    
    # Salva JSON do modelo
    if best_model:
        salvar_json_parametros(nome_saida, PASTA_RESULTADOS, best_model, best_params)


def main():
    utils_reologia.setup_graficos()
    
    if not os.path.exists(PASTA_DADOS_BRUTOS):
        os.makedirs(PASTA_DADOS_BRUTOS)
        
    while True:
        print("\n=== PROCESSADOR REÔMETRO ROTACIONAL ===")
        print("1. Processar Arquivo Único (Limpeza Manual)")
        print("2. Unificar e Tratar Estatisticamente Múltiplos Arquivos")
        print("0. Sair")
        
        opcao = input("Escolha: ").strip()
        
        if opcao == '1':
            modo_arquivo_unico()
        elif opcao == '2':
            modo_multiplos_arquivos()
        elif opcao == '0':
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    main()
