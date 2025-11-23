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
            
<<<<<<< Updated upstream
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_disponiveis):
                arquivo_selecionado = arquivos_disponiveis[escolha_num - 1]
                caminho_completo = os.path.join(pasta_json, arquivo_selecionado)
=======
            if any(i < 0 or i >= len(arquivos_disponiveis) for i in indices_escolhidos):
                print("ERRO: Um ou mais números estão fora do intervalo válido.")
                continue

            caminhos_selecionados = [os.path.join(pasta_json, arquivos_disponiveis[i]) for i in indices_escolhidos]
            nomes_selecionados = [arquivos_disponiveis[i] for i in indices_escolhidos]
            
            print(f"Selecionados ({len(caminhos_selecionados)}): {', '.join(nomes_selecionados)}")
            return caminhos_selecionados
            
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite números separados por vírgula.")

def validar_e_combinar_jsons(caminhos_jsons):
    """Carrega, valida parâmetros globais e combina a lista de testes."""
    if not caminhos_jsons: return None

    dados_base = ler_dados_json(caminhos_jsons[0])
    if not dados_base: return None

    todos_testes = dados_base.get('testes', [])
    
    # 1. Validação de Compatibilidade
    params_base = {k: dados_base.get(k) for k in ['diametro_capilar_mm', 'comprimento_capilar_mm', 'densidade_pasta_g_cm3']}
    if any(p is None for p in params_base.values()):
        print("ERRO: JSON base está incompleto (D, L, ou rho ausente).")
        return None

    for i, caminho in enumerate(caminhos_jsons[1:]):
        dados = ler_dados_json(caminho)
        if not dados: continue
        
        # Compara parâmetros globais com tolerância
        if not (np.isclose(dados.get('diametro_capilar_mm', 0), params_base['diametro_capilar_mm']) and
                np.isclose(dados.get('comprimento_capilar_mm', 0), params_base['comprimento_capilar_mm']) and
                np.isclose(dados.get('densidade_pasta_g_cm3', 0), params_base['densidade_pasta_g_cm3'])):
            print(f"ALERTA: JSON {os.path.basename(caminho)} tem parâmetros globais divergentes. Ignorando este arquivo.")
            continue
        
        todos_testes.extend(dados.get('testes', []))

    if not todos_testes:
        print("ERRO: Nenhuma lista de testes válida foi combinada.")
        return None

    # 2. Ordenação e Renumeração Final
    # Ordena por Pressão para garantir a curva correta
    todos_testes = sorted(todos_testes, key=lambda t: t.get('media_pressao_final_ponto_bar', 0))
    
    # Renumera os pontos sequencialmente
    for i, teste in enumerate(todos_testes):
        teste['ponto_n'] = i + 1

    dados_base['testes'] = todos_testes
    
    return dados_base

# -----------------------------------------------------------------------------
# --- FUNÇÕES DE CÁLCULO E TRATAMENTO (NOVO NÚCLEO) ---
# -----------------------------------------------------------------------------

def calcular_dados_reologicos_brutos(df_testes, rho_g_cm3, D_mm, L_mm, usar_pressao_pasta=False):
    """Calcula Tau_w, Gamma_aw e Taxa de Fluxo de Massa para cada ponto bruto."""
    rho_si = rho_g_cm3 * 1000
    R_cap_si, L_cap_m = (D_mm / 2000), L_mm / 1000
    
    # Seleciona a pressão correta
    if usar_pressao_pasta:
        # Tenta usar 'media_pressao_pasta_bar', se não existir (arquivos antigos), usa 'media_pressao_entrada_bar' ou 0.0
        df_testes['P_bar_selected'] = df_testes.get('media_pressao_pasta_bar', df_testes.get('media_pressao_entrada_bar', 0.0))
    else:
        # Tenta usar 'media_pressao_linha_bar', fallback para 'media_pressao_barril_bar' ou 'media_pressao_final_ponto_bar'
        if 'media_pressao_linha_bar' in df_testes.columns:
             df_testes['P_bar_selected'] = df_testes['media_pressao_linha_bar'].fillna(df_testes['media_pressao_final_ponto_bar'])
        elif 'media_pressao_barril_bar' in df_testes.columns:
             df_testes['P_bar_selected'] = df_testes['media_pressao_barril_bar'].fillna(df_testes['media_pressao_final_ponto_bar'])
        else:
             df_testes['P_bar_selected'] = df_testes['media_pressao_final_ponto_bar']

    df_testes['P_Pa'] = df_testes['P_bar_selected'] * 1e5
    df_testes['M_kg'] = df_testes['massa_g_registrada'] / 1000
    
    # Filtra dados de duração zero (evita Divisão por Zero)
    df_testes = df_testes[df_testes['duracao_real_s'] > 0].copy()
    
    # Cálculos reológicos básicos
    df_testes['τw (Pa)'] = df_testes['P_Pa'] * R_cap_si / (2 * L_cap_m)
    df_testes['Q_m3_s'] = (df_testes['M_kg'] / rho_si) / df_testes['duracao_real_s']
    df_testes['γ̇aw (s⁻¹)'] = (4 * df_testes['Q_m3_s']) / (np.pi * R_cap_si**3)
    
    # Taxa de fluxo de massa (para cálculo de CV)
    df_testes['mass_flow_rate_g_s'] = df_testes['massa_g_registrada'] / df_testes['duracao_real_s']
    
    return df_testes

