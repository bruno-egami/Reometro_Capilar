# Relatório de Equacionamento Utilizado na Análise Reológica

Este relatório descreve as equações implementadas no script Python para a análise reológica de pastas utilizando dados de um reômetro capilar, incluindo a correção de Bagley opcional.

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

4.  **Taxa de Cisalhamento Aparente na Parede ($\dot{\gamma}_{aw,raw}$):**
    $$\dot{\gamma}_{aw,raw} = \frac{4 \cdot Q}{\pi \cdot R_{cap}^3}$$
    * $\dot{\gamma}_{aw,raw}$: Taxa de cisalhamento aparente na parede \[s⁻¹]
    * **Propósito/Utilização:** Calcular a taxa de deformação do fluido na parede do capilar, assumindo um comportamento Newtoniano. É usada como base para correções posteriores (Weissenberg-Rabinowitsch) para fluidos não-Newtonianos.

5.  **Viscosidade Aparente (Bruta/Não Corrigida, $\eta_{a,raw}$):**
    $$\eta_{a,raw} = \frac{\tau_{w,raw}}{\dot{\gamma}_{aw,raw}} \quad (\text{se } \dot{\gamma}_{aw,raw} \neq 0)$$
    * $\eta_{a,raw}$: Viscosidade aparente \[Pa·s]
    * **Propósito/Utilização:** Fornecer uma primeira estimativa da resistência ao fluxo, como a razão entre a tensão de cisalhamento na parede e a taxa de cisalhamento aparente. Varia com a taxa de cisalhamento para fluidos não-Newtonianos.

---

## 3. Correção de Bagley (Opcional)

Utiliza múltiplos capilares com mesmo raio $R_{Bagley}$ e diferentes comprimentos $L_i$.

1.  **Interpolação de Dados:**
    * **Propósito/Utilização:** Obter valores de pressão ($\Delta P_{total,ik}^*$) para cada capilar ($L_i$) em um conjunto comum de taxas de cisalhamento aparente alvo ($\dot{\gamma}_{aw,k}^*$). Necessário pois os pontos experimentais raramente coincidem nas mesmas taxas alvo.

2.  **Ajuste Linear (Plot de Bagley):** Para cada $\dot{\gamma}_{aw,k}^*$, ajusta-se:
    $$\Delta P_{total,k}^* = \text{Slope}_k \cdot \left(\frac{L_i}{R_{Bagley}}\right) + \text{Intercept}_k$$
    * $\text{Slope}_k$: Inclinação da reta de Bagley \[Pa]
    * $\text{Intercept}_k$: Perda de pressão nas extremidades ($\Delta P_{e,k}$) \[Pa]
    * **Propósito/Utilização:** Separar a queda de pressão devida ao escoamento viscoso no comprimento do capilar das perdas de pressão nas extremidades. O script também gera um gráfico deste ajuste.

3.  **Tensão de Cisalhamento na Parede Corrigida por Bagley ($\tau_{w,corr,k}$):**
    $$\tau_{w,corr,k} = \frac{\text{Slope}_k}{2}$$
    * **Propósito/Utilização:** Determinar a tensão de cisalhamento na parede devida apenas ao escoamento viscoso, removendo a influência das perdas nas extremidades. É um valor mais preciso, especialmente para capilares curtos.

* **Curva de Fluxo Corrigida por Bagley:** Os pares $(\dot{\gamma}_{aw,k}^*, \tau_{w,corr,k})$ formam a nova curva de fluxo (`gamma_dot_aw_an` e `tau_w_an`) usada nas etapas seguintes.

---

## 4. Correção de Weissenberg-Rabinowitsch

Aplica-se aos dados da curva de fluxo (`tau_w_an`, `gamma_dot_aw_an`).

