/**
 * @file Pro-micro-Transdutor-Reometro-capilar.ino
 * @brief Firmware para reômetro capilar com DOIS transdutores de pressão
 * analógicos (0-5V) e referência externa LM4040 (4.096V).
 * @version 3.1
 * @author Bruno Egami (Modificado por Gemini)
 * @date 21/03/2026
 *
 * @details
 * Este código lê sinais de tensão de dois transdutores de pressão:
 * 1. Transdutor do Barril (Principal) -> Pino A0
 * 2. Transdutor da Entrada do Capilar (Membrana Aflorante) -> Pino A1
 *
 * Referência de tensão: LM4040 4.096V no pino AREF.
 * Resolução ADC: 4.096 / 1024 = 0.004 V/bit.
 * Nota: Com Vref = 4.096V, a leitura máxima é ~8.99 bar (saturação do ADC).
 *
 * O firmware aguarda comandos via porta serial e responde com as tensões.
 *
 * Conexão do Hardware:
 * - Sensor 1 (Barril): Sinal -> A0, VCC -> 5V, GND -> GND
 * - Sensor 2 (Capilar): Sinal -> A1, VCC -> 5V, GND -> GND
 * - LM4040 4.096V: Vout -> AREF
 */

// --- CONFIGURAÇÕES ---

// Define os pinos analógicos
#define SENSOR_PIN_1 A0
#define SENSOR_PIN_2 A1

// Parâmetro para o filtro de Média Móvel Exponencial (EMA).
#define EMA_ALPHA 0.3

// --- Variáveis Globais ---
float ema_voltage_1 = 0.0;
float ema_voltage_2 = 0.0;
bool ema_initialized = false;

/**
 * @brief Função de configuração inicial.
 */
void setup() {
  analogReference(EXTERNAL); // LM4040 4.096V como referência estável
  Serial.begin(115200);
  Serial.setTimeout(100); // A-04: limita bloqueio do readStringUntil a 100 ms
  pinMode(SENSOR_PIN_1, INPUT);
  pinMode(SENSOR_PIN_2, INPUT);

  Serial.println(
      F("Arduino: Inicializado com 2 transdutores de pressao 0-5V."));
  Serial.println(F("Arduino: Pronto."));
}

/**
 * @brief Lê a tensão de um pino e aplica o filtro EMA específico.
 */
void updateReadings() {
  // Oversampling 4x para +1 bit de resolução efetiva (~1ms adicional)
  long sum1 = 0, sum2 = 0;
  for (int i = 0; i < 4; i++) {
    sum1 += analogRead(SENSOR_PIN_1);
    sum2 += analogRead(SENSOR_PIN_2);
    delayMicroseconds(250);
  }
  float v1 = (sum1 / 4.0) * (4.096 / 1024.0);
  float v2 = (sum2 / 4.0) * (4.096 / 1024.0);

  if (!ema_initialized) {
    ema_voltage_1 = v1;
    ema_voltage_2 = v2;
    ema_initialized = true;
  } else {
    ema_voltage_1 = (v1 * EMA_ALPHA) + (ema_voltage_1 * (1.0 - EMA_ALPHA));
    ema_voltage_2 = (v2 * EMA_ALPHA) + (ema_voltage_2 * (1.0 - EMA_ALPHA));
  }
}

/**
 * @brief Loop principal.
 */
void loop() {
  // Atualiza as leituras constantemente para o filtro funcionar bem
  updateReadings();

  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    // --- Processamento de Comandos ---

    // Retorna "V1;V2"
    if (command == "READ_VOLTAGE") {
      Serial.print(ema_voltage_1, 4);
      Serial.print(";");
      Serial.println(ema_voltage_2, 4);
    } else if (command == "PING") {
      Serial.println(F("ACK_PING_OK"));
    }
    // A-02: Reinicializa o filtro EMA para novo ensaio
    else if (command == "RESET_EMA") {
      ema_initialized = false;
      Serial.println(F("ACK_RESET_EMA"));
    } else {
      Serial.print(F("Arduino: Comando desconhecido - "));
      Serial.println(command);
    }
  }
  delay(10); // Pequeno delay para estabilidade
}
