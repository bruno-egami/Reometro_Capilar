#include <HX711.h>

//Conexão com Arduino
#define DOUT1 A0
#define CLK1 A1

HX711 scale1;

// Parâmetros de calibração
const float coeficiente = -0.3251;  // multiplicador para ajuste após regressão
const float offset = -0.50;      // Offset de zero

// Filtro exponencial (EMA)
float alpha = 1.0;              // Fator de suavização (menor atenua, maior mais sensível)
float mvRead1 = 0;
float ema_mvRead1 = 0;
float pressure_bar = 0;

// Tempo de aquecimento (em minutos) 
const unsigned int warmup_minutes = 1;

void setup() {
  Serial.begin(115200);
  scale1.begin(DOUT1, CLK1);
  scale1.set_gain(128);

  unsigned long warmup_seconds = warmup_minutes * 60;

  Serial.print("Aquecimento... Esperando ");
  Serial.print(warmup_minutes);
  Serial.println(" minuto(s) para tara automática.");
  Serial.println("Pressione qualquer tecla para pular.");

  for (unsigned long i = 0; i < warmup_seconds; i++) {
    if (Serial.available()) {
      Serial.read();  // Lê e descarta o caractere pressionado
      Serial.println("Aquecimento interrompido pelo usuário.");
      break;
    }

    Serial.print("Aquecimento dos resistores, pressione enviar para pular: ");
    Serial.print((warmup_seconds - i) / 60);
    Serial.print(" min ");
    Serial.print((warmup_seconds - i) % 60);
    Serial.println(" s");

    delay(1000);  // Espera 1 segundo
  }

  scale1.tare();  // Tara após aquecimento ou interrupção
  Serial.println("Tara concluída.");
}

void loop() {
  // Leitura bruta do HX711
  long data_in1 = scale1.get_value();

  // Conversão para milivolts
  mvRead1 = (((data_in1 * 5.0) / 16777215.0) / 128.0) * 1000.0;

  // Filtro EMA
  ema_mvRead1 = alpha * mvRead1 + (1 - alpha) * ema_mvRead1;

  // Conversão para pressão (com offset)
  pressure_bar = coeficiente * ema_mvRead1 - offset;

  // Exibição no monitor serial
  //Serial.print(mvRead1, 10);// dados brutos do HX711
  //Serial.print(" mV (EMA): ");
  //Serial.print(ema_mvRead1, 10); //dados filtrados (EMA)
  Serial.print(" | Pressão: ");
  Serial.print(pressure_bar * 14.5, 4);
  Serial.print(" PSI / ");
  Serial.print(pressure_bar, 4);
  Serial.println(" bar");

  // Verifica comando de tara
  if (Serial.available()) {
    char comando = Serial.read();
    if (comando == 't' || comando == 'T') {
      Serial.println("Tara ativada!");
      scale1.tare();
    }
  }

  delay(1000);  // 1 leitura por segundo
}
