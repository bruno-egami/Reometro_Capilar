// Código para teste reológico com várias pressões e entrada manual da massa extrudada
// Versão otimizada com menor uso de memória

#include <HX711.h>

#define DOUT1 A0
#define CLK1 A1

HX711 scale1;

// Constantes do sistema (em milímetros) - APENAS EDITÁVEIS NO CÓDIGO
const float L_mm = 10.0;            // Comprimento do bico (mm)
const float R_mm = 1.5;             // Raio do bico (mm)

// Constantes de calibração dos extensômetros
const float coeficiente = -0.00000082077;  // Ajuste de calibração -0.3251 -0,0000008247765619
const float offset = 0.35;         // Offset de tara

const int temposExtrusao = 3;       // Tempo de extrusão (s)
const int tempoPreparacao = 3;      // Tempo de preparação (s)
const float pressao_testes_bar[] PROGMEM = {1, 2, 3, 4, 5};
const int num_testes = 5;

// Variáveis globais reduzidas
float densidade = 0.0;
float massas[num_testes];
float pressoesReais[num_testes];

void setup() {
  Serial.begin(115200);
  
  // Inicialização do HX711
  scale1.begin(DOUT1, CLK1);
  scale1.set_gain(128);
  delay(2000);
  scale1.tare();
  
  Serial.println(F("=== SISTEMA DE MEDIÇÃO REOLÓGICA ==="));
  Serial.println(F("Sistema inicializado e pronto para uso.\n"));
  
  // Pergunta sobre calibração
  Serial.println(F("Deseja calibrar os extensômetros? (s/n):"));
  char resposta = aguardarEntradaChar();
  if (resposta == 's' || resposta == 'S') {
    calibrarExtensometros();
  }
  
  // Solicita apenas densidade
  solicitarDensidade();
  
  // Executa primeira bateria de testes
  executarTestes();
}

void loop() {
  Serial.println(F("\n=== OPÇÕES ==="));
  Serial.println(F("1 - Nova bateria de testes"));
  Serial.println(F("2 - Alterar densidade"));
  Serial.println(F("3 - Calibrar extensômetros"));
  Serial.println(F("4 - Visualizar últimos resultados"));
  Serial.println(F("5 - Sair"));
  Serial.println(F("Digite sua opção (1-5):"));
  
  char opcao = aguardarEntradaChar();
  
  switch(opcao) {
    case '1':
      executarTestes();
      break;
    case '2':
      solicitarDensidade();
      break;
    case '3':
      calibrarExtensometros();
      break;
    case '4':
      mostrarResultados();
      break;
    case '5':
      Serial.println(F("Programa encerrado. Obrigado por usar o sistema!"));
      Serial.println(F("Para reiniciar, pressione o botão RESET do Arduino."));
      while(true) { 
        delay(10000); // Para o programa definitivamente
      }
      break;
    default:
      Serial.println(F("Opção inválida! Tente novamente (1-5)."));
      break;
  }
}

void solicitarDensidade() {
  Serial.println(F("\n=== CONFIGURAÇÃO DE DENSIDADE ==="));
  Serial.println(F("Insira a densidade da pasta (g/cm³):"));
  densidade = aguardarEntradaFloat();
  Serial.print(F("Densidade registrada: "));
  Serial.print(densidade, 3);
  Serial.println(F(" g/cm³"));
  
  // Mostra dimensões fixas do bico
  Serial.print(F("Dimensões do bico (fixas): L="));
  Serial.print(L_mm, 1);
  Serial.print(F("mm, R="));
  Serial.print(R_mm, 2);
  Serial.println(F("mm\n"));
}