1.  **Índice de Comportamento de Fluxo Local (n' ou `n_prime_global`):**
    Determinado como a inclinação da reta no gráfico de <span class="math-inline">\\ln\(\\tau\_\{w,an\}\)</span> versus <span class="math-inline">\\ln\(\\dot\{\\gamma\}\_\{aw,an\}\)</span> (para <span class="math-inline">\\tau\_\{w,an\}\>0, \\dot\{\\gamma\}\_\{aw,an\}\>0</span>).
    <span class="math-block">n' \= \\frac\{d\(\\ln \\tau\_\{w,an\}\)\}\{d\(\\ln \\dot\{\\gamma\}\_\{aw,an\}\)\}</span>
    * <span class="math-inline">n'</span>: Adimensional
    * **Propósito/Utilização:** Caracterizar a pseudoplasticidade ou dilatância local do fluido. Indica o quanto a viscosidade aparente muda com a taxa de cisalhamento.

2.  **Taxa de Cisalhamento Real na Parede (<span class="math-inline">\\dot\{\\gamma\}\_\{w,an\}</span>):**
    <span class="math-block">\\dot\{\\gamma\}\_\{w,an\} \= \\left\( \\frac\{3n' \+ 1\}\{4n'\} \\right\) \\cdot \\dot\{\\gamma\}\_\{aw,an\}</span>
    * <span class="math-inline">\\dot\{\\gamma\}\_\{w,an\}</span>: Taxa de cisalhamento real na parede \[s⁻¹]
    * **Propósito/Utilização:** Corrigir a taxa de cisalhamento aparente para levar em conta o perfil de velocidade não parabólico de fluidos não-Newtonianos. É a taxa de cisalhamento efetiva na parede do capilar.

---

## 5. Viscosidade Real (<span class="math-inline">\\eta\_\{true,an\}</span>)

<span class="math-block">\\eta\_\{true,an\} \= \\frac\{\\tau\_\{w,an\}\}\{\\dot\{\\gamma\}\_\{w,an\}\} \\quad \(\\text\{se \} \\dot\{\\gamma\}\_\{w,an\} \\neq 0\)</span>
* <span class="math-inline">\\eta\_\{true,an\}</span>: Viscosidade real \[Pa·s]
* <span class="math-inline">\\tau\_\{w,an\}</span>: Tensão de cisalhamento na parede (bruta ou corrigida por Bagley) \[Pa]
* **Propósito/Utilização:** Calcular a viscosidade verdadeira do material na parede do capilar. Para fluidos não-Newtonianos, <span class="math-inline">\\eta\_\{true,an\}</span> varia com <span class="math-inline">\\dot\{\\gamma\}\_\{w,an\}</span>.

---

## 6. Modelos Reológicos Constitutivos

Ajustados aos dados <span class="math-inline">\(\\tau\_\{w,an\}, \\dot\{\\gamma\}\_\{w,an\}\)</span>. <span class="math-inline">\\tau</span> representa <span class="math-inline">\\tau\_\{w,an\}</span> e <span class="math-inline">\\dot\{\\gamma\}</span> representa <span class="math-inline">\\dot\{\\gamma\}\_\{w,an\}</span>.

1.  **Modelo Newtoniano:**
    <span class="math-block">\\tau \= \\eta \\cdot \\dot\{\\gamma\}</span>
    * <span class="math-inline">\\eta</span>: Viscosidade Newtoniana \[Pa·s]
    * **Utilização:** Descreve fluidos ideais com viscosidade constante.

2.  **Modelo Lei da Potência (Ostwald-de Waele):**
    <span class="math-block">\\tau \= K \\cdot \\dot\{\\gamma\}^n</span>
    * <span class="math-inline">K</span>: Índice de Consistência \[Pa·sⁿ]
    * <span class="math-inline">n</span>: Índice de Comportamento de Fluxo \[adimensional]
    * **Utilização:** Modelo simples para fluidos não-Newtonianos sem tensão de escoamento.

3.  **Modelo de Bingham Plastic:**
    <span class="math-block">\\tau \= \\tau\_0 \+ \\eta\_p \\cdot \\dot\{\\gamma\} \\quad \(\\text\{para \} \\tau \> \\tau\_0\)</span>
    * <span class="math-inline">\\tau\_0</span>: Tensão de Escoamento \[Pa]
