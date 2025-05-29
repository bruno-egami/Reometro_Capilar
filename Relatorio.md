# Relatório de Equacionamento Utilizado na Análise Reológica

Este relatório descreve as equações fundamentais implementadas no script Python para a análise reológica de pastas utilizando dados de um reômetro capilar, incluindo a correção de Bagley opcional.

---

## 1. Dados de Entrada e Conversões de Unidades

**Propósito/Utilização:**
Garantir que todas as medições experimentais e parâmetros geométricos estejam em um sistema de unidades consistente (SI: metros, quilogramas, segundos, Pascals) para a correta aplicação das equações reológicas fundamentais.

* **Diâmetro do Capilar ($D_{cap}$):**
    * Entrada: $D_{cap,mm}$ \[mm]
    * Cálculo SI: $$D_{cap} = \frac{D_{cap,mm}}{1000} \quad [\text{m}]$$

* **Raio do Capilar ($R_{cap}$):**
    * Cálculo SI: $$R_{cap} = \frac{D_{cap}}{2} \quad [\text{m}]$$

* **Comprimento do Capilar ($L_{cap}$):**
    * Entrada: $L_{cap,mm}$ \[mm]
    * Cálculo SI: $$L_{cap} = \frac{L_{cap,mm}}{1000} \quad [\text{m}]$$

* **Densidade da Pasta ($\rho_{pasta}$):**
    * Entrada: $\rho_{pasta,g/cm³}$ \[g/cm³]
    * Cálculo SI: $$\rho_{pasta} = \rho_{pasta,g/cm³} \times 1000 \quad [\text{kg/m³}]$$

* **Tempo de Extrusão ($t_{extrusao}$):**
    * Entrada: $t_{extrusao,s}$ \[s] (valor fixo para todos os testes)

* **Pressão Medida ($P_{medida}$):**
    * Entrada: $P_{medida,bar}$ \[bar]
    * Cálculo SI (Queda de Pressão Total, $\Delta P$): $$\Delta P = P_{medida,bar} \times 10^5 \quad [\text{Pa}]$$

* **Massa Extrudada ($m_{extrudada}$):**
    * Entrada: $m_{extrudada,g}$ \[g]
    * Cálculo SI: $$m_{extrudada,kg} = \frac{m_{extrudada,g}}{1000} \quad [\text{kg}]$$

---

## 2. Cálculos Reológicos Primários

Estes cálculos são realizados para cada ponto experimental. Se a Correção de Bagley não for usada, aplicam-se aos dados do capilar único. Se Bagley for usada, são o primeiro passo para cada capilar individualmente.

1.  **Volume Extrudado ($V$):**
    $$V = \frac{m_{extrudada,kg}}{\rho_{pasta}}$$
    * $V$: Volume extrudado \[m³]
    * $m_{extrudada,kg}$: Massa extrudada \[kg]
    * $\rho_{pasta}$: Densidade da pasta \[kg/m³]
    * **Propósito/Utilização:** Converter a massa de material extrudado em um volume correspondente. O volume é necessário para o cálculo da vazão volumétrica.

2.  **Vazão Volumétrica ($Q$):**
    $$Q = \frac{V}{t_{extrusao}}$$
    * $Q$: Vazão volumétrica \[m³/s]
    * $V$: Volume extrudado \[m³]
    * $t_{extrusao}$: Tempo de extrusão \[s]
    * *Nota:* Para exibição em tabelas, $Q_{display} [\text{mm³/s}] = Q [\text{m³/s}] \times 10^9$.
    * **Propósito/Utilização:** Determinar a taxa na qual o volume de pasta flui através do capilar. A vazão é um parâmetro experimental chave, diretamente relacionado à taxa de cisalhamento.

3.  **Tensão de Cisalhamento na Parede (Bruta/Não Corrigida, $\tau_{w,raw}$):**
    Calculada para cada ponto de um capilar específico $(R_{cap}, L_{cap})$:
    $$\tau_{w,raw} = \frac{\Delta P \cdot R_{cap}}{2 \cdot L_{cap}}$$
    * $\tau_{w,raw}$: Tensão de cisalhamento na parede \[Pa]
    * $\Delta P$: Queda de pressão total medida \[Pa]
    * $R_{cap}$: Raio do capilar \[m]
    * $L_{cap}$: Comprimento do capilar \[m]
    * **Propósito/Utilização:** Calcular a força por unidade de área que o fluido exerce na parede interna do capilar. É uma das duas variáveis primárias da curva de fluxo. O valor "raw" não considera efeitos de entrada/saída.

