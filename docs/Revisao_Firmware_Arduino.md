# Revisão do Firmware Arduino
## Pro-micro + Transdutor — Reômetro Capilar

**Arquivo:** `Pro-micro+Transdutor-Reometro-capilar` (sketch `.ino`, v3.0)  
**Plataforma:** Arduino Pro Micro (ATmega32U4)  
**Data da Revisão:** 25 de fevereiro de 2026

---

## Sumário de Achados

| ID | Severidade | Descrição | Impacto máximo |
|----|------------|-----------|----------------|
| A-01 | 🟡 MÉDIO | Instabilidade do Vref (USB 5V como referência ADC) | ±6,7% em pressão entre sessões |
| A-02 | 🟡 MÉDIO | Ausência de comando RESET_EMA | Erro transitório até 60% nos primeiros ~130 ms |
| A-03 | 🔵 BAIXO | Divisor ADC incorreto: `1023` deveria ser `1024` | +0,1% sistemático em tensão |
| A-04 | 🔵 BAIXO | `readStringUntil()` pode bloquear o EMA por até 1 s | EMA não atualizado durante bloqueio |
| V-01 | ✅ OK | Filtro EMA implementado corretamente | — |
| V-02 | ✅ OK | Protocolo serial simples e robusto | — |
| V-03 | ✅ OK | Inicialização do EMA sem spike inicial | — |

---

## Contexto: Arquitetura do Sistema de Aquisição

O Arduino Pro Micro lê dois sensores de pressão analógicos (0–5 V):
- **Sensor 1 (Linha / A0):** pressão upstream, calibrado pelo usuário
- **Sensor 2 (Pasta / A1):** pressão na câmara, calibração de fábrica (`P = 2,5·V − 1,25` bar, faixa 0–10 bar, saída 0,5–4,5 V)

O firmware aplica um filtro EMA (Média Móvel Exponencial) às leituras brutas e responde a dois comandos via serial: `READ_VOLTAGE` (retorna `V1;V2`) e `PING`. O Python converte as tensões para pressão usando parâmetros de calibração armazenados em arquivo JSON.

---

## Parte I — Problemas Identificados

---

### A-01 🟡 MÉDIO — Instabilidade do Vref (USB 5 V como Referência ADC)

**Localização:** implícita — ausência de `analogReference()` no `setup()`  
**Impacto:** erro sistemático de até ±6,7% na pressão calculada, variável entre sessões de medição

#### Descrição

O Arduino Pro Micro, quando não recebe chamada explícita a `analogReference()`, usa o pino AVCC como referência do ADC. No Pro Micro conectado via USB, AVCC é derivado diretamente da tensão USB — que a especificação USB 2.0 permite variar de **4,75 V a 5,25 V** (±5%) dependendo da fonte (computador, hub ativo/passivo, cabo).

O firmware converte o resultado do ADC para tensão com:

```c
float v = raw * (5.0 / 1023.0);  // assume Vref = 5,000 V exato
```

Se o Vref real no momento da medição for diferente do Vref no momento da calibração, surge um erro sistemático proporcional ao desvio:

```
P_erro = P_real × (Vref_calibração / Vref_medição)
```

#### Quantificação do Erro

Simulação para P = 5 bar, calibração feita com Vref = 5,0 V:

| Vref na medição | P calculado (bar) | Erro |
|----------------:|------------------:|-----:|
| 4,75 V (mín. USB) | 5,335 | **+6,7%** |
| 4,90 V | 5,134 | +2,7% |
| 5,00 V | 5,006 | +0,1% |
| 5,10 V | 4,883 | −2,3% |
| 5,25 V (máx. USB) | 4,708 | −5,8% |

O erro de 6,7% em pressão se propaga diretamente para τ_w (que é proporcional à pressão), portanto também para a viscosidade calculada — podendo superar a incerteza nominal do próprio sensor (2%).

