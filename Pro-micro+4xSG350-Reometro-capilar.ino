#include <HX711.h>
#include <EEPROM.h>

// Definições dos pinos do HX711
#define DOUT1 A0
#define CLK1 A1

HX711 scale1;

// Constantes para a calibração por interpolação
const int NUM_PONTOS_CALIBRACAO_INTERPOL = 4;
const float g_pressoes_calibracao_conhecidas[NUM_PONTOS_CALIBRACAO_INTERPOL] = {1.0, 2.0, 3.0, 4.0};

// Variáveis globais para os dados de calibração por interpolação
float g_leituras_calibracao_sensor[NUM_PONTOS_CALIBRACAO_INTERPOL];
bool g_calibracao_interpol_concluida = false;
int g_direcao_tendencia_calibracao = 0;

// Endereços na EEPROM para CALIBRAÇÃO
#define EEPROM_ADDR_LEITURAS_CAL_START 0
#define EEPROM_ADDR_FLAG_CAL_INTERPOL_CONCLUIDA (EEPROM_ADDR_LEITURAS_CAL_START + (sizeof(float) * NUM_PONTOS_CALIBRACAO_INTERPOL))
#define EEPROM_ADDR_DIRECAO_TENDENCIA (EEPROM_ADDR_FLAG_CAL_INTERPOL_CONCLUIDA + sizeof(bool))
#define EEPROM_FLAG_CAL_INTERPOL_VALIDA 0xCE

// Endereços na EEPROM para RESULTADOS DA ÚLTIMA BATERIA DE TESTES
#define EEPROM_ADDR_TEST_RESULTS_BASE 30
#define EEPROM_ADDR_TEST_RESULTS_FLAG (EEPROM_ADDR_TEST_RESULTS_BASE)
const int MAX_DESC_LEN = 20;
#define EEPROM_ADDR_TEST_DESC_START (EEPROM_ADDR_TEST_RESULTS_BASE + 1)
#define EEPROM_ADDR_TEST_RESULTS_NUM_TESTS (EEPROM_ADDR_TEST_DESC_START + MAX_DESC_LEN)
#define EEPROM_ADDR_TEST_RESULTS_DURATION (EEPROM_ADDR_TEST_RESULTS_NUM_TESTS + sizeof(int))
#define EEPROM_ADDR_TEST_RESULTS_DATA_START (EEPROM_ADDR_TEST_RESULTS_DURATION + sizeof(int))
#define EEPROM_FLAG_TEST_RESULTS_VALIDA 0xDF

// Parâmetro para o filtro EMA
#define EMA_ALPHA 0.8 // 1.0 desabilita

float ema_S = 0.0;
bool ema_inicializado = false;

// Variáveis globais para os parâmetros e dados dos testes atuais
int g_num_testes_atuais = 0;
int g_duracao_teste_s_atuais = 0;
float* g_media_pressao_testes_atuais = nullptr;

const float MIN_SENSOR_STEP_DIFFERENCE = 1e-5;

//*************************************************************************
// DECLARAÇÕES ANTECIPADAS DE FUNÇÕES (FORWARD DECLARATIONS)
//*************************************************************************
void carregarDadosCalibracaoInterpol();
void salvarDadosCalibracaoInterpol();
void salvarUltimaBateriaTestesEEPROM();
void carregarEVisualizarUltimaBateriaTestesEEPROM();
float obterLeituraSensorEMA();
void determinarETChecarMonotonicidade(float leituras[], int num_pontos, int& tendencia_detectada, bool& monotonicidade_ok_flag);
void realizarCalibracaoPorInterpolacao();
void inserirLeiturasCalibracaoManualmente();
void visualizarPontosDeCalibracao();
float lerPressaoPorInterpolacao();
void configurarEExecutarColeta();
void mostrarResultadosColetaAtual();
void liberarMemoriaDadosAtuais();
void taraRapidaSensor();
void mostrarLeituraImediataPressao();
String aguardarEntradaString();
char aguardarEntradaChar();
void aguardarEnter();

