#include <HX711.h>
#include <EEPROM.h> // Biblioteca para memória não volátil

// Definições dos pinos do HX711
#define DOUT1 A0
#define CLK1 A1

HX711 scale1;

// Endereços na EEPROM para salvar os coeficientes de calibração
#define EEPROM_ADDR_COEFICIENTE 0                     // Início do float para o coeficiente (4 bytes)
#define EEPROM_ADDR_OFFSET      (EEPROM_ADDR_COEFICIENTE + sizeof(float)) // Início do float para o offset (4 bytes)
#define EEPROM_ADDR_FLAG_VALIDO (EEPROM_ADDR_OFFSET + sizeof(float))      // Endereço para um byte de flag
#define EEPROM_FLAG_VALOR_ESPERADO 0xCA // Um valor arbitrário para indicar que a EEPROM tem dados válidos

// Variáveis globais para calibração (serão carregadas da EEPROM ou terão valores padrão)
float g_coeficiente;
float g_offset;

// Parâmetro para o filtro EMA
#define EMA_ALPHA 0.2

// Variáveis globais para o filtro EMA
float ema_S = 0.0;
bool ema_inicializado = false;

// Variáveis globais para os parâmetros e dados dos testes
int g_num_testes = 0;
int g_duracao_teste_s = 0;
float* g_media_pressao_testes = nullptr;

void carregarCalibracaoDaEEPROM() {
  Serial.println(F("Verificando dados de calibração na EEPROM..."));
  byte flag = EEPROM.read(EEPROM_ADDR_FLAG_VALIDO);

  if (flag == EEPROM_FLAG_VALOR_ESPERADO) {
    Serial.println(F("Dados de calibração válidos encontrados. Carregando..."));
    EEPROM.get(EEPROM_ADDR_COEFICIENTE, g_coeficiente);
    EEPROM.get(EEPROM_ADDR_OFFSET, g_offset);
  } else {
    Serial.println(F("Nenhum dado válido na EEPROM ou primeira execução."));
    Serial.println(F("Usando coeficientes padrão e salvando na EEPROM para referência futura."));
    // Valores padrão iniciais se nada for encontrado na EEPROM
    g_coeficiente = -0.00000082077;
    g_offset = 0.35;
    
    // Salva os valores padrão na EEPROM
    EEPROM.put(EEPROM_ADDR_COEFICIENTE, g_coeficiente);
    EEPROM.put(EEPROM_ADDR_OFFSET, g_offset);
    EEPROM.write(EEPROM_ADDR_FLAG_VALIDO, EEPROM_FLAG_VALOR_ESPERADO); // Marca que a EEPROM foi inicializada
  }
}

void salvarCalibracaoNaEEPROM() {
  Serial.println(F("Salvando novos coeficientes de calibração na EEPROM..."));
  EEPROM.put(EEPROM_ADDR_COEFICIENTE, g_coeficiente);
  EEPROM.put(EEPROM_ADDR_OFFSET, g_offset);
  // O flag já deve estar correto, mas podemos reescrevê-lo por segurança
  EEPROM.write(EEPROM_ADDR_FLAG_VALIDO, EEPROM_FLAG_VALOR_ESPERADO);
  Serial.println(F("Coeficientes salvos na EEPROM. Eles persistirão após reinício."));
}

void setup() {
  Serial.begin(115200);
  
  scale1.begin(DOUT1, CLK1);
  scale1.set_gain(128);
  delay(2000);
  
  Serial.println(F("=== SISTEMA DE COLETA DE DADOS DE PRESSÃO ==="));
  
  // Carrega os coeficientes de calibração da EEPROM ou usa/salva os padrões
  carregarCalibracaoDaEEPROM();

  Serial.println(F("Realizando tara inicial e reset do EMA..."));
  scale1.tare();
  ema_S = 0.0;
  ema_inicializado = false;
  Serial.println(F("Tara inicial concluída."));

  Serial.print(F("Coeficiente em uso: ")); Serial.println(g_coeficiente, 10);
  Serial.print(F("Offset em uso: ")); Serial.println(g_offset, 4);
  
  Serial.println(F("Sistema pronto.\n"));
}

