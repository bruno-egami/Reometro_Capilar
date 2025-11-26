# -*- coding: utf-8 -*-
import os
import json
import glob
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from datetime import datetime
import utils_reologia

def input_sim_nao(mensagem_prompt):
    """Pede uma entrada do usuário e valida se é 'sim' ou 'não'."""
    while True:
        resp = input(mensagem_prompt).strip().lower()
        if resp in ['s', 'sim', 'y', 'yes']: return True
        if resp in ['n', 'nao', 'não', 'no']: return False
        print("Resposta inválida. Digite 's' ou 'n'.")

def input_float_com_virgula(mensagem_prompt, permitir_vazio=False):
    """Pede um número float ao usuário, aceitando ',' como decimal. Permite entrada vazia opcionalmente."""
    while True:
        entrada = input(mensagem_prompt).strip().replace(',', '.')
        if permitir_vazio and entrada == "": return None
        try:
            return float(entrada)
        except ValueError:
            print("Entrada inválida. Por favor, digite um número.")

def ler_dados_json(json_filepath):
    """Lê dados de um arquivo JSON, suportando duração fixa ('duracao_por_teste_s') ou variável ('duracao_real_s')."""
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # --- Lógica de Compatibilidade para Tempo ---
        duracoes = []
        
        # 1. Tenta ler o array de testes (formato novo/padrão)
        if 'testes' in data and isinstance(data['testes'], list):
            for t in data['testes']:
                # Tenta 'duracao_real_s' (novo), fallback para 'duracao_s' (alguns antigos)
                d = t.get('duracao_real_s', t.get('duracao_s'))
                if d is not None: duracoes.append(float(d))
        
        # 2. Se não achou no array ou array vazio, tenta campos globais antigos
        if not duracoes:
            duracao_global = data.get('duracao_por_teste_s')
            if duracao_global is not None:
                duracoes = [float(duracao_global)]
        
        # 3. Garante que temos listas de pressão e massa para retornar estrutura padronizada
        pressoes_bar_list = []
        massas_g_list = []
        
        if 'testes' in data:
            for t in data['testes']:
                p_linha = t.get('media_pressao_linha_bar', 0.0)
                p_pasta = t.get('media_pressao_pasta_bar', 0.0)
                # Fallbacks para pressão
                if p_linha == 0 and 'pressao_bar' in t: p_linha = t['pressao_bar'] # Antigo
                
                m = t.get('massa_g_registrada', t.get('massa_g', 0.0))
                
                pressoes_bar_list.append({'linha': p_linha, 'pasta': p_pasta})
                massas_g_list.append(m)
        else:
            # Tenta formato antigo plano (listas diretas)
            p_old = data.get('pressoes_bar_list', [])
            m_old = data.get('massas_g_list', [])
            if p_old and m_old:
                for p, m in zip(p_old, m_old):
                    pressoes_bar_list.append({'linha': p, 'pasta': p}) # Assume igual se não especificado
                    massas_g_list.append(m)

        # Retorna um dicionário padronizado
        return {
            'id_amostra': data.get('id_amostra', 'Desconhecido'),
            'rho_g_cm3_json': data.get('densidade_pasta_g_cm3', data.get('rho_g_cm3', 0.0)),
            'D_mm': data.get('diametro_capilar_mm', data.get('D_mm', 0.0)),
            'L_mm': data.get('comprimento_capilar_mm', data.get('L_mm', 0.0)),
            'duracoes_s_list': duracoes,
            'pressoes_bar_list': pressoes_bar_list,
            'massas_g_list': massas_g_list,
            'raw_data': data # Mantém o original se precisar de algo extra
        }

    except Exception as e:
        print(f"Erro ao ler JSON '{os.path.basename(json_filepath)}': {e}")
        return None