//-----------------------------------------------------------------------------------------
// GERENCIAMENTO DA CALIBRAÇÃO NA EEPROM
// (código como antes)
//-----------------------------------------------------------------------------------------
void carregarDadosCalibracaoInterpol() {
  Serial.println(F("Verificando dados de calibração na EEPROM..."));
  byte flag = EEPROM.read(EEPROM_ADDR_FLAG_CAL_INTERPOL_CONCLUIDA);

  if (flag == EEPROM_FLAG_CAL_INTERPOL_VALIDA) {
    Serial.println(F("Dados de calibração (4 pontos) válidos encontrados. Carregando..."));
    for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) {
      EEPROM.get(EEPROM_ADDR_LEITURAS_CAL_START + (i * sizeof(float)), g_leituras_calibracao_sensor[i]);
    }
    EEPROM.get(EEPROM_ADDR_DIRECAO_TENDENCIA, g_direcao_tendencia_calibracao);
    g_calibracao_interpol_concluida = true;
  } else {
    Serial.println(F("Nenhum dado de calibração (4 pontos) válido na EEPROM ou flag diferente."));
    Serial.println(F("É NECESSÁRIO REALIZAR A CALIBRAÇÃO ou INSERIR LEITURAS MANUALMENTE."));
    g_calibracao_interpol_concluida = false;
    g_direcao_tendencia_calibracao = 0;
    for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) {
      g_leituras_calibracao_sensor[i] = 0.0; 
    }
  }
}

void salvarDadosCalibracaoInterpol() {
  Serial.println(F("Salvando dados de calibração por interpolação (4 pontos) na EEPROM..."));
  for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) {
    EEPROM.put(EEPROM_ADDR_LEITURAS_CAL_START + (i * sizeof(float)), g_leituras_calibracao_sensor[i]);
  }
  EEPROM.put(EEPROM_ADDR_DIRECAO_TENDENCIA, g_direcao_tendencia_calibracao);
  EEPROM.write(EEPROM_ADDR_FLAG_CAL_INTERPOL_CONCLUIDA, EEPROM_FLAG_CAL_INTERPOL_VALIDA);
  g_calibracao_interpol_concluida = true;
  Serial.println(F("Dados de calibração salvos na EEPROM."));
}

//-----------------------------------------------------------------------------------------
// GERENCIAMENTO DOS RESULTADOS DA ÚLTIMA BATERIA NA EEPROM
// (código como antes)
//-----------------------------------------------------------------------------------------
void salvarUltimaBateriaTestesEEPROM() {
    if (g_num_testes_atuais == 0 || g_media_pressao_testes_atuais == nullptr) {
        Serial.println(F("Nenhum resultado de teste atual para salvar."));
        return;
    }
    unsigned int tamanhoNecessario = (1 + MAX_DESC_LEN + (2*sizeof(int)) + (g_num_testes_atuais * sizeof(float)));
    if (EEPROM_ADDR_TEST_RESULTS_BASE + tamanhoNecessario > EEPROM.length()) {
        Serial.println(F("ERRO: Espaço insuficiente na EEPROM."));
        return;
    }

    Serial.println(F("\n--- Inserir Detalhes para Salvar Teste ---"));
    char descricao_teste[MAX_DESC_LEN];
    Serial.print(F("Insira uma descrição (max ")); Serial.print(MAX_DESC_LEN - 1); Serial.println(F(" caracteres):"));
    String strDesc = aguardarEntradaString();
    strDesc.toCharArray(descricao_teste, MAX_DESC_LEN); 
    
    Serial.println(F("Salvando resultados e descrição da última bateria na EEPROM..."));
    EEPROM.write(EEPROM_ADDR_TEST_RESULTS_FLAG, EEPROM_FLAG_TEST_RESULTS_VALIDA);
    for (int k=0; k < MAX_DESC_LEN; k++){ EEPROM.write(EEPROM_ADDR_TEST_DESC_START + k, descricao_teste[k]); if(descricao_teste[k] == '\0') break; }
    for (int k = strlen(descricao_teste); k < MAX_DESC_LEN; k++) { EEPROM.write(EEPROM_ADDR_TEST_DESC_START + k, '\0');}
    EEPROM.put(EEPROM_ADDR_TEST_RESULTS_NUM_TESTS, g_num_testes_atuais);
    EEPROM.put(EEPROM_ADDR_TEST_RESULTS_DURATION, g_duracao_teste_s_atuais);
    for (int i = 0; i < g_num_testes_atuais; i++) { EEPROM.put(EEPROM_ADDR_TEST_RESULTS_DATA_START + (i * sizeof(float)), g_media_pressao_testes_atuais[i]); }
    Serial.println(F("Resultados e Descrição salvos na EEPROM."));
}