def calcular_estatisticas_e_cv(df_testes):
    """Agrupa por pressão nominal e calcula estatísticas, incluindo CV."""
    
    # Arredonda a pressão para agrupamento (2 casas decimais é razoável para a precisão do transdutor)
    df_testes['P_NOMINAL_AGRUPADA'] = df_testes['P_bar_selected'].round(2)
    
    # Colunas para calcular estatísticas (Taxa de Fluxo de Massa como proxy de Vazão)
    cols_to_group = ['τw (Pa)', 'γ̇aw (s⁻¹)', 'mass_flow_rate_g_s']

    # Calcular Média e Desvio Padrão
    df_mean = df_testes.groupby('P_NOMINAL_AGRUPADA')[cols_to_group].mean().reset_index()
    df_std = df_testes.groupby('P_NOMINAL_AGRUPADA')[cols_to_group].std().reset_index()
    df_count = df_testes.groupby('P_NOMINAL_AGRUPADA').size().reset_index(name='N')

    # Renomear para juntar
    df_mean.columns = ['P_NOMINAL_AGRUPADA', 'mu_tau_w', 'mu_gamma_aw', 'mu_mass_flow']
    df_std.columns = ['P_NOMINAL_AGRUPADA', 'std_tau_w', 'std_gamma_aw', 'std_mass_flow']

    # Juntar e calcular CV
    df_stats = pd.merge(df_mean, df_std, on='P_NOMINAL_AGRUPADA')
    df_stats = pd.merge(df_stats, df_count, on='P_NOMINAL_AGRUPADA')
    
    # Filtro: Apenas grupos com N >= 2 para CV
    df_stats = df_stats[df_stats['N'] >= 2].copy()
    
    # Garante que não haja divisão por zero no CV
    df_stats = df_stats[df_stats['mu_mass_flow'] > 1e-9].copy()

    # Cálculo do CV (Coefficient of Variation)
    df_stats['CV_τw(%)'] = (df_stats['std_tau_w'] / df_stats['mu_tau_w']) * 100
    df_stats['CV_γ̇aw(%)'] = (df_stats['std_gamma_aw'] / df_stats['mu_gamma_aw']) * 100

    return df_stats

def remover_outliers_por_cv(df_testes, df_stats_atual, cv_limite_pct=10):
    """
    Identifica e remove pontos outliers cuja taxa de fluxo de massa esteja
    fora de 2 desvios padrão da média do seu grupo, SE o CV do grupo exceder o limite.
    
    Retorna o DataFrame limpo e o DataFrame de estatísticas recalculado.
    """
    
    df_stats_map = df_stats_atual[['P_NOMINAL_AGRUPADA', 'mu_mass_flow', 'std_mass_flow', 'CV_γ̇aw(%)']].set_index('P_NOMINAL_AGRUPADA').to_dict('index')

    indices_para_remover = set()
    pontos_removidos_total = 0
    
    # Itera sobre cada ponto no DataFrame original de testes
    for index, row in df_testes.iterrows():
        p_nominal = row['P_NOMINAL_AGRUPADA']
        
        if p_nominal in df_stats_map:
            stats = df_stats_map[p_nominal]
            
            cv_do_grupo = stats['CV_γ̇aw(%)']
            fluxo_atual = row['mass_flow_rate_g_s']
            
            # Condição de remoção: Se o CV do grupo está alto E o ponto está fora de 2*STD
            if cv_do_grupo > cv_limite_pct:
                limite_superior = stats['mu_mass_flow'] + 2 * stats['std_mass_flow']
                limite_inferior = stats['mu_mass_flow'] - 2 * stats['std_mass_flow']
>>>>>>> Stashed changes
                
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
    
<<<<<<< Updated upstream
    if not all([D_cap_mm, L_cap_mm, rho_g_cm3]):
        print("ERRO: Dados geométricos (D, L) ou densidade (rho) ausentes no JSON.")
        return None