def salvar_calibracao_json(tipo_correcao, tau_w_corrigido, gamma_dot_corrigido, arquivos_origem, pasta_calibracao):
    """
    Salva os resultados de uma calibração (Bagley, Mooney, etc.) em um arquivo JSON.
    Estes dados (tau vs gamma) representam a "curva mestra" da correção.
    """
    if not os.path.exists(pasta_calibracao):
        os.makedirs(pasta_calibracao)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"calibracao_{tipo_correcao}_{timestamp}.json"
    caminho_completo = os.path.join(pasta_calibracao, nome_arquivo)
    
    dados_calibracao = {
        "tipo_calibracao": tipo_correcao,
        "data_geracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "arquivos_origem": arquivos_origem,
        "pontos_calibracao": {
            "tau_w_pa": list(tau_w_corrigido),
            "gamma_dot_corrigido_s-1": list(gamma_dot_corrigido)
        }
    }
    
    try:
        with open(caminho_completo, 'w', encoding='utf-8') as f:
            json.dump(dados_calibracao, f, indent=4)
        print(f"\nArquivo de calibração salvo: {nome_arquivo}")
        return caminho_completo
    except Exception as e:
        print(f"Erro ao salvar calibração: {e}")
        return None

def listar_e_selecionar_calibracao(pasta_calibracao):
    """
    Lista os arquivos de calibração .json disponíveis na pasta de calibrações
    e permite ao usuário selecionar um para aplicar em um novo ensaio.
    """
    return utils_reologia.selecionar_arquivo(pasta_calibracao, "calibracao_*.json", "Selecione um arquivo de Calibração", ".json")

def carregar_e_aplicar_calibracao(caminho_calibracao, tau_w_nao_corrigido):
    """
    Carrega os dados de um arquivo de calibração JSON e os aplica aos dados de tensão de cisalhamento
    de um capilar único, usando interpolação para encontrar a taxa de cisalhamento corrigida correspondente.
    """
    try:
        with open(caminho_calibracao, 'r', encoding='utf-8') as f:
            cal_data = json.load(f)
        
        print(f"\nAplicando calibração do tipo '{cal_data.get('tipo_calibracao', 'N/A')}' de {cal_data.get('data_geracao', 'N/A')}")
        
        pontos = cal_data.get('pontos_calibracao', {})
        tau_cal = np.array(pontos.get('tau_w_pa', []))
        gamma_cal = np.array(pontos.get('gamma_dot_corrigido_s-1', []))

        if len(tau_cal) < 2 or len(gamma_cal) < 2:
            print("ERRO na calibração: Arquivo não contém pontos suficientes para interpolação.")
            return None

        funcao_calibracao = interp1d(tau_cal, gamma_cal, kind='linear', bounds_error=False, fill_value="extrapolate")
        gamma_dot_aplicado = funcao_calibracao(tau_w_nao_corrigido)
        
        print("SUCESSO: Calibração aplicada aos dados.")
        return gamma_dot_aplicado

    except FileNotFoundError:
        print(f"ERRO: Arquivo de calibração não encontrado: '{caminho_calibracao}'")
        return None
    except Exception as e:
        print(f"ERRO ao carregar ou aplicar calibração: {e}")
        return None

def carregar_csv_resultados(filepath):
    """
    Carrega um arquivo CSV de resultados reológicos padrão.
    Retorna um DataFrame pandas.
    """
    try:
        # Tenta primeiro com ponto e vírgula (padrão Excel BR/Script 2)
        df = pd.read_csv(filepath, sep=';', decimal=',', encoding='utf-8')
        
        # Se leu apenas 1 coluna, provavelmente o separador é vírgula
        if len(df.columns) == 1:
            # Tenta com vírgula (padrão Pandas/Script 2b)
            df = pd.read_csv(filepath, sep=',', decimal='.', encoding='utf-8')
            
        # Limpeza básica de nomes de colunas (remove espaços extras)
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception as e:
        print(f"Erro ao carregar CSV {filepath}: {e}")
        return None

def carregar_dados_estatisticos(filepath):
    """
    Carrega um arquivo CSV de dados estatísticos.
    """
    return carregar_csv_resultados(filepath)

def encontrar_arquivo_associado(base_path, pattern_glob):
    """
    Busca um arquivo associado em um diretório base usando um padrão glob.
    Retorna o caminho completo do primeiro arquivo encontrado ou None.
    """
    busca = os.path.join(base_path, pattern_glob)
    arquivos = glob.glob(busca)
    if arquivos:
        return arquivos[0]
    return None