**Importante:** esse erro é não-sistemático entre sessões — pode somar-se ou opor-se à incerteza do sensor de forma imprevisível. Duas medições do mesmo material realizadas em dias diferentes, em computadores ou portas USB distintas, podem divergir por esse mecanismo.

#### Por que a Referência Interna não Resolve Diretamente

As referências internas do ATmega32U4 são 2,56 V e 1,1 V. O sensor Pasta tem saída máxima de 4,5 V — acima de ambas as referências internas — tornando-as inutilizáveis sem condicionamento de sinal.

#### Correções Possíveis

**Opção A — Software (imediata, sem modificação de hardware):** realizar a calibração de cada sensor sempre na mesma sessão de trabalho (mesmo Arduino, mesma porta USB, mesma fonte). A calibração absorve o Vref atual e o erro cancela desde que Vref não mude entre calibração e medição na mesma sessão. **Documentar esta restrição no manual.**

**Opção B — Hardware (recomendada para publicação):** instalar uma referência de tensão externa de precisão (ex.: LM4040-5.0 ou LM385-5.0) no pino AREF do Pro Micro e adicionar ao firmware:

```c
void setup() {
    analogReference(EXTERNAL);  // usa pino AREF como referência
    ...
}
```

O LM4040-5.0 tem tolerância de 0,1% e deriva típica de 50 ppm/°C, reduzindo a incerteza de Vref de ±5% para ±0,1%. Custo do componente: ~R$ 3–5.

---

### A-02 🟡 MÉDIO — Ausência de Comando RESET_EMA

**Localização:** firmware — nenhuma lógica de reinicialização do filtro  
**Impacto:** leituras incorretas nos primeiros ~130 ms de cada ensaio quando a pressão parte de um valor diferente do ensaio anterior

#### Descrição

O filtro EMA é inicializado apenas uma vez — na primeira execução do `loop()`:

```c
if (!ema_initialized) {
    ema_voltage_1 = v1;
    ema_voltage_2 = v2;
    ema_initialized = true;
}
```

Após esse ponto, o estado do filtro persiste indefinidamente. Se o ensaio anterior terminou com alta pressão (ex.: 8 bar) e o novo ensaio começa com pressão próxima de zero, o EMA carrega o valor antigo como estado inicial. A equação do filtro é:

```
EMA[t] = α × leitura[t] + (1−α) × EMA[t−1]
```

Com α = 0,3 e ciclos de 10 ms, a constante de tempo é:

```
τ = −10 ms / ln(1−0,3) ≈ 28 ms
```

O tempo para atingir 99% do valor final é aproximadamente **5τ ≈ 140 ms**.

#### Quantificação do Erro Transitório

Cenário: EMA em 8,0 bar (ensaio anterior), pressão real agora = 5,0 bar:

| Tempo após início | EMA (bar) | Erro absoluto | Erro relativo |
|------------------:|----------:|--------------:|--------------:|
| 0 ms | 8,000 | +3,000 bar | +60,0% |
| 50 ms | 5,504 | +0,504 bar | +10,1% |
| 100 ms | 5,085 | +0,085 bar | +1,7% |
| 130 ms | 5,025 | +0,025 bar | +0,5% |
| 200 ms | 5,002 | +0,002 bar | <0,1% |

#### Contexto com o Sistema Python

O módulo `coleta.py` implementa detecção de regime estacionário por janela de menor desvio padrão (M2), buscando a janela mais estável na segunda metade dos dados. Isso **atenua significativamente** o problema A-02 na prática: a janela usada para calcular a pressão média do ensaio é selecionada após o sistema se estabilizar, o que exclui naturalmente os primeiros 130 ms de transiente.

Ainda assim, em ensaios muito curtos (poucos segundos) ou quando o operador salva um ponto logo no início da coleta, os dados transitórios podem ser incluídos.

#### Correção

Adicionar o comando `RESET_EMA` ao firmware e chamar-lo do Python antes de cada novo ponto de coleta:

```c
// Firmware:
else if (command == "RESET_EMA") {
    ema_initialized = false;  // força reinicialização na próxima leitura
    Serial.println(F("ACK_RESET_EMA"));
}
```

