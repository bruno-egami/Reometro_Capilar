import serial
import serial.tools.list_ports
import time
import json
import os
from datetime import datetime

# --- Configurações ---
SERIAL_PORT = None 
BAUD_RATE = 115200
TIMEOUT_SERIAL = 2
CALIBRATION_FILE = 'calibracao_reometro.json'
RESULTS_JSON_DIR = "resultados_testes_reometro"

# --- Parâmetros Padrão de Calibração (podem ser alterados pelo usuário) ---
NUM_PONTOS_CALIBRACAO = 4
PRESSOES_CALIBRACAO_CONHECIDAS = [1.5, 2.0, 2.3, 2.5]

MIN_SENSOR_STEP_DIFFERENCE_PY = 1e-5

# Variáveis globais para dados de calibração em memória
g_calibracao_leituras_sensor = [0.0] * NUM_PONTOS_CALIBRACAO
g_calibracao_tendencia = 0
g_calibracao_concluida = False

# --- Funções de Comunicação com Arduino ---
def conectar_arduino(port, baud):
    try:
        ser = serial.Serial(port, baud, timeout=TIMEOUT_SERIAL)
        time.sleep(2) 
        if ser.isOpen():
            print(f"Conectado ao Arduino na porta {port}.")
            for _ in range(5): 
                if ser.in_waiting > 0: print(f"Arduino (inicial): {ser.readline().decode('utf-8', 'ignore').strip()}")
                else: break
            ser.write(b"PING\n")
            resposta = ser.readline().decode('utf-8', 'ignore').strip()
            if "ACK_PING_OK" in resposta: print("Comunicação PING-ACK OK."); return ser
            else: print(f"Falha no PING-ACK: {resposta}"); ser.close(); return None
    except serial.SerialException as e: print(f"Erro ao conectar em {port}: {e}"); return None

def enviar_comando_e_ler_resposta(ser, comando, esperar_ack=True, timeout_ack=TIMEOUT_SERIAL):
    if ser and ser.isOpen():
        ser.write(comando.encode('utf-8') + b'\n'); ser.flush() 
        start_time = time.time()
        while ser.in_waiting == 0 and (time.time() - start_time) < timeout_ack: time.sleep(0.01)
        if ser.in_waiting > 0: return ser.readline().decode('utf-8', 'ignore').strip()
        return None
    return None

def ler_float_do_arduino(ser, comando_leitura="READ_PRESSURE_EMA", timeout_float=TIMEOUT_SERIAL):
    resposta_str = enviar_comando_e_ler_resposta(ser, comando_leitura, esperar_ack=False, timeout_ack=timeout_float)
    if resposta_str:
        try: return float(resposta_str)
        except ValueError: print(f"Erro: Resposta '{resposta_str}' não é float."); return None
    return None

# --- Funções de Calibração ---
def determinar_tendencia_e_monotonicidade_py(leituras, num_pontos):
    tendencia_detectada = 0; monotonicidade_ok = True
    if num_pontos < 2: return 0, True 
    diff_inicial = leituras[1] - leituras[0]
    if abs(diff_inicial) < MIN_SENSOR_STEP_DIFFERENCE_PY * 10: tendencia_detectada = 0
    elif diff_inicial > 0: tendencia_detectada = 1
    else: tendencia_detectada = -1
    for i in range(2, num_pontos):
        diff_atual = leituras[i] - leituras[i-1]
        if tendencia_detectada == 1:
            if diff_atual <= (MIN_SENSOR_STEP_DIFFERENCE_PY * 5): monotonicidade_ok = False; break
        elif tendencia_detectada == -1:
            if diff_atual >= (-MIN_SENSOR_STEP_DIFFERENCE_PY * 5): monotonicidade_ok = False; break
        else: 
            if abs(diff_atual) > MIN_SENSOR_STEP_DIFFERENCE_PY * 10: monotonicidade_ok = False; break
    if tendencia_detectada == 0 : monotonicidade_ok = False
    return tendencia_detectada, monotonicidade_ok

