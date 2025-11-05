# -*- coding: utf-8 -*-
"""
SCRIPT PARA EDITAR ARQUIVOS JSON DE COLETA (Compatível com 1 ou 2 Sensores)
Permite visualizar, modificar (massa/tempo) ou excluir pontos de um ensaio.
Cria um novo arquivo 'edit_[nome_original].json' com as modificações.
VERSÃO 2.0 - Suporte a JSON antigo (1 sensor) e novo (2 sensores)
Autor: Bruno Egami (Modificado por Gemini)
Data: 04/11/2025
"""

import json
import os
import glob
from datetime import datetime

# --- Configurações ---
RESULTS_JSON_DIR = "resultados_testes_reometro"

# --- [NOVO] Variáveis Globais para detecção de formato ---
g_formato_novo = False # Flag para saber se é o formato de 2 sensores
g_chave_pressao_principal = "media_pressao_final_ponto_bar" # Chave padrão (formato antigo)

def input_float_com_virgula(mensagem_prompt, permitir_vazio=False, default_val=None):
    """Pede um número float ao usuário, aceitando ',' como decimal."""
    while True:
        if default_val is not None:
            # Formata o default_val para exibição (ex: 3.140)
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
    """[MODIFICADO] Lista, seleciona e DETECTA O FORMATO do arquivo JSON."""
    global g_formato_novo, g_chave_pressao_principal
    
    print("\n" + "="*60)
    print("--- SELECIONAR ARQUIVO JSON PARA EDIÇÃO ---")
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
                
                print(f"  -> Selecionado: {arquivo_selecionado}")
                print(f"  -> Amostra: {data.get('id_amostra', 'N/A')}")
                
                # --- [NOVO] Lógica de Detecção de Formato ---
                if data.get('testes') and len(data['testes']) > 0:
                    primeiro_ponto = data['testes'][0]
                    if 'media_pressao_sistema_bar' in primeiro_ponto:
                        g_formato_novo = True
                        g_chave_pressao_principal = 'media_pressao_sistema_bar'
                        print("  -> Formato: NOVO (2 Sensores) detectado.")
                    else:
                        g_formato_novo = False
                        g_chave_pressao_principal = 'media_pressao_final_ponto_bar'
                        print("  -> Formato: ANTIGO (1 Sensor) detectado.")
                else:
                    g_formato_novo = False # Assume antigo se vazio
                    g_chave_pressao_principal = 'media_pressao_final_ponto_bar'
                    print("  -> Ensaio vazio ou formato não reconhecido (assumindo antigo).")
                
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
    """[MODIFICADO] Lista os pontos de medição de forma tabular, adaptando-se ao formato."""
    global g_formato_novo, g_chave_pressao_principal
    
    if not data.get('testes'):
        print("Nenhum ponto de medição encontrado neste ensaio.")
        return

    print("\n" + "-"*80)
    print("--- PONTOS DE MEDIÇÃO REGISTRADOS ---")
    
    # Ordena pela chave de pressão principal detectada
    testes_ordenados = sorted(data['testes'], key=lambda t: t.get(g_chave_pressao_principal, 0))
    
    # [MODIFICADO] Cabeçalho dinâmico
    if g_formato_novo:
        print(f"{'Idx':<4} | {'Ponto Nº':<8} | {'P. Sistema (bar)':<18} | {'P. Pasta (bar)':<16} | {'Massa (g)':<12} | {'Tempo (s)':<10}")
        print("-" * 80)
    else:
        print(f"{'Idx':<4} | {'Ponto Nº':<8} | {'Pressão Média (bar)':<20} | {'Massa (g)':<12} | {'Tempo (s)':<10}")
        print("-" * 60)
        
    
    for i, ponto in enumerate(testes_ordenados):
        idx = i
        ponto_n = ponto.get('ponto_n', 'N/A')
        massa = ponto.get('massa_g_registrada', 0.0)
        tempo = ponto.get('duracao_real_s', 0.0)
        
        # [MODIFICADO] Exibição dinâmica
        if g_formato_novo:
            pressao_sis = ponto.get('media_pressao_sistema_bar', 0.0)
            pressao_pas = ponto.get('media_pressao_pasta_bar', 0.0)
            print(f"{idx:<4} | {ponto_n:<8} | {pressao_sis:<18.4f} | {pressao_pas:<16.4f} | {massa:<12.3f} | {tempo:<10.2f}")
        else:
            pressao = ponto.get('media_pressao_final_ponto_bar', 0.0)
            print(f"{idx:<4} | {ponto_n:<8} | {pressao:<20.4f} | {massa:<12.3f} | {tempo:<10.2f}")

    if g_formato_novo:
        print("-" * 80)
    else:
        print("-" * 60)