void loop() {
  Serial.println(F("\n=== MENU PRINCIPAL ==="));
  Serial.println(F("1 - Iniciar nova coleta de dados (médias)"));
  Serial.println(F("2 - Realizar Calibração Multiponto (1-5 bar)"));
  Serial.println(F("3 - Zerar Sensor (Tara Rápida)"));
  Serial.println(F("4 - Visualizar Coeficientes Atuais"));
  Serial.println(F("5 - Mostrar Leitura de Pressão Imediata")); 
  Serial.println(F("6 - Sair"));                               
  Serial.println(F("Digite sua opção (1-6):"));

  char opcao = aguardarEntradaChar();
  switch(opcao) {
    case '1':
      configurarEExecutarColeta();
      break;
    case '2':
      calibracaoMultipontoAvancada(); // Esta função agora chamará salvarCalibracaoNaEEPROM
      break;
    case '3':
      taraRapidaSensor();
      break;
    case '4':
      mostrarCoeficientesAtuais();
      break;
    case '5': // Novo item de menu
      mostrarLeituraImediataPressao();
      break;
    case '6': // Opção para Sair
      Serial.println(F("Programa encerrado. Obrigado!"));
      liberarMemoriaDadosPressao(); // Libera memória se houver dados de teste alocados
      while(true) { 
        delay(10000); // Loop infinito para parar a execução
      }
      break;
    default:
      Serial.println(F("Opção inválida! Tente novamente (1-6)."));
      break;
  }
}

void mostrarLeituraImediataPressao() {
  Serial.println(F("\n=== LEITURA DE PRESSÃO IMEDIATA ==="));
  Serial.println(F("Exibindo pressão atual. Pressione 's' e ENTER para sair..."));
  
  // Pode ser útil resetar o EMA aqui se você quiser que a leitura imediata
  // comece "limpa" toda vez que entrar nesta tela, ou pode deixar continuar.
  // Se resetar:
  // ema_S = 0.0; 
  // ema_inicializado = false;

  while (true) {
    // Verifica se o usuário quer sair
    if (Serial.available() > 0) {
      String comando = Serial.readStringUntil('\n'); // Lê até o Enter
      comando.trim();
      if (comando == "s" || comando == "S") {
        break; // Sai do loop da leitura imediata
      }
    }
    
    float pressao_atual = lerPressaoComEMA();
    Serial.print(F("Pressão Atual: "));
    Serial.print(pressao_atual, 2); // 2 casas decimais
    Serial.println(F(" bar        \r")); // O '\r' ajuda a sobrescrever a linha no mesmo lugar em alguns terminais
    
    delay(250); // Atualiza a leitura a cada 0.25 segundos. Ajuste conforme necessidade.
  }
  Serial.println(F("\nRetornando ao menu principal..."));
}


void calibracaoMultipontoAvancada() {
  const int num_pontos_calibracao = 5;
  float pressoes_conhecidas[num_pontos_calibracao] = {1.0, 2.0, 3.0, 4.0, 5.0};
  float leituras_sensor_ema[num_pontos_calibracao];

  float cal_ema_S = 0.0;
  bool cal_ema_inicializado = false;

  Serial.println(F("\n=== CALIBRAÇÃO MULTIPONTO AVANÇADA (1-5 BAR) ==="));
  Serial.println(F("Esta rotina irá calcular e SALVAR um novo Coeficiente e Offset."));
  Serial.println(F("Certifique-se de que o sistema esteja DESPRESSURIZADO antes de iniciar."));
  Serial.println(F("Pressione ENTER para iniciar a calibração..."));
  aguardarEnter();
  
  for (int i = 0; i < num_pontos_calibracao; i++) {
    Serial.print(F("\nPonto de Calibração ")); Serial.print(i + 1); Serial.print(F("/")); Serial.println(num_pontos_calibracao);
    Serial.print(F("Aplique exatamente ")); Serial.print(pressoes_conhecidas[i], 1); Serial.println(F(" bar no sistema."));
    Serial.println(F("Quando a pressão estiver estável, pressione ENTER para registrar a leitura..."));
    aguardarEnter();

    const int num_leituras_para_media_cal = 20;
    float soma_leituras_hx_raw = 0;
    for(int j=0; j < num_leituras_para_media_cal; j++) {
        soma_leituras_hx_raw += scale1.get_units(5);
        delay(50);
    }
    float leitura_hx_avg = soma_leituras_hx_raw / num_leituras_para_media_cal;
    
    if (!cal_ema_inicializado) {
      cal_ema_S = leitura_hx_avg;
      cal_ema_inicializado = true;
    } else {
      cal_ema_S = (leitura_hx_avg * EMA_ALPHA) + (cal_ema_S * (1.0 - EMA_ALPHA));
    }
    leituras_sensor_ema[i] = cal_ema_S;
    Serial.print(F("Leitura do sensor (EMA) para ")); Serial.print(pressoes_conhecidas[i], 1);
    Serial.print(F(" bar: ")); Serial.println(leituras_sensor_ema[i], 4);
  }

  float sum_x = 0, sum_y = 0, sum_xy = 0, sum_x_sq = 0;
  for (int i = 0; i < num_pontos_calibracao; i++) {
    sum_x += leituras_sensor_ema[i];
    sum_y += pressoes_conhecidas[i];
    sum_xy += leituras_sensor_ema[i] * pressoes_conhecidas[i];
    sum_x_sq += leituras_sensor_ema[i] * leituras_sensor_ema[i];
  }

  float N_float = num_pontos_calibracao; // Usar float para os cálculos
  float denominador = (N_float * sum_x_sq) - (sum_x * sum_x);

  if (abs(denominador) < 1e-9) {
    Serial.println(F("ERRO DE CALIBRAÇÃO: Leituras do sensor muito similares ou inválidas."));
    Serial.println(F("Coeficientes NÃO foram atualizados. Verifique o sensor e tente novamente."));
    return; // Retorna ao menu sem salvar
  }

  float novo_coeficiente = ((N_float * sum_xy) - (sum_x * sum_y)) / denominador;
  float novo_offset = (sum_y - (novo_coeficiente * sum_x)) / N_float;

  Serial.println(F("\n--- Novos Coeficientes Calculados ---"));
  Serial.print(F("Novo Coeficiente (m): ")); Serial.println(novo_coeficiente, 10);
  Serial.print(F("Novo Offset (c): ")); Serial.println(novo_offset, 4);

  // Atualiza os coeficientes globais
  g_coeficiente = novo_coeficiente;
  g_offset = novo_offset;
  
  // Salva os novos coeficientes na EEPROM
  salvarCalibracaoNaEEPROM();

  ema_S = 0.0; // Reseta o EMA principal para usar os novos coeficientes corretamente
  ema_inicializado = false;
  Serial.println(F("EMA principal resetado. Calibração concluída e salva."));
}