void carregarEVisualizarUltimaBateriaTestesEEPROM() {
    Serial.println(F("\n=== ÚLTIMOS RESULTADOS DE TESTE SALVOS NA EEPROM ==="));
    byte flag = EEPROM.read(EEPROM_ADDR_TEST_RESULTS_FLAG);

    if (flag != EEPROM_FLAG_TEST_RESULTS_VALIDA) {
        Serial.println(F("Nenhum resultado de teste válido (com descrição) salvo na EEPROM."));
        return;
    }
    char descricao_salva[MAX_DESC_LEN];
    for (int k=0; k < MAX_DESC_LEN; k++){ descricao_salva[k] = EEPROM.read(EEPROM_ADDR_TEST_DESC_START + k); if (descricao_salva[k] == '\0' && k < MAX_DESC_LEN -1) {for(int l=k+1; l<MAX_DESC_LEN; ++l) descricao_salva[l] = '\0'; break;}}
    descricao_salva[MAX_DESC_LEN - 1] = '\0';
    int num_testes_salvos; int duracao_salva;
    EEPROM.get(EEPROM_ADDR_TEST_RESULTS_NUM_TESTS, num_testes_salvos);
    EEPROM.get(EEPROM_ADDR_TEST_RESULTS_DURATION, duracao_salva);

    if (num_testes_salvos <= 0 || num_testes_salvos > 200) { Serial.println(F("Dados de Nro de Testes inválidos.")); return; }
    
    Serial.print(F("Descrição do Teste: ")); Serial.println(descricao_salva);
    Serial.print(F("Resultados da bateria com ")); Serial.print(num_testes_salvos); Serial.print(F(" testes de ")); Serial.print(duracao_salva); Serial.println(F("s cada:"));
    Serial.println(F("---------------------------------------------------------"));
    for (int i = 0; i < num_testes_salvos; i++) {
        float media_pressao;
        EEPROM.get(EEPROM_ADDR_TEST_RESULTS_DATA_START + (i * sizeof(float)), media_pressao);
        Serial.print(F("Teste ")); Serial.print(i + 1); Serial.print(F(" - Média: "));
        if (media_pressao < -0.5) { Serial.print(F("Inválido"));}
        else if (media_pressao < 0 && media_pressao >= -0.5) { Serial.print(0.00, 2); }
        else { Serial.print(media_pressao, 2); }
        Serial.println(F(" bar"));
    }
    Serial.println(F("---------------------------------------------------------"));
}

//-----------------------------------------------------------------------------------------
// CONFIGURAÇÃO INICIAL (SETUP)
//-----------------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  scale1.begin(DOUT1, CLK1);
  scale1.set_gain(128);
  delay(2000);
  Serial.println(F("=== SISTEMA REOLÓGICO (INTERPOL 4 PONTOS, DESC) ==="));
  carregarDadosCalibracaoInterpol();
  Serial.println(F("Realizando tara inicial e reset do EMA..."));
  scale1.tare();
  ema_S = 0.0; ema_inicializado = false;
  Serial.println(F("Tara inicial concluída."));
  if (g_calibracao_interpol_concluida) {
    Serial.print(F("Calibração carregada. Tendência: "));
    if(g_direcao_tendencia_calibracao == 1) Serial.println(F("Crescente"));
    else if(g_direcao_tendencia_calibracao == -1) Serial.println(F("Decrescente"));
    else Serial.println(F("Indefinida (INVÁLIDA!)"));
  } else {
    Serial.println(F("ATENÇÃO: CALIBRAÇÃO NÃO REALIZADA OU INVÁLIDA."));
  }
  Serial.println(F("Sistema pronto.\n"));
}

//-----------------------------------------------------------------------------------------
// LOOP PRINCIPAL E MENU
//-----------------------------------------------------------------------------------------
void loop() {
  Serial.println(F("\n=== MENU PRINCIPAL ==="));
  Serial.println(F("1 - Iniciar nova coleta de dados"));
  Serial.println(F("2 - Realizar Calibração Interativa (1-4 bar)"));
  Serial.println(F("3 - Inserir Leituras de Calibração Manualmente"));
  Serial.println(F("4 - Visualizar Pontos de Calibração Atuais"));
  Serial.println(F("5 - Zerar Sensor (Tara Rápida)"));
  Serial.println(F("6 - Mostrar Leitura de Pressão Imediata"));
  Serial.println(F("7 - Visualizar Últimos Resultados Salvos"));
  Serial.println(F("8 - Sair"));
  Serial.println(F("Digite sua opção (1-8):"));

  char opcao = aguardarEntradaChar();
    switch(opcao) {
    case '1':
      if (!g_calibracao_interpol_concluida || g_direcao_tendencia_calibracao == 0) {
        Serial.println(F("Calibração válida é necessária.")); break; }
      configurarEExecutarColeta();
      break;
    case '2':
      realizarCalibracaoPorInterpolacao();
      break;
    case '3':
      inserirLeiturasCalibracaoManualmente();
      break;
    case '4':
      visualizarPontosDeCalibracao();
      break;
    case '5':
      taraRapidaSensor();
      break;
    case '6':
       if (!g_calibracao_interpol_concluida || g_direcao_tendencia_calibracao == 0) {
        Serial.println(F("Calibração válida é necessária.")); break; }
      mostrarLeituraImediataPressao();
      break;
    case '7': 
      carregarEVisualizarUltimaBateriaTestesEEPROM();
      break;
    case '8': 
      Serial.println(F("Programa encerrado."));
      liberarMemoriaDadosAtuais();
      while(true) { delay(10000); }
      break;
    default:
      Serial.println(F("Opção inválida!"));
      break;
  }
}