void executarTestes() {
  Serial.println(F("=== INICIANDO BATERIA DE TESTES ===\n"));
  
  for (int i = 0; i < num_testes; i++) {
    float pressao_bar = pgm_read_float(&pressao_testes_bar[i]);
    
    Serial.print(F("TESTE "));
    Serial.print(i + 1);
    Serial.print(F("/"));
    Serial.print(num_testes);
    Serial.print(F(" - Pressão: "));
    Serial.print(pressao_bar);
    Serial.println(F(" bar"));
    
    Serial.println(F("Configure o sistema para a pressão indicada."));
    Serial.println(F("Pressione ENTER quando estiver pronto..."));
    aguardarEnter();
    
    // Contagem regressiva
    Serial.print(F("Iniciando em: "));
    for (int t = tempoPreparacao; t > 0; t--) {
      Serial.print(t);
      Serial.print(F("... "));
      delay(1000);
    }
    Serial.println(F("EXTRUSÃO INICIADA!"));
    
    // Cronômetro de extrusão
    for (int t = 1; t <= temposExtrusao; t++) {
      Serial.print(F("Tempo decorrido: "));
      Serial.print(t);
      Serial.print(F("/"));
      Serial.print(temposExtrusao);
      Serial.println(F(" s"));
      delay(1000);
    }
    
    Serial.println(F("EXTRUSÃO FINALIZADA!"));
    
    // Lê pressão real dos extensômetros
    float pressaoReal = lerPressaoExtensometros();
    pressoesReais[i] = pressaoReal;
    
    Serial.print(F("Pressão medida pelos extensômetros: "));
    Serial.print(pressaoReal, 2);
    Serial.println(F(" bar"));
    
    // Loop para permitir refazer o teste se necessário
    bool testeOk = false;
    while (!testeOk) {
      Serial.println(F("Insira a massa extrudada (g) ou digite 'n' para refazer este teste:"));
      
      String entrada = aguardarEntradaString();
      
      if (entrada == "n" || entrada == "N") {
        Serial.println(F("Refazendo o teste para esta pressão...\n"));
        i--; // Decrementa para repetir o mesmo índice
        break; // Sai do while e volta para o for
      } else {
        float massa = entrada.toFloat();
        if (massa >= 0) {
          massas[i] = massa;
          
          Serial.print(F("Massa registrada: "));
          Serial.print(massa, 2);
          Serial.println(F(" g"));
          
          if (massa == 0) {
            Serial.println(F("Pressão insuficiente para extrusão.\n"));
          } else {
            Serial.println(F("Parâmetros calculados!\n"));
          }
          
          testeOk = true; // Teste foi concluído com sucesso
        } else {
          Serial.println(F("Valor inválido! Digite um número não-negativo ou 'n' para refazer."));
        }
      }
    }
  }
  
  // Mostra resultados
  mostrarResultados();
}

void mostrarResultados() {
  Serial.println(F("\n========================== RESULTADOS ==========================="));
  Serial.println(F("Pressão | Pressão | Massa  | Volume | Vazão  | Taxa Cisal. | Tensão Cisal. | Viscosidade"));
  Serial.println(F("Nominal | Medida  |  (g)   | (mm³)  |(mm³/s) |    (1/s)    |     (Pa)      |   (Pa·s)   "));
  Serial.println(F(" (bar)  | (bar)   |        |        |        |             |               |            "));
  Serial.println(F("--------|---------|--------|--------|--------|-------------|---------------|------------"));
  
  float somaViscosidade = 0;
  float maxVazao = 0;
  float maxDiferenca = 0;
  
  for (int i = 0; i < num_testes; i++) {
    float pressao_bar = pgm_read_float(&pressao_testes_bar[i]);
    
    // Calcula parâmetros dinamicamente para economizar RAM
    float volume = (massas[i] / densidade) * 1000.0; // Converte cm³ para mm³
    float vazao = volume / temposExtrusao; // mm³/s
    
    // Cálculos reológicos (só se houver massa extrudada)
    float taxaCisalhamento = 0;
    float tensaoCisalhamento = 0;
    float viscosidade = 0;
    
    if (massas[i] > 0) {
      float L_m = L_mm / 1000.0;
      float R_m = R_mm / 1000.0;
      float vazao_m3s = vazao * 1e-9; // mm³/s para m³/s
      taxaCisalhamento = (4.0 * vazao_m3s) / (PI * pow(R_m, 3));
      float pressao_Pa = pressoesReais[i] * 1e5;
      tensaoCisalhamento = (pressao_Pa * R_m) / (2.0 * L_m);
      viscosidade = (taxaCisalhamento > 0) ? tensaoCisalhamento / taxaCisalhamento : 0;
    }
    
    Serial.print(F("  "));
    Serial.print(pressao_bar, 1);
    Serial.print(F("   |  "));
    Serial.print(pressoesReais[i], 2);
    Serial.print(F("  | "));
    Serial.print(massas[i], 2);
    Serial.print(F(" | "));
    
    if (massas[i] == 0) {
      Serial.print(F("  0.00 |  0.00  |      0.0     |       0.0     |    0.0000"));
    } else {
      Serial.print(volume, 1);
      Serial.print(F(" | "));
      Serial.print(vazao, 1);
      Serial.print(F(" | "));
      Serial.print(taxaCisalhamento, 1);
      Serial.print(F("     | "));
      Serial.print(tensaoCisalhamento, 1);
      Serial.print(F("       | "));
      Serial.print(viscosidade, 4);
    }
    Serial.println();
    
    // Acumula para análise (apenas se houve extrusão)
    if (massas[i] > 0) {
      somaViscosidade += viscosidade;
      if (vazao > maxVazao) maxVazao = vazao;
    }
    
    float diferenca = abs(pressao_bar - pressoesReais[i]);
    if (diferenca > maxDiferenca) maxDiferenca = diferenca;
  }
  
  Serial.println(F("==================================================================="));
  
  // Análise básica
  Serial.println(F("\n=== ANÁLISE BÁSICA ==="));
  
  // Parâmetros do teste
  Serial.println(F("--- Parâmetros do Teste ---"));
  Serial.print(F("Densidade: "));
  Serial.print(densidade, 3);
  Serial.println(F(" g/cm³"));
  Serial.print(F("Comprimento do bico: "));
  Serial.print(L_mm, 1);
  Serial.println(F(" mm"));
  Serial.print(F("Raio do bico: "));
  Serial.print(R_mm, 2);
  Serial.println(F(" mm"));
  Serial.print(F("Tempo de extrusão: "));
  Serial.print(temposExtrusao);
  Serial.println(F(" s"));
  
  // Resultados
  Serial.println(F("\n--- Resultados ---"));
  
  // Conta quantos testes tiveram extrusão
  int testesComExtrusao = 0;
  for (int i = 0; i < num_testes; i++) {
    if (massas[i] > 0) testesComExtrusao++;
  }
  
  if (testesComExtrusao > 0) {
    Serial.print(F("Viscosidade média: "));
    Serial.print(somaViscosidade / testesComExtrusao, 4);
    Serial.println(F(" Pa·s"));
    
    Serial.print(F("Vazão máxima: "));
    Serial.print(maxVazao, 1);
    Serial.println(F(" mm³/s"));
  } else {
    Serial.println(F("Nenhum teste resultou em extrusão."));
  }
  
  Serial.print(F("Diferença máxima entre pressão nominal e medida: "));
  Serial.print(maxDiferenca, 2);
  Serial.println(F(" bar"));
}

