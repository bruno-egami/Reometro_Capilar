# -*- coding: utf-8 -*-
"""
SCRIPT PARA CONTROLE DE REÔMETRO CAPILAR COM DUPLO TRANSDUTOR DE PRESSÃO
VERSÃO 3.1 - Dual Sensor (Linha & Pasta) + Diagnóstico Delta P
Autor: Bruno Egami (Modificado por Gemini)
Data: 22/11/2025
"""

import serial
import serial.tools.list_ports
import time
import json
import os
from datetime import datetime
import numpy as np
import glob

# Tenta importar msvcrt para input não bloqueante no Windows
try:
    import msvcrt
    WINDOWS_OS = True
except ImportError:
    WINDOWS_OS = False

# --- Configurações ---
SERIAL_PORT = None 
BAUD_RATE = 115200
TIMEOUT_SERIAL = 2
# [MODIFICADO] Arquivos de calibração separados
CALIBRATION_FILE = 'calibracao_reometro_dual.json' 
RESULTS_JSON_DIR = "resultados_testes_reometro"

# --- NOVAS CONFIGURAÇÕES DE GATILHO DE PRESSÃO ---
PRESSURE_THRESHOLD_START = 0.15 # Pressão em [bar] para iniciar o cronômetro
PRESSURE_THRESHOLD_STOP = 0.10  # Pressão em [bar] para parar o cronômetro
DELTA_P_ALERTA_BAR = 2.0        # Diferença de pressão (Linha - Pasta) para alerta

# --- Variáveis Globais para a Nova Calibração Linear (DUAL) ---
# Sensor 1: Linha (Antigo Barril)
g_calib_slope_linha = None
g_calib_intercept_linha = None
# Sensor 2: Pasta (Antigo Entrada)
g_calib_slope_pasta = None
g_calib_intercept_pasta = None

g_calibracao_concluida = False

# --- Funções de Comunicação com Arduino (Adaptadas) ---

def conectar_arduino(port, baud):
    """Tenta conectar ao Arduino na porta especificada e verifica a comunicação."""
    try:
        ser = serial.Serial(port, baud, timeout=TIMEOUT_SERIAL)
        time.sleep(2) # Aguarda a inicialização do Arduino
        if ser.isOpen():
            print(f"Conectado ao Arduino na porta {port}.")
            ser.flushInput()
            ser.flushOutput()
            ser.write(b"PING\n")
            resposta = ser.readline().decode('utf-8', 'ignore').strip()
            if "ACK_PING_OK" in resposta:
                print("Comunicação PING-ACK com o firmware do transdutor OK.")
                return ser
            else:
                print(f"Falha no PING-ACK. Resposta recebida: '{resposta}'. Verifique o firmware.")
                ser.close()
                return None
    except serial.SerialException as e:
        print(f"Erro ao conectar em {port}: {e}")
        return None

def ler_voltagens_do_arduino(ser, comando_leitura="READ_VOLTAGE", timeout_float=TIMEOUT_SERIAL):
    """
    Envia um comando para o Arduino e espera uma resposta com DUAS tensões (V1;V2).
    Retorna uma tupla (v1, v2) ou (None, None).
    """
    if ser and ser.isOpen():
        ser.write(comando_leitura.encode('utf-8') + b'\n')
        ser.flush()
        start_time = time.time()
        while ser.in_waiting == 0 and (time.time() - start_time) < timeout_float:
            time.sleep(0.01)
        
        if ser.in_waiting > 0:
            resposta_str = ser.readline().decode('utf-8', 'ignore').strip()
            try:
                # Espera formato "V1;V2" ex: "0.004;0.002"
                partes = resposta_str.split(';')
                if len(partes) == 2:
                    return float(partes[0]), float(partes[1])
                else:
                    # Fallback para firmware antigo (apenas 1 valor)
                    val = float(resposta_str)
                    return val, 0.0
            except (ValueError, TypeError):
                return None, None
    return None, None