4.  **Taxa de Cisalhamento Aparente na Parede ($\dot{\gamma}_{aw,raw}$):** [cite: 1]
    $$\dot{\gamma}_{aw,raw} = \frac{4 \cdot Q}{\pi \cdot R_{cap}^3}$$
    * $\dot{\gamma}_{aw,raw}$: Taxa de cisalhamento aparente na parede \[s⁻¹] [cite: 1]
    * **Propósito/Utilização:** Calcular a taxa de deformação do fluido na parede do capilar, assumindo um comportamento Newtoniano. É usada como base para correções posteriores (Weissenberg-Rabinowitsch) para fluidos não-Newtonianos. [cite: 1]

5.  **Viscosidade Aparente (Bruta/Não Corrigida, $\eta_{a,raw}$):** [cite: 2]
    $$\eta_{a,raw} = \frac{\tau_{w,raw}}{\dot{\gamma}_{aw,raw}} \quad (\text{se } \dot{\gamma}_{aw,raw} \neq 0)$$
    * $\eta_{a,raw}$: Viscosidade aparente \[Pa·s]
    * **Propósito/Utilização:** Fornecer uma primeira estimativa da resistência ao fluxo, como a razão entre a tensão de cisalhamento na parede e a taxa de cisalhamento aparente. Varia com a taxa de cisalhamento para fluidos não-Newtonianos.

---

## 3. Correção de Bagley (Opcional)

Utiliza múltiplos capilares com mesmo raio $R_{Bagley}$ e diferentes comprimentos $L_i$.

1.  **Interpolação de Dados:**
    * **Propósito/Utilização:** Obter valores de pressão ($\Delta P_{total,ik}^*$) para cada capilar ($L_i$) em um conjunto comum de taxas de cisalhamento aparente alvo ($\dot{\gamma}_{aw,k}^*$). Necessário pois os pontos experimentais raramente coincidem nas mesmas taxas alvo. [cite: 3]

2.  **Ajuste Linear (Plot de Bagley):** Para cada $\dot{\gamma}_{aw,k}^*$, ajusta-se: [cite: 4]
    $$\Delta P_{total,k}^* = (\text{Slope}_k) \cdot \left(\frac{L_i}{R_{Bagley}}\right) + \text{Intercept}_k$$
    * $\text{Slope}_k$: Inclinação da reta de Bagley para $\dot{\gamma}_{aw,k}^*$ \[Pa] [cite: 4]
    * $\text{Intercept}_k$: Perda de pressão nas extremidades ($\Delta P_{e,k}$) para $\dot{\gamma}_{aw,k}^*$ \[Pa] [cite: 4]
    * **Propósito/Utilização:** Separar a queda de pressão devida ao escoamento viscoso no comprimento do capilar das perdas de pressão nas extremidades. O script também gera um gráfico deste ajuste. [cite: 4]

3.  **Tensão de Cisalhamento na Parede Corrigida por Bagley ($\tau_{w,corr,k}$):**
    $$\tau_{w,corr,k} = \frac{\text{Slope}_k}{2}$$
    * **Propósito/Utilização:** Determinar a tensão de cisalhamento na parede devida apenas ao escoamento viscoso, removendo a influência das perdas nas extremidades. É um valor mais preciso, especialmente para capilares curtos.

* **Curva de Fluxo Corrigida por Bagley:** Os pares $(\dot{\gamma}_{aw,k}^*, \tau_{w,corr,k})$ formam a nova curva de fluxo (`gamma_dot_aw_an` e `tau_w_an`) usada nas etapas seguintes.

---

## 4. Correção de Weissenberg-Rabinowitsch

Aplica-se aos dados da curva de fluxo (`tau_w_an`, `gamma_dot_aw_an`).