// --- g_coeficiente e g_offset são agora carregados/salvos da EEPROM e não hardcoded com valores iniciais fixos exceto na primeira execução.                                                       ---

// Função para coletar dados (praticamente inalterada, apenas para referência de contexto)
void configurarEExecutarColeta() {
  liberarMemoriaDadosPressao(); // Limpa dados de coletas anteriores

  Serial.println(F("\n=== CONFIGURAÇÃO DA NOVA COLETA (MÉDIAS) ==="));
  
  Serial.println(F("Quantos testes gostaria de realizar?"));
  g_num_testes = aguardarEntradaString().toInt();
  if (g_num_testes <= 0) {
    Serial.println(F("Número de testes inválido. Retornando ao menu."));
    g_num_testes = 0;
    return;
  }

  Serial.println(F("Qual a duração de cada teste (em segundos)?"));
  g_duracao_teste_s = aguardarEntradaString().toInt();
  // Adicionar uma checagem mais robusta para g_duracao_teste_s
  if (g_duracao_teste_s <= 0 || g_duracao_teste_s > 600) { // Ex: Limite de 10 minutos por teste
    Serial.println(F("Duração de teste inválida (sugestão: 1-600s). Retornando ao menu."));
    g_duracao_teste_s = 0;
    g_num_testes = 0; // Evitar alocação com g_num_testes > 0 e g_duracao_teste_s = 0
    return;
  }

  g_media_pressao_testes = new float[g_num_testes];
  if (!g_media_pressao_testes) {
      Serial.println(F("ERRO: Falha ao alocar memória para as médias dos testes!"));
      g_num_testes = 0;
      return;
  }

  Serial.println(F("\n=== INICIANDO COLETA DE DADOS (MÉDIAS) ==="));
  for (int i = 0; i < g_num_testes; ++i) {
    Serial.print(F("Prepare-se para o TESTE "));
    Serial.print(i + 1); Serial.print(F(" de ")); Serial.println(g_num_testes);
    Serial.println(F("Pressione ENTER quando estiver pronto..."));
    aguardarEnter();

    Serial.print(F("Iniciando em: "));
    for (int t = 3; t > 0; t--) {
      Serial.print(t); Serial.print(F("... ")); delay(1000);
    }
    Serial.println(F("COLETA INICIADA!"));

    ema_S = 0.0; // Reseta EMA para cada teste
    ema_inicializado = false;
    
    float soma_pressoes_teste_atual = 0.0;
    long leituras_contadas = 0; // Usar long para caso de muitos segundos

    for (int s = 0; s < g_duracao_teste_s; ++s) {
      float pressao_instantanea = lerPressaoComEMA();
      soma_pressoes_teste_atual += pressao_instantanea;
      leituras_contadas++;

      Serial.print(F("Teste ")); Serial.print(i + 1);
      Serial.print(F(" - Tempo restante: ")); Serial.print(g_duracao_teste_s - 1 - s);
      Serial.print(F("s - Pressão Instantânea: ")); Serial.print(pressao_instantanea, 2);
      Serial.println(F(" bar"));
      
      delay(1000); // Intervalo de 1 segundo entre leituras
    }
    
    if (leituras_contadas > 0) {
        g_media_pressao_testes[i] = soma_pressoes_teste_atual / leituras_contadas;
    } else {
        g_media_pressao_testes[i] = 0.0; 
    }

    Serial.print(F("TESTE ")); Serial.print(i + 1); Serial.println(F(" FINALIZADO!"));
    Serial.print(F("Pressão Média Registrada para o Teste ")); Serial.print(i+1);
    Serial.print(F(": ")); Serial.print(g_media_pressao_testes[i], 2); Serial.println(F(" bar\n"));
  }

  mostrarResultadosColeta();
}