def input_float_com_virgula(mensagem_prompt, permitir_vazio=False):
    """Pede um número float ao usuário, aceitando ',' como decimal."""
    while True:
        entrada = input(mensagem_prompt).strip()
        if permitir_vazio and entrada == "":
            return None
        try:
            return float(entrada.replace(',', '.'))
        except ValueError:
            print("ERRO: Entrada inválida. Insira um número.")
        except Exception as e:
            print(f"Ocorreu um erro: {e}")

# --- Funções de Validação (NOVO) ---

def validar_ponto(p_linha, p_pasta, massa_g, duracao_s):
    """
    Valida dados coletados antes de salvar.
    Retorna uma ação: 'accept', 'retry', 'skip', 'finish'
    """
    avisos = []
    erros_criticos = []
    
    # Validações CRÍTICAS (bloqueiam salvamento)
    if p_linha <= 0 or p_pasta <= 0:
        erros_criticos.append(f"Pressão inválida/negativa: L={p_linha:.3f}, P={p_pasta:.3f}")
    
    if massa_g <= 0:
        erros_criticos.append(f"Massa inválida: {massa_g:.3f}g")
        
    if duracao_s <= 0:
        erros_criticos.append(f"Duração inválida: {duracao_s:.2f}s")
    
    # Validações de AVISO (permitem override)
    delta_p = abs(p_linha - p_pasta)
    if delta_p > 10:
        avisos.append(f"Delta P muito alto: {delta_p:.2f} bar")
    
    if massa_g < 0.1:
        avisos.append(f"Massa muito baixa: {massa_g:.3f}g")
    
    if massa_g > 500:
        avisos.append(f"Massa muito alta: {massa_g:.3f}g")
    
    if duracao_s < 5:
        avisos.append(f"Duração muito curta: {duracao_s:.1f}s")
    
    if delta_p > 5:
        avisos.append(f"Delta P alto: {delta_p:.2f} bar")
    
    # Lógica de Retorno
    if erros_criticos:
        print("\n" + "!"*60)
        print("❌ ERROS CRÍTICOS DETECTADOS:")
        for erro in erros_criticos:
            print(f"   • {erro}")
        print("!"*60)
        print("\nOpções:")
        print("  1. Repetir coleta deste ponto")
        print("  2. Pular para o próximo ponto (descarta dados)")
        print("  3. Finalizar ensaio agora")
        
        while True:
            escolha = input("\nEscolha (1/2/3): ").strip()
            if escolha == '1': return 'retry'
            if escolha == '2': return 'skip'
            if escolha == '3': return 'finish'
    
    if avisos:
        print("\n" + "="*60)
        print("⚠️  AVISOS DETECTADOS:")
        for aviso in avisos:
            print(f"   • {aviso}")
        print("="*60)
        print("\nOpções:")
        print("  1. Aceitar e salvar ponto")
        print("  2. Repetir coleta deste ponto")
        print("  3. Pular para o próximo ponto (descarta dados)")
        print("  4. Finalizar ensaio agora")
        
        while True:
            escolha = input("\nEscolha (1/2/3/4): ").strip()
            if escolha == '1': return 'accept'
            if escolha == '2': return 'retry'
            if escolha == '3': return 'skip'
            if escolha == '4': return 'finish'
            
    return 'accept'

# --- Funções de Calibração ---

