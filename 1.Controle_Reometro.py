# -*- coding: utf-8 -*-
"""
SCRIPT PARA CONTROLE DE REÔMETRO CAPILAR COM DOIS TRANSDUTORES DE PRESSÃO
VERSÃO 3.0 - Suporte a Transdutor de Sistema (Pistão) e Transdutor de Pasta (Capilar)
Autor: Bruno Egami (Modificado por Gemini)
Data: 04/11/2025
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
CALIBRATION_FILE_SISTEMA = 'calibracao_reometro_sistema.json' # Sensor 1 (Original)
CALIBRATION_FILE_PASTA = 'calibracao_reometro_pasta.json'     # Sensor 2 (Novo, 0-10 bar)
RESULTS_JSON_DIR = "resultados_testes_reometro"

# --- CONFIGURAÇÕES DE GATILHO DE PRESSÃO (Baseado no Sensor de SISTEMA) ---
PRESSURE_THRESHOLD_START = 0.15 # Pressão em [bar] para iniciar o cronômetro (lida do Sensor de Sistema)
PRESSURE_THRESHOLD_STOP = 0.10  # Pressão em [bar] para parar o cronômetro (lida do Sensor de Sistema)

# --- [MODIFICADO] Variáveis Globais para Calibração (Sistema) ---
g_calibracao_slope_sistema = None
g_calibracao_intercept_sistema = None
g_calibracao_concluida_sistema = False

# --- [NOVO] Variáveis Globais para Calibração (Pasta) ---
g_calibracao_slope_pasta = None
g_calibracao_intercept_pasta = None
g_calibracao_concluida_pasta = False

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
            # Envia um comando PING para verificar se o firmware correto está rodando
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

def ler_float_do_arduino(ser, comando_leitura="READ_VOLTAGE_SISTEMA", timeout_float=TIMEOUT_SERIAL):
    """
    [MODIFICADO] Envia um comando específico para o Arduino e espera uma resposta float (tensão).
    Comandos esperados do Arduino:
    - "READ_VOLTAGE_SISTEMA" (Sensor 1)
    - "READ_VOLTAGE_PASTA" (Sensor 2)
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
                return float(resposta_str)
            except (ValueError, TypeError):
                # print(f"Erro: Resposta do Arduino ('{resposta_str}') não é um float válido.")
                return None
    return None

def input_float_com_virgula(mensagem_prompt, permitir_vazio=False):
    """Pede um número float ao usuário, aceitando ',' como decimal. Permite entrada vazia opcionalmente."""
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

# --- Funções de Calibração ---

