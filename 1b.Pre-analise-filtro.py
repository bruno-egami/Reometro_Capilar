# -*- coding: utf-8 -*-
"""
SCRIPT PARA PRÉ-ANÁLISE E FILTRAGEM DE DADOS JSON (Formato NOVO - 2 Sensores)
VERSÃO 3.0
Autor: Bruno Egami (Modificado por Gemini)
Data: 04/11/2025

Funcionalidade:
1.  Carrega um arquivo JSON (assume formato de 2 sensores).
2.  Calcula a vazão (Q) e a tensão de cisalhamento na parede (Tw) 
    usando a PRESSÃO DO SISTEMA (media_pressao_sistema_bar).
3.  Plota Pressão do Sistema (bar) vs Vazão (mm³/s) em escala log-log.
4.  Permite ao usuário selecionar outliers visualmente para exclusão.
5.  Salva um novo arquivo JSON "limpo_" contendo apenas os pontos selecionados.
"""

import json
import os
import glob
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# --- Configurações ---
RESULTS_JSON_DIR = "resultados_testes_reometro"
# [NOVO] Chave de pressão para filtragem (Pressão do Pistão/Sistema)
CHAVE_PRESSAO_FILTRAGEM = "media_pressao_sistema_bar"


def selecionar_json_para_filtrar(pasta_json):
    """
    [MODIFICADO] Lista e seleciona arquivos JSON. 
    Assume que todos são do NOVO formato (2 sensores).
    """
    print("\n" + "="*60)
    print("--- SELECIONAR ARQUIVO JSON PARA PRÉ-ANÁLISE E FILTRAGEM ---")
    print(f"(Atenção: Este script assume o novo formato de 2 sensores)")
    print("="*60)
    
    if not os.path.exists(pasta_json):
        print(f"ERRO: Pasta '{pasta_json}' não encontrada.")
        return None, None
        
    # Prioriza arquivos 'edit_' se existirem, senão os 'raw'
    arquivos_edit = sorted([f for f in os.listdir(pasta_json) if f.startswith('edit_') and f.endswith('.json')], reverse=True)
    arquivos_raw = sorted([f for f in os.listdir(pasta_json) if not f.startswith('edit_') and not f.startswith('limpo_') and f.endswith('.json')], reverse=True)
    
    arquivos_disponiveis = arquivos_edit + arquivos_raw
    
    if not arquivos_disponiveis:
        print(f"Nenhum arquivo .json (raw ou editado) encontrado em '{pasta_json}'.")
        return None, None
    
    print("Ensaios disponíveis (Prioridade para 'edit_'):")
    for i, arq in enumerate(arquivos_disponiveis):
        prefixo = "[Editado] " if arq.startswith('edit_') else "[Original] "
        print(f"  {i+1}: {prefixo}{arq}")
    
    while True:
        try:
            escolha_str = input(f"\nEscolha o NÚMERO do ensaio (1 a {len(arquivos_disponiveis)}) (ou '0' para cancelar): ").strip()
            if escolha_str == '0': return None, None
            
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_disponiveis):
                arquivo_selecionado = arquivos_disponiveis[escolha_num - 1]
                caminho_completo = os.path.join(pasta_json, arquivo_selecionado)
                
                with open(caminho_completo, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                print(f"  -> Selecionado: {arquivo_selecionado}")
                print(f"  -> Amostra: {data.get('id_amostra', 'N/A')}")
                
                # [MODIFICADO] Validação simples do formato
                if (data.get('testes') and len(data['testes']) > 0 and 
                    CHAVE_PRESSAO_FILTRAGEM not in data['testes'][0]):
                    print(f"\nERRO: O arquivo '{arquivo_selecionado}' não parece ser do formato novo.")
                    print(f"      Faltando a chave '{CHAVE_PRESSAO_FILTRAGEM}' no primeiro ponto.")
                    print("      Por favor, use a versão antiga deste script para arquivos antigos.")
                    return None, None
                
                print(f"  -> Formato: NOVO (2 Sensores) assumido.")
                print(f"  -> Usando a chave de pressão: '{CHAVE_PRESSAO_FILTRAGEM}'")
                print(f"  -> Pontos existentes: {len(data.get('testes', []))}")
                return data, arquivo_selecionado
            else:
                print("ERRO: Escolha inválida.")
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite um número.")
        except Exception as e:
            print(f"ERRO ao carregar o arquivo: {e}")
            return None, None

def calcular_vazao_e_tensao(data):
    """
    [MODIFICADO] Calcula Q e Tw (Tensão de cisalhamento) usando 
    SEMPRE a 'media_pressao_sistema_bar'.
    """
    D_cap_mm = data.get('diametro_capilar_mm')
    L_cap_mm = data.get('comprimento_capilar_mm')
    rho_g_cm3 = data.get('densidade_pasta_g_cm3')
    
    if not all([D_cap_mm, L_cap_mm, rho_g_cm3]):
        print("ERRO: Dados geométricos (D, L) ou densidade (rho) ausentes no JSON.")
        return None
        
    R_cap_mm = D_cap_mm / 2.0
    
    pontos_processados = []
    
    for i, ponto in enumerate(data.get('testes', [])):
        massa_g = ponto.get('massa_g_registrada')
        duracao_s = ponto.get('duracao_real_s')
        
        # [MODIFICADO] Usa diretamente a chave do sensor de Sistema
        pressao_bar = ponto.get(CHAVE_PRESSAO_FILTRAGEM) 
        
        if not all([massa_g, duracao_s, pressao_bar]) or duracao_s <= 0 or massa_g <= 0 or pressao_bar < 0:
            print(f"Aviso: Ponto {i} (Ponto N° {ponto.get('ponto_n', '?')}) ignorado por dados incompletos (massa, tempo ou pressão <= 0).")
            continue
            
        # 1. Vazão Volumétrica (Q) em [mm³/s]
        volume_mm3 = (massa_g / rho_g_cm3) * 1000
        Q_mm3_s = volume_mm3 / duracao_s
        
        # 2. Tensão de Cisalhamento na Parede (Tw) em [Pa]
        pressao_Pa = pressao_bar * 100000
        Tw_Pa = (pressao_Pa * R_cap_mm) / (2 * L_cap_mm)
        
        ponto_novo = {
            "ponto_original": ponto, 
            "Q_mm3_s": Q_mm3_s,
            "Tw_Pa": Tw_Pa,
            "Pressao_Sistema_bar": pressao_bar, # Chave explícita para plotagem
            "id_display": i 
        }
        pontos_processados.append(ponto_novo)
        
    return pontos_processados


def plotar_e_filtrar_interativo(pontos_processados, id_amostra):
    """
    [MODIFICADO] Plota os dados (Pressão do SISTEMA vs Q) e permite a 
    seleção interativa de pontos.
    """
    
    if not pontos_processados:
        print("Nenhum ponto válido para plotar.")
        return None

    pontos_para_manter = list(pontos_processados)
    
    while True:
        fig, ax = plt.subplots(figsize=(12, 8))
        
        Q_plot = np.array([p['Q_mm3_s'] for p in pontos_para_manter])
        P_plot = np.array([p['Pressao_Sistema_bar'] for p in pontos_para_manter]) # Usa a pressão do Sistema
        ids_plot = [p['id_display'] for p in pontos_para_manter]

        if len(Q_plot) == 0:
            print("Nenhum ponto restante para plotar.")
            plt.close(fig)
            break 

        sc = ax.scatter(Q_plot, P_plot, c='blue', label='Pontos Mantidos', picker=True, pickradius=5)
        
        Q_removidos = [p['Q_mm3_s'] for p in pontos_processados if p not in pontos_para_manter]
        P_removidos = [p['Pressao_Sistema_bar'] for p in pontos_processados if p not in pontos_para_manter] # Usa a pressão do Sistema
        if Q_removidos:
            ax.scatter(Q_removidos, P_removidos, c='red', marker='x', label='Pontos Removidos')

        for i, p in enumerate(pontos_para_manter):
            ponto_n = p['ponto_original'].get('ponto_n', ids_plot[i])
            ax.text(Q_plot[i], P_plot[i], f" N{ponto_n}", fontsize=9, ha='left')

        ax.set_xlabel('Vazão Volumétrica (Q) [mm³/s] (Log)')
        # [MODIFICADO] Label do eixo Y
        ax.set_ylabel('Pressão Sistema (P) [bar] (Log)')
        # [MODIFICADO] Título
        ax.set_title(f'Pré-Análise: {id_amostra} (Usando Pressão do Sistema)\nClique (Esq) para REMOVER | Clique (Dir) ou [ENTER] para FINALIZAR')
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.grid(True, which="both", ls="--")
        ax.legend()
        
        plt.tight_layout()
        
        print("\n" + "-"*50)
        print("--- INSTRUÇÕES DE FILTRAGEM ---")
        print("1. Analise o gráfico gerado (Pressão do Sistema vs Vazão).")
        print("2. Clique com o BOTÃO ESQUERDO perto de um ponto para marcá-lo para REMOÇÃO.")
        print("3. O gráfico será atualizado, mostrando o ponto em vermelho.")
        print("4. Para finalizar a seleção e salvar, feche a janela ou clique com o BOTÃO DIREITO.")
        
        clicks = plt.ginput(n=1, timeout=0, show_clicks=True)
        
        if not clicks: 
            print("Janela fechada. Finalizando seleção.")
            plt.close(fig)
            break
            
        click_info = clicks[0]
        x_click, y_click, button = click_info
        
        if button == 3: 
            print("Botão direito clicado. Finalizando seleção.")
            plt.close(fig)
            break
            
        if button == 1: 
            if len(Q_plot) == 0:
                 print("Não há pontos para remover.")
                 plt.close(fig)
                 continue
                 
            log_Q = np.log(Q_plot)
            log_P = np.log(P_plot)
            log_x_click = np.log(x_click)
            log_y_click = np.log(y_click)
            
            distancias = np.sqrt((log_Q - log_x_click)**2 + (log_P - log_y_click)**2)
            
            if distancias.size > 0:
                idx_mais_proximo = np.argmin(distancias)
                ponto_removido = pontos_para_manter.pop(idx_mais_proximo) 
                
                p_n = ponto_removido['ponto_original'].get('ponto_n', 'N/A')
                print(f"Ponto N°{p_n} (Idx: {ponto_removido['id_display']}) marcado para remoção.")
            
            plt.close(fig) 
    
    print(f"\nSeleção finalizada. {len(pontos_para_manter)} pontos serão mantidos.")
    
    pontos_originais_filtrados = [p['ponto_original'] for p in pontos_para_manter]
    return pontos_originais_filtrados


def salvar_json_limpo(data_original, pontos_filtrados, nome_arquivo_original):
    """
    [MODIFICADO] Salva um novo JSON com os pontos filtrados,
    ordenando pela chave de pressão do sistema.
    """
    data_limpa = {key: value for key, value in data_original.items() if key != 'testes'}
    
    data_limpa['testes'] = pontos_filtrados
    data_limpa["data_hora_filtragem"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if nome_arquivo_original.startswith('edit_'):
        base_name = nome_arquivo_original[5:]
    elif nome_arquivo_original.startswith('limpo_'):
         base_name = nome_arquivo_original[6:]
    else:
        base_name = nome_arquivo_original
        
    base_name = os.path.splitext(base_name)[0] 
    nome_arquivo_limpo = f"limpo_{base_name}.json"
    
    caminho_completo_saida = os.path.join(RESULTS_JSON_DIR, nome_arquivo_limpo)
    
    try:
        # [MODIFICADO] Reordena pela chave de pressão do sistema
        data_limpa['testes'] = sorted(data_limpa['testes'], key=lambda t: t.get(CHAVE_PRESSAO_FILTRAGEM, 0))
        
        with open(caminho_completo_saida, 'w', encoding='utf-8') as f:
            json.dump(data_limpa, f, indent=4, ensure_ascii=False)
        print(f"\nArquivo filtrado salvo com sucesso em: {caminho_completo_saida}")
        print(f"Total de pontos salvos: {len(pontos_filtrados)}")
    except IOError as e:
        print(f"Erro ao salvar o arquivo JSON limpo: {e}")


def main():
    """Função principal do script."""
    if not os.path.exists(RESULTS_JSON_DIR):
        os.makedirs(RESULTS_JSON_DIR)
        
    data, nome_arquivo = selecionar_json_para_filtrar(RESULTS_JSON_DIR)
    
    if not data or not nome_arquivo:
        print("Nenhum arquivo selecionado. Saindo.")
        return
        
    if not data.get('testes'):
        print("Arquivo JSON selecionado não contém testes. Saindo.")
        return

    # 1. Calcular Q e Tw (usa CHAVE_PRESSAO_FILTRAGEM)
    pontos_processados = calcular_vazao_e_tensao(data)
    
    if not pontos_processados:
        print("Não foi possível processar os pontos (verifique dados no JSON). Saindo.")
        return
        
    # 2. Plotar e Filtrar (usa Pressao_Sistema_bar derivada da CHAVE_PRESSAO_FILTRAGEM)
    id_amostra = data.get('id_amostra', 'Ensaio Desconhecido')
    pontos_filtrados = plotar_e_filtrar_interativo(pontos_processados, id_amostra)
    
    # 3. Salvar (ordena por CHAVE_PRESSAO_FILTRAGEM)
    if pontos_filtrados is not None:
        salvar_json_limpo(data, pontos_filtrados, nome_arquivo)
    else:
        print("Processo de filtragem cancelado ou falhou. Nenhum arquivo salvo.")

if __name__ == "__main__":
    main()