def realizar_calibracao_interativa_py(ser):
    global g_calibracao_leituras_sensor, g_calibracao_tendencia, g_calibracao_concluida, PRESSOES_CALIBRACAO_CONHECIDAS, NUM_PONTOS_CALIBRACAO

    print("\n=== CALIBRAÇÃO INTERATIVA DO SENSOR DE PRESSÃO ===")
    
    print(f"As pressões de calibração padrão são: {PRESSOES_CALIBRACAO_CONHECIDAS}")
    if input("Deseja usar as pressões padrão? (s/n): ").lower() != 's':
        try:
            novas_pressoes_str = input("Digite as novas pressões separadas por vírgula (ex: 1.0, 2.5, 3.0): ")
            novas_pressoes = [float(p.strip().replace(',', '.')) for p in novas_pressoes_str.split(',')]
            if len(novas_pressoes) > 1:
                PRESSOES_CALIBRACAO_CONHECIDAS = novas_pressoes
                NUM_PONTOS_CALIBRACAO = len(novas_pressoes)
                g_calibracao_leituras_sensor = [0.0] * NUM_PONTOS_CALIBRACAO
                print(f"Novas pressões de calibração definidas: {PRESSOES_CALIBRACAO_CONHECIDAS}")
            else:
                print("Entrada inválida. Usando as pressões padrão.")
        except ValueError:
            print("Formato inválido. Usando as pressões padrão.")
    
    input("\nDespressurize completamente o sistema e pressione ENTER para tarar o sensor...");
    if not enviar_comando_e_ler_resposta(ser, "TARE_PRESSURE"): print("ERRO: Falha ao tarar."); return
    temp_leituras = [0.0] * NUM_PONTOS_CALIBRACAO; leituras_por_ponto_cal = 5
    for i in range(NUM_PONTOS_CALIBRACAO):
        print(f"\nPonto {i+1}/{NUM_PONTOS_CALIBRACAO}: Aplique {PRESSOES_CALIBRACAO_CONHECIDAS[i]:.1f} bar.")
        input("ENTER para registrar..."); soma_leituras_ponto=0.0; leituras_validas_ponto=0
        print(f"  Lendo sensor {leituras_por_ponto_cal}x...");
        for _ in range(leituras_por_ponto_cal):
            leitura = ler_float_do_arduino(ser, "READ_PRESSURE_EMA")
            if leitura is not None: soma_leituras_ponto+=leitura; leituras_validas_ponto+=1; print(f"    EMA: {leitura:.4f}")
            else: print("    Falha ao ler."); time.sleep(0.2)
        if leituras_validas_ponto > 0: temp_leituras[i] = soma_leituras_ponto/leituras_validas_ponto; print(f"  Média EMA: {temp_leituras[i]:.4f}")
        else: print(f"  ERRO: Sem leituras válidas P{i+1}. Abortando."); return
    tendencia, monotonicidade_ok = determinar_tendencia_e_monotonicidade_py(temp_leituras, NUM_PONTOS_CALIBRACAO)
    if not monotonicidade_ok:
        print("\nAVISO: PROBLEMA DE MONOTONICIDADE!");
        if input("Salvar mesmo assim? (s/n): ").lower() != 's': print("Calibração cancelada."); return
        print("Salvando com aviso.")
    g_calibracao_leituras_sensor=list(temp_leituras); g_calibracao_tendencia=tendencia; g_calibracao_concluida=True
    salvar_dados_calibracao_py(CALIBRATION_FILE, {"leituras_sensor":g_calibracao_leituras_sensor, "pressoes_conhecidas":PRESSOES_CALIBRACAO_CONHECIDAS, "tendencia":g_calibracao_tendencia})
    print("Calibração concluída e salva."); print_tendencia(g_calibracao_tendencia)