//-----------------------------------------------------------------------------------------
// FUNÇÕES DE LÓGICA E OPERAÇÕES
//-----------------------------------------------------------------------------------------

float obterLeituraSensorEMA() {
  // Reduzido para 2 amostras para acelerar a leitura.
  // Se 10SPS, get_units(2) ~200ms. Se 80SPS, get_units(2) ~25ms.
  float leitura_hx_raw = scale1.get_units(2); // ALTERADO DE 10 PARA 2, em 10 o delay era > 1s
  
  if (EMA_ALPHA == 1.0) {
      ema_S = leitura_hx_raw;
      if(!ema_inicializado) ema_inicializado = true; 
  } else { 
      if (!ema_inicializado) {
        ema_S = leitura_hx_raw;
        ema_inicializado = true;
      } else {
        ema_S = (leitura_hx_raw * EMA_ALPHA) + (ema_S * (1.0 - EMA_ALPHA));
      }
  }
  return ema_S;
}

void determinarETChecarMonotonicidade(float leituras[], int num_pontos, int& tendencia_detectada, bool& monotonicidade_ok_flag) {
    // ... (código como antes) ...
    tendencia_detectada = 0; 
    monotonicidade_ok_flag = true;
    if (num_pontos < 2) { if (num_pontos == 1) tendencia_detectada = 0; return; }
    float diff_inicial = leituras[1] - leituras[0];
    if (abs(diff_inicial) < MIN_SENSOR_STEP_DIFFERENCE * 10) { tendencia_detectada = 0; }
    else if (diff_inicial > 0) { tendencia_detectada = 1; }
    else { tendencia_detectada = -1; }
    for (int i = 2; i < num_pontos; i++) {
        float diff_atual = leituras[i] - leituras[i-1];
        if (tendencia_detectada == 1) { if (diff_atual <= (MIN_SENSOR_STEP_DIFFERENCE * 5)) { monotonicidade_ok_flag = false; break; }}
        else if (tendencia_detectada == -1) { if (diff_atual >= (-MIN_SENSOR_STEP_DIFFERENCE * 5)) { monotonicidade_ok_flag = false; break; }}
        else { if (abs(diff_atual) > MIN_SENSOR_STEP_DIFFERENCE * 10) { monotonicidade_ok_flag = false; break; }}}
    if (tendencia_detectada == 0) { monotonicidade_ok_flag = false; }
}