def salvar_dados_calibracao_py(filepath, data):
    """Salva os dados da calibração em um arquivo JSON."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Dados de calibração salvos com sucesso em: {filepath}")
    except IOError as e:
        print(f"Erro ao salvar o arquivo de calibração: {e}")

def carregar_dados_calibracao_py(filepath):
    """Carrega os parâmetros da calibração linear do arquivo JSON."""
    global g_calib_slope_linha, g_calib_intercept_linha
    global g_calib_slope_pasta, g_calib_intercept_pasta
    global g_calibracao_concluida
    
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Tenta carregar formato novo (Dual)
            if "linha" in data and "pasta" in data:
                g_calib_slope_linha = data["linha"]["slope"]
                g_calib_intercept_linha = data["linha"]["intercept"]
                g_calib_slope_pasta = data["pasta"]["slope"]
                g_calib_intercept_pasta = data["pasta"]["intercept"]
                g_calibracao_concluida = True
                print(f"Calibração DUAL carregada de: {filepath}")
                return True
            
            # Fallback para formato antigo (Single) - aplica o mesmo para os dois ou avisa
            elif "slope" in data and "intercept" in data:
                print("AVISO: Arquivo de calibração antigo (sensor único) detectado.")
                print("       Aplicando calibração antiga para AMBOS os sensores provisoriamente.")
                g_calib_slope_linha = data["slope"]
                g_calib_intercept_linha = data["intercept"]
                g_calib_slope_pasta = data["slope"] # Assume igual
                g_calib_intercept_pasta = data["intercept"]
                g_calibracao_concluida = True
                return True
            else:
                print(f"ERRO: Formato inválido em '{filepath}'. Recalibre.")
                g_calibracao_concluida = False
        except Exception as e:
            print(f"Erro ao carregar calibração: {e}")
            g_calibracao_concluida = False
    else:
        print(f"Arquivo '{filepath}' não encontrado. Calibração necessária.")
        g_calibracao_concluida = False
    return False

def realizar_calibracao_interativa_py(ser):
    """Guia o usuário através de uma calibração linear de 2 pontos para AMBOS os sensores."""
    global g_calib_slope_linha, g_calib_intercept_linha
    global g_calib_slope_pasta, g_calib_intercept_pasta
    global g_calibracao_concluida
    
    print("\n" + "="*60)
    print("ASSISTENTE DE CALIBRAÇÃO DUAL (LINHA & PASTA)")
    print("="*60)
    print("Este processo calibrará os dois sensores simultaneamente.")
    
    # --- Ponto 1: Zero Pressão ---
    input("\nPasso 1: Despressurize o sistema (0 bar) e pressione ENTER...")
    
    v1_list, v2_list = [], []
    for _ in range(5):
        v1, v2 = ler_voltagens_do_arduino(ser)
        if v1 is not None:
            v1_list.append(v1); v2_list.append(v2)
        time.sleep(0.1)
    
    if not v1_list:
        print("ERRO: Falha na leitura do Arduino."); return
        
    v1_p1 = np.mean(v1_list)
    v2_p1 = np.mean(v2_list)
    p_p1 = 0.0
    print(f"  -> Zero (0 bar): V_Linha={v1_p1:.4f}V, V_Pasta={v2_p1:.4f}V")

    # --- Ponto 2: Pressão Conhecida ---
    p_p2 = 0.0
    while p_p2 <= 0:
        p_p2 = input_float_com_virgula("\nPasso 2: Aplique uma pressão conhecida (ex: 5.0 bar): ")
        if p_p2 is None or p_p2 <= 0: print("  Valor deve ser > 0.")
            
    input(f"Pressione ENTER para ler as tensões a {p_p2:.2f} bar...")
    
    v1_list, v2_list = [], []
    for _ in range(5):
        v1, v2 = ler_voltagens_do_arduino(ser)
        if v1 is not None:
            v1_list.append(v1); v2_list.append(v2)
        time.sleep(0.1)

    if not v1_list:
        print("ERRO: Falha na leitura."); return
        
    v1_p2 = np.mean(v1_list)
    v2_p2 = np.mean(v2_list)
    print(f"  -> Alta ({p_p2:.2f} bar): V_Linha={v1_p2:.4f}V, V_Pasta={v2_p2:.4f}V")

    # --- Cálculo ---
    if abs(v1_p2 - v1_p1) < 0.01 or abs(v2_p2 - v2_p1) < 0.01:
        print("\nERRO: Variação de tensão muito baixa em um dos sensores.")
        if input("Deseja salvar mesmo assim? (s/n): ").lower() != 's': return

    # Linha (Sensor 1)
    slope_L = (p_p2 - p_p1) / (v1_p2 - v1_p1)
    intercept_L = p_p1 - slope_L * v1_p1
    
    # Pasta (Sensor 2)
    slope_P = (p_p2 - p_p1) / (v2_p2 - v2_p1)
    intercept_P = p_p1 - slope_P * v2_p1

    print("\n" + "-"*25 + " RESULTADOS " + "-"*25)
    print(f"LINHA: P = {slope_L:.4f}*V + {intercept_L:.4f}")
    print(f"PASTA: P = {slope_P:.4f}*V + {intercept_P:.4f}")

    g_calib_slope_linha = slope_L; g_calib_intercept_linha = intercept_L
    g_calib_slope_pasta = slope_P; g_calib_intercept_pasta = intercept_P
    g_calibracao_concluida = True
    
    dados = {
        "linha": {"slope": slope_L, "intercept": intercept_L},
        "pasta": {"slope": slope_P, "intercept": intercept_P},
        "data": datetime.now().strftime("%Y-%m-%d")
    }
    salvar_dados_calibracao_py(CALIBRATION_FILE, dados)

def visualizar_pontos_calibracao_py():
    print("\n=== CALIBRAÇÃO DUAL ===")
    if g_calibracao_concluida:
        print(f"LINHA: {g_calib_slope_linha:.4f} * V + {g_calib_intercept_linha:.4f}")
        print(f"PASTA: {g_calib_slope_pasta:.4f} * V + {g_calib_intercept_pasta:.4f}")
    else:
        print("Nenhuma calibração carregada.")

def converter_tensoes_para_pressoes(v1, v2):
    """Converte V1 e V2 para P_Linha e P_Pasta."""
    if not g_calibracao_concluida: return -1.0, -1.0
    
    p1 = (g_calib_slope_linha * v1) + g_calib_intercept_linha
    p2 = (g_calib_slope_pasta * v2) + g_calib_intercept_pasta
    return max(p1, 0), max(p2, 0)

# --- Funções de Coleta e Salvamento ---

def salvar_resultados_json_individual_py(data_bateria, json_filename=None):
    """Salva os dados completos de um ensaio em um arquivo JSON único."""
    if not data_bateria or not data_bateria.get('testes'):
        print("Nenhum dado de teste para salvar.")
        return
        
    def sanitize_filename(name):
        return "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()[:50].replace(' ', '_')

    if json_filename:
        filename = os.path.join(RESULTS_JSON_DIR, json_filename)
        print(f"\nCONTINUAÇÃO: Atualizando: {json_filename}")
    else:
        base_filename = data_bateria.get('id_amostra') or 'resultado_teste'
        sane_basename = sanitize_filename(base_filename)
        timestamp_str_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(RESULTS_JSON_DIR, f"{sane_basename}_{timestamp_str_file}.json")
    
    if not os.path.exists(RESULTS_JSON_DIR): os.makedirs(RESULTS_JSON_DIR)
        
    try:
        # Ordena por pressão da LINHA (Sensor 1) como referência principal
        data_bateria['testes'] = sorted(data_bateria['testes'], key=lambda t: t.get('media_pressao_linha_bar', 0))
        data_bateria["data_hora_ultima_coleta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_bateria, f, indent=4, ensure_ascii=False)
        print(f"\nSalvo em: {filename}")
    except IOError as e:
        print(f"Erro ao salvar JSON: {e}")

def executar_ciclo_preview_e_reset(ser):
    """Ciclo de condicionamento usando P.LINHA como gatilho."""
    print("\n" + "="*50)
    print("--- CICLO DE PRÉ-VISUALIZAÇÃO ---")
    print(f"1. APLICAR PRESSÃO (Linha > {PRESSURE_THRESHOLD_START:.2f} bar).")
    print("   (Pressione 'c' para CANCELAR)")
    print("="*50)
    
    pressure_triggered = False
    
    while not pressure_triggered:
        v1, v2 = ler_voltagens_do_arduino(ser)
        if v1 is not None:
            p1, p2 = converter_tensoes_para_pressoes(v1, v2)
            print(f"  P.Linha: {p1:.2f} | P.Pasta: {p2:.2f} bar   \r", end="")
            
            if WINDOWS_OS and msvcrt.kbhit():
                if msvcrt.getch().lower() == b'c': return False
                 
            if p1 > PRESSURE_THRESHOLD_START:
                pressure_triggered = True
                print(f"\nCiclo INICIADO! (P.Linha: {p1:.2f} bar)")
                break
        time.sleep(0.1)
    
    print(f"2. ALIVIAR PRESSÃO (Linha < {PRESSURE_THRESHOLD_STOP:.2f} bar).")
    max_p = 0
    while True:
        v1, v2 = ler_voltagens_do_arduino(ser)
        if v1 is not None:
            p1, p2 = converter_tensoes_para_pressoes(v1, v2)
            max_p = max(max_p, p1)
            print(f"  P.Linha: {p1:.2f} | P.Pasta: {p2:.2f} | Máx: {max_p:.2f}   \r", end="")

            if p1 < PRESSURE_THRESHOLD_STOP:
                print(f"\n[OK] Repouso atingido. PRONTO PARA MEDIR.")
                return True
        time.sleep(0.1)


def realizar_coleta_de_teste_py(ser, data_bateria=None, json_filename=None):
    """Função principal de coleta."""
    is_continuation = data_bateria is not None
    
    if not g_calibracao_concluida:
        print("\nERRO: Calibração necessária.")
        return

    print("\n" + "="*60)
    if is_continuation:
        print(f"CONTINUANDO ENSAIO: {json_filename}")
        # Ordena e mostra últimos pontos
        data_bateria['testes'] = sorted(data_bateria['testes'], key=lambda t: t.get('media_pressao_linha_bar', 0))
        num_pontos_existentes = len(data_bateria['testes'])
        print(f"Pontos existentes: {num_pontos_existentes}")
        num_ponto_inicial = num_pontos_existentes + 1
    else:
        print("NOVA COLETA DE DADOS REOLÓGICOS")
        num_ponto_inicial = 1
    print("="*60)
    
    if not is_continuation:
        id_amostra = input("ID da amostra: ")
        descricao = input("Descrição: ")
        D_cap_mm = input_float_com_virgula("D capilar [mm]: ")
        L_cap_mm = input_float_com_virgula("L capilar [mm]: ")
        rho_g_cm3 = input_float_com_virgula("Densidade [g/cm³]: ")

        if any(p is None or p <= 0 for p in [D_cap_mm, L_cap_mm, rho_g_cm3]):
             print("ERRO: Parâmetros inválidos."); return

        data_bateria = {
            "id_amostra": id_amostra,
            "descricao": descricao,
            "data_hora_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "diametro_capilar_mm": D_cap_mm,
            "comprimento_capilar_mm": L_cap_mm,
            "densidade_pasta_g_cm3": rho_g_cm3,
            "calibracao_aplicada": {
                "linha": {"slope": g_calib_slope_linha, "intercept": g_calib_intercept_linha},
                "pasta": {"slope": g_calib_slope_pasta, "intercept": g_calib_intercept_pasta}
            },
            "testes": []
        }

    num_ponto = num_ponto_inicial
    
    while True:
        print("\n" + "-"*20 + f" PONTO Nº {num_ponto} " + "-"*20)
        
        # Loop de repetição do ponto (caso o usuário escolha 'retry')
        while True:
            if not executar_ciclo_preview_e_reset(ser): 
                return # Sai da função se cancelar no preview
            
            print(f"INICIANDO MEDIÇÃO REAL (Aguardando P.Linha > {PRESSURE_THRESHOLD_START:.2f} bar)...")
            
            start_time = time.time()
            pressure_triggered = False

            while not pressure_triggered:
                v1, v2 = ler_voltagens_do_arduino(ser)
                if v1 is not None:
                    p1, p2 = converter_tensoes_para_pressoes(v1, v2)
                    print(f"  P.Linha: {p1:.2f} | P.Pasta: {p2:.2f}   \r", end="")
                    if p1 > PRESSURE_THRESHOLD_START:
                        start_time = time.time()
                        pressure_triggered = True
                        print(f"\nINÍCIO! Cronômetro rodando.")
                        break
                time.sleep(0.1)
            
            if not pressure_triggered: continue

            print(f"MEDINDO... (Parar quando P.Linha < {PRESSURE_THRESHOLD_STOP:.2f} bar)")
            leituras_p1, leituras_p2 = [], []
            leituras_v1, leituras_v2 = [], []
            
            while True:
                v1, v2 = ler_voltagens_do_arduino(ser)
                if v1 is not None:
                    p1, p2 = converter_tensoes_para_pressoes(v1, v2)
                    leituras_p1.append(p1); leituras_p2.append(p2)
                    leituras_v1.append(v1); leituras_v2.append(v2)
                    
                    t_dec = time.time() - start_time
                    
                    # DIAGNÓSTICO DELTA P
                    delta_p = p1 - p2
                    diag_msg = ""
                    if delta_p > DELTA_P_ALERTA_BAR:
                        diag_msg = f" [ALERTA: Delta P Alto! {delta_p:.1f} bar]"
                    
                    print(f"  L: {p1:.2f} | P: {p2:.2f} | t: {t_dec:.1f}s{diag_msg}   \r", end="")

                    if p1 < PRESSURE_THRESHOLD_STOP:
                        end_time = time.time()
                        print(f"\nFIM! (Última P.Linha: {p1:.2f} bar)")
                        break
                time.sleep(0.1)
                
            duracao_s = end_time - start_time
            print(f"  -> Duração: {duracao_s:.2f} s")
            
            massa_g = input_float_com_virgula("Massa extrudada [g]: ")
            if massa_g is None: massa_g = 0.0 # Trata cancelamento como 0 para validar

            p1_med = np.mean(leituras_p1) if leituras_p1 else 0
            p2_med = np.mean(leituras_p2) if leituras_p2 else 0
            v1_med = np.mean(leituras_v1) if leituras_v1 else 0
            v2_med = np.mean(leituras_v2) if leituras_v2 else 0
            
            print(f"  -> Médias: P.Linha={p1_med:.3f} bar, P.Pasta={p2_med:.3f} bar")
            
            # --- VALIDAÇÃO ---
            acao = validar_ponto(p1_med, p2_med, massa_g, duracao_s)
            
            if acao == 'retry':
                print("\n--> Reiniciando coleta deste ponto...")
                continue # Volta para o início do loop 'while True' interno (preview)
            elif acao == 'skip':
                print("\n--> Ponto pulado. Dados descartados.")
                break # Sai do loop interno, vai para o próximo ponto
            elif acao == 'finish':
                print("\n--> Finalizando ensaio e salvando...")
                salvar_resultados_json_individual_py(data_bateria, json_filename)
                return
            elif acao == 'accept':
                # Salva o ponto
                ponto_atual = {
                    "ponto_n": num_ponto,
                    "massa_g_registrada": massa_g, 
                    "duracao_real_s": duracao_s,
                    "media_tensao_linha_V": v1_med,
                    "media_tensao_pasta_V": v2_med,
                    "media_pressao_linha_bar": p1_med,
                    "media_pressao_pasta_bar": p2_med,
                    "media_pressao_final_ponto_bar": p1_med 
                }
                data_bateria["testes"].append(ponto_atual)
                print(f"--> Ponto {num_ponto} salvo com sucesso.")
                break # Sai do loop interno, vai para o próximo ponto
        
        # Pergunta se quer continuar (se não tiver finalizado)
        if input("\nAdicionar outro ponto? (s/n): ").lower() != 's': break
        num_ponto += 1
        
    salvar_resultados_json_individual_py(data_bateria, json_filename)

def selecionar_json_existente(pasta_json):
    """Lista JSONs para continuação."""
    print("\n" + "="*60)
    print("--- SELECIONAR ARQUIVO JSON PARA CONTINUIDADE ---")
    print("="*60)
    if not os.path.exists(pasta_json):
        print(f"ERRO: Pasta '{pasta_json}' não encontrada.")
        return None, None
        
    arquivos_raw = sorted([f for f in os.listdir(pasta_json) if f.endswith('.json') and not f.startswith('edit_')], reverse=True)
    
    if not arquivos_raw:
        print(f"Nenhum arquivo encontrado."); return None, None
    
    for i, arq in enumerate(arquivos_raw):
        print(f"  {i+1}: {arq}")
    
    while True:
        try:
            escolha_str = input("\nEscolha o NÚMERO (ou '0'): ").strip()
            if escolha_str == '0': return None, None
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_raw):
                arq = arquivos_raw[escolha_num - 1]
                with open(os.path.join(pasta_json, arq), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data, arq
        except: pass

def realizar_coleta_de_continuacao(ser, data_existente, nome_arquivo_existente):
    realizar_coleta_de_teste_py(ser, data_bateria=data_existente, json_filename=nome_arquivo_existente)

def encontrar_e_conectar_arduino():
    print("Procurando Arduino...")
    portas = serial.tools.list_ports.comports()
    for p in portas:
        if "USB" in p.description.upper() or "ARDUINO" in p.description.upper() or "CH340" in p.description.upper():
            print(f"Tentando {p.device}...")
            ser = conectar_arduino(p.device, BAUD_RATE)
            if ser: return ser
    return None

def menu_principal_py(ser):
    while True:
        print("\n" + "="*20 + " MENU REÔMETRO DUAL " + "="*20)
        print("1. NOVA Coleta")
        print("2. CONTINUAR Coleta")
        print("3. CALIBRAR (Linha & Pasta)")
        print("4. Ver Calibração")
        print("5. Ler Pressões (Monitor)")
        print("0. Sair")
        
        escolha = input("Opção: ")

        if escolha == '1':
            if ser: realizar_coleta_de_teste_py(ser)
            else: print("Sem conexão.")
        elif escolha == '2':
            if ser:
                data, nome = selecionar_json_existente(RESULTS_JSON_DIR)
                if data: realizar_coleta_de_continuacao(ser, data, nome)
            else: print("Sem conexão.")
        elif escolha == '3':
            if ser: realizar_calibracao_interativa_py(ser)
            else: print("Sem conexão.")
        elif escolha == '4':
            visualizar_pontos_calibracao_py()
        elif escolha == '5':
            if ser and g_calibracao_concluida:
                try:
                    print("\nCTRL+C para parar.")
                    while True:
                        v1, v2 = ler_voltagens_do_arduino(ser)
                        if v1 is not None:
                            p1, p2 = converter_tensoes_para_pressoes(v1, v2)
                            print(f"Linha: {p1:.2f} bar | Pasta: {p2:.2f} bar   \r", end="")
                        time.sleep(0.25)
                except KeyboardInterrupt: pass
            else: print("Sem conexão ou calibração.")
        elif escolha == '0': break

if __name__ == "__main__":
    if not os.path.exists(RESULTS_JSON_DIR): os.makedirs(RESULTS_JSON_DIR)
    arduino_ser = None
    try:
        if SERIAL_PORT: arduino_ser = conectar_arduino(SERIAL_PORT, BAUD_RATE)
        else: arduino_ser = encontrar_e_conectar_arduino()

        if not arduino_ser:
            print("\nAVISO: Arduino não encontrado.")
            if input("Continuar offline? (s/n):").lower() != 's': exit()
        
        carregar_dados_calibracao_py(CALIBRATION_FILE)
        menu_principal_py(arduino_ser)

    except Exception as e:
        print(f"Erro fatal: {e}")
    finally:
        if arduino_ser and arduino_ser.isOpen(): arduino_ser.close()