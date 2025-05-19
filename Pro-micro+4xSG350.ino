// Código para teste reológico com várias pressões e entrada manual da massa extrudada

#include <HX711.h>

#define DOUT1 A0
#define CLK1 A1

HX711 scale1;

const float alpha = 0.2;         // Filtro EMA
const float coeficiente = -0.44; // Ajuste de calibração
const float offset = 0.0;        // Offset de tara
const float L = 0.01;            // Comprimento do bico em metros (10 mm)
const float R = 0.0015;          // Raio do bico em metros (3 mm / 2)

// Configurações do teste
const int temposExtrusao = 30; // Tempo de extrusão em segundos (ajustável)
const int tempoPreparacao = 3; // Tempo para o usuário se preparar antes de iniciar cada extrusão
const float pressao_testes_bar[] = {1, 2, 3, 4, 5};
const int num_testes = sizeof(pressao_testes_bar) / sizeof(pressao_testes_bar[0]);

float densidade = 0.0;
float ema_mvRead1 = 0;

void setup() {
  Serial.begin(115200);
  scale1.begin(DOUT1, CLK1);
  scale1.set_gain(128);
  delay(2000);
  scale1.tare();

  Serial.println("Insira a densidade da pasta (g/cm3):");
  while (Serial.available() == 0) {}
  densidade = Serial.parseFloat();
  Serial.print("Densidade registrada: ");
  Serial.print(densidade, 3);
  Serial.println(" g/cm3\n");

  for (int i = 0; i < num_testes; i++) {
    float pressao_bar = pressao_testes_bar[i];
    Serial.print("\nConfigure o sistema para ");
    Serial.print(pressao_bar);
    Serial.println(" bar e pressione qualquer tecla para iniciar...");
    while (Serial.available() == 0) {}
    while (Serial.available()) Serial.read();

    // Tempo para preparação
    Serial.print("Iniciando em: ");
    for (int t = tempoPreparacao; t > 0; t--) {
      Serial.print(t); Serial.print("...");
      delay(1000);
    }
    Serial.println("Iniciando extrusão!");

    // Inicia contagem
    unsigned long inicio = millis();
    while (millis() - inicio < temposExtrusao * 1000UL) {
      long data_in1 = scale1.get_value();
      float mvRead1 = (((data_in1 * 5.0) / 16777215.0) / 128.0) * 1000.0;
      ema_mvRead1 = alpha * mvRead1 + (1 - alpha) * ema_mvRead1;
      delay(1000);
    }

    Serial.print("Tempo finalizado. Insira a massa extrudada (g) para ");
    Serial.print(pressao_bar);
    Serial.println(" bar (pressione Enter se nada foi extrudado):");

    while (Serial.available() == 0) {}
    float massa = Serial.parseFloat();

    if (massa > 0) {
      float volume = massa / densidade / 1000.0; // cm3 -> m3
      float Q = volume / temposExtrusao;         // Vazão m3/s
      float deltaP = pressao_bar * 100000;       // bar -> Pa
      float viscosidade = (deltaP * pow(R, 4)) / (8 * Q * L); // Poiseuille
      Serial.print("Viscosidade: ");
      Serial.print(viscosidade, 2);
      Serial.println(" Pa.s\n");
    } else {
      Serial.println("Sem extrusão registrada para esta pressão.\n");
    }
  }
  Serial.println("\nTestes finalizados.");
}

void loop() {
  // Não faz mais nada após a série de testes
}