void realizarCalibracaoPorInterpolacao() {
  // ... (código como antes) ...
  Serial.println(F("\n=== CALIBRAÇÃO INTERATIVA (1-4 BAR) ==="));
  Serial.println(F("Registrará leitura do sensor para 4 pressões conhecidas."));
  Serial.println(F("Sistema DESPRESSURIZADO antes do 1º ponto."));
  float temp_leituras_sensor[NUM_PONTOS_CALIBRACAO_INTERPOL];
  for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) {
    Serial.print(F("\nPonto ")); Serial.print(i + 1); Serial.print(F("/")); Serial.println(NUM_PONTOS_CALIBRACAO_INTERPOL);
    Serial.print(F("Aplique ")); Serial.print(g_pressoes_calibracao_conhecidas[i], 1); Serial.println(F(" bar e ESTABILIZE."));
    Serial.println(F("Pressione ENTER...")); aguardarEnter();
    ema_S = 0.0; ema_inicializado = false; 
    float leitura_estabilizada_ema_ponto = 0;
    Serial.print(F("  Lendo e estabilizando... "));
    const int leituras_para_estabilizar_ema = 60;
    for(int j=0; j < leituras_para_estabilizar_ema; j++) { leitura_estabilizada_ema_ponto = obterLeituraSensorEMA(); delay(50); }
    temp_leituras_sensor[i] = leitura_estabilizada_ema_ponto;
    Serial.println(F("OK."));
    Serial.print(F("  Para ")); Serial.print(g_pressoes_calibracao_conhecidas[i], 1); Serial.print(F(" bar, EMA: ")); Serial.println(temp_leituras_sensor[i], 4);
  }
  int tendencia_detectada; bool monotonicidade_ok;
  determinarETChecarMonotonicidade(temp_leituras_sensor, NUM_PONTOS_CALIBRACAO_INTERPOL, tendencia_detectada, monotonicidade_ok);
  if (!monotonicidade_ok) {
    Serial.println(F("\nPROBLEMA DE MONOTONICIDADE!"));
    if (tendencia_detectada == 1) { Serial.println(F("Esperava-se crescente, mas não ocorreu.")); }
    else if (tendencia_detectada == -1) { Serial.println(F("Esperava-se decrescente, mas não ocorreu.")); }
    else { Serial.println(F("Tendência não clara ou plana.")); }
    Serial.println(F("Salvar mesmo assim? (s/n):")); char resp = aguardarEntradaChar();
    if (resp != 's' && resp != 'S') { Serial.println(F("Calibração cancelada.")); return; }
    Serial.println(F("Salvando apesar do aviso."));
  }
  for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) { g_leituras_calibracao_sensor[i] = temp_leituras_sensor[i]; }
  g_direcao_tendencia_calibracao = tendencia_detectada;
  salvarDadosCalibracaoInterpol();
  Serial.println(F("Calibração interativa concluída."));
  Serial.print(F("Tendência: "));
  if (g_direcao_tendencia_calibracao == 1) Serial.println(F("Crescente."));
  else if (g_direcao_tendencia_calibracao == -1) Serial.println(F("Decrescente."));
  else Serial.println(F("Indefinida/Plana (INVÁLIDA!)."));
}

void inserirLeiturasCalibracaoManualmente() {
    Serial.println(F("\n=== INSERIR LEITURAS DE CALIBRAÇÃO MANUALMENTE (1-4 BAR) ==="));
    float temp_leituras_manuais[NUM_PONTOS_CALIBRACAO_INTERPOL];

    for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) {
        Serial.print(F("Insira leitura EMA para ")); 
        Serial.print(g_pressoes_calibracao_conhecidas[i], 1);
        Serial.println(F(" bar: ")); // ALTERADO PARA PRINTLN
        temp_leituras_manuais[i] = aguardarEntradaString().toFloat();
    }

    Serial.println(F("\nLeituras Inseridas:"));
    for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) {
        Serial.print(F("  ")); Serial.print(g_pressoes_calibracao_conhecidas[i], 1);
        Serial.print(F(" bar -> EMA: ")); Serial.println(temp_leituras_manuais[i], 4);
    }
    int tendencia_detectada; bool monotonicidade_ok;
    determinarETChecarMonotonicidade(temp_leituras_manuais, NUM_PONTOS_CALIBRACAO_INTERPOL, tendencia_detectada, monotonicidade_ok);
    if (!monotonicidade_ok) {
        Serial.println(F("\nAVISO: Leituras manuais não são monotonicamente consistentes!"));
        if (tendencia_detectada == 1) Serial.println(F("Esperava-se crescente, mas houve quebra."));
        else if (tendencia_detectada == -1) Serial.println(F("Esperava-se decrescente, mas houve quebra."));
        else Serial.println(F("Não foi possível determinar uma tendência clara ou é plana."));
        Serial.println(F("A calibração PODE NÃO SER PRECISA. Deseja salvar mesmo assim? (s/n):")); char resp = aguardarEntradaChar();
        if (resp != 's' && resp != 'S') { Serial.println(F("Entrada manual cancelada.")); return; }
        Serial.println(F("Salvando apesar do aviso."));
    }
    for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) { g_leituras_calibracao_sensor[i] = temp_leituras_manuais[i]; }
    g_direcao_tendencia_calibracao = tendencia_detectada;
    g_calibracao_interpol_concluida = true;
    salvarDadosCalibracaoInterpol();
    Serial.println(F("Leituras manuais aplicadas e salvas."));
    Serial.print(F("Tendência: "));
    if (g_direcao_tendencia_calibracao == 1) Serial.println(F("Crescente."));
    else if (g_direcao_tendencia_calibracao == -1) Serial.println(F("Decrescente."));
    else Serial.println(F("Indefinida/Plana (INVÁLIDA!)."));
}


