# -*- coding: utf-8 -*-
"""
SCRIPT PARA CONTROLE DE REÔMETRO CAPILAR COM TRANSDUTOR DE PRESSÃO ANALÓGICO
VERSÃO 2.3 - Corrigida a chave de pressão no JSON para compatibilidade.
Autor: Bruno Egami (Modificado por Gemini)
Data: 17/08/2025
"""

import serial
import serial.tools.list_ports
import time
import json
import os
from datetime import datetime
import numpy as np

# --- Configurações ---
SERIAL_PORT = None 
BAUD_RATE = 115200
TIMEOUT_SERIAL = 2
CALIBRATION_FILE = 'calibracao_reometro.json' # Arquivo para salvar a nova calibração linear
RESULTS_JSON_DIR = "resultados_testes_reometro"

# --- NOVAS CONFIGURAÇÕES DE GATILHO DE PRESSÃO ---
PRESSURE_THRESHOLD_START = 0.15 # Pressão em [bar] para iniciar o cronômetro
PRESSURE_THRESHOLD_STOP = 0.10  # Pressão em [bar] para parar o cronômetro

# --- Variáveis Globais para a Nova Calibração Linear ---
# A calibração agora é baseada na equação: Pressão = slope * Tensão + intercept
g_calibracao_slope = None
g_calibracao_intercept = None
g_calibracao_concluida = False

# --- Funções de Comunicação com Arduino (Adaptadas) ---

def conectar_arduino(port, baud):
    """Tenta conectar ao Arduino na porta especificada e verifica a comunicação."""
    try:
        ser = serial.Serial(port, baud, timeout=TIMEOUT_SERIAL)
        time.sleep(2) # Aguarda a inicialização do Arduino
        if ser.isOpen():
            print(f"Conectado ao Arduino na porta {port}.")
            # Limpa qualquer dado inicial na porta serial
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

def ler_float_do_arduino(ser, comando_leitura="READ_VOLTAGE", timeout_float=TIMEOUT_SERIAL):
    """Envia um comando para o Arduino e espera uma resposta float (tensão)."""
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
                print(f"Erro: Resposta do Arduino ('{resposta_str}') não é um float válido.")
                return None
    return None

# --- Funções de Calibração (Totalmente Reescritas) ---

