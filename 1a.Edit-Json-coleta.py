# -*- coding: utf-8 -*-
"""
SCRIPT PARA EDITAR ARQUIVOS JSON DE COLETA (Formato NOVO - 2 Sensores)
Permite visualizar, modificar (massa/tempo) ou excluir pontos de um ensaio.
Cria um novo arquivo 'edit_[nome_original].json' com as modificações.

VERSÃO 2.0 (Simplificada - Apenas 2 Sensores)
Autor: Bruno Egami (Modificado por Gemini)
Data: 04/11/2025
"""

import json
import os
import glob
from datetime import datetime

# --- Configurações ---
RESULTS_JSON_DIR = "resultados_testes_reometro"
# [NOVO] Chave de pressão principal para este script (Sensor de Sistema)
CHAVE_PRESSAO_PRINCIPAL = "media_pressao_sistema_bar"

def input_float_com_virgula(mensagem_prompt, permitir_vazio=False, default_val=None):
    """Pede um número float ao usuário, aceitando ',' como decimal."""
    while True:
        if default_val is not None:
            if isinstance(default_val, (int, float)):
                default_str = f"{default_val:.3f}".replace('.', ',') if default_val > 0.1 else f"{default_val:.4f}".replace('.', ',')
            else:
                default_str = str(default_val)
            
            prompt = f"{mensagem_prompt} (Atual: {default_str}) [ENTER para manter]: "
        else:
            prompt = mensagem_prompt
            
        entrada = input(prompt).strip()
        
        if permitir_vazio and entrada == "":
            return default_val if default_val is not None else None
        
        try:
            return float(entrada.replace(',', '.'))
        except ValueError:
            print("ERRO: Entrada inválida. Insira um número.")
        except Exception as e:
            print(f"Ocorreu um erro: {e}")