void visualizarPontosDeCalibracao() {
  // ... (código como antes) ...
  Serial.println(F("\n=== PONTOS DE CALIBRAÇÃO ATUAIS (1-4 BAR) ==="));
  if (!g_calibracao_interpol_concluida) { Serial.println(F("Nenhuma calibração realizada/carregada.")); return; }
  Serial.println(F("Pressão (bar) | Leitura Sensor (EMA)"));
  Serial.println(F("----------------|--------------------"));
  for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL; i++) {
    Serial.print(F("      ")); Serial.print(g_pressoes_calibracao_conhecidas[i], 1); Serial.print(F("      | ")); Serial.println(g_leituras_calibracao_sensor[i], 4); }
  Serial.print(F("Tendência Salva: "));
  if(g_direcao_tendencia_calibracao == 1) Serial.println(F("Crescente"));
  else if(g_direcao_tendencia_calibracao == -1) Serial.println(F("Decrescente"));
  else Serial.println(F("Indefinida/Plana (INVÁLIDA!)"));
}

float lerPressaoPorInterpolacao() {
  
  if (!g_calibracao_interpol_concluida) return -1.0; 
  if (g_direcao_tendencia_calibracao == 0) return -3.0;
  float leitura_atual_ema = obterLeituraSensorEMA();

  if (g_direcao_tendencia_calibracao == 1) { 
    if (leitura_atual_ema <= g_leituras_calibracao_sensor[0]) { 
      float R0 = g_leituras_calibracao_sensor[0]; float P0 = g_pressoes_calibracao_conhecidas[0];
      float R1 = g_leituras_calibracao_sensor[1]; float P1 = g_pressoes_calibracao_conhecidas[1];
      if (abs(R1 - R0) < MIN_SENSOR_STEP_DIFFERENCE) return P0;
      return P0 + (P1 - P0) * (leitura_atual_ema - R0) / (R1 - R0);
    }
    if (leitura_atual_ema >= g_leituras_calibracao_sensor[NUM_PONTOS_CALIBRACAO_INTERPOL - 1]) { 
      int L = NUM_PONTOS_CALIBRACAO_INTERPOL - 1; int SL = L - 1;
      float RL = g_leituras_calibracao_sensor[L]; float PL = g_pressoes_calibracao_conhecidas[L];
      float RSL = g_leituras_calibracao_sensor[SL]; float PSL = g_pressoes_calibracao_conhecidas[SL];
      if (abs(RL - RSL) < MIN_SENSOR_STEP_DIFFERENCE) return PL;
      return PSL + (PL - PSL) * (leitura_atual_ema - RSL) / (RL - RSL);
    }
  } else { 
    if (leitura_atual_ema >= g_leituras_calibracao_sensor[0]) { 
      float R0 = g_leituras_calibracao_sensor[0]; float P0 = g_pressoes_calibracao_conhecidas[0];
      float R1 = g_leituras_calibracao_sensor[1]; float P1 = g_pressoes_calibracao_conhecidas[1];
      if (abs(R1 - R0) < MIN_SENSOR_STEP_DIFFERENCE) return P0;
      return P0 + (P1 - P0) * (leitura_atual_ema - R0) / (R1 - R0);
    }
    if (leitura_atual_ema <= g_leituras_calibracao_sensor[NUM_PONTOS_CALIBRACAO_INTERPOL - 1]) { 
      int L = NUM_PONTOS_CALIBRACAO_INTERPOL - 1; int SL = L - 1;
      float RL = g_leituras_calibracao_sensor[L]; float PL = g_pressoes_calibracao_conhecidas[L];
      float RSL = g_leituras_calibracao_sensor[SL]; float PSL = g_pressoes_calibracao_conhecidas[SL];
      if (abs(RL - RSL) < MIN_SENSOR_STEP_DIFFERENCE) return PL;
      return PSL + (PL - PSL) * (leitura_atual_ema - RSL) / (RL - RSL);
    }
  }

  for (int i = 0; i < NUM_PONTOS_CALIBRACAO_INTERPOL - 1; i++) {
    bool in_segment = false;
    if (g_direcao_tendencia_calibracao == 1) { 
      if (leitura_atual_ema >= g_leituras_calibracao_sensor[i] && leitura_atual_ema < g_leituras_calibracao_sensor[i+1]) {
        in_segment = true;
      } else if (i == NUM_PONTOS_CALIBRACAO_INTERPOL - 2 && abs(leitura_atual_ema - g_leituras_calibracao_sensor[i+1]) < MIN_SENSOR_STEP_DIFFERENCE / 10.0) {
        return g_pressoes_calibracao_conhecidas[i+1];
      }
    } else { 
      if (leitura_atual_ema <= g_leituras_calibracao_sensor[i] && leitura_atual_ema > g_leituras_calibracao_sensor[i+1]) {
        in_segment = true;
      } else if (i == NUM_PONTOS_CALIBRACAO_INTERPOL - 2 && abs(leitura_atual_ema - g_leituras_calibracao_sensor[i+1]) < MIN_SENSOR_STEP_DIFFERENCE / 10.0) {
        return g_pressoes_calibracao_conhecidas[i+1];
      }
    }
    if (in_segment) {
      float R_k = g_leituras_calibracao_sensor[i];     float P_k = g_pressoes_calibracao_conhecidas[i];
      float R_k1 = g_leituras_calibracao_sensor[i+1]; float P_k1 = g_pressoes_calibracao_conhecidas[i+1];
      if (abs(R_k1 - R_k) < MIN_SENSOR_STEP_DIFFERENCE) return P_k;
      return P_k + (P_k1 - P_k) * (leitura_atual_ema - R_k) / (R_k1 - R_k);
    }
  }
  if (abs(leitura_atual_ema - g_leituras_calibracao_sensor[0]) < MIN_SENSOR_STEP_DIFFERENCE / 10.0) {
      return g_pressoes_calibracao_conhecidas[0];
  }
  return -2.0;
}