float lerPressaoComEMA() {
  float leitura_hx_raw = scale1.get_units(10); // Média de 10 leituras internas da HX711

  if (!ema_inicializado) {
    ema_S = leitura_hx_raw;
    ema_inicializado = true;
  } else {
    ema_S = (leitura_hx_raw * EMA_ALPHA) + (ema_S * (1.0 - EMA_ALPHA));
  }

  // Aplica os coeficientes de calibração (carregados/calculados)
  float pressao_bar = (ema_S * g_coeficiente) + g_offset;
  
  if (pressao_bar < 0) { // Garante que a pressão não seja negativa
    pressao_bar = 0.0;
  }
  return pressao_bar;
}

void mostrarResultadosColeta() {
  if (g_num_testes == 0 || g_media_pressao_testes == nullptr) {
    Serial.println(F("Nenhum dado de coleta (médias) para mostrar."));
    return;
  }
  Serial.println(F("\n====================== RESULTADOS FINAIS (MÉDIAS POR TESTE) ======================"));
  for (int i = 0; i < g_num_testes; ++i) {
    Serial.print(F("Teste ")); Serial.print(i + 1);
    Serial.print(F(" - Pressão Média: "));
    Serial.print(g_media_pressao_testes[i], 2); // 2 casas decimais
    Serial.println(F(" bar"));
  }
  Serial.println(F("===================================================================================="));
}

void liberarMemoriaDadosPressao() {
  if (g_media_pressao_testes != nullptr) {
    delete[] g_media_pressao_testes;
    g_media_pressao_testes = nullptr;
  }
  
}

void taraRapidaSensor() {
  Serial.println(F("\n=== ZERAR SENSOR (TARA RÁPIDA) ==="));
  Serial.println(F("Certifique-se de que o sistema esteja DESPRESSURIZADO."));
  Serial.println(F("Pressione ENTER para fazer a tara..."));
  aguardarEnter();
  
  scale1.tare(); // Realiza a tara na célula de carga
  ema_S = 0.0; // Reseta o valor do EMA após a tara
  ema_inicializado = false; // EMA precisa ser reinicializado
  
  Serial.println(F("Tara rápida realizada com sucesso!"));
  Serial.println(F("Leituras subsequentes serão relativas a este novo zero (antes da aplicação de g_coeficiente/g_offset).\n"));
}

void mostrarCoeficientesAtuais() {
    Serial.println(F("\n=== COEFICIENTES DE CALIBRAÇÃO ATUAIS (da EEPROM/última calibração) ==="));
    Serial.print(F("Coeficiente (slope): ")); Serial.println(g_coeficiente, 10);
    Serial.print(F("Offset (intercept): ")); Serial.println(g_offset, 4);
}


String aguardarEntradaString() {
  while (Serial.available() == 0) { delay(50); }
  String entrada = Serial.readStringUntil('\n'); // Lê até encontrar nova linha
  entrada.trim(); // Remove espaços em branco e caracteres de nova linha
  // Não precisa limpar o buffer aqui, pois readStringUntil('\n') consome o '\n'
  return entrada;
}

char aguardarEntradaChar() {
  while (Serial.available() == 0) { delay(50); }
  char valor = Serial.read();
  // Limpa qualquer caractere adicional no buffer (como CR/LF se enviado por terminal)
  delay(2); // Pequeno delay para garantir que caracteres subsequentes cheguem ao buffer
  while (Serial.available() > 0) { Serial.read(); }
  return valor;
}

void aguardarEnter() {
  // Aguarda qualquer byte ser enviado (geralmente o caractere de nova linha do Enter)
  while (Serial.available() == 0) { delay(50); }
  // Limpa todo o buffer serial para garantir que apenas o "Enter" e seus acompanhantes (CR/LF) sejam consumidos
  delay(2); 
  while (Serial.available() > 0) { Serial.read(); }
}