def salvar_dados_calibracao_py(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Dados de calibração salvos em: {filepath}")
    except IOError as e: print(f"Erro ao salvar calibração: {e}")

def carregar_dados_calibracao_py(filepath):
    global g_calibracao_leituras_sensor, g_calibracao_tendencia, g_calibracao_concluida, PRESSOES_CALIBRACAO_CONHECIDAS, NUM_PONTOS_CALIBRACAO
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
            
            # Carrega os dados do arquivo, mantendo os padrões se as chaves não existirem
            g_calibracao_leituras_sensor = data.get("leituras_sensor", g_calibracao_leituras_sensor)
            PRESSOES_CALIBRACAO_CONHECIDAS = data.get("pressoes_conhecidas", PRESSOES_CALIBRACAO_CONHECIDAS)
            NUM_PONTOS_CALIBRACAO = len(PRESSOES_CALIBRACAO_CONHECIDAS)

            if len(g_calibracao_leituras_sensor) != NUM_PONTOS_CALIBRACAO:
                print(f"AVISO: Número de pontos no arquivo de calibração é incompatível com o número de pressões. Re-calibrar é recomendado."); g_calibracao_concluida=False; return False
            g_calibracao_tendencia = data.get("tendencia", 0); g_calibracao_concluida=True
            print(f"Dados de calibração carregados de: {filepath}"); print_tendencia(g_calibracao_tendencia)
            if g_calibracao_tendencia == 0 and NUM_PONTOS_CALIBRACAO > 1: print("AVISO: Tendência indefinida!")
            return True
        except Exception as e: print(f"Erro ao carregar calibração: {e}."); g_calibracao_concluida=False
    else: print(f"Arquivo '{filepath}' não encontrado. Realize calibração."); g_calibracao_concluida=False
    return False

def visualizar_pontos_calibracao_py():
    print("\n=== PONTOS DE CALIBRAÇÃO ATUAIS (do PC) ===")
    if not g_calibracao_concluida: print("Nenhuma calibração carregada."); return
    print("Pressão (bar) | Leitura Sensor (EMA)"); print("----------------|--------------------")
    for i in range(NUM_PONTOS_CALIBRACAO): print(f"      {PRESSOES_CALIBRACAO_CONHECIDAS[i]:<13.1f} | {g_calibracao_leituras_sensor[i]:.4f}")
    print_tendencia(g_calibracao_tendencia)

def print_tendencia(tendencia_val):
    if tendencia_val == 1: print("Tendência: Crescente")
    elif tendencia_val == -1: print("Tendência: Decrescente")
    else: print("Tendência: Indefinida/Plana (PODE CAUSAR ERROS NA LEITURA!)")

def converter_sensor_para_pressao_py(leitura_ema_atual):
    if not g_calibracao_concluida: return -1.0 
    if g_calibracao_tendencia == 0: return -3.0 
    leituras_cal = g_calibracao_leituras_sensor; pressoes_cal = PRESSOES_CALIBRACAO_CONHECIDAS
    tendencia = g_calibracao_tendencia; n_pontos = NUM_PONTOS_CALIBRACAO
    if tendencia == 1: 
        if leitura_ema_atual <= leituras_cal[0]: R0,P0,R1,P1=leituras_cal[0],pressoes_cal[0],leituras_cal[1],pressoes_cal[1]; return P0+(P1-P0)*(leitura_ema_atual-R0)/(R1-R0) if abs(R1-R0)>MIN_SENSOR_STEP_DIFFERENCE_PY else P0
        if leitura_ema_atual >= leituras_cal[n_pontos-1]: L,SL=n_pontos-1,n_pontos-2; RL,PL,RSL,PSL=leituras_cal[L],pressoes_cal[L],leituras_cal[SL],pressoes_cal[SL]; return PSL+(PL-PSL)*(leitura_ema_atual-RSL)/(RL-RSL) if abs(RL-RSL)>MIN_SENSOR_STEP_DIFFERENCE_PY else PL
    elif tendencia == -1: 
        if leitura_ema_atual >= leituras_cal[0]: R0,P0,R1,P1=leituras_cal[0],pressoes_cal[0],leituras_cal[1],pressoes_cal[1]; return P0+(P1-P0)*(leitura_ema_atual-R0)/(R1-R0) if abs(R1-R0)>MIN_SENSOR_STEP_DIFFERENCE_PY else P0
        if leitura_ema_atual <= leituras_cal[n_pontos-1]: L,SL=n_pontos-1,n_pontos-2; RL,PL,RSL,PSL=leituras_cal[L],pressoes_cal[L],leituras_cal[SL],pressoes_cal[SL]; return PSL+(PL-PSL)*(leitura_ema_atual-RSL)/(RL-RSL) if abs(RL-RSL)>MIN_SENSOR_STEP_DIFFERENCE_PY else PL
    for i in range(n_pontos-1):
        in_segment=False
        if tendencia==1: 
            if leituras_cal[i]<=leitura_ema_atual<leituras_cal[i+1]: in_segment=True
            elif i==n_pontos-2 and abs(leitura_ema_atual-leituras_cal[i+1])<MIN_SENSOR_STEP_DIFFERENCE_PY/10.0: return pressoes_cal[i+1]
        else: 
            if leituras_cal[i]>=leitura_ema_atual>leituras_cal[i+1]: in_segment=True
            elif i==n_pontos-2 and abs(leitura_ema_atual-leituras_cal[i+1])<MIN_SENSOR_STEP_DIFFERENCE_PY/10.0: return pressoes_cal[i+1]
        if in_segment: R_k,P_k,R_k1,P_k1=leituras_cal[i],pressoes_cal[i],leituras_cal[i+1],pressoes_cal[i+1]; return P_k+(P_k1-P_k)*(leitura_ema_atual-R_k)/(R_k1-R_k) if abs(R_k1-R_k)>MIN_SENSOR_STEP_DIFFERENCE_PY else P_k
    if abs(leitura_ema_atual-leituras_cal[0])<MIN_SENSOR_STEP_DIFFERENCE_PY/10.0: return pressoes_cal[0]
    return -2.0

def inserir_leituras_calibracao_manualmente_py(ser):
    global g_calibracao_leituras_sensor, g_calibracao_tendencia, g_calibracao_concluida, PRESSOES_CALIBRACAO_CONHECIDAS, NUM_PONTOS_CALIBRACAO

    print("\n=== INSERIR LEITURAS DE CALIBRAÇÃO MANUALMENTE ===")

    pressoes_atuais = PRESSOES_CALIBRACAO_CONHECIDAS
    print(f"As leituras manuais serão para as pressões padrão: {pressoes_atuais}")
    if input("Deseja inserir leituras para um conjunto de pressões diferente? (s/n): ").lower() == 's':
        try:
            novas_pressoes_str = input("Digite as novas pressões para as quais você tem os valores de EMA, separadas por vírgula: ")
            novas_pressoes = [float(p.strip().replace(',', '.')) for p in novas_pressoes_str.split(',')]
            if len(novas_pressoes) > 1:
                pressoes_atuais = novas_pressoes
                print(f"OK. Inserindo leituras para as pressões personalizadas: {pressoes_atuais}")
            else:
                print("Entrada inválida. Usando as pressões padrão.")
        except ValueError:
            print("Formato inválido. Usando as pressões padrão.")

    num_pontos_atuais = len(pressoes_atuais)
    temp_leituras_manuais = [0.0] * num_pontos_atuais
    
    print("\n--- Inserção de Dados ---")
    for i in range(num_pontos_atuais):
        while True:
            try: 
                prompt_text = f"Insira o valor EMA para a pressão de {pressoes_atuais[i]:.2f} bar: "
                leitura_str = input(prompt_text)
                temp_leituras_manuais[i] = float(leitura_str.replace(',', '.'))
                break
            except ValueError: print("Entrada inválida. Insira um número.")

    print("\nLeituras Inseridas:")
    for i in range(num_pontos_atuais): 
        print(f"  {pressoes_atuais[i]:.2f} bar -> EMA: {temp_leituras_manuais[i]:.4f}")
        
    tendencia, monotonicidade_ok = determinar_tendencia_e_monotonicidade_py(temp_leituras_manuais, num_pontos_atuais)
    
    if not monotonicidade_ok:
        print("\nAVISO: Leituras manuais não são monotonicamente consistentes!");
        if input("Salvar mesmo assim? (s/n): ").lower()!='s': 
            print("Entrada manual cancelada."); return
        print("Salvando com aviso.")

    PRESSOES_CALIBRACAO_CONHECIDAS = pressoes_atuais
    NUM_PONTOS_CALIBRACAO = num_pontos_atuais
    g_calibracao_leituras_sensor = list(temp_leituras_manuais)
    g_calibracao_tendencia = tendencia
    g_calibracao_concluida = True
    
    salvar_dados_calibracao_py(CALIBRATION_FILE, {
        "leituras_sensor": g_calibracao_leituras_sensor, 
        "pressoes_conhecidas": PRESSOES_CALIBRACAO_CONHECIDAS, 
        "tendencia": g_calibracao_tendencia
    })
    print("Leituras manuais aplicadas e salvas."); print_tendencia(g_calibracao_tendencia)

def sanitize_filename(name):
    name = str(name).replace(' ', '_').replace('/', '-').replace('\\', '-').replace('.', '_')
    valid_chars = "-_()abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(c for c in name if c in valid_chars)[:50]

def salvar_resultados_json_individual_py(data_bateria):
    if not data_bateria: print("Nenhum dado de teste para salvar."); return
    base_filename = data_bateria.get('id_amostra') or data_bateria.get('descricao','resultado_teste')
    sane_basename = sanitize_filename(base_filename)
    datetime_obj = datetime.strptime(data_bateria.get('data_hora_inicio', datetime.now().strftime("%Y-%m-%d %H:%M:%S")), "%Y-%m-%d %H:%M:%S")
    timestamp_str_file = datetime_obj.strftime("%Y%m%d_%H%M%S")
    if not os.path.exists(RESULTS_JSON_DIR): 
        os.makedirs(RESULTS_JSON_DIR)
    filename = os.path.join(RESULTS_JSON_DIR, f"{sane_basename}_{timestamp_str_file}.json")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_bateria, f, indent=4, ensure_ascii=False)
        print(f"Resultados da bateria salvos em: {filename}")
    except IOError as e: print(f"Erro ao salvar resultados em JSON: {e}")