```python
# reometer_controller.py — antes de iniciar nova coleta:
def reset_ema(self):
    """Reinicializa o filtro EMA do Arduino para o novo ensaio."""
    if self.ser and self.ser.is_open:
        self.ser.write(b"RESET_EMA\n")
        resp = self.ser.readline().decode('utf-8', 'ignore').strip()
        return resp == "ACK_RESET_EMA"
    return False
```

---

### A-03 🔵 BAIXO — Divisor ADC Incorreto: `1023` em vez de `1024`

**Localização:** `updateReadings()`, linhas de conversão  
**Impacto:** superestimativa sistemática de +0,098% em tensão em todos os canais

#### Descrição

O código converte o resultado bruto do ADC para tensão com:

```c
float v1 = raw1 * (5.0 / 1023.0);
```

O datasheet do ATmega32U4 define a fórmula do ADC como:

```
ADC = floor(Vin × 1024 / Vref)   →   Vin = ADC × Vref / 1024
```

O divisor correto é **1024**, não 1023. A diferença provém de um equívoco comum: o ADC tem 10 bits e portanto 1024 passos (0 a 1023). Usar 1023 mapeia o valor máximo (1023) para exatamente Vref, mas isso é fisicamente incorreto — o ADC só satura em 1023 quando Vin está entre `Vref × 1023/1024` e `Vref`, nunca exatamente em Vref.

#### Quantificação

| ADC lido | V com `/1023` | V correto (`/1024`) | Erro |
|---------:|--------------:|--------------------:|-----:|
| 512 | 2,5024 V | 2,5000 V | +2,44 mV (+0,098%) |
| 1000 | 4,8876 V | 4,8828 V | +4,77 mV (+0,098%) |
| 1023 | 5,0000 V | 4,9951 V | +4,88 mV (+0,098%) |

Em termos de pressão (sensor 0–10 bar): erro máximo de **+0,011 bar** na faixa plena — bem abaixo da incerteza do sensor (2% = 0,2 bar) e portanto de baixo impacto prático. Vale corrigir por rigor metrológico.

#### Correção

```c
// ANTES:
float v1 = raw1 * (5.0 / 1023.0);
float v2 = raw2 * (5.0 / 1023.0);

// DEPOIS:
float v1 = raw1 * (5.0 / 1024.0);
float v2 = raw2 * (5.0 / 1024.0);
```

---

### A-04 🔵 BAIXO — `readStringUntil()` Pode Bloquear a Atualização do EMA

**Localização:** `loop()`, linha `String command = Serial.readStringUntil('\n');`  
**Impacto:** até 1 segundo sem atualização do EMA em caso de comando malformado ou ruído serial

#### Descrição

A função `Serial.readStringUntil('\n')` aguarda o caractere delimitador `'\n'` por até `Serial.getTimeout()` milissegundos (padrão: **1000 ms**). Durante essa espera, o `loop()` fica bloqueado e `updateReadings()` — que atualiza o EMA — não é chamado.

No fluxo normal de operação (Python envia `READ_VOLTAGE\n` → Arduino responde → Python aguarda), isso não é um problema: o `'\n'` chega imediatamente. O risco existe em dois cenários:

1. **Ruído ou corrupção serial:** caractere recebido sem `'\n'` subsequente
2. **Reinicialização do Python:** se o host reiniciar a comunicação sem enviar `'\n'`, o Arduino fica bloqueado por 1 segundo

Durante o bloqueio, o EMA acumula 100 ciclos perdidos (~35 constantes de tempo) — ao retomar, a primeira leitura real é aplicada com todo o peso do filtro sem o benefício do histórico filtrado.

#### Correção

Definir um timeout mais curto explicitamente no `setup()`:

```c
void setup() {
    Serial.begin(115200);
    Serial.setTimeout(100);  // máximo 100 ms para readStringUntil()
    ...
}
```