void configurarEExecutarColeta() {
  liberarMemoriaDadosAtuais();
  Serial.println(F("\n=== CONFIGURAÇÃO DA COLETA ==="));
  Serial.println(F("Quantos testes?"));
  g_num_testes_atuais = aguardarEntradaString().toInt();
  if (g_num_testes_atuais <= 0) { Serial.println(F("Inválido.")); g_num_testes_atuais = 0; return; }
  Serial.println(F("Duração de cada teste (s)?"));
  g_duracao_teste_s_atuais = aguardarEntradaString().toInt();
  if (g_duracao_teste_s_atuais <= 0 || g_duracao_teste_s_atuais > 600) { Serial.println(F("Inválido.")); g_duracao_teste_s_atuais = 0; g_num_testes_atuais = 0; return; }
  
  g_media_pressao_testes_atuais = new float[g_num_testes_atuais];
  if (!g_media_pressao_testes_atuais) { Serial.println(F("ERRO: Memória!")); g_num_testes_atuais = 0; return; }

  Serial.println(F("\n=== INICIANDO COLETA ==="));
  unsigned long desiredLoopIntervalMillis = 1000; // Alvo de 1 segundo por iteração

  for (int i = 0; i < g_num_testes_atuais; ++i) {
    Serial.print(F("Prepare TESTE ")); Serial.print(i + 1); Serial.print(F(" de ")); Serial.println(g_num_testes_atuais);
    Serial.println(F("Pressione ENTER...")); aguardarEnter();
    Serial.print(F("Iniciando em: "));
    for (int t = 3; t > 0; t--) { Serial.print(t); Serial.print(F("..")); delay(1000); }
    Serial.println(F("COLETA!"));
    
    float soma_pressoes_teste_atual = 0.0; 
    long leituras_contadas_validas = 0;
    unsigned long testeStartTimeMillis = millis(); // Tempo de início da coleta deste teste

    for (int s = 0; s < g_duracao_teste_s_atuais; ++s) {
      unsigned long iterationStartTimeMillis = millis();

      float pressao_instantanea = lerPressaoPorInterpolacao();
      if (pressao_instantanea >= 0) { 
        soma_pressoes_teste_atual += pressao_instantanea; 
        leituras_contadas_validas++; 
      }

      Serial.print(F("T")); Serial.print(i + 1); 
      Serial.print(F(" [")); Serial.print(g_duracao_teste_s_atuais - 1 - s); // Iterações restantes
      Serial.print(F("s] P: ")); 
      if (pressao_instantanea < -0.5) { Serial.print(F("Err(")); Serial.print(pressao_instantanea,0); Serial.print(F(")")); }
      else if (pressao_instantanea < 0 && pressao_instantanea >= -0.5) { Serial.print(0.00, 2); }
      else { Serial.print(pressao_instantanea, 2); }
      Serial.println(F(" bar")); 
      
      unsigned long processingTimeMillis = millis() - iterationStartTimeMillis;
      if (processingTimeMillis < desiredLoopIntervalMillis) {
        delay(desiredLoopIntervalMillis - processingTimeMillis);
      } else {
        Serial.print(F("AVISO: Loop T")); Serial.print(i+1); Serial.print(F(" iter. ")); Serial.print(s+1);
        Serial.print(F(" demorou ")); Serial.print(processingTimeMillis); Serial.println(F("ms"));
      }
    }
    
    unsigned long testeEndTimeMillis = millis();
    float actualTestDurationSec = (testeEndTimeMillis - testeStartTimeMillis) / 1000.0;
    Serial.print(F("Duração real da coleta para Teste ")); Serial.print(i+1);
    Serial.print(F(": ")); Serial.print(actualTestDurationSec, 2); Serial.println(F("s"));

    if (leituras_contadas_validas > 0) { 
      g_media_pressao_testes_atuais[i] = soma_pressoes_teste_atual / leituras_contadas_validas; 
    } else { 
      g_media_pressao_testes_atuais[i] = -4.0; // Erro, nenhuma leitura válida
    }

    Serial.print(F("TESTE ")); Serial.print(i + 1); Serial.println(F(" FIM!"));
    Serial.print(F("Média T")); Serial.print(i+1); Serial.print(F(": ")); 
    if (g_media_pressao_testes_atuais[i] < -0.5) { Serial.print(F("Erro")); }
    else if (g_media_pressao_testes_atuais[i] < 0 && g_media_pressao_testes_atuais[i] >= -0.5) { Serial.print(0.00, 2); }
    else { Serial.print(g_media_pressao_testes_atuais[i], 2); }
    Serial.println(F(" bar\n"));
  }
  mostrarResultadosColetaAtual();
  Serial.println(F("Salvar esta bateria na EEPROM? (s/n):"));
  char resp = aguardarEntradaChar();
  if (resp == 's' || resp == 'S') { salvarUltimaBateriaTestesEEPROM(); }
}

