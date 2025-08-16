# -----------------------------------------------------------------------------
# SCRIPT PARA PROCESSAMENTO INTERATIVO DE DADOS REOLÓGICOS
# -----------------------------------------------------------------------------
# Esta ferramenta permite selecionar um arquivo de dados,
# visualizar os pontos e remover outliers manualmente antes de salvar.
# -----------------------------------------------------------------------------

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

# --- Configurações ---
# Pasta onde os arquivos .txt de origem estão localizados.
PASTA_DADOS_BRUTOS = "dados_reometro_rotacional"
# Pasta onde os resultados processados (.csv) serão salvos.
PASTA_RESULTADOS = "resultados_processados_interativo"

def selecionar_arquivo_dados_brutos():
    """Permite ao usuário selecionar um arquivo de texto para processar."""
    print("-" * 60)
    print(f"Passo 1: Selecione o arquivo de dados da pasta '{PASTA_DADOS_BRUTOS}'")
    print("-" * 60)
    
    if not os.path.isdir(PASTA_DADOS_BRUTOS):
        print(f"ERRO: A pasta '{PASTA_DADOS_BRUTOS}' não foi encontrada.")
        return None, None

    caminho_busca = os.path.join(PASTA_DADOS_BRUTOS, '*.txt')
    arquivos_txt = glob.glob(caminho_busca)
    
    if not arquivos_txt:
        print(f"ERRO: Nenhum arquivo .txt encontrado na pasta '{PASTA_DADOS_BRUTOS}'.")
        return None, None
    
    print("Arquivos .txt disponíveis:")
    for i, arq in enumerate(arquivos_txt):
        print(f"  {i+1}: {os.path.basename(arq)}")
        
    while True:
        try:
            escolha_str = input("\nDigite o NÚMERO do arquivo que deseja processar (ou '0' para sair): ")
            if escolha_str == '0':
                return None, None
            escolha = int(escolha_str)
            if 1 <= escolha <= len(arquivos_txt):
                caminho_arquivo = arquivos_txt[escolha - 1]
                nome_base = os.path.basename(caminho_arquivo).replace('.txt', '')
                return caminho_arquivo, nome_base
            else:
                print("ERRO: Escolha inválida.")
        except ValueError:
            print("ERRO: Entrada inválida. Digite um número.")

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

    df_final_csv = pd.DataFrame({
        'Taxa de Cisalhamento (s-1)': df_processado['Shear Rate'],
        'Tensao de Cisalhamento (Pa)': df_processado['Shear Stress'],
        'Viscosidade (Pa.s)': df_processado['Viscosity']
    })
    
    caminho_csv = os.path.join(pasta_destino, f"{nome_base_saida}_processado.csv")
    
    try:
        df_final_csv.to_csv(caminho_csv, sep=';', decimal=',', index=False, float_format='%.4f')
        print(f"\n-> Arquivo de resultado salvo com sucesso em: {caminho_csv}")
    except Exception as e:
        print(f"-> ERRO ao salvar o arquivo CSV: {e}")

# --- Bloco Principal ---
if __name__ == "__main__":
    while True:
        caminho_arquivo, nome_base = selecionar_arquivo_dados_brutos()
        
        if not caminho_arquivo:
            break # Sai do loop se o usuário digitar 0
            
        df_bruto = processar_dados_iniciais(caminho_arquivo)
        
        if df_bruto is not None:
            df_filtrado = filtrar_dados_interativamente(df_bruto)
            
            if df_filtrado is not None and not df_filtrado.empty:
                confirm = input("\nDeseja salvar os dados filtrados? (s/n): ").lower()
                if confirm == 's':
                    salvar_csv_final(df_filtrado, nome_base, PASTA_RESULTADOS)
                else:
                    print("Operação cancelada. Nenhum arquivo foi salvo.")
        
        print("\n" + "="*60)

    print("\n--- FIM DO SCRIPT ---")
