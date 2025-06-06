#include <HX711.h>

// Definições dos pinos do HX711
#define DOUT1 A0
#define CLK1 A1

HX711 scale1_pressure; // célula de carga para pressão
// Se adicionar uma segunda célula para massa, ela precisará de seu próprio objeto HX711 e pinos.

// Parâmetro para o filtro EMA 
#define EMA_ALPHA_PRESSURE 1.0 // Ajusta sensibilidade do filtro
float ema_S_pressure = 0.0;
bool ema_inicializado_pressure = false;

// --- INÍCIO DAS MODIFICAÇÕES PARA UMA SEGUNDA CÉLULA DE CARGA PARA MASSA ---
// #define DOUT2 A2 // Exemplo de pino para a segunda célula de carga
// #define CLK2  A3 // Exemplo de pino
// HX711 scale2_mass;
// #define EMA_ALPHA_MASS 0.2 // Pode ser diferente para a massa
// float ema_S_mass = 0.0;
// bool ema_inicializado_mass = false;
// --- FIM DAS MODIFICAÇÕES PARA A CÉLULA DE CARGA DE MASSA ---


void setup() {
  Serial.begin(115200); // Taxa de comunicação com Python

  // Inicializa o HX711 para o sensor de PRESSÃO
  scale1_pressure.begin(DOUT1, CLK1);
  scale1_pressure.set_gain(128); 
  Serial.println(F("Arduino: Inicializando sensor de pressão..."));
  scale1_pressure.tare(); // Tara inicial do sensor de pressão
  ema_S_pressure = 0.0;
  ema_inicializado_pressure = false;
  Serial.println(F("Arduino: Sensor de pressão tarado e pronto."));

  // --- INÍCIO DAS MODIFICAÇÕES PARA A CÉLULA DE CARGA DE MASSA ---
  // if (/* condição para inicializar a célula de massa */) {
  //   scale2_mass.begin(DOUT2, CLK2);
  //   scale2_mass.set_gain(128); // Ajuste o ganho conforme necessário para a célula de massa
  //   Serial.println(F("Arduino: Inicializando sensor de massa..."));
  //   scale2_mass.tare();
  //   ema_S_mass = 0.0;
  //   ema_inicializado_mass = false;
  //   Serial.println(F("Arduino: Sensor de massa tarado e pronto."));
  // }
  // --- FIM DAS MODIFICAÇÕES PARA A CÉLULA DE CARGA DE MASSA ---

  Serial.println(F("Arduino: Pronto para receber comandos do Python."));
}

float obterLeituraSensorEMAPressure() {
  float leitura_hx_raw = scale1_pressure.get_units(2); // Leitura rápida
  
  if (EMA_ALPHA_PRESSURE == 1.0) {
      ema_S_pressure = leitura_hx_raw;
      if(!ema_inicializado_pressure) ema_inicializado_pressure = true; 
  } else { 
      if (!ema_inicializado_pressure) {
        ema_S_pressure = leitura_hx_raw;
        ema_inicializado_pressure = true;
      } else {
        ema_S_pressure = (leitura_hx_raw * EMA_ALPHA_PRESSURE) + (ema_S_pressure * (1.0 - EMA_ALPHA_PRESSURE));
      }
  }
  return ema_S_pressure;
}

// --- INÍCIO DAS MODIFICAÇÕES PARA A CÉLULA DE CARGA DE MASSA ---
/*
float obterLeituraSensorEMAMass() {
  float leitura_hx_raw = scale2_mass.get_units(5); // Pode usar mais amostras para massa se necessário
  
  if (EMA_ALPHA_MASS == 1.0) { // Se quiser desativar o EMA para massa também
      ema_S_mass = leitura_hx_raw;
      if(!ema_inicializado_mass) ema_inicializado_mass = true; 
  } else { 
      if (!ema_inicializado_mass) {
        ema_S_mass = leitura_hx_raw;
        ema_inicializado_mass = true;
      } else {
        ema_S_mass = (leitura_hx_raw * EMA_ALPHA_MASS) + (ema_S_mass * (1.0 - EMA_ALPHA_MASS));
      }
  }
  return ema_S_mass;
}
*/
// --- FIM DAS MODIFICAÇÕES PARA A CÉLULA DE CARGA DE MASSA ---


void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "TARE_PRESSURE") {
      scale1_pressure.tare();
      ema_S_pressure = 0.0;
      ema_inicializado_pressure = false;
      Serial.println(F("ACK_TARE_PRESSURE_OK"));
    } else if (command == "READ_PRESSURE_EMA") {
      float sensorValue = obterLeituraSensorEMAPressure();
      Serial.println(sensorValue, 4); // Envia o valor com 4 casas decimais
    } 
    // --- INÍCIO DAS MODIFICAÇÕES PARA A CÉLULA DE CARGA DE MASSA ---
    /*
    else if (command == "TARE_MASS") {
      scale2_mass.tare();
      ema_S_mass = 0.0;
      ema_inicializado_mass = false;
      Serial.println(F("ACK_TARE_MASS_OK"));
    } else if (command == "READ_MASS_EMA") {
      float sensorValueMass = obterLeituraSensorEMAMass();
      Serial.println(sensorValueMass, 4); // Envia o valor com 4 casas decimais
    }
    */
    // --- FIM DAS MODIFICAÇÕES PARA A CÉLULA DE CARGA DE MASSA ---
    else if (command == "PING") {
      Serial.println(F("ACK_PING_OK")); // Comando simples para verificar conexão
    }
    // Outros comandos podem ser adicionados conforme necessário, por exemplo, para ler
    // o valor bruto do HX711 sem EMA, ou para controlar LEDs, atuadores ou relé para controle de registro pneumático se houver. 
    else {
      Serial.print(F("Arduino: Comando desconhecido - "));
      Serial.println(command);
    }
  }
  // O Arduino pode realizar outras tarefas aqui se necessário, mas o foco é responder ao Python.
}