def visualizar_resultados_salvos_py(): 
    print("\n=== RESULTADOS DE TESTES SALVOS (JSON Individuais) ===")
    if not os.path.exists(RESULTS_JSON_DIR):
        print(f"Diretório '{RESULTS_JSON_DIR}' não encontrado."); return
    saved_files = sorted([f for f in os.listdir(RESULTS_JSON_DIR) if f.endswith(".json")])
    if not saved_files: print("Nenhum arquivo de resultado (.json) encontrado."); return
    print("Arquivos de resultado disponíveis:")
    for idx, filename in enumerate(saved_files): print(f"  {idx + 1}: {filename}")
    try:
        choice_str = input("Digite o número do arquivo para visualizar (0 para cancelar): ")
        choice = int(choice_str)
        if choice == 0 or choice > len(saved_files) or choice < 0: print("Cancelado."); return
        selected_filename = os.path.join(RESULTS_JSON_DIR, saved_files[choice - 1])
        with open(selected_filename, 'r', encoding='utf-8') as f:
            bateria = json.load(f)
            # (O código detalhado de visualização foi omitido por brevidade, mas deve ser mantido como no original)
            print(f"\n--- Visualizando Bateria: {bateria.get('id_amostra', 'N/A')} ---")

    except ValueError: print("Escolha inválida.")
    except Exception as e: print(f"Erro ao visualizar: {e}")