=======
    print("="*70); print("--- FUSÃO, LIMPEZA E PRÉ-TRATAMENTO ESTATÍSTICO (2X) ---"); print("="*70)
    
    # 1. Fusão e Combinação de JSONs
    caminhos_jsons = selecionar_multiplos_json(JSON_INPUT_DIR, "Selecione os JSONs de teste a serem combinados")
    if not caminhos_jsons: return
    
    dados_combinados = validar_e_combinar_jsons(caminhos_jsons)
    if not dados_combinados: return
    
    nome_sessao_base = dados_combinados['id_amostra']
    D_mm = dados_combinados['diametro_capilar_mm']
    L_mm = dados_combinados['comprimento_capilar_mm']
    rho_g_cm3 = dados_combinados['densidade_pasta_g_cm3']

    # 2. Carrega para DataFrame e Calcula Dados Brutos
    df_testes = pd.DataFrame(dados_combinados['testes'])
    
    # SELEÇÃO DO SENSOR DE PRESSÃO
    # Padrão definido pelo usuário: USAR SENSOR DA PASTA (2)
    print("\n--- Seleção do Sensor de Pressão para Análise ---")
    print(">> Configuração Padrão: USANDO PRESSÃO DA PASTA (Sensor 2).")
    usar_pressao_pasta = True
    
    # if usar_pressao_pasta:
    #     print(">> USANDO PRESSÃO DA PASTA.")
    # else:
    #     print(">> USANDO PRESSÃO DA LINHA.")

    df_testes = calcular_dados_reologicos_brutos(df_testes, rho_g_cm3, D_mm, L_mm, usar_pressao_pasta)
    
    # Limpa valores óbvios (Q ou Tau zero)
    df_testes.dropna(subset=['τw (Pa)', 'γ̇aw (s⁻¹)'], inplace=True)
    df_testes = df_testes[(df_testes['τw (Pa)'] > 1e-9) & (df_testes['γ̇aw (s⁻¹)'] > 1e-9)].copy()
    
    if len(df_testes) < 2:
        print("\nERRO: Menos de 2 pontos válidos após a limpeza inicial (Duração ou Pressão zero).")
        return

    # 3. Processamento Iterativo de Outliers
    
    df_limpo = df_testes.copy()
    
    # Exibe estatísticas iniciais
    df_stats_inicial = calcular_estatisticas_e_cv(df_limpo)
    if df_stats_inicial.empty:
        print("\nERRO: Nenhuma repetição (N >= 2) encontrada para calcular o CV. Continue com o Script 2.")
        return
>>>>>>> Stashed changes
        
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
    
<<<<<<< Updated upstream
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
=======
    # 5.1. Mapeia colunas do df_limpo de volta para a estrutura de lista de dicionários do JSON
    testes_limpos_json = []
    
    # As colunas `media_pressao_final_ponto_bar`, `massa_g_registrada`, `duracao_real_s`, etc.,
    # são as colunas originais que o Script 1 espera dentro da lista 'testes'.
    # O Ponto_n é a numeração sequencial após a ordenação/limpeza.
    
    for i, row in df_limpo.reset_index(drop=True).iterrows():
        testes_limpos_json.append({
            "ponto_n": i + 1, # Renumeração final após a limpeza
            "massa_g_registrada": row['massa_g_registrada'],
            "duracao_real_s": row['duracao_real_s'],
            "duracao_real_s": row['duracao_real_s'],
            "media_tensao_final_ponto_V": row.get('media_tensao_final_ponto_V', 0.0), 
            "media_pressao_final_ponto_bar": row.get('media_pressao_final_ponto_bar', row['P_bar_selected']), # Mantém compatibilidade
            "media_pressao_barril_bar": row.get('media_pressao_barril_bar', 0.0),
            "media_pressao_entrada_bar": row.get('media_pressao_entrada_bar', 0.0)
            # Omissão de 'leituras_pressao_detalhadas_bar' para simplificar o JSON
        })

    # 5.2. Cria o novo objeto JSON
    dados_combinados['testes'] = testes_limpos_json
    dados_combinados['data_hora_limpeza'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dados_combinados['observacoes_limpeza'] = f"Combinado(s) de {len(caminhos_jsons)} arquivo(s). {total_pontos_orig - len(df_limpo)} ponto(s) removido(s) automaticamente (CV > {cv_limite:.1f}%)."
    
    # 5.3. Salva o JSON na pasta de testes
    df_saida_individual = df_limpo.rename(columns={
        'P_bar_selected': 'P_ext(bar)',
        'massa_g_registrada': 'M_ext(g)',
        'duracao_real_s': 't_ext(s)',
    })
    
    df_saida_individual['D_cap(mm)'] = D_mm
    df_saida_individual['L_cap(mm)'] = L_mm
    df_saida_individual['rho(g/cm³)'] = rho_g_cm3
    df_saida_individual['τw (Pa)'] = df_saida_individual['τw (Pa)'] 
    df_saida_individual['γ̇w (s⁻¹)'] = df_saida_individual['γ̇aw (s⁻¹)']
    df_saida_individual['η (Pa·s)'] = df_saida_individual['τw (Pa)'] / df_saida_individual['γ̇w (s⁻¹)'].replace(0, np.nan)
    
    colunas_finais = ['P_ext(bar)', 'M_ext(g)', 't_ext(s)', 'D_cap(mm)', 'L_cap(mm)', 'rho(g/cm³)', 'τw (Pa)', 'γ̇w (s⁻¹)', 'η (Pa·s)']
    df_saida_individual = df_saida_individual[colunas_finais]
    
    nome_pasta_analise = f"{nome_sessao_base}_ANALISE_LIMPA_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    caminho_pasta_individual = os.path.join("resultados_analise_reologica", nome_pasta_analise)
    if not os.path.exists(caminho_pasta_individual):
        os.makedirs(caminho_pasta_individual)
>>>>>>> Stashed changes


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