100 ms é tempo suficiente para receber qualquer comando válido, e limita o bloqueio máximo do EMA a 10 ciclos (~10 constantes de tempo de erro acumulado, recuperado em ~30 ms).

---

## Parte II — Aspectos Corretos

---

### V-01 ✅ Filtro EMA Implementado Corretamente

O filtro EMA é a escolha adequada para suavizar ruído de sensores analógicos em microcontroladores com recursos limitados. A implementação está correta:

```c
ema_voltage_1 = (v1 * EMA_ALPHA) + (ema_voltage_1 * (1.0 - EMA_ALPHA));
```

Com `EMA_ALPHA = 0.3` e ciclos de ~10 ms, a frequência de corte efetiva é ≈ 5,7 Hz, adequada para sinais de pressão que variam na escala de dezenas a centenas de milissegundos. O filtro é atualizado continuamente (a cada iteração do `loop()`), garantindo que os valores filtrados estejam sempre atualizados quando o comando `READ_VOLTAGE` chega.

---

### V-02 ✅ Protocolo Serial Simples e Robusto

O protocolo de comando/resposta baseado em strings ASCII (`READ_VOLTAGE`, `PING`, `ACK_PING_OK`) é simples, fácil de depurar e adequado para a taxa de amostragem de 10 Hz requerida. O echo de comandos desconhecidos facilita diagnóstico:

```c
Serial.print(F("Arduino: Comando desconhecido - "));
Serial.println(command);
```

O uso de `F()` para strings literais é boa prática — armazena as strings na memória flash (program memory) em vez de na RAM (SRAM), preservando os ~2,5 KB de SRAM do ATmega32U4 para variáveis.

---

### V-03 ✅ Inicialização do EMA Sem Spike Inicial

A inicialização do EMA com a primeira leitura real (em vez de zero) evita o transiente de arranque que ocorreria se o estado inicial fosse 0:

```c
if (!ema_initialized) {
    ema_voltage_1 = v1;   // inicializa com valor real, não zero
    ema_voltage_2 = v2;
    ema_initialized = true;
}
```

Sem isso, o EMA partiria de 0 V e levaria ~140 ms para atingir o valor real na inicialização do sistema — o que já foi corretamente evitado.

---

## Parte III — Resumo e Orçamento de Incerteza

### Ações Recomendadas

| Prioridade | ID | Ação | Onde | Esforço |
|------------|----|------|------|---------|
| 🟡 Curto prazo | A-01 | Documentar restrição: calibrar sempre na mesma sessão de medição | Manual | 30 min |
| 🟡 Curto prazo | A-02 | Adicionar comando `RESET_EMA` no firmware e chamá-lo do Python antes de cada ponto | Firmware + Python | 30 min |
| 🔵 Baixa prioridade | A-03 | Alterar divisor de `1023.0` para `1024.0` | Firmware | 5 min |
| 🔵 Baixa prioridade | A-04 | Adicionar `Serial.setTimeout(100)` no `setup()` | Firmware | 5 min |
| 🏗️ Longo prazo | A-01 | Instalar referência externa LM4040-5.0 no pino AREF | Hardware | 2–4h |

### Orçamento de Incerteza Consolidado (Pressão)

| Fonte | Erro máx. | Tipo |
|-------|----------:|------|
| Sensor de pressão (especificação, classe C) | ±2,0% | hardware |
| Vref USB — variação entre sessões | até ±6,7% | firmware/hardware |
| Divisor ADC 1023 vs 1024 | +0,10% | firmware |
| EMA — lag transitório (t < 130 ms) | até 60% (transitório) | firmware |
| EMA — regime estacionário | 0% | — |

> A instabilidade do Vref USB (A-01) é a maior fonte de erro do firmware, podendo superar a incerteza nominal do sensor em mais de três vezes. Em condições desfavoráveis (dois computadores/sessões com tensão USB distintas), pode comprometer a reprodutibilidade dos ensaios e a comparação entre amostras medidas em dias diferentes.

---

*Revisão realizada por: Claude (Anthropic) — Fevereiro 2026*