def selecionar_json_para_edicao(pasta_json):
    """
    [MODIFICADO] Lista e seleciona arquivos JSON.
    Valida se o arquivo selecionado é do NOVO formato (2 sensores).
    """
    print("\n" + "="*60)
    print("--- SELECIONAR ARQUIVO JSON PARA EDIÇÃO ---")
    print(f"(Atenção: Este script aceita apenas o novo formato de 2 sensores)")
    print("="*60)
    if not os.path.exists(pasta_json):
        print(f"ERRO: Pasta '{pasta_json}' não encontrada.")
        return None, None
        
    arquivos_json = sorted([f for f in os.listdir(pasta_json) if f.endswith('.json') and os.path.isfile(os.path.join(pasta_json, f))], reverse=True)
    
    if not arquivos_json:
        print(f"Nenhum arquivo .json encontrado na pasta '{pasta_json}'.")
        return None, None
    
    print("Ensaios disponíveis (do mais recente ao mais antigo):")
    for i, arq in enumerate(arquivos_json):
        print(f"  {i+1}: {arq}")
    
    while True:
        try:
            escolha_str = input("\nEscolha o NÚMERO do ensaio para editar (ou '0' para cancelar): ").strip()
            if escolha_str == '0': return None, None
            
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_json):
                arquivo_selecionado = arquivos_json[escolha_num - 1]
                caminho_completo = os.path.join(pasta_json, arquivo_selecionado)
                
                with open(caminho_completo, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # --- [NOVO] Validação do Formato ---
                if (not data.get('testes') or len(data['testes']) == 0 or 
                    CHAVE_PRESSAO_PRINCIPAL not in data['testes'][0]):
                    
                    print(f"\nERRO: O arquivo '{arquivo_selecionado}' não é do formato novo (2 sensores).")
                    print(f"      Faltando a chave '{CHAVE_PRESSAO_PRINCIPAL}' no primeiro ponto.")
                    print("      Por favor, use a versão antiga (V1.0) deste script para arquivos antigos.")
                    return None, None
                
                print(f"  -> Selecionado: {arquivo_selecionado}")
                print(f"  -> Amostra: {data.get('id_amostra', 'N/A')}")
                print(f"  -> Formato: NOVO (2 Sensores) validado.")
                print(f"  -> Pontos existentes: {len(data.get('testes', []))}")
                return data, arquivo_selecionado
            else:
                print(f"ERRO: Escolha inválida. Digite um número entre 1 e {len(arquivos_json)}, ou '0'.")
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite um número.")
        except Exception as e:
            print(f"ERRO ao carregar o arquivo: {e}")
            return None, None

def listar_pontos_do_ensaio(data):
    """
    [MODIFICADO] Lista os pontos de medição, assumindo o formato de 2 sensores.
    """
    if not data.get('testes'):
        print("Nenhum ponto de medição encontrado neste ensaio.")
        return

    print("\n" + "-"*80)
    print("--- PONTOS DE MEDIÇÃO REGISTRADOS (Formato 2 Sensores) ---")
    
    # [MODIFICADO] Ordena pela pressão do SISTEMA
    testes_ordenados = sorted(data['testes'], key=lambda t: t.get(CHAVE_PRESSAO_PRINCIPAL, 0))
    
    # [MODIFICADO] Cabeçalho para 2 sensores
    print(f"{'Idx':<4} | {'Ponto Nº':<8} | {'P. Sistema (bar)':<18} | {'P. Pasta (bar)':<16} | {'Massa (g)':<12} | {'Tempo (s)':<10}")
    print("-" * 80)
    
    for i, ponto in enumerate(testes_ordenados):
        idx = i
        ponto_n = ponto.get('ponto_n', 'N/A')
        massa = ponto.get('massa_g_registrada', 0.0)
        tempo = ponto.get('duracao_real_s', 0.0)
        
        # [MODIFICADO] Exibe ambos os sensores
        pressao_sis = ponto.get('media_pressao_sistema_bar', 0.0)
        pressao_pas = ponto.get('media_pressao_pasta_bar', 0.0)
        print(f"{idx:<4} | {ponto_n:<8} | {pressao_sis:<18.4f} | {pressao_pas:<16.4f} | {massa:<12.3f} | {tempo:<10.2f}")

    print("-" * 80)


def modificar_ponto(data):
    """
    [MODIFICADO] Permite ao usuário modificar a massa ou o tempo, 
    assumindo o formato de 2 sensores.
    """
    listar_pontos_do_ensaio(data)
    if not data.get('testes'):
        return

    # [MODIFICADO] Ordena pela pressão do SISTEMA
    testes_ordenados = sorted(data['testes'], key=lambda t: t.get(CHAVE_PRESSAO_PRINCIPAL, 0))
    
    while True:
        try:
            idx_str = input(f"Digite o 'Idx' (0 a {len(testes_ordenados)-1}) do ponto a modificar (ou 's' para sair): ").strip()
            if idx_str.lower() == 's':
                break
            
            idx = int(idx_str)
            if 0 <= idx < len(testes_ordenados):
                ponto_original = testes_ordenados[idx]
                
                print(f"\nModificando Ponto Nº {ponto_original.get('ponto_n', 'N/A')} (Idx: {idx})")
                
                # [MODIFICADO] Exibe ambas as pressões
                print(f"  P. Sistema: {ponto_original.get('media_pressao_sistema_bar', 0.0):.4f} bar")
                print(f"  P. Pasta:   {ponto_original.get('media_pressao_pasta_bar', 0.0):.4f} bar")
                
                # Modificar Massa
                massa_antiga = ponto_original.get('massa_g_registrada', 0.0)
                nova_massa = input_float_com_virgula("Nova Massa (g): ", permitir_vazio=True, default_val=massa_antiga)
                if nova_massa is not None:
                    ponto_original['massa_g_registrada'] = nova_massa
                    print(f"  -> Massa atualizada para {nova_massa:.3f} g")

                # Modificar Tempo
                tempo_antigo = ponto_original.get('duracao_real_s', 0.0)
                novo_tempo = input_float_com_virgula("Novo Tempo (s): ", permitir_vazio=True, default_val=tempo_antigo)
                if novo_tempo is not None:
                    ponto_original['duracao_real_s'] = novo_tempo
                    print(f"  -> Tempo atualizado para {novo_tempo:.2f} s")
                    
                # Recalcula a lista ordenada
                testes_ordenados = sorted(data['testes'], key=lambda t: t.get(CHAVE_PRESSAO_PRINCIPAL, 0))
                listar_pontos_do_ensaio(data) # Mostra a lista atualizada
                
            else:
                print("ERRO: 'Idx' fora do intervalo válido.")
        except ValueError:
            print("ERRO: Entrada inválida. Digite um número.")

def excluir_ponto(data):
    """
    [MODIFICADO] Permite ao usuário excluir um ponto específico,
    assumindo o formato de 2 sensores.
    """
    listar_pontos_do_ensaio(data)
    if not data.get('testes'):
        return False

    # [MODIFICADO] Ordena pela pressão do SISTEMA
    testes_ordenados = sorted(data['testes'], key=lambda t: t.get(CHAVE_PRESSAO_PRINCIPAL, 0))

    while True:
        try:
            idx_str = input(f"Digite o 'Idx' (0 a {len(testes_ordenados)-1}) do ponto a EXCLUIR (ou 's' para sair): ").strip()
            if idx_str.lower() == 's':
                break
            
            idx = int(idx_str)
            if 0 <= idx < len(testes_ordenados):
                ponto_a_excluir_display = testes_ordenados[idx]
                ponto_n_excluir = ponto_a_excluir_display.get('ponto_n', 'N/A')
                
                # [MODIFICADO] Usa a pressão do SISTEMA para encontrar o ponto
                pressao_referencia = ponto_a_excluir_display.get(CHAVE_PRESSAO_PRINCIPAL, 0.0)
                
                ponto_original_para_excluir = None
                for p in data['testes']:
                    if (p.get('ponto_n') == ponto_n_excluir and 
                        abs(p.get(CHAVE_PRESSAO_PRINCIPAL, -1) - pressao_referencia) < 1e-6):
                        ponto_original_para_excluir = p
                        break
                
                if ponto_original_para_excluir:
                    confirm = input(f"Tem certeza que deseja EXCLUIR Ponto Nº {ponto_n_excluir} (Idx: {idx})? (s/n): ").lower()
                    if confirm == 's':
                        data['testes'].remove(ponto_original_para_excluir)
                        print(f"Ponto Nº {ponto_n_excluir} (Idx: {idx}) excluído.")
                        
                        testes_ordenados = sorted(data['testes'], key=lambda t: t.get(CHAVE_PRESSAO_PRINCIPAL, 0))
                        listar_pontos_do_ensaio(data) # Mostra a lista atualizada
                        return True # Indica que houve mudança
                    else:
                        print("Exclusão cancelada.")
                else:
                     print("ERRO: Não foi possível encontrar o ponto original para exclusão (disparidade de dados).")
                     
            else:
                print("ERRO: 'Idx' fora do intervalo válido.")
        except ValueError:
            print("ERRO: Entrada inválida. Digite um número.")
    return False

def salvar_json_editado(data, nome_arquivo_original):
    """
    [MODIFICADO] Salva os dados modificados, ordenando pela 
    pressão do SISTEMA.
    """
    if nome_arquivo_original.startswith('edit_'):
        nome_arquivo_editado = nome_arquivo_original
    else:
        nome_arquivo_editado = f"edit_{nome_arquivo_original}"
        
    caminho_completo_saida = os.path.join(RESULTS_JSON_DIR, nome_arquivo_editado)
    
    try:
        # [MODIFICADO] Reordena pela pressão do SISTEMA
        if data.get('testes'):
            data['testes'] = sorted(data['testes'], key=lambda t: t.get(CHAVE_PRESSAO_PRINCIPAL, 0))
        
        data["data_hora_ultima_edicao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(caminho_completo_saida, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"\nArquivo editado salvo com sucesso em: {caminho_completo_saida}")
    except IOError as e:
        print(f"Erro ao salvar o arquivo JSON editado: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao salvar: {e}")


def menu_edicao(data, nome_arquivo_original):
    """Menu principal para edição do JSON carregado."""
    houve_mudanca = False
    while True:
        print("\n" + "="*20 + f" Editando: {nome_arquivo_original} " + "="*20)
        print("1. Listar Pontos de Medição")
        print("2. Modificar Ponto (Massa / Tempo)")
        print("3. Excluir Ponto")
        print("0. Salvar e Sair")
        print("9. Sair SEM Salvar")
        
        escolha = input("Digite sua opção: ").strip()
        
        if escolha == '1':
            listar_pontos_do_ensaio(data)
        
        elif escolha == '2':
            modificar_ponto(data)
            houve_mudanca = True 
        
        elif escolha == '3':
            if excluir_ponto(data):
                houve_mudanca = True
        
        elif escolha == '0':
            if houve_mudanca:
                salvar_json_editado(data, nome_arquivo_original)
            else:
                print("Nenhuma mudança detectada. Saindo sem salvar.")
            break
            
        elif escolha == '9':
            if houve_mudanca:
                confirm = input("AVISO: Você tem mudanças não salvas. Deseja sair mesmo assim? (s/n): ").lower()
                if confirm != 's':
                    continue
            print("Saindo sem salvar.")
            break
        
        else:
            print("Opção inválida. Tente novamente.")

def main():
    """Função principal do script."""
    if not os.path.exists(RESULTS_JSON_DIR):
        os.makedirs(RESULTS_JSON_DIR)
        
    data, nome_arquivo = selecionar_json_para_edicao(RESULTS_JSON_DIR)
    
    if data and nome_arquivo:
        menu_edicao(data, nome_arquivo)
    else:
        print("Nenhum arquivo selecionado ou formato inválido. Saindo.")

if __name__ == "__main__":
    main()