def salvar_dados_calibracao_py(filepath, data):
    """Salva os dados da calibração (slope, intercept) em um arquivo JSON."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Dados de calibração salvos com sucesso em: {filepath}")
    except IOError as e:
        print(f"Erro ao salvar o arquivo de calibração: {e}")

# [MODIFICADO] Função para carregar Sensor 1 (Sistema)
def carregar_calibracao_sistema(filepath):
    """Carrega os parâmetros da calibração (Sistema) do arquivo JSON."""
    global g_calibracao_slope_sistema, g_calibracao_intercept_sistema, g_calibracao_concluida_sistema
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "slope" in data and "intercept" in data:
                g_calibracao_slope_sistema = data["slope"]
                g_calibracao_intercept_sistema = data["intercept"]
                g_calibracao_concluida_sistema = True
                print(f"Dados de calibração (Sistema) carregados de: {filepath}")
                print(f"  -> Eq. Sistema: Pressão = {g_calibracao_slope_sistema:.4f} * Tensão + {g_calibracao_intercept_sistema:.4f}")
                return True
            else:
                print(f"ERRO: Arquivo '{filepath}' (Sistema) não contém 'slope' e 'intercept'.")
                g_calibracao_concluida_sistema = False
        except Exception as e:
            print(f"Erro ao carregar o arquivo de calibração (Sistema): {e}")
            g_calibracao_concluida_sistema = False
    else:
        print(f"Arquivo de calibração (Sistema) '{filepath}' não encontrado. É necessário calibrar.")
        g_calibracao_concluida_sistema = False
    return False

# [NOVO] Função para carregar Sensor 2 (Pasta)
def carregar_calibracao_pasta(filepath):
    """Carrega os parâmetros da calibração (Pasta) do arquivo JSON."""
    global g_calibracao_slope_pasta, g_calibracao_intercept_pasta, g_calibracao_concluida_pasta
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "slope" in data and "intercept" in data:
                g_calibracao_slope_pasta = data["slope"]
                g_calibracao_intercept_pasta = data["intercept"]
                g_calibracao_concluida_pasta = True
                print(f"Dados de calibração (Pasta) carregados de: {filepath}")
                print(f"  -> Eq. Pasta: Pressão = {g_calibracao_slope_pasta:.4f} * Tensão + {g_calibracao_intercept_pasta:.4f}")
                return True
            else:
                print(f"ERRO: Arquivo '{filepath}' (Pasta) não contém 'slope' e 'intercept'.")
                g_calibracao_concluida_pasta = False
        except Exception as e:
            print(f"Erro ao carregar o arquivo de calibração (Pasta): {e}")
            g_calibracao_concluida_pasta = False
    else:
        print(f"Arquivo de calibração (Pasta) '{filepath}' não encontrado. É necessário calibrar.")
        g_calibracao_concluida_pasta = False
    return False

# [NOVO] Função genérica para realizar calibração interativa
def realizar_calibracao_interativa_generica(ser, nome_sensor, comando_arduino, arquivo_calibracao):
    """Guia o usuário através de uma calibração linear de 2 pontos para um sensor específico."""
    
    print("\n" + "="*60)
    print(f"ASSISTENTE DE CALIBRAÇÃO DO TRANSDUTOR: {nome_sensor.upper()}")
    print("="*60)
    
    # --- Ponto 1: Zero Pressão ---
    input(f"\nPasso 1 ({nome_sensor}): Despressurize o sistema e pressione ENTER para ler a tensão de base (0 bar)...")
    
    leituras_p1 = [ler_float_do_arduino(ser, comando_arduino) for _ in range(5)]
    leituras_p1 = [v for v in leituras_p1 if v is not None]
    
    if not leituras_p1:
        print("ERRO: Não foi possível ler a tensão do Arduino. Verifique a conexão. Abortando.")
        return False
        
    tensao_p1 = np.mean(leituras_p1)
    pressao_p1 = 0.0
    print(f"  -> Tensão média a {pressao_p1:.1f} bar: {tensao_p1:.4f} V")

    # --- Ponto 2: Pressão Conhecida ---
    pressao_p2 = 0.0
    while pressao_p2 <= 0:
        # [NOVO] Adicionada sugestão para o sensor de pasta (0-10 bar)
        sugestao = "(ex: 5.0)" if nome_sensor == "Pasta" else "(ex: 50.0)"
        pressao_p2 = input_float_com_virgula(f"\nPasso 2 ({nome_sensor}): Aplique uma pressão conhecida {sugestao} e digite o valor em [bar]: ")
        if pressao_p2 is None or pressao_p2 <= 0:
             print("  A pressão deve ser um número maior que zero.")
            
    input(f"Pressione ENTER para ler a tensão correspondente a {pressao_p2:.2f} bar...")
    
    leituras_p2 = [ler_float_do_arduino(ser, comando_arduino) for _ in range(5)]
    leituras_p2 = [v for v in leituras_p2 if v is not None]

    if not leituras_p2:
        print("ERRO: Não foi possível ler a tensão do Arduino. Abortando.")
        return False
        
    tensao_p2 = np.mean(leituras_p2)
    print(f"  -> Tensão média a {pressao_p2:.2f} bar: {tensao_p2:.4f} V")

    # --- Cálculo dos Parâmetros da Reta ---
    if abs(tensao_p2 - tensao_p1) < 0.01: 
        print("\nERRO DE CALIBRAÇÃO: A variação de tensão é muito pequena.")
        return False

    slope = (pressao_p2 - pressao_p1) / (tensao_p2 - tensao_p1)
    intercept = pressao_p1 - slope * tensao_p1

    print("\n" + "-"*20 + f" CALIBRAÇÃO {nome_sensor.upper()} CONCLUÍDA " + "-"*20)
    print(f"Slope (a):     {slope:.4f} bar/V")
    print(f"Intercept (b): {intercept:.4f} bar")
    print(f"EQUAÇÃO FINAL: Pressão [bar] = {slope:.4f} * Tensão [V] + {intercept:.4f}")

    # Salva no arquivo
    dados_calibracao = {"slope": slope, "intercept": intercept, "units": "bar/V"}
    salvar_dados_calibracao_py(arquivo_calibracao, dados_calibracao)
    
    # Recarrega os dados na memória
    return True

# [MODIFICADO] Wrapper para calibração do Sistema
def realizar_calibracao_sistema(ser):
    if realizar_calibracao_interativa_generica(ser, "Sistema", "READ_VOLTAGE_SISTEMA", CALIBRATION_FILE_SISTEMA):
        carregar_calibracao_sistema(CALIBRATION_FILE_SISTEMA)

# [NOVO] Wrapper para calibração da Pasta
def realizar_calibracao_pasta(ser):
    if realizar_calibracao_interativa_generica(ser, "Pasta", "READ_VOLTAGE_PASTA", CALIBRATION_FILE_PASTA):
        carregar_calibracao_pasta(CALIBRATION_FILE_PASTA)

# [MODIFICADO] Visualizar Sensor 1 (Sistema)
def visualizar_calibracao_sistema():
    """Mostra a calibração (Sistema) atualmente carregada."""
    print("\n=== CALIBRAÇÃO ATUAL (SISTEMA) ===")
    if g_calibracao_concluida_sistema:
        print(f"  Slope (a):     {g_calibracao_slope_sistema:.4f} bar/V")
        print(f"  Intercept (b): {g_calibracao_intercept_sistema:.4f} bar")
        print(f"  Equação: Pressão = {g_calibracao_slope_sistema:.4f} * Tensão + {g_calibracao_intercept_sistema:.4f}")
    else:
        print("Nenhuma calibração (Sistema) válida carregada. Por favor, realize a calibração.")

# [NOVO] Visualizar Sensor 2 (Pasta)
def visualizar_calibracao_pasta():
    """Mostra a calibração (Pasta) atualmente carregada."""
    print("\n=== CALIBRAÇÃO ATUAL (PASTA) ===")
    if g_calibracao_concluida_pasta:
        print(f"  Slope (a):     {g_calibracao_slope_pasta:.4f} bar/V")
        print(f"  Intercept (b): {g_calibracao_intercept_pasta:.4f} bar")
        print(f"  Equação: Pressão = {g_calibracao_slope_pasta:.4f} * Tensão + {g_calibracao_intercept_pasta:.4f}")
    else:
        print("Nenhuma calibração (Pasta) válida carregada. Por favor, realize a calibração.")

# [MODIFICADO] Conversor Sensor 1 (Sistema)
def converter_tensao_para_pressao_sistema(tensao_lida):
    """Converte tensão (Sistema) para pressão usando a calibração carregada."""
    if not g_calibracao_concluida_sistema or tensao_lida is None:
        return 0.0 # Retorna 0 se não houver calibração ou tensão
    
    pressao = (g_calibracao_slope_sistema * tensao_lida) + g_calibracao_intercept_sistema
    return max(pressao, 0) # Garante que a pressão nunca seja negativa

# [NOVO] Conversor Sensor 2 (Pasta)
def converter_tensao_para_pressao_pasta(tensao_lida):
    """Converte tensão (Pasta) para pressão usando a calibração carregada."""
    if not g_calibracao_concluida_pasta or tensao_lida is None:
        return 0.0 # Retorna 0 se não houver calibração ou tensão
    
    # O sensor de 0-10 bar (0.5-4.5V) pode ter uma calibração diferente
    pressao = (g_calibracao_slope_pasta * tensao_lida) + g_calibracao_intercept_pasta
    return max(pressao, 0) # Garante que a pressão nunca seja negativa

# --- Funções de Coleta e Salvamento ---

def salvar_resultados_json_individual_py(data_bateria, json_filename=None):
    """Salva os dados completos de um ensaio em um arquivo JSON único."""
    # (Esta função não precisa de modificação, pois salva o dict 'data_bateria' que conterá os novos dados)
    if not data_bateria or not data_bateria.get('testes'):
        print("Nenhum dado de teste para salvar.")
        return
        
    def sanitize_filename(name):
        return "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()[:50].replace(' ', '_')

    if json_filename:
        filename = os.path.join(RESULTS_JSON_DIR, json_filename)
        print(f"\nCONTINUAÇÃO: Sobrescrevendo o arquivo existente: {json_filename}")
    else:
        base_filename = data_bateria.get('id_amostra') or 'resultado_teste'
        sane_basename = sanitize_filename(base_filename)
        timestamp_str_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(RESULTS_JSON_DIR, f"{sane_basename}_{timestamp_str_file}.json")
    
    if not os.path.exists(RESULTS_JSON_DIR):
        os.makedirs(RESULTS_JSON_DIR)
        
    try:
        # [MODIFICADO] Ordena pela pressão do SISTEMA
        data_bateria['testes'] = sorted(data_bateria['testes'], key=lambda t: t.get('media_pressao_sistema_bar', 0))
        data_bateria["data_hora_ultima_coleta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_bateria, f, indent=4, ensure_ascii=False)
        print(f"\nResultados do ensaio salvos/atualizados com sucesso em: {filename}")
    except IOError as e:
        print(f"Erro ao salvar resultados em JSON: {e}")

def executar_ciclo_preview_e_reset(ser):
    """
    [MODIFICADO] Executa um ciclo de pré-visualização OBRIGATÓRIO.
    Monitora a pressão do SISTEMA (> START) e espera o RESET (< STOP).
    Exibe a pressão de AMBOS os sensores.
    
    Retorna True se o ciclo foi concluído e o sistema está pronto.
    Retorna False se o usuário CANCELAR.
    """
    print("\n" + "="*50)
    print("--- CICLO DE PRÉ-VISUALIZAÇÃO (AJUSTE E CONDICIONAMENTO) ---")
    print(f"1. APLICAR PRESSÃO (Gatilho no Sensor de Sistema > {PRESSURE_THRESHOLD_START:.2f} bar)")
    print("   (Pressione 'c' e ENTER a qualquer momento para CANCELAR a medição.)")
    print("="*50)
    
    start_time_preview = time.time()
    pressure_triggered = False
    
    while not pressure_triggered:
        # [MODIFICADO] Ler ambos os sensores
        tensao_sis = ler_float_do_arduino(ser, "READ_VOLTAGE_SISTEMA")
        tensao_pas = ler_float_do_arduino(ser, "READ_VOLTAGE_PASTA")
        
        pressao_sis = converter_tensao_para_pressao_sistema(tensao_sis)
        pressao_pas = converter_tensao_para_pressao_pasta(tensao_pas)
        
        # [MODIFICADO] Exibir ambos
        print(f"  Sistema: {pressao_sis:.2f} bar | Pasta: {pressao_pas:.2f} bar (PREVIEW)   \r", end="")
        
        # Checagem de cancelamento
        if WINDOWS_OS and msvcrt.kbhit():
            char = msvcrt.getch()
            if char.lower() == b'c':
                 print("\nCiclo de Preview CANCELADO pelo usuário.")
                 return False
        
        # [MODIFICADO] Gatilho baseado apenas no sensor de Sistema
        if pressao_sis > PRESSURE_THRESHOLD_START:
            start_time_preview = time.time()
            pressure_triggered = True
            print(f"\nCiclo INICIADO! (Início Sistema: {pressao_sis:.2f} bar | Pasta: {pressao_pas:.2f} bar)")
            break
        
        time.sleep(0.1)
    
    if not pressure_triggered:
        print("\nAVISO: Falha na detecção do início do ciclo de preview.")
        return True # Permite continuar mesmo assim

    # Fase 2: Espera pelo reset (alívio da pressão) - AUTOMÁTICO
    print(f"2. ALIVIAR PRESSÃO (Gatilho no Sensor de Sistema < {PRESSURE_THRESHOLD_STOP:.2f} bar)")
    
    max_pressure_sis = 0
    max_pressure_pas = 0
    
    while True:
        tensao_sis = ler_float_do_arduino(ser, "READ_VOLTAGE_SISTEMA")
        tensao_pas = ler_float_do_arduino(ser, "READ_VOLTAGE_PASTA")
        
        pressao_sis = converter_tensao_para_pressao_sistema(tensao_sis)
        pressao_pas = converter_tensao_para_pressao_pasta(tensao_pas)

        max_pressure_sis = max(max_pressure_sis, pressao_sis)
        max_pressure_pas = max(max_pressure_pas, pressao_pas)
        
        # [MODIFICADO] Exibir ambos
        print(f"  Sis: {pressao_sis:.2f} (Máx {max_pressure_sis:.2f}) | Pas: {pressao_pas:.2f} (Máx {max_pressure_pas:.2f})   \r", end="")

        # [MODIFICADO] Gatilho baseado apenas no sensor de Sistema
        if pressao_sis < PRESSURE_THRESHOLD_STOP:
            print(f"\n[OK] Pressão de repouso (Sistema) atingida. Início do ponto de MEDIÇÃO REAL.")
            return True # Condicionamento concluído
        
        time.sleep(0.1)


def realizar_coleta_de_teste_py(ser, data_bateria=None, json_filename=None):
    """[MODIFICADO] Função principal para guiar o usuário na coleta de dados,
       lendo ambos os transdutores."""
    
    is_continuation = data_bateria is not None
    
    # [MODIFICADO] Verifica ambas as calibrações
    if not g_calibracao_concluida_sistema or not g_calibracao_concluida_pasta:
        print("\nERRO: É necessário realizar ou carregar a calibração de AMBOS os sensores (Sistema e Pasta).")
        visualizar_calibracao_sistema()
        visualizar_calibracao_pasta()
        return

    print("\n" + "="*60)
    if is_continuation:
        print(f"CONTINUANDO ENSAIO: {json_filename}")
        print(f"Amostra: {data_bateria.get('id_amostra', 'N/A')}")
        
        # [MODIFICADO] Ordena pela pressão do SISTEMA
        data_bateria['testes'] = sorted(data_bateria['testes'], key=lambda t: t.get('media_pressao_sistema_bar', 0))
        num_pontos_existentes = len(data_bateria['testes'])
        print(f"Pontos existentes: {num_pontos_existentes}")

        if num_pontos_existentes > 0:
            print("\nÚLTIMOS PONTOS REGISTRADOS (para referência):")
            pontos_recentes = data_bateria['testes'][-min(3, num_pontos_existentes):]
            # [MODIFICADO] Exibe pressão do Sistema e da Pasta
            print(f"{'Ponto':<6} | {'P. Sistema (bar)':<17} | {'P. Pasta (bar)':<15} | {'Massa (g)':<10} | {'Tempo (s)':<10}")
            print("-" * 62)
            for p in pontos_recentes:
                pressao_sis = p.get('media_pressao_sistema_bar', 0.0)
                pressao_pas = p.get('media_pressao_pasta_bar', 0.0) # [NOVO]
                massa = p.get('massa_g_registrada', 0.0)
                tempo = p.get('duracao_real_s', 0.0)
                print(f"{p.get('ponto_n', 'N/A'):<6} | {pressao_sis:<17.3f} | {pressao_pas:<15.3f} | {massa:<10.3f} | {tempo:<10.2f}")
            print("-" * 62)

        num_ponto_inicial = num_pontos_existentes + 1
        
    else:
        print("ASSISTENTE DE NOVA COLETA DE DADOS REOLÓGICOS")
        num_ponto_inicial = 1
    print("="*60)
    
    if not is_continuation:
        id_amostra = input("ID ou nome da amostra: ")
        descricao = input("Descrição breve do ensaio: ")
        
        D_cap_mm = input_float_com_virgula("Diâmetro do capilar [mm]: ")
        L_cap_mm = input_float_com_virgula("Comprimento do capilar [mm]: ")
        rho_g_cm3 = input_float_com_virgula("Densidade da pasta [g/cm³]: ")

        if any(p is None or p <= 0 for p in [D_cap_mm, L_cap_mm, rho_g_cm3]):
             print("ERRO: Parâmetros geométricos ou densidade devem ser números positivos. Abortando coleta.")
             return

        data_bateria = {
            "id_amostra": id_amostra,
            "descricao": descricao,
            "data_hora_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "diametro_capilar_mm": D_cap_mm,
            "comprimento_capilar_mm": L_cap_mm,
            "densidade_pasta_g_cm3": rho_g_cm3,
            # [MODIFICADO] Salva ambas as calibrações
            "calibracao_aplicada_sistema": {
                "slope": g_calibracao_slope_sistema,
                "intercept": g_calibracao_intercept_sistema
            },
            "calibracao_aplicada_pasta": {
                "slope": g_calibracao_slope_pasta,
                "intercept": g_calibracao_intercept_pasta
            },
            "testes": []
        }

    num_ponto = num_ponto_inicial
    
    # --- Loop de Coleta de Pontos ---
    while True:
        print("\n" + "-"*20 + f" PONTO DE MEDIÇÃO Nº {num_ponto} " + "-"*20)
        
        # Etapa 0: PRÉ-MEDIÇÃO OBRIGATÓRIA (Preview/Condicionamento)
        if not executar_ciclo_preview_e_reset(ser):
             break 
        
        # Etapa 1: Aguardando o início do ensaio REAL (Gatilho no Sensor de Sistema)
        print(f"INICIANDO MEDIÇÃO. Aguardando pressão (Sistema) > {PRESSURE_THRESHOLD_START:.2f} bar...")
        
        start_time = time.time()
        pressure_triggered = False

        while not pressure_triggered:
            tensao_sis = ler_float_do_arduino(ser, "READ_VOLTAGE_SISTEMA")
            tensao_pas = ler_float_do_arduino(ser, "READ_VOLTAGE_PASTA")
            
            pressao_sis = converter_tensao_para_pressao_sistema(tensao_sis)
            pressao_pas = converter_tensao_para_pressao_pasta(tensao_pas)

            # [MODIFICADO] Exibe ambos
            print(f"  Sistema: {pressao_sis:.2f} bar | Pasta: {pressao_pas:.2f} bar   \r", end="")
            
            # [MODIFICADO] Gatilho baseado apenas no sensor de Sistema
            if pressao_sis > PRESSURE_THRESHOLD_START:
                start_time = time.time()
                pressure_triggered = True
                print(f"\nINÍCIO DO ENSAIO! Cronômetro iniciado. (Sis: {pressao_sis:.2f} bar | Pas: {pressao_pas:.2f} bar)")
                break
            time.sleep(0.1)
        
        if not pressure_triggered:
             print("\nERRO: Falha ao detectar o início do ensaio.")
             continue


        # Etapa 2: Ensaio em andamento
        print(f"Ensaio em andamento... Alivie a pressão (Sistema) < {PRESSURE_THRESHOLD_STOP:.2f} bar para finalizar.")
        
        # [MODIFICADO] Listas para ambos os sensores
        leituras_pressao_sistema_ensaio = []
        leituras_tensao_sistema_ensaio = []
        leituras_pressao_pasta_ensaio = []
        leituras_tensao_pasta_ensaio = []
        
        while True:
            tensao_sis = ler_float_do_arduino(ser, "READ_VOLTAGE_SISTEMA")
            tensao_pas = ler_float_do_arduino(ser, "READ_VOLTAGE_PASTA")

            if tensao_sis is not None and tensao_pas is not None:
                pressao_sis = converter_tensao_para_pressao_sistema(tensao_sis)
                pressao_pas = converter_tensao_para_pressao_pasta(tensao_pas)
                
                leituras_pressao_sistema_ensaio.append(pressao_sis)
                leituras_tensao_sistema_ensaio.append(tensao_sis)
                leituras_pressao_pasta_ensaio.append(pressao_pas)
                leituras_tensao_pasta_ensaio.append(tensao_pas)
                
                tempo_decorrido = time.time() - start_time
                # [MODIFICADO] Exibe ambos
                print(f"  Sis: {pressao_sis:.2f} bar | Pas: {pressao_pas:.2f} bar | T: {tempo_decorrido:.1f} s   \r", end="")

                # [MODIFICADO] Gatilho baseado apenas no sensor de Sistema
                if pressao_sis < PRESSURE_THRESHOLD_STOP:
                    end_time = time.time()
                    print(f"\nFIM DO ENSAIO! (Última Sis: {pressao_sis:.2f} bar | Pas: {pressao_pas:.2f} bar)")
                    break
            time.sleep(0.1)
            
        # Etapa 3: Coleta da massa e cálculo dos resultados
        duracao_s = end_time - start_time
        print(f"  -> Tempo total do ensaio registrado: {duracao_s:.2f} segundos.")
        
        massa_g = input_float_com_virgula("Digite a massa extrudada durante o ensaio [g]: ")
        
        if massa_g is None or massa_g < 0:
             print("ERRO: Massa inválida ou negativa. Ponto descartado.")
             continue

        # [MODIFICADO] Calcula médias para ambos
        pressao_media_sistema_ensaio = np.mean(leituras_pressao_sistema_ensaio) if leituras_pressao_sistema_ensaio else 0
        tensao_media_sistema_ensaio = np.mean(leituras_tensao_sistema_ensaio) if leituras_tensao_sistema_ensaio else 0
        pressao_media_pasta_ensaio = np.mean(leituras_pressao_pasta_ensaio) if leituras_pressao_pasta_ensaio else 0
        tensao_media_pasta_ensaio = np.mean(leituras_tensao_pasta_ensaio) if leituras_tensao_pasta_ensaio else 0
        
        print(f"  -> Pressão MÉDIA (Sistema): {pressao_media_sistema_ensaio:.3f} bar")
        print(f"  -> Pressão MÉDIA (Pasta):   {pressao_media_pasta_ensaio:.3f} bar")
        
        ponto_atual = {
            "ponto_n": num_ponto,
            "massa_g_registrada": massa_g, 
            "duracao_real_s": duracao_s,
            # [MODIFICADO] Chaves atualizadas
            "media_tensao_sistema_V": tensao_media_sistema_ensaio,
            "media_pressao_sistema_bar": pressao_media_sistema_ensaio,
            "media_tensao_pasta_V": tensao_media_pasta_ensaio,
            "media_pressao_pasta_bar": pressao_media_pasta_ensaio
        }
        data_bateria["testes"].append(ponto_atual)
        
        if input("\nDeseja adicionar outro ponto de medição? (s/n): ").lower() != 's':
            break
            
        num_ponto += 1
        
    salvar_resultados_json_individual_py(data_bateria, json_filename)


def selecionar_json_existente(pasta_json):
    """Lista todos os arquivos .json em uma pasta e permite selecionar um para continuação."""
    print("\n" + "="*60)
    print("--- SELECIONAR ARQUIVO JSON PARA CONTINUIDADE ---")
    print("="*60)
    if not os.path.exists(pasta_json):
        print(f"ERRO: Pasta '{pasta_json}' não encontrada.")
        return None, None
        
    arquivos_raw = sorted([f for f in os.listdir(pasta_json) if f.endswith('.json') and not f.startswith('edit_') and os.path.isfile(os.path.join(pasta_json, f))], reverse=True)
    
    if not arquivos_raw:
        print(f"Nenhum arquivo .json 'raw' de teste encontrado na pasta '{pasta_json}'.")
        return None, None
    
    print("Ensaios disponíveis (do mais recente ao mais antigo):")
    for i, arq in enumerate(arquivos_raw):
        print(f"  {i+1}: {arq}")
    
    while True:
        try:
            escolha_str = input("\nEscolha o NÚMERO do ensaio para continuar (ou '0' para cancelar): ").strip()
            if escolha_str == '0': return None, None
            
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_raw):
                arquivo_selecionado = arquivos_raw[escolha_num - 1]
                caminho_completo = os.path.join(pasta_json, arquivo_selecionado)
                
                with open(caminho_completo, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                print(f"  -> Selecionado: {arquivo_selecionado}")
                print(f"  -> Amostra: {data.get('id_amostra', 'N/A')}")
                print(f"  -> D/L: {data.get('diametro_capilar_mm', 'N/A')} mm / {data.get('comprimento_capilar_mm', 'N/A')} mm")
                print(f"  -> Pontos existentes: {len(data.get('testes', []))}")
                
                # [NOVO] Verifica se o JSON antigo tem dados do sensor de pasta. Se não tiver, avisa.
                if "calibracao_aplicada_pasta" not in data:
                    print("\nAVISO: Este arquivo JSON é de um formato antigo (sem dados do sensor de pasta).")
                    print("Os novos pontos incluirão dados da pasta, mas os antigos não.")
                    # [NOVO] Adiciona chaves de calibração 'dummy' para compatibilidade
                    data["calibracao_aplicada_pasta"] = {
                        "slope": g_calibracao_slope_pasta,
                        "intercept": g_calibracao_intercept_pasta
                    }
                
                return data, arquivo_selecionado
            else:
                print(f"ERRO: Escolha inválida. Digite um número entre 1 e {len(arquivos_raw)}, ou '0'.")
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite um número.")
        except Exception as e:
            print(f"ERRO ao carregar o arquivo: {e}")
            return None, None

def realizar_coleta_de_continuacao(ser, data_existente, nome_arquivo_existente):
    """Função que gerencia o fluxo de Continuação."""
    print("\n" + "="*60)
    print("--- FLUXO DE CONTINUAÇÃO DE TESTE ---")
    print("Prepara-se para o ciclo de condicionamento do primeiro novo ponto.")
    print("="*60)
    realizar_coleta_de_teste_py(ser, data_bateria=data_existente, json_filename=nome_arquivo_existente)
    

def encontrar_e_conectar_arduino():
    """Tenta encontrar e conectar ao Arduino automaticamente."""
    print("Procurando portas seriais disponíveis...")
    portas_disponiveis = serial.tools.list_ports.comports()
    
    if not portas_disponiveis:
        print("Nenhuma porta serial foi encontrada no sistema.")
        return None
        
    portas_promissoras = []
    print("Portas encontradas:")
    for porta in portas_disponiveis:
        print(f"  - {porta.device}: {porta.description}")
        if "USB" in porta.description.upper() or \
           "ARDUINO" in porta.description.upper() or \
           "CH340" in porta.description.upper():
            portas_promissoras.append(porta)
    
    for porta in portas_promissoras:
        print(f"\nTentando conectar na porta promissora: {porta.device}...")
        ser = conectar_arduino(porta.device, BAUD_RATE)
        if ser:
            return ser
            
    for porta in portas_disponiveis:
        if porta not in portas_promissoras:
            print(f"\nTentando conectar na porta genérica: {porta.device}...")
            ser = conectar_arduino(porta.device, BAUD_RATE)
            if ser:
                return ser
                
    return None


# --- Menu Principal e Execução ---

def menu_principal_py(ser):
    """[MODIFICADO] Exibe o menu principal e gerencia a interação com o usuário."""
    while True:
        print("\n" + "="*20 + " MENU - CONTROLE REÔMETRO (2 SENSORES) " + "="*20)
        print("1. INICIAR NOVA Coleta de Dados")
        print("2. CONTINUAR Coleta de Dados (Adicionar Pontos)")
        print("-" * 59)
        print("3. Realizar Calibração (Sensor SISTEMA)")
        print("3a. Realizar Calibração (Sensor PASTA)")
        print("4. Visualizar Calibração (Sensor SISTEMA)")
        print("4a. Visualizar Calibração (Sensor PASTA)")
        print("5. Ler Pressões Imediatas (Ambos Sensores)")
        print("0. Sair")
        
        escolha = input("Digite sua opção: ").strip().lower()

        if escolha == '1':
            if ser:
                realizar_coleta_de_teste_py(ser)
            else:
                print("Arduino não conectado. Não é possível iniciar a coleta.")
        
        elif escolha == '2':
            if not ser:
                print("Arduino não conectado. Não é possível continuar a coleta.")
                continue
            
            data_existente, nome_arquivo_existente = selecionar_json_existente(RESULTS_JSON_DIR)
            if data_existente:
                realizar_coleta_de_continuacao(ser, data_existente, nome_arquivo_existente)
        
        elif escolha == '3':
            if ser:
                realizar_calibracao_sistema(ser)
            else:
                print("Arduino não conectado. Não é possível calibrar.")

        # [NOVO] Opção 3a
        elif escolha == '3a':
            if ser:
                realizar_calibracao_pasta(ser)
            else:
                print("Arduino não conectado. Não é possível calibrar.")

        elif escolha == '4':
            visualizar_calibracao_sistema()

        # [NOVO] Opção 4a
        elif escolha == '4a':
            visualizar_calibracao_pasta()

        elif escolha == '5':
            # [MODIFICADO] Lê ambos os sensores
            if ser and g_calibracao_concluida_sistema and g_calibracao_concluida_pasta:
                try:
                    print("\nLendo pressões imediatas... Pressione CTRL+C para parar.")
                    while True:
                        tensao_sis = ler_float_do_arduino(ser, "READ_VOLTAGE_SISTEMA")
                        tensao_pas = ler_float_do_arduino(ser, "READ_VOLTAGE_PASTA")
                        
                        pressao_sis = converter_tensao_para_pressao_sistema(tensao_sis)
                        pressao_pas = converter_tensao_para_pressao_pasta(tensao_pas)
                        
                        print(f"Sistema: {pressao_sis:6.2f} bar (T: {tensao_sis:.3f} V) | Pasta: {pressao_pas:6.2f} bar (T: {tensao_pas:.3f} V)   \r", end="")
                        time.sleep(0.25)
                except KeyboardInterrupt:
                    print("\nLeitura imediata interrompida.")
            elif not ser:
                print("Arduino não conectado.")
            else:
                print("Calibração necessária para AMBOS os sensores (Sistema e Pasta).")
                if not g_calibracao_concluida_sistema: print(" - Calibração do SISTEMA pendente.")
                if not g_calibracao_concluida_pasta: print(" - Calibração da PASTA pendente.")

        elif escolha == '0':
            print("Saindo do script.")
            break
            
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    if not os.path.exists(RESULTS_JSON_DIR):
        os.makedirs(RESULTS_JSON_DIR)
        
    arduino_ser = None
    try:
        if SERIAL_PORT:
            arduino_ser = conectar_arduino(SERIAL_PORT, BAUD_RATE)
        else:
            arduino_ser = encontrar_e_conectar_arduino()

        if not arduino_ser:
            print("\nAVISO: Não foi possível conectar ao Arduino.")
            if input("Deseja continuar offline para visualizar calibrações? (s/n):").lower() != 's': 
                exit()
        
        # [MODIFICADO] Carrega ambas as calibrações
        carregar_calibracao_sistema(CALIBRATION_FILE_SISTEMA)
        carregar_calibracao_pasta(CALIBRATION_FILE_PASTA)
        
        menu_principal_py(arduino_ser)

    except Exception as e:
        print(f"Ocorreu um erro geral e inesperado no script: {e}")
    finally:
        if arduino_ser and arduino_ser.isOpen():
            arduino_ser.close()
            print("Porta serial fechada.")