String aguardarEntradaString() {
  while (Serial.available() == 0) {
    delay(10);
  }
  
  String entrada = Serial.readString();
  entrada.trim();
  
  // Limpa buffer
  while (Serial.available()) {
    Serial.read();
  }
  
  return entrada;
}

float aguardarEntradaFloat() {
  while (Serial.available() == 0) {
    delay(10);
  }
  
  float valor = Serial.parseFloat();
  
  // Limpa buffer
  while (Serial.available()) {
    Serial.read();
  }
  
  return valor;
}

char aguardarEntradaChar() {
  while (Serial.available() == 0) {
    delay(10);
  }
  
  char valor = Serial.read();
  
  // Limpa buffer
  while (Serial.available()) {
    Serial.read();
  }
  
  return valor;
}

void aguardarEnter() {
  while (Serial.available() == 0) {
    delay(10);
  }
  
  // Limpa todo o buffer
  while (Serial.available()) {
    Serial.read();
  }
}

void calibrarExtensometros() {
  Serial.println(F("\n=== CALIBRAÇÃO DOS EXTENSÔMETROS ==="));
  Serial.println(F("Certifique-se de que o sistema esteja despressurizado."));
  Serial.println(F("Pressione ENTER para fazer a tara..."));
  aguardarEnter();
  
  // Faz tara do sistema
  scale1.tare();
  Serial.println(F("Tara realizada com sucesso!"));
  
  Serial.println(F("Sistema pronto para medições de pressão."));
  delay(1000);
}

float lerPressaoExtensometros() {
  // Faz várias leituras para maior precisão
  const int numLeituras = 10;
  float somaLeituras = 0;
  
  for (int i = 0; i < numLeituras; i++) {
    float leitura = scale1.get_units();
    somaLeituras += leitura;
    delay(50);
  }
  
  float leituraMedia = somaLeituras / numLeituras;
  
  // Conversão da leitura do HX711 para pressão em bar
  float pressao_bar = (leituraMedia * coeficiente) + offset;
  
  // Garante que pressão não seja negativa
  if (pressao_bar < 0) {
    pressao_bar = 0;
  }
  
  return pressao_bar;
}