void mostrarResultadosColetaAtual() {
  if (g_num_testes_atuais == 0 || g_media_pressao_testes_atuais == nullptr) { Serial.println(F("Nenhum dado atual.")); return; }
  Serial.println(F("\n=== RESULTADOS DA COLETA ATUAL ==="));
  for (int i = 0; i < g_num_testes_atuais; ++i) {
    Serial.print(F("Teste ")); Serial.print(i + 1); Serial.print(F(" - Média: "));
    if (g_media_pressao_testes_atuais[i] < -0.5) { Serial.print(F("Erro")); }
    else if (g_media_pressao_testes_atuais[i] < 0 && g_media_pressao_testes_atuais[i] >= -0.5) { Serial.print(0.00, 2); }
    else { Serial.print(g_media_pressao_testes_atuais[i], 2); }
    Serial.println(F(" bar"));
  }
  Serial.println(F("==================================="));
}

void liberarMemoriaDadosAtuais() {
  if (g_media_pressao_testes_atuais != nullptr) { delete[] g_media_pressao_testes_atuais; g_media_pressao_testes_atuais = nullptr; }
  g_num_testes_atuais = 0;
}

void taraRapidaSensor() {
  Serial.println(F("\n=== TARA RÁPIDA ==="));
  Serial.println(F("Sistema DESPRESSURIZADO. ENTER para tarar...")); aguardarEnter();
  scale1.tare(); ema_S = 0.0; ema_inicializado = false; 
  Serial.println(F("Tara OK!\n"));
}

void mostrarLeituraImediataPressao() {
  Serial.println(F("\n=== LEITURA IMEDIATA ==="));
  Serial.println(F("Pressione 's' + ENTER para sair..."));
  while (true) {
    if (Serial.available() > 0) { String cmd = Serial.readStringUntil('\n'); cmd.trim(); if (cmd == "s" || cmd == "S") break; }
    float p = lerPressaoPorInterpolacao();
    Serial.print(F("Pressão: "));
    if (p < -0.5) { Serial.print(F("Err(")); Serial.print(p,0); Serial.print(F(")")); }
    else if (p < 0 && p >= -0.5) { Serial.print(0.00, 2); }
    else { Serial.print(p, 2); }
    Serial.println(F(" bar        \r")); delay(250);
  }
  Serial.println(F("\nRetornando..."));
}

String aguardarEntradaString() {
  while (Serial.available() == 0) { delay(50); }
  String entrada = Serial.readStringUntil('\n'); entrada.trim(); return entrada;
}
char aguardarEntradaChar() {
  while (Serial.available() == 0) { delay(50); }
  char valor = Serial.read(); delay(2); while (Serial.available() > 0) { Serial.read(); } return valor;
}
void aguardarEnter() {
  while (Serial.available() == 0) { delay(50); }
  delay(2); while (Serial.available() > 0) { Serial.read(); }
}