def realizar_coleta_de_teste_py(ser):
    # (A função original completa deve ser mantida aqui)
    pass

def menu_principal_py(ser):
    while True:
        print("\n======= MENU PYTHON - CONTROLE REÔMETRO =======")
        print("1. Iniciar Nova Coleta de Dados")
        print("2. Realizar Calibração Interativa")
        print("3. Inserir Leituras de Calibração Manualmente")
        print("4. Visualizar Pontos de Calibração")
        print("5. Tarar Sensor de Pressão")
        print("6. Ler Pressão Imediata")
        print("7. Visualizar Resultados Salvos")
        print("0. Sair")
        
        escolha = input("Digite sua opção: ")
        if escolha == '1':
            if ser: realizar_coleta_de_teste_py(ser)
            else: print("Arduino não conectado.")
        elif escolha == '2':
            if ser: realizar_calibracao_interativa_py(ser)
            else: print("Arduino não conectado.")
        elif escolha == '3':
             inserir_leituras_calibracao_manualmente_py(ser)
        elif escolha == '4':
            visualizar_pontos_calibracao_py()
        elif escolha == '5':
            if ser: enviar_comando_e_ler_resposta(ser, "TARE_PRESSURE")
            else: print("Arduino não conectado.")
        elif escolha == '6':
            if ser and g_calibracao_concluida and g_calibracao_tendencia != 0:
                try:
                    print("Lendo pressão imediata... Pressione CTRL+C para parar.")
                    while True:
                        leitura_ema = ler_float_do_arduino(ser, "READ_PRESSURE_EMA")
                        if leitura_ema is not None:
                            pressao = converter_sensor_para_pressao_py(leitura_ema)
                            print(f"Pressão Imediata: {pressao:.2f} bar (EMA: {leitura_ema:.2f})        \r", end="")
                        time.sleep(0.25)
                except KeyboardInterrupt: print("\nLeitura imediata interrompida.")
            elif not ser: print("Arduino não conectado.")
            else: print("Calibração necessária ou inválida.")
        elif escolha == '7':
            visualizar_resultados_salvos_py()
        elif escolha == '0':
            print("Saindo do script Python."); break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    arduino_ser = None
    try:
        print("Tentando conectar ao Arduino...")
        if SERIAL_PORT:
            arduino_ser = conectar_arduino(SERIAL_PORT, BAUD_RATE)
        else:
            print("Nenhuma porta serial especificada. Procurando portas disponíveis...")
            portas_disponiveis = serial.tools.list_ports.comports()
            
            if not portas_disponiveis:
                print("Nenhuma porta serial física foi encontrada no sistema.")
            else:
                portas_promissoras = []
                print("Portas encontradas:")
                for porta in portas_disponiveis:
                    print(f"  - {porta.device}: {porta.description}")
                    if "USB" in porta.description.upper() or \
                       "ARDUINO" in porta.description.upper() or \
                       "CH340" in porta.description.upper():
                        portas_promissoras.append(porta)
                
                for porta in portas_promissoras:
                    print(f"\nTentando porta promissora: {porta.device}")
                    arduino_ser = conectar_arduino(porta.device, BAUD_RATE)
                    if arduino_ser:
                        SERIAL_PORT = porta.device
                        print(f"Conexão bem-sucedida em: {SERIAL_PORT}")
                        break
            
            if not arduino_ser and portas_disponiveis:
                print("\nNão foi possível conectar a uma porta conhecida. Tentando todas as portas...")
                for porta in portas_disponiveis:
                    if porta not in portas_promissoras:
                        print(f"  Tentando porta genérica {porta.device}...")
                        arduino_ser = conectar_arduino(porta.device, BAUD_RATE)
                        if arduino_ser:
                            SERIAL_PORT = porta.device
                            print(f"Conexão bem-sucedida em: {SERIAL_PORT}")
                            break

        if not arduino_ser:
            print("\nNão foi possível conectar ao Arduino.")
            if input("Deseja continuar offline para ver/inserir calibração ou ver resultados? (s/n):").lower() != 's': 
                exit()
        
        carregar_dados_calibracao_py(CALIBRATION_FILE)
        menu_principal_py(arduino_ser)
    except Exception as e:
        print(f"Ocorreu um erro geral no script: {e}")
    finally:
        if arduino_ser and arduino_ser.isOpen():
            arduino_ser.close()
            print("Porta serial fechada.")
