# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# SCRIPT 0.LIMPEZA_JSON.PY
# Ferramenta para visualizar, excluir pontos e reordenar o JSON de testes brutos.
# -----------------------------------------------------------------------------

import os
import glob
import json
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO DE PASTAS ---
JSON_INPUT_DIR = "resultados_testes_reometro"

# --- FUNÇÕES AUXILIARES ---

def listar_arquivos_json_numerados(pasta_json):
    """Lista todos os arquivos .json em uma pasta para que o usuário possa escolher pelo número."""
    if not os.path.exists(pasta_json):
        print(f"AVISO: A pasta '{pasta_json}' não existe. Não foi possível listar arquivos JSON.")
        return []
    # Busca por arquivos JSON que não contenham o prefixo de edição
    arquivos = sorted([f for f in os.listdir(pasta_json) if f.endswith('.json') and not f.startswith('edit_') and os.path.isfile(os.path.join(pasta_json, f))])
    if not arquivos:
        print(f"Nenhum arquivo .json não editado encontrado na pasta '{pasta_json}'.")
    else:
        print(f"\nArquivos JSON disponíveis em '{pasta_json}':")
        for i, arq in enumerate(arquivos):
            print(f"  {i+1}: {arq}")
    return arquivos

def selecionar_arquivo_json(pasta_json):
    """Gerencia o menu para o usuário escolher um arquivo JSON da lista."""
    arquivos_disponiveis = listar_arquivos_json_numerados(pasta_json)
    if not arquivos_disponiveis:
        return None 
    while True:
        try:
            escolha_str = input("\nEscolha o NÚMERO do arquivo JSON a ser editado (ou '0' para sair): ").strip()
            if escolha_str == '0':
                return None
            
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_disponiveis):
                arquivo_selecionado = arquivos_disponiveis[escolha_num - 1]
                return os.path.join(pasta_json, arquivo_selecionado)
            else:
                print(f"ERRO: Escolha inválida. Digite um número entre 1 e {len(arquivos_disponiveis)}, ou '0'.")
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite um número ou '0'.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado na seleção: {e}")
            return None

def processar_limpeza():
    """Função principal de limpeza e reordenação."""
    caminho_arquivo_original = selecionar_arquivo_json(JSON_INPUT_DIR)
    
    if not caminho_arquivo_original:
        print("\nProcessamento cancelado.")
        return

    nome_arquivo_original = os.path.basename(caminho_arquivo_original)
    print(f"\nCarregando arquivo: {nome_arquivo_original}")

    # 1. Carregar o JSON
    try:
        with open(caminho_arquivo_original, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERRO: Arquivo não encontrado.")
        return
    except json.JSONDecodeError:
        print("ERRO: Falha ao decodificar o arquivo JSON. Verifique o formato.")
        return
    except Exception as e:
        print(f"ERRO ao carregar o arquivo: {e}")
        return

    testes_originais = data.get("testes", [])
    if not testes_originais:
        print("AVISO: O arquivo JSON não contém nenhum teste para editar.")
        return

    # 2. Exibir Tabela de Pontos para Edição
    pontos_para_tabela = []
    for teste in testes_originais:
        pontos_para_tabela.append({
            "Ponto No.": teste.get("ponto_n"),
            "Massa (g)": f"{teste.get('massa_g_registrada', 0.0):.3f}",
            "Duracao (s)": f"{teste.get('duracao_real_s', 0.0):.3f}",
            "Pressao Media (bar)": f"{teste.get('media_pressao_final_ponto_bar', 0.0):.3f}"
        })
    
    df_pontos = pd.DataFrame(pontos_para_tabela)
    
    print("\n" + "="*70)
    print("VISUALIZAÇÃO DOS PONTOS DISPONÍVEIS PARA EDIÇÃO")
    print("="*70)
    # Garante que a coluna de ponto_n esteja sempre visível e não truncada
    with pd.option_context('display.max_rows', None, 'display.width', 150):
        print(df_pontos.to_string(index=False))
    print("="*70)

    # 3. Solicitar Pontos a Excluir
    while True:
        pontos_str = input("\nDigite os NÚMEROS de 'Ponto No.' a EXCLUIR, separados por vírgula (ex: 4, 36). Pressione Enter para NÃO excluir nenhum: ").strip()
        
        if not pontos_str:
            indices_para_remover = set()
            print("Nenhum ponto será excluído.")
            break
            
        try:
            # Converte a entrada do usuário para um set de inteiros
            partes = pontos_str.replace(' ', '').split(',')
            indices_para_remover = set(int(p) for p in partes if p.isdigit())
            
            pontos_validos = set(t.get("ponto_n") for t in testes_originais)
            
            # Valida se todos os pontos a remover existem
            if not indices_para_remover.issubset(pontos_validos):
                pontos_invalidos = indices_para_remover.difference(pontos_validos)
                print(f"ERRO: Os seguintes números de ponto não existem: {list(pontos_invalidos)}. Tente novamente.")
                continue
            
            break
        except ValueError:
            print("ERRO: Entrada inválida. Use apenas números separados por vírgula.")
        except Exception as e:
            print(f"Ocorreu um erro: {e}")
            return

    # 4. Remover e Renumerar
    testes_limpos = []
    novo_indice = 1
    
    for teste in testes_originais:
        if teste.get("ponto_n") not in indices_para_remover:
            # Renumera o ponto
            teste["ponto_n"] = novo_indice
            testes_limpos.append(teste)
            novo_indice += 1

    pontos_removidos_count = len(testes_originais) - len(testes_limpos)
    print(f"\n--- Processamento Concluído ---")
    print(f"{pontos_removidos_count} ponto(s) removido(s) do total. {len(testes_limpos)} ponto(s) restante(s).")
    
    # 5. Atualizar o Objeto JSON e Salvar Novo Arquivo
    data["testes"] = testes_limpos
    
    caminho_saida = os.path.join(JSON_INPUT_DIR, f"edit_{nome_arquivo_original}")
    
    try:
        with open(caminho_saida, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"SUCESSO: Arquivo limpo e reordenado salvo em: {caminho_saida}")
        print("\nVocê deve usar este novo arquivo ('edit_...') nos scripts de análise (2.Analise_reologica.py e 2b.Tratamento_Estatistico.py).")
    except Exception as e:
        print(f"ERRO ao salvar o novo arquivo JSON: {e}")

# --- Bloco Principal ---
if __name__ == "__main__":
    if not os.path.exists(JSON_INPUT_DIR):
        os.makedirs(JSON_INPUT_DIR)
        print(f"A pasta de entrada '{JSON_INPUT_DIR}' foi criada. Por favor, coloque os arquivos JSON de ensaio aqui.")
    
    processar_limpeza()
    print("\n--- FIM DO SCRIPT ---")