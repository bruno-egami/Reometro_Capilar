import serial
import time
import json
import os
from datetime import datetime
import serial.tools.list_ports

# --- Configurações ---
SERIAL_PORT = None 
BAUD_RATE = 115200
TIMEOUT_SERIAL = 2
CALIBRATION_FILE = 'calibracao_reometro.json'
RESULTS_JSON_DIR = "resultados_testes_reometro" # NOME DA PASTA ALTERADO

NUM_PONTOS_CALIBRACAO = 4
PRESSOES_CALIBRACAO_CONHECIDAS = [1.5, 2.0, 2.3, 2.5]

MIN_SENSOR_STEP_DIFFERENCE_PY = 1e-5

# Variáveis globais para dados de calibração em memória
g_calibracao_leituras_sensor = [0.0] * NUM_PONTOS_CALIBRACAO
g_calibracao_tendencia = 0
g_calibracao_concluida = False

# --- Funções de Comunicação com Arduino (mantidas como antes) ---
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

# --- Funções de Calibração (mantidas como antes) ---
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
    
    # --- LÓGICA DE PERSONALIZAÇÃO ADICIONADA ---
    print(f"As pressões de calibração padrão são: {PRESSOES_CALIBRACAO_CONHECIDAS}")
    if input("Deseja usar as pressões padrão? (s/n): ").lower() != 's':
        try:
            novas_pressoes_str = input("Digite as novas pressões separadas por vírgula (ex: 1.0, 2.5, 3.0): ")
            novas_pressoes = [float(p.strip()) for p in novas_pressoes_str.split(',')]
            if len(novas_pressoes) > 1:
                PRESSOES_CALIBRACAO_CONHECIDAS = novas_pressoes
                NUM_PONTOS_CALIBRACAO = len(novas_pressoes)
                g_calibracao_leituras_sensor = [0.0] * NUM_PONTOS_CALIBRACAO # Redimensiona o array global
                print(f"Novas pressões de calibração definidas: {PRESSOES_CALIBRACAO_CONHECIDAS}")
            else:
                print("Entrada inválida. Usando as pressões padrão.")
        except ValueError:
            print("Formato inválido. Usando as pressões padrão.")
    # --- FIM DA LÓGICA DE PERSONALIZAÇÃO ---

    input("\nDespressurize completamente o sistema e pressione ENTER para tarar o sensor...");
    # ... resto da função original, sem alterações ...
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
    global g_calibracao_leituras_sensor, g_calibracao_tendencia, g_calibracao_concluida
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
            g_calibracao_leituras_sensor = data.get("leituras_sensor", [0.0]*NUM_PONTOS_CALIBRACAO)
            if len(g_calibracao_leituras_sensor) != NUM_PONTOS_CALIBRACAO:
                print(f"AVISO: Nro de pontos no arquivo incompatível."); g_calibracao_concluida=False; return False
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
    # ... (Lógica de interpolação/extrapolação como na versão anterior) ...
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
    global g_calibracao_leituras_sensor, g_calibracao_tendencia, g_calibracao_concluida
    print("\n=== INSERIR LEITURAS DE CALIBRAÇÃO MANUALMENTE (1-4 BAR) ===")
    temp_leituras_manuais = [0.0] * NUM_PONTOS_CALIBRACAO
    for i in range(NUM_PONTOS_CALIBRACAO):
        while True:
            try: 
                prompt_text = f"Insira leitura EMA para {PRESSOES_CALIBRACAO_CONHECIDAS[i]:.1f} bar: "
                leitura_str = input(prompt_text)
                temp_leituras_manuais[i] = float(leitura_str)
                break
            except ValueError: print("Entrada inválida. Insira um número.")
    print("\nLeituras Inseridas:")
    for i in range(NUM_PONTOS_CALIBRACAO): print(f"  {PRESSOES_CALIBRACAO_CONHECIDAS[i]:.1f} bar -> EMA: {temp_leituras_manuais[i]:.4f}")
    tendencia, monotonicidade_ok = determinar_tendencia_e_monotonicidade_py(temp_leituras_manuais, NUM_PONTOS_CALIBRACAO)
    if not monotonicidade_ok:
        print("\nAVISO: Leituras manuais não monotonicamente consistentes!");
        if input("Salvar mesmo assim? (s/n): ").lower()!='s': print("Entrada manual cancelada."); return
        print("Salvando com aviso.")
    g_calibracao_leituras_sensor=list(temp_leituras_manuais); g_calibracao_tendencia=tendencia; g_calibracao_concluida=True
    salvar_dados_calibracao_py(CALIBRATION_FILE, {"leituras_sensor":g_calibracao_leituras_sensor, "pressoes_conhecidas":PRESSOES_CALIBRACAO_CONHECIDAS, "tendencia":g_calibracao_tendencia})
    print("Leituras manuais aplicadas e salvas."); print_tendencia(g_calibracao_tendencia)


# --- Funções de Coleta de Teste (Modificadas) ---
def sanitize_filename(name):
    name = str(name).replace(' ', '_').replace('/', '-').replace('\\', '-').replace('.', '_')
    valid_chars = "-_()abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(c for c in name if c in valid_chars)[:50]

def salvar_resultados_json_individual_py(data_bateria):
    if not data_bateria: print("Nenhum dado de teste para salvar."); return
    
    # Usa id_amostra para o nome do arquivo, senão a descrição geral
    base_filename = data_bateria.get('id_amostra') or data_bateria.get('descricao','resultado_teste')
    sane_basename = sanitize_filename(base_filename)
    
    datetime_obj = datetime.strptime(data_bateria.get('data_hora_inicio', datetime.now().strftime("%Y-%m-%d %H:%M:%S")), "%Y-%m-%d %H:%M:%S")
    timestamp_str_file = datetime_obj.strftime("%Y%m%d_%H%M%S")
    
    if not os.path.exists(RESULTS_JSON_DIR): 
        os.makedirs(RESULTS_JSON_DIR)
        print(f"Diretório '{RESULTS_JSON_DIR}' criado para salvar os JSONs.")
        
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
    saved_files = sorted([f for f in os.listdir(RESULTS_JSON_DIR) if f.endswith(".json")]) # Ordena os arquivos
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
            print(f"\n--- Visualizando Bateria: {saved_files[choice - 1]} ---")
            print(f"  ID Amostra: {bateria.get('id_amostra', 'N/A')}")
            print(f"  Descrição Geral: {bateria.get('descricao', 'N/A')}")
            print(f"  Composição da Pasta: {bateria.get('composicao_pasta', 'N/A')}")
            print(f"  Lote Material Principal: {bateria.get('lote_material_principal', 'N/A')}")
            print(f"  Densidade da Pasta: {bateria.get('densidade_pasta_g_cm3', 'N/A')} g/cm³")
            print(f"  Observações Gerais: {bateria.get('observacoes_gerais', 'N/A')}")
            print(f"  Data/Hora Início: {bateria.get('data_hora_inicio', 'N/A')}")
            print(f"  Diâmetro Capilar: {bateria.get('diametro_capilar_mm', 'N/A')} mm")
            print(f"  Comprimento Capilar: {bateria.get('comprimento_capilar_mm', 'N/A')} mm")
            print(f"  Total de Pontos de Teste: {bateria.get('num_total_testes', 'N/A')}")
            print(f"  Duração Configurada por Ponto: {bateria.get('duracao_por_teste_s', 'N/A')}s")
            
            soma_total_massa_p1 = bateria.get("soma_total_massa_p1_g")
            num_corridas_p1 = bateria.get("num_corridas_massa_p1")
            if soma_total_massa_p1 is not None and num_corridas_p1 is not None and num_corridas_p1 > 0:
                 media_m_p1_calc = soma_total_massa_p1 / num_corridas_p1
                 print(f"  Info Massa Ponto 1: Total {soma_total_massa_p1:.3f}g de {num_corridas_p1} corridas (Média: {media_m_p1_calc:.3f} g/corrida)")
            
            print("  Dados Detalhados dos Pontos de Pressão:")
            for teste_data in bateria.get("testes", []):
                ponto_n = teste_data.get('ponto_n', '?')
                pressao_alvo = teste_data.get('pressao_alvo_bar', 'N/A')
                media_p = teste_data.get('media_pressao_final_ponto_bar')
                massa_registrada = teste_data.get('massa_g_registrada', 'N/A')
                
                print(f"    Ponto {ponto_n}:")
                print(f"      Pressão Alvo: {pressao_alvo:.1f} bar")
                print(f"      Média Pressão Medida: {media_p if media_p is not None else 'N/A'} bar")
                print(f"      Massa Registrada: {massa_registrada if isinstance(massa_registrada, (int,float)) else 'N/A'} g")
                
                corridas_det = teste_data.get("corridas_executadas", [])
                if corridas_det:
                    print(f"      Detalhes das Corridas ({len(corridas_det)}):")
                    for idx_corrida, corrida_info in enumerate(corridas_det):
                        media_p_corrida = corrida_info.get('media_pressao_calculada_corrida_bar')
                        num_leituras_det = len(corrida_info.get('leituras_pressao_detalhadas_bar', []))
                        print(f"        Corrida {corrida_info.get('numero_corrida', idx_corrida+1)}: "
                              f"Média P. = {media_p_corrida:.3f} bar, "
                              f"{num_leituras_det} leituras detalhadas salvas.")
                        # Opcional: imprimir algumas leituras detalhadas
                        # leituras_det = corrida_info.get('leituras_pressao_detalhadas_bar', [])
                        # if leituras_det:
                        #     print(f"          Leituras (primeiras 3): {leituras_det[:3]}")


    except ValueError: print("Escolha inválida.")
    except Exception as e: print(f"Erro ao visualizar: {e}")


def realizar_coleta_de_teste_py(ser):
    global g_calibracao_concluida, g_calibracao_tendencia
    if not g_calibracao_concluida or g_calibracao_tendencia == 0: 
        print("ERRO: Calibração válida é necessária."); return

    print("\n=== CONFIGURAÇÃO DA NOVA BATERIA DE TESTES ===")
    try:
        # Solicitações de identificação
        descricao_bateria = input("Insira uma DESCRIÇÃO GERAL para esta bateria de testes: ")
        
        id_amostra_default = f"Amostra_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        id_amostra_input = input(f"ID da Amostra (padrão: {id_amostra_default}, Enter para padrão): ")
        id_amostra = id_amostra_input.strip() if id_amostra_input.strip() else id_amostra_default
        
        composicao_pasta = input("Composição da Pasta (opcional, Enter para pular): ").strip()
        lote_material_principal = input("Lote do Material Principal (opcional, Enter para pular): ").strip()
        
        while True:
            try:
                densidade_str = input("DENSIDADE da pasta (g/cm³): ")
                densidade_pasta_g_cm3 = float(densidade_str)
                if densidade_pasta_g_cm3 > 0: break
                else: print("Densidade deve ser um valor positivo.")
            except ValueError: print("Entrada inválida. Insira um número para densidade (ex: 1.23).")

        diametro_capilar_mm = float(input("DIÂMETRO do capilar/die (mm): "))
        comprimento_capilar_mm = float(input("COMPRIMENTO do capilar/die (mm): "))
        num_total_testes = int(input("Quantos PONTOS DE PRESSÃO diferentes nesta bateria? "))
        duracao_s_por_ponto = int(input("Duração da coleta para CADA PONTO (s)? "))

        if num_total_testes <= 0 or duracao_s_por_ponto <= 0 or diametro_capilar_mm <=0 or comprimento_capilar_mm <=0:
            print("Valores de configuração inválidos."); return
    except ValueError: print("Entrada inválida para configuração numérica."); return
    
    num_corridas_para_massa_p1 = 0
    if num_total_testes > 0:
        try:
            print("\nPara o PRIMEIRO PONTO de pressão:")
            num_corridas_para_massa_p1 = int(input(f"Quantas corridas para o somatório da massa do Ponto 1 (1 para normal)? "))
            if num_corridas_para_massa_p1 <= 0: num_corridas_para_massa_p1 = 1
        except ValueError: print("Inválido, usando 1 corrida para P1."); num_corridas_para_massa_p1 = 1

    resultados_bateria = {
        "descricao": descricao_bateria,
        "id_amostra": id_amostra,
        "composicao_pasta": composicao_pasta,
        "lote_material_principal": lote_material_principal,
        "densidade_pasta_g_cm3": densidade_pasta_g_cm3,
        "data_hora_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "diametro_capilar_mm": diametro_capilar_mm, 
        "comprimento_capilar_mm": comprimento_capilar_mm,
        "num_total_testes": num_total_testes,
        "duracao_por_teste_s": duracao_s_por_ponto,
        "num_corridas_massa_p1": num_corridas_para_massa_p1 if num_total_testes > 0 else 0,
        "soma_total_massa_p1_g": None, 
        "observacoes_gerais": "", # Será preenchido no final
        "testes": [] 
    }

    print("\n=== INICIANDO COLETA DE DADOS DA BATERIA ==="); intervalo_leitura_s = 1.0 

    for i in range(num_total_testes): 
        pressao_alvo_atual = PRESSOES_CALIBRACAO_CONHECIDAS[i] if i < len(PRESSOES_CALIBRACAO_CONHECIDAS) else (float(input(f"Insira a pressão alvo para o Ponto {i+1} (bar): ")))
        print(f"\n--- PONTO DE PRESSÃO {i + 1}/{num_total_testes} (Alvo: {pressao_alvo_atual:.1f} bar) ---")
        print(f"Ajuste a pressão para ~{pressao_alvo_atual:.1f} bar.")
        
        dados_ponto_pressao_atual = {
            "ponto_n": i + 1, "pressao_alvo_bar": pressao_alvo_atual,
            "media_pressao_final_ponto_bar": None,
            "massa_g_registrada": None, # Para P1: média do somatório; para P>1: entrada direta
            "corridas_executadas": [] # Lista para armazenar detalhes de cada corrida
        }

        num_corridas_aqui = num_corridas_para_massa_p1 if i == 0 else 1
        soma_pressoes_medias_ponto = 0.0; corridas_com_pressao_valida = 0
        
        for j in range(num_corridas_aqui): 
            if num_corridas_aqui > 1: print(f"\n  --- CORRIDA {j + 1}/{num_corridas_aqui} para Ponto {i + 1} ---")
            input("  Pressione ENTER para iniciar esta corrida..."); 
            
            print("  Contagem regressiva:") # TIMER CORRIGIDO
            print("  3...", flush=True); time.sleep(1)
            print("  2...", flush=True); time.sleep(1)
            print("  1...", flush=True); time.sleep(1)
            print("  COLETA!", flush=True)

            leituras_p_instantaneas_corrida = [] # Para armazenar pressões detalhadas desta corrida
            soma_pressoes_nesta_corrida = 0.0
            leituras_validas_nesta_corrida = 0
            t_inicio_coleta_corrida = time.time()

            for s_iter in range(duracao_s_por_ponto):
                t_inicio_iter = time.time(); leitura_ema = ler_float_do_arduino(ser, "READ_PRESSURE_EMA")
                p_inst = -999.0 
                if leitura_ema is not None:
                    p_inst = converter_sensor_para_pressao_py(leitura_ema)
                    if p_inst >= -0.5 : 
                         p_inst = max(0.0, p_inst) 
                         leituras_p_instantaneas_corrida.append(round(p_inst,3)) # Salva leitura detalhada
                         soma_pressoes_nesta_corrida += p_inst
                         leituras_validas_nesta_corrida += 1
                
                print(f"    P{i+1}{f'-C{j+1}' if num_corridas_aqui > 1 else ''} [{duracao_s_por_ponto - 1 - s_iter}s] P: ", end="")
                if p_inst < -0.5: print(f"ErroCalib({p_inst:.0f}) bar")
                else: print(f"{p_inst:.2f} bar")
                t_proc = time.time()-t_inicio_iter; time.sleep(max(0, intervalo_leitura_s-t_proc))
            
            print(f"  Duração real da corrida {j+1}: {time.time()-t_inicio_coleta_corrida:.2f}s")
            
            media_p_corrida_atual = None
            if leituras_validas_nesta_corrida > 0:
                media_p_corrida_atual = soma_pressoes_nesta_corrida / leituras_validas_nesta_corrida
                soma_pressoes_medias_ponto += media_p_corrida_atual
                corridas_com_pressao_valida +=1
                print(f"  Média Pressão Corrida {j+1}: {media_p_corrida_atual:.3f} bar")
            else: 
                print(f"  Sem leituras válidas de pressão para Corrida {j+1}.")

            dados_ponto_pressao_atual["corridas_executadas"].append({
                "corrida_num": j + 1,
                "media_pressao_calculada_corrida_bar": round(media_p_corrida_atual,3) if media_p_corrida_atual is not None else None,
                "leituras_pressao_detalhadas_bar": leituras_p_instantaneas_corrida
            })
        
        # Fim do loop de corridas (j)
        if corridas_com_pressao_valida > 0:
            dados_ponto_pressao_atual["media_pressao_final_ponto_bar"] = round(soma_pressoes_medias_ponto / corridas_com_pressao_valida, 3)
        
        print(f"\n  RESULTADO DE PRESSÃO PARA PONTO {i+1}:")
        print(f"    Média das Pressões Medidas: {dados_ponto_pressao_atual['media_pressao_final_ponto_bar'] if dados_ponto_pressao_atual['media_pressao_final_ponto_bar'] is not None else 'N/A'} bar")

        # Coleta de Massa
        if i == 0: # Primeiro ponto de pressão - coleta somatório da massa
            try:
                soma_total_massas_para_p1_input = float(input(f"  Insira o SOMATÓRIO da massa extrudada para TODAS as {num_corridas_para_massa_p1} corridas do Ponto 1 (g): "))
                resultados_bateria["soma_total_massa_p1_g"] = soma_total_massas_para_p1_input
                if num_corridas_para_massa_p1 > 0:
                    media_massa_calculada_p1 = soma_total_massas_para_p1_input / num_corridas_para_massa_p1
                    dados_ponto_pressao_atual["massa_g_registrada"] = round(media_massa_calculada_p1,3)
                    print(f"    Média de Massa Calculada para Ponto 1 (por corrida): {media_massa_calculada_p1:.3f} g")
                else: print("    Não foi possível calcular média de massa (0 corridas).")
            except ValueError: print("    Entrada de somatório de massa inválida."); dados_ponto_pressao_atual["massa_g_registrada"] = None
        else: # Pontos de pressão subsequentes (i > 0) - coleta massa individual
            try:
                massa_g_ponto_atual = float(input(f"  Insira a MASSA EXTRUDADA para Ponto {i+1} ({pressao_alvo_atual:.1f} bar) (g): "))
                dados_ponto_pressao_atual["massa_g_registrada"] = round(massa_g_ponto_atual,3)
                print(f"    Massa Registrada para Ponto {i+1}: {massa_g_ponto_atual:.3f} g")
            except ValueError: print("    Entrada de massa inválida. Usando 0.0g."); dados_ponto_pressao_atual["massa_g_registrada"] = 0.0
        
        resultados_bateria["testes"].append(dados_ponto_pressao_atual)
        print(f"--- Ponto de Teste {i+1} concluído ---")

    # Após todos os pontos de pressão
    resultados_bateria["observacoes_gerais"] = input("\nObservações Gerais sobre esta bateria de testes (opcional, Enter para pular): ").strip()

    print("\n=== COLETA DE DADOS DA BATERIA CONCLUÍDA ===")
    print(f"ID Amostra: {resultados_bateria['id_amostra']}")
    print(f"Descrição: {resultados_bateria['descricao']}")
    # ... (imprimir outros novos campos)
    print(f"Diâmetro: {resultados_bateria['diametro_capilar_mm']} mm, Comprimento: {resultados_bateria['comprimento_capilar_mm']} mm")
    print(f"Densidade: {resultados_bateria['densidade_pasta_g_cm3']} g/cm³")
    
    soma_massa_p1_info = resultados_bateria.get("soma_total_massa_p1_g")
    num_corridas_p1_info = resultados_bateria.get("num_corridas_massa_p1")
    if soma_massa_p1_info is not None and num_corridas_p1_info is not None and num_corridas_p1_info > 0:
        media_m_p1 = soma_massa_p1_info / num_corridas_p1_info
        print(f"Info Massa Ponto 1: Total {soma_massa_p1_info:.3f}g de {num_corridas_p1_info} corridas (Média: {media_m_p1:.3f} g/corrida)")
    
    for teste_data_final in resultados_bateria["testes"]:
        print(f"  Ponto {teste_data_final['ponto_n']} (Alvo {teste_data_final['pressao_alvo_bar']:.1f} bar): "
              f"P.Medida={teste_data_final['media_pressao_final_ponto_bar'] if teste_data_final['media_pressao_final_ponto_bar'] is not None else 'N/A'} bar, "
              f"Massa={teste_data_final.get('massa_g_registrada', 'N/A')} g")

    if input("\nDeseja salvar esta bateria de testes? (s/n): ").lower() == 's':
        salvar_resultados_json_individual_py(resultados_bateria)


# --- Menu Principal do Python (sem alterações na estrutura) ---
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
        # ... (resto das opções do menu como antes) ...
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
                            print(f"Pressão Imediata: {pressao:.2f} bar (EMA: {leitura_ema:.2f})   
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
            # --- LÓGICA DE DETECÇÃO AUTOMÁTICA E MULTIPLATAFORMA ---
            print("Nenhuma porta serial especificada. Procurando portas disponíveis...")
            portas_disponiveis = serial.tools.list_ports.comports()
            
            if not portas_disponiveis:
                print("Nenhuma porta serial física foi encontrada no sistema.")
            else:
                print("Portas encontradas:")
                for porta in portas_disponiveis:
                    # Tenta se conectar a portas que parecem ser um Arduino
                    if "USB" in porta.description.upper() or \
                       "ARDUINO" in porta.description.upper() or \
                       "CH340" in porta.description.upper():
                        
                        print(f"  Tentando porta promissora: {porta.device} ({porta.description})")
                        arduino_ser = conectar_arduino(porta.device, BAUD_RATE)
                        if arduino_ser:
                            SERIAL_PORT = porta.device
                            print(f"Conexão bem-sucedida em: {SERIAL_PORT}")
                            break # Sai do laço se conectar com sucesso
            
            # Se ainda não conectou, tenta todas as portas como último recurso
            if not arduino_ser and portas_disponiveis:
                print("\nNão foi possível conectar a uma porta conhecida. Tentando todas as portas...")
                for porta in portas_disponiveis:
                    print(f"  Tentando porta genérica {porta.device}...")
                    arduino_ser = conectar_arduino(porta.device, BAUD_RATE)
                    if arduino_ser:
                        SERIAL_PORT = porta.device
                        print(f"Conexão bem-sucedida em: {SERIAL_PORT}")
                        break
            # --- FIM DA NOVA LÓGICA ---

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