1.  **Índice de Comportamento de Fluxo Local ($n'$ ou `n_prime_global`):**
    Determinado como a inclinação da reta no gráfico de $\ln(\tau_{w,an})$ versus $\ln(\dot{\gamma}_{aw,an})$ (para $\tau_{w,an}>0, \dot{\gamma}_{aw,an}>0$).
    $$n' = \frac{d(\ln \tau_{w,an})}{d(\ln \dot{\gamma}_{aw,an})}$$
    * $n'$: Adimensional
    * **Propósito/Utilização:** Caracterizar a pseudoplasticidade ou dilatância local do fluido. Indica o quanto a viscosidade aparente muda com a taxa de cisalhamento.

2.  **Taxa de Cisalhamento Real na Parede ($\dot{\gamma}_{w,an}$):**
    $$\dot{\gamma}_{w,an} = \left( \frac{3n' + 1}{4n'} \right) \cdot \dot{\gamma}_{aw,an}$$
    * $\dot{\gamma}_{w,an}$: Taxa de cisalhamento real na parede \[s⁻¹]
    * **Propósito/Utilização:** Corrigir a taxa de cisalhamento aparente para levar em conta o perfil de velocidade não parabólico de fluidos não-Newtonianos. É a taxa de cisalhamento efetiva na parede do capilar.

---

## 5. Viscosidade Real ($\eta_{true,an}$)

$$\eta_{true,an} = \frac{\tau_{w,an}}{\dot{\gamma}_{w,an}} \quad (\text{se } \dot{\gamma}_{w,an} \neq 0)$$
* $\eta_{true,an}$: Viscosidade real \[Pa·s]
* $\tau_{w,an}$: Tensão de cisalhamento na parede (bruta ou corrigida por Bagley) \[Pa]
* **Propósito/Utilização:** Calcular a viscosidade verdadeira do material na parede do capilar. Para fluidos não-Newtonianos, $\eta_{true,an}$ tipicamente varia com $\dot{\gamma}_{w,an}$.

---

## 6. Modelos Reológicos Constitutivos

Ajustados aos dados $(\tau_{w,an}, \dot{\gamma}_{w,an})$. $\tau$ representa $\tau_{w,an}$ e $\dot{\gamma}$ representa $\dot{\gamma}_{w,an}$.

1.  **Modelo Newtoniano:**
    $$\tau = \eta \cdot \dot{\gamma}$$
    * $\eta$: Viscosidade Newtoniana \[Pa·s]
    * **Utilização:** Descreve fluidos ideais com viscosidade constante.

2.  **Modelo Lei da Potência (Ostwald-de Waele):**
    $$\tau = K \cdot \dot{\gamma}^n$$
    * $K$: Índice de Consistência \[Pa·sⁿ]
    * $n$: Índice de Comportamento de Fluxo \[adimensional]
    * **Utilização:** Modelo simples para fluidos não-Newtonianos sem tensão de escoamento.

3.  **Modelo de Bingham Plastic:**
    $$\tau = \tau_0 + \eta_p \cdot \dot{\gamma} \quad (\text{para } \tau > \tau_0)$$
    * $\tau_0$: Tensão de Escoamento \[Pa]
    * $\eta_p$: Viscosidade Plástica \[Pa·s]
    * **Utilização:** Descreve materiais que necessitam de uma tensão mínima ($\tau_0$) para fluir.

4.  **Modelo de Herschel-Bulkley:**
    $$\tau = \tau_0 + K \cdot \dot{\gamma}^n \quad (\text{para } \tau > \tau_0)$$
    * $\tau_0$: Tensão de Escoamento \[Pa]
    * $K$: Índice de Consistência \[Pa·sⁿ]
    * $n$: Índice de Comportamento de Fluxo \[adimensional]
    * **Utilização:** Modelo versátil para fluidos viscoplásticos, combinando tensão de escoamento com comportamento de Lei da Potência.

* **Propósito/Utilização Geral dos Modelos:** Quantificar o comportamento reológico através de parâmetros, entender a natureza do fluido e prever seu comportamento.

---

## 7. Cálculo da Viscosidade a Partir dos Modelos Ajustados

Para plotar as curvas de viscosidade teóricas.

$$\eta_{modelo}(\dot{\gamma}) = \frac{\tau_{modelo}(\dot{\gamma})}{\dot{\gamma}}$$
* **Propósito/Utilização:** Calcular a viscosidade prevista por cada modelo ajustado em função da taxa de cisalhamento, para comparação visual com os dados experimentais de viscosidade.

---