def modificar_ponto(data):
    """[MODIFICADO] Permite ao usuário modificar a massa ou o tempo de um ponto específico."""
    global g_formato_novo, g_chave_pressao_principal
    
    listar_pontos_do_ensaio(data)
    if not data.get('testes'):
        return

    # [MODIFICADO] Usa a chave de pressão correta para ordenar
    testes_ordenados = sorted(data['testes'], key=lambda t: t.get(g_chave_pressao_principal, 0))
    
    while True:
        try:
            idx_str = input(f"Digite o 'Idx' (0 a {len(testes_ordenados)-1}) do ponto a modificar (ou 's' para sair): ").strip()
            if idx_str.lower() == 's':
                break
            
            idx = int(idx_str)
            if 0 <= idx < len(testes_ordenados):
                ponto_original = testes_ordenados[idx]
                
                print(f"\nModificando Ponto Nº {ponto_original.get('ponto_n', 'N/A')} (Idx: {idx})")
                
                # [MODIFICADO] Exibe a(s) pressão(ões) corretas
                if g_formato_novo:
                    print(f"  P. Sistema: {ponto_original.get('media_pressao_sistema_bar', 0.0):.4f} bar")
                    print(f"  P. Pasta:   {ponto_original.get('media_pressao_pasta_bar', 0.0):.4f} bar")
                else:
                    print(f"  Pressão: {ponto_original.get('media_pressao_final_ponto_bar', 0.0):.4f} bar")
                
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
                testes_ordenados = sorted(data['testes'], key=lambda t: t.get(g_chave_pressao_principal, 0))
                listar_pontos_do_ensaio(data) # Mostra a lista atualizada
                
            else:
                print("ERRO: 'Idx' fora do intervalo válido.")
        except ValueError:
            print("ERRO: Entrada inválida. Digite um número.")

def excluir_ponto(data):
    """[MODIFICADO] Permite ao usuário excluir um ponto específico."""
    global g_formato_novo, g_chave_pressao_principal
    
    listar_pontos_do_ensaio(data)
    if not data.get('testes'):
        return False

    # [MODIFICADO] Usa a chave de pressão correta para ordenar
    testes_ordenados = sorted(data['testes'], key=lambda t: t.get(g_chave_pressao_principal, 0))

    while True:
        try:
            idx_str = input(f"Digite o 'Idx' (0 a {len(testes_ordenados)-1}) do ponto a EXCLUIR (ou 's' para sair): ").strip()
            if idx_str.lower() == 's':
                break
            
            idx = int(idx_str)
            if 0 <= idx < len(testes_ordenados):
                ponto_a_excluir_display = testes_ordenados[idx]
                ponto_n_excluir = ponto_a_excluir_display.get('ponto_n', 'N/A')
                
                # [MODIFICADO] Usa a chave de pressão correta para encontrar o ponto
                pressao_referencia = ponto_a_excluir_display.get(g_chave_pressao_principal, 0.0)
                
                # Encontrar o ponto real na lista 'data['testes']' (que não está ordenada)
                ponto_original_para_excluir = None
                for p in data['testes']:
                    if (p.get('ponto_n') == ponto_n_excluir and 
                        abs(p.get(g_chave_pressao_principal, -1) - pressao_referencia) < 1e-6):
                        ponto_original_para_excluir = p
                        break
                
                if ponto_original_para_excluir:
                    confirm = input(f"Tem certeza que deseja EXCLUIR Ponto Nº {ponto_n_excluir} (Idx: {idx})? (s/n): ").lower()
                    if confirm == 's':
                        data['testes'].remove(ponto_original_para_excluir)
                        print(f"Ponto Nº {ponto_n_excluir} (Idx: {idx}) excluído.")
                        # Atualiza a lista ordenada para o próximo loop
                        testes_ordenados = sorted(data['testes'], key=lambda t: t.get(g_chave_pressao_principal, 0))
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
    """[MODIFICADO] Salva os dados modificados usando a chave de ordenação correta."""
    global g_chave_pressao_principal
    
    # Garante que o nome do arquivo de saída comece com 'edit_'
    if nome_arquivo_original.startswith('edit_'):
        nome_arquivo_editado = nome_arquivo_original
    else:
        nome_arquivo_editado = f"edit_{nome_arquivo_original}"
        
    caminho_completo_saida = os.path.join(RESULTS_JSON_DIR, nome_arquivo_editado)
    
    try:
        # [MODIFICADO] Reordena pela chave de pressão correta antes de salvar
        if data.get('testes'):
            data['testes'] = sorted(data['testes'], key=lambda t: t.get(g_chave_pressao_principal, 0))
        
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
            houve_mudanca = True # Assume que modificar sempre muda
        
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
                    continue # Volta ao menu
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
        print("Nenhum arquivo selecionado. Saindo.")

if __name__ == "__main__":
    main()