def salvar_dados_calibracao_py(filepath, data):
    """Salva os dados da calibração (slope, intercept) em um arquivo JSON."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Dados de calibração salvos com sucesso em: {filepath}")
    except IOError as e:
        print(f"Erro ao salvar o arquivo de calibração: {e}")

def carregar_dados_calibracao_py(filepath):
    """Carrega os parâmetros da calibração linear do arquivo JSON."""
    global g_calibracao_slope, g_calibracao_intercept, g_calibracao_concluida
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Verifica se as chaves necessárias existem no arquivo
            if "slope" in data and "intercept" in data:
                g_calibracao_slope = data["slope"]
                g_calibracao_intercept = data["intercept"]
                g_calibracao_concluida = True
                print(f"Dados de calibração carregados de: {filepath}")
                print(f"  -> Equação: Pressão = {g_calibracao_slope:.4f} * Tensão + {g_calibracao_intercept:.4f}")
                return True
            else:
                print(f"ERRO: Arquivo '{filepath}' não contém 'slope' e 'intercept'. Realize uma nova calibração.")
                g_calibracao_concluida = False
        except Exception as e:
            print(f"Erro ao carregar ou processar o arquivo de calibração: {e}")
            g_calibracao_concluida = False
    else:
        print(f"Arquivo de calibração '{filepath}' não encontrado. É necessário calibrar o sistema.")
        g_calibracao_concluida = False
    return False

def realizar_calibracao_interativa_py(ser):
    """Guia o usuário através de uma calibração linear de 2 pontos."""
    global g_calibracao_slope, g_calibracao_intercept, g_calibracao_concluida
    
    print("\n" + "="*60)
    print("ASSISTENTE DE CALIBRAÇÃO DO TRANSDUTOR DE PRESSÃO (2 PONTOS)")
    print("="*60)
    print("Este processo irá gerar uma equação linear para converter Tensão (V) em Pressão (bar).")
    
    # --- Ponto 1: Zero Pressão ---
    input("\nPasso 1: Despressurize completamente o sistema e pressione ENTER para ler a tensão de base (0 bar)...")
    
    leituras_p1 = [ler_float_do_arduino(ser, "READ_VOLTAGE") for _ in range(5)]
    leituras_p1 = [v for v in leituras_p1 if v is not None]
    
    if not leituras_p1:
        print("ERRO: Não foi possível ler a tensão do Arduino. Verifique a conexão. Abortando.")
        return
        
    tensao_p1 = np.mean(leituras_p1)
    pressao_p1 = 0.0
    print(f"  -> Tensão média a {pressao_p1:.1f} bar: {tensao_p1:.4f} V")

    # --- Ponto 2: Pressão Conhecida ---
    pressao_p2 = 0.0
    while pressao_p2 <= 0:
        try:
            pressao_p2_str = input("\nPasso 2: Aplique uma pressão conhecida (ex: 5.0) e digite o valor em [bar]: ").replace(',', '.')
            pressao_p2 = float(pressao_p2_str)
            if pressao_p2 <= 0: print("  A pressão deve ser maior que zero.")
        except ValueError:
            print("  Valor inválido. Por favor, insira um número.")
            
    input(f"Pressione ENTER para ler a tensão correspondente a {pressao_p2:.2f} bar...")
    
    leituras_p2 = [ler_float_do_arduino(ser, "READ_VOLTAGE") for _ in range(5)]
    leituras_p2 = [v for v in leituras_p2 if v is not None]

    if not leituras_p2:
        print("ERRO: Não foi possível ler a tensão do Arduino. Abortando.")
        return
        
    tensao_p2 = np.mean(leituras_p2)
    print(f"  -> Tensão média a {pressao_p2:.2f} bar: {tensao_p2:.4f} V")

    # --- Cálculo dos Parâmetros da Reta ---
    if abs(tensao_p2 - tensao_p1) < 0.01: # Verifica se a mudança de tensão é significativa
        print("\nERRO DE CALIBRAÇÃO: A variação de tensão é muito pequena. Verifique o transdutor ou use uma pressão maior.")
        return

    # Equação da reta: y = ax + b -> P = a*V + b
    # a (slope) = (P2 - P1) / (V2 - V1)
    # b (intercept) = P1 - a * V1
    slope = (pressao_p2 - pressao_p1) / (tensao_p2 - tensao_p1)
    intercept = pressao_p1 - slope * tensao_p1

    print("\n" + "-"*25 + " CALIBRAÇÃO CONCLUÍDA " + "-"*25)
    print(f"Slope (a):     {slope:.4f} bar/V")
    print(f"Intercept (b): {intercept:.4f} bar")
    print(f"EQUAÇÃO FINAL: Pressão [bar] = {slope:.4f} * Tensão [V] + {intercept:.4f}")

    # Atualiza as variáveis globais e salva no arquivo
    g_calibracao_slope = slope
    g_calibracao_intercept = intercept
    g_calibracao_concluida = True
    
    dados_calibracao = {"slope": slope, "intercept": intercept, "units": "bar/V"}
    salvar_dados_calibracao_py(CALIBRATION_FILE, dados_calibracao)

def visualizar_pontos_calibracao_py():
    """Mostra a calibração linear atualmente carregada."""
    print("\n=== CALIBRAÇÃO ATUALMENTE EM MEMÓRIA ===")
    if g_calibracao_concluida:
        print(f"  Slope (a):     {g_calibracao_slope:.4f} bar/V")
        print(f"  Intercept (b): {g_calibracao_intercept:.4f} bar")
        print(f"  Equação: Pressão [bar] = {g_calibracao_slope:.4f} * Tensão [V] + {g_calibracao_intercept:.4f}")
    else:
        print("Nenhuma calibração válida carregada. Por favor, realize a calibração.")

def converter_tensao_para_pressao_py(tensao_lida):
    """Converte um valor de tensão para pressão usando a calibração carregada."""
    if not g_calibracao_concluida:
        return -1.0 # Retorna um valor de erro se não houver calibração
    
    pressao = (g_calibracao_slope * tensao_lida) + g_calibracao_intercept
    return max(pressao, 0) # Garante que a pressão nunca seja negativa

# --- Funções de Coleta e Visualização (MODIFICADA) ---

def realizar_coleta_de_teste_py(ser):
    """Função principal para guiar o usuário na coleta de dados de um ensaio,
    com medição de tempo automática baseada em gatilho de pressão."""
    if not g_calibracao_concluida:
        print("\nERRO: É necessário realizar ou carregar uma calibração antes de iniciar uma coleta.")
        return

    print("\n" + "="*60)
    print("ASSISTENTE DE COLETA DE DADOS REOLÓGICOS (GATILHO AUTOMÁTICO)")
    print("="*60)
    
    # Coleta de metadados do ensaio
    id_amostra = input("ID ou nome da amostra: ")
    descricao = input("Descrição breve do ensaio: ")
    try:
        D_cap_mm = float(input("Diâmetro do capilar [mm]: ").replace(',', '.'))
        L_cap_mm = float(input("Comprimento do capilar [mm]: ").replace(',', '.'))
        rho_g_cm3 = float(input("Densidade da pasta [g/cm³]: ").replace(',', '.'))
    except ValueError:
        print("ERRO: Valor inválido para os parâmetros. Abortando coleta.")
        return

    bateria_de_testes = {
        "id_amostra": id_amostra,
        "descricao": descricao,
        "data_hora_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "diametro_capilar_mm": D_cap_mm,
        "comprimento_capilar_mm": L_cap_mm,
        "densidade_pasta_g_cm3": rho_g_cm3,
        "calibracao_aplicada": {
            "slope": g_calibracao_slope,
            "intercept": g_calibracao_intercept
        },
        "testes": []
    }

    num_ponto = 1
    while True:
        print("\n" + "-"*20 + f" PONTO DE MEDIÇÃO Nº {num_ponto} " + "-"*20)
        
        # Etapa 1: Aguardando o início do ensaio
        print(f"Aguardando pressão subir acima de {PRESSURE_THRESHOLD_START:.2f} bar para iniciar o cronômetro...")
        while True:
            tensao = ler_float_do_arduino(ser)
            if tensao is not None:
                pressao = converter_tensao_para_pressao_py(tensao)
                print(f"  Pressão atual: {pressao:.2f} bar   \r", end="")
                if pressao > PRESSURE_THRESHOLD_START:
                    start_time = time.time()
                    print(f"\nINÍCIO DO ENSAIO! Cronômetro iniciado. Pressão: {pressao:.2f} bar")
                    break
            time.sleep(0.1)

        # Etapa 2: Ensaio em andamento
        print(f"Ensaio em andamento... Alivie a pressão abaixo de {PRESSURE_THRESHOLD_STOP:.2f} bar para finalizar.")
        leituras_pressao_ensaio = []
        leituras_tensao_ensaio = []
        while True:
            tensao = ler_float_do_arduino(ser)
            if tensao is not None:
                pressao = converter_tensao_para_pressao_py(tensao)
                leituras_pressao_ensaio.append(pressao)
                leituras_tensao_ensaio.append(tensao)
                
                tempo_decorrido = time.time() - start_time
                print(f"  Pressão: {pressao:.2f} bar | Tempo: {tempo_decorrido:.1f} s   \r", end="")

                if pressao < PRESSURE_THRESHOLD_STOP:
                    end_time = time.time()
                    print(f"\nFIM DO ENSAIO! Pressão aliviada. (Última leitura: {pressao:.2f} bar)")
                    break
            time.sleep(0.1)
            
        # Etapa 3: Coleta da massa e cálculo dos resultados
        duracao_s = end_time - start_time
        print(f"  -> Tempo total do ensaio registrado: {duracao_s:.2f} segundos.")
        
        try:
            massa_g_str = input("Digite a massa extrudada durante o ensaio [g]: ").replace(',', '.')
            massa_g = float(massa_g_str)
        except ValueError:
            print("ERRO: Massa inválida. Tente este ponto novamente.")
            continue

        # Calcula a pressão e tensão médias durante o ensaio
        pressao_media_ensaio = np.mean(leituras_pressao_ensaio) if leituras_pressao_ensaio else 0
        tensao_media_ensaio = np.mean(leituras_tensao_ensaio) if leituras_tensao_ensaio else 0
        print(f"  -> Pressão MÉDIA do ensaio: {pressao_media_ensaio:.3f} bar")
        
        ponto_atual = {
            "ponto_n": num_ponto,
            "massa_g_registrada": massa_g,
            "duracao_real_s": duracao_s,
            "media_tensao_final_ponto_V": tensao_media_ensaio,
            "media_pressao_final_ponto_bar": pressao_media_ensaio
        }
        bateria_de_testes["testes"].append(ponto_atual)
        
        if input("\nDeseja adicionar outro ponto de medição? (s/n): ").lower() != 's':
            break
        num_ponto += 1
        
    # Salvar resultados
    salvar_resultados_json_individual_py(bateria_de_testes)

def salvar_resultados_json_individual_py(data_bateria):
    """Salva os dados completos de um ensaio em um arquivo JSON único."""
    if not data_bateria or not data_bateria.get('testes'):
        print("Nenhum dado de teste para salvar.")
        return
        
    def sanitize_filename(name):
        return "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip()[:50].replace(' ', '_')

    base_filename = data_bateria.get('id_amostra') or 'resultado_teste'
    sane_basename = sanitize_filename(base_filename)
    timestamp_str_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if not os.path.exists(RESULTS_JSON_DIR):
        os.makedirs(RESULTS_JSON_DIR)
        
    filename = os.path.join(RESULTS_JSON_DIR, f"{sane_basename}_{timestamp_str_file}.json")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_bateria, f, indent=4, ensure_ascii=False)
        print(f"\nResultados do ensaio salvos com sucesso em: {filename}")
    except IOError as e:
        print(f"Erro ao salvar resultados em JSON: {e}")

# --- Menu Principal e Execução ---

def menu_principal_py(ser):
    """Exibe o menu principal e gerencia a interação com o usuário."""
    while True:
        print("\n" + "="*20 + " MENU - CONTROLE REÔMETRO " + "="*20)
        print("1. Iniciar Nova Coleta de Dados")
        print("2. Realizar Calibração do Transdutor")
        print("3. Visualizar Calibração Atual")
        print("4. Ler Pressão Imediata")
        print("0. Sair")
        
        escolha = input("Digite sua opção: ")

        if escolha == '1':
            if ser:
                realizar_coleta_de_teste_py(ser)
            else:
                print("Arduino não conectado. Não é possível iniciar a coleta.")
        
        elif escolha == '2':
            if ser:
                realizar_calibracao_interativa_py(ser)
            else:
                print("Arduino não conectado. Não é possível calibrar.")

        elif escolha == '3':
            visualizar_pontos_calibracao_py()

        elif escolha == '4':
            if ser and g_calibracao_concluida:
                try:
                    print("\nLendo pressão imediata... Pressione CTRL+C para parar.")
                    while True:
                        tensao_lida = ler_float_do_arduino(ser, "READ_VOLTAGE")
                        if tensao_lida is not None:
                            pressao = converter_tensao_para_pressao_py(tensao_lida)
                            print(f"Pressão Imediata: {pressao:.2f} bar (Tensão: {tensao_lida:.3f} V)        \r", end="")
                        time.sleep(0.25)
                except KeyboardInterrupt:
                    print("\nLeitura imediata interrompida.")
            elif not ser:
                print("Arduino não conectado.")
            else:
                print("Calibração necessária para ler a pressão.")

        elif escolha == '0':
            print("Saindo do script.")
            break
            
        else:
            print("Opção inválida. Tente novamente.")

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
        # Palavras-chave comuns para Arduinos
        if "USB" in porta.description.upper() or \
           "ARDUINO" in porta.description.upper() or \
           "CH340" in porta.description.upper():
            portas_promissoras.append(porta)
    
    # Tenta conectar primeiro nas portas mais prováveis
    for porta in portas_promissoras:
        print(f"\nTentando conectar na porta promissora: {porta.device}...")
        ser = conectar_arduino(porta.device, BAUD_RATE)
        if ser:
            return ser
            
    # Se não funcionar, tenta nas outras
    for porta in portas_disponiveis:
        if porta not in portas_promissoras:
            print(f"\nTentando conectar na porta genérica: {porta.device}...")
            ser = conectar_arduino(porta.device, BAUD_RATE)
            if ser:
                return ser
                
    return None

if __name__ == "__main__":
    arduino_ser = None
    try:
        # Tenta conectar ao Arduino
        if SERIAL_PORT:
            arduino_ser = conectar_arduino(SERIAL_PORT, BAUD_RATE)
        else:
            arduino_ser = encontrar_e_conectar_arduino()

        if not arduino_ser:
            print("\nAVISO: Não foi possível conectar ao Arduino.")
            if input("Deseja continuar offline para visualizar a calibração? (s/n):").lower() != 's': 
                exit()
        
        # Carrega a calibração existente (se houver)
        carregar_dados_calibracao_py(CALIBRATION_FILE)
        
        # Inicia o menu principal
        menu_principal_py(arduino_ser)

    except Exception as e:
        print(f"Ocorreu um erro geral e inesperado no script: {e}")
    finally:
        # Garante que a porta serial seja fechada ao sair
        if arduino_ser and arduino_ser.isOpen():
            arduino_ser.close()
            print("Porta serial fechada.")
