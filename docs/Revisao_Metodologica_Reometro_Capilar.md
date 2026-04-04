# Revisão Metodológica — Sistema de Reômetro Capilar

**Projeto:** Reômetro Capilar com Transdutor de Pressão (v4.1)  
**Repositório:** `Reometro_Capilar-Reometro-capilar-Transdutor_Pasta`  
**Data da Revisão:** 23 de fevereiro de 2026  
**Escopo:** Metodologia de cálculos e fórmulas reológicas  
**Módulos analisados:** `analise.py` · `reologia_corrections.py` · `modelos_reologicos.py` · `reologia_fitting.py`

---

## Sumário de Achados

| ID | Severidade | Descrição | Arquivo | Status |
|----|------------|-----------|---------|--------|
| F-01 | 🔴 CRÍTICO | Fator de extração de τ_w na correção de Bagley | `reologia_corrections.py` | Aguarda correção |
| F-02 | 🟡 MÉDIO | Aplicação do n' global nos dados brutos (W-R) | `analise.py` | Documentar |
| F-03 | 🟡 MÉDIO | Incerteza de ρ ausente na propagação de u(γ̇) | `analise.py` | Melhoria recomendada |
| F-04 | 🔵 BAIXO | delta_p calculado mas não utilizado no τ_w | `analise.py` | Esclarecer ou remover |

---

## Problemas e Erros Identificados

---

### F-01 🔴 CRÍTICO — Fator de Extração de τ_w na Correção de Bagley

**Arquivo:** `reologia_corrections.py`  
**Linha:** `tau_w_corr = slope / 2.0` (dentro de `perform_bagley_correction`)  
**Impacto:** τ_w resultante da correção de Bagley está superestimado por um fator de **2×**

#### Descrição do Problema

O gráfico de Bagley é construído plotando a pressão medida `P` no eixo Y contra a razão geométrica `L/D` no eixo X, mantendo a taxa de cisalhamento aparente (γ̇_app) constante. A regressão linear neste gráfico fornece um coeficiente angular (`slope`) do qual se extrai a tensão de cisalhamento na parede (τ_w).

A questão é: **qual é a relação algébrica correta entre `slope` e τ_w?**

#### Derivação Matemática

A fórmula fundamental da tensão de cisalhamento na parede em um capilar é:

```
τ_w = (ΔP · R) / (2 · L)
```

Isolando ΔP e substituindo R = D/2:

```
ΔP = τ_w · (2L / R)
   = τ_w · (2L / (D/2))
   = τ_w · (4L / D)
   = 4 · τ_w · (L/D)
```

Portanto, na regressão `P = slope · (L/D) + intercept`, o coeficiente angular é:

```
slope = 4 · τ_w   →   τ_w = slope / 4
```

#### O que o Código Faz

```python
# CÓDIGO ATUAL (INCORRETO):
tau_w_corr = slope / 2.0
```

O divisor `2` seria matematicamente válido apenas se o eixo X do gráfico fosse `L/R` (e não `L/D`), pois `L/R = 2 · (L/D)`. Como o código usa corretamente `L/D`:

```python
L_D_target_list.append(cap_data['L_mm'] / cap_data['D_mm'])  # correto: eixo X = L/D
```

...o divisor deveria ser `4`. O erro introduz um fator de 2× na tensão de parede calculada pelo módulo de correções.

O docstring do módulo também apresenta a fórmula incorreta:

```python
# DOCSTRING INCORRETO:
# P = 2τ_w × (L/D) + ΔP_entrada

# DOCSTRING CORRETO:
# P = 4τ_w × (L/D) + ΔP_entrada
```

#### Correção

```python
# CORRETO:
tau_w_corr = slope / 4.0

# E no docstring:
# Slope = 4 × τ_w  →  τ_w = slope / 4
```

#### Contexto e Impacto

> **Importante:** Este erro afeta **exclusivamente** o módulo de correções avançadas (aba "Correções" da GUI). A análise padrão em `analise.py` — que usa diretamente `tau_w = p_pa * R / (2 * L)` — está **correta** e não é impactada.

O impacto prático é que, quando o usuário aplica a correção de Bagley para eliminar efeitos de entrada/saída do capilar, os valores de τ_w corrigidos ficam **duas vezes maiores** do que deveriam. Isso distorce sistematicamente toda a curva de fluxo resultante das correções e inviabiliza a comparação com dados de referência.

#### Referência

> Bagley, E.B. (1957). *End corrections in the capillary flow of polyethylene*. Journal of Applied Physics, 28(5), 624–627.

---

### F-02 🟡 MÉDIO — Aplicação do n' Global nos Dados Brutos (Weissenberg-Rabinowitsch)

**Arquivo:** `analise.py`  
**Linha:** `gd_true_arr = gd_app_arr * ((3 * n_prime_global + 1) / (4 * n_prime_global))`  
**Impacto:** Superestimação ou subestimação da correção W-R nos dados individuais dependendo da curvatura da curva de fluxo

#### Descrição do Problema

A correção de Weissenberg-Rabinowitsch (W-R) converte a taxa de cisalhamento aparente (γ̇_app, válida para fluido Newtoniano) para a taxa real na parede (γ̇_true), usando o índice de comportamento de fluxo local n':

```
γ̇_true = γ̇_app · (3n' + 1) / (4n')
```

O código implementa a correção em **dois momentos distintos**:

**Momento 1 (correto):** Sobre as **médias agrupadas**, usando n' local calculado ponto a ponto:

```python
local_n_primes = np.gradient(log_tau_mean, log_gd_mean)  # n' local em cada ponto
local_n_primes = np.clip(local_n_primes, 0.05, 3.0)
gd_true_sorted = gd_app_sorted * ((3 * local_n_primes + 1) / (4 * local_n_primes))
```

**Momento 2 (aproximação):** Sobre os **dados brutos individuais**, usando um único n' global (média de todos os n' locais):

```python
n_prime_global = np.mean(local_n_primes)
gd_true_arr = gd_app_arr * ((3 * n_prime_global + 1) / (4 * n_prime_global))
```

#### Por que Isso é um Problema

Para fluidos com comportamento não-linear acentuado (suspensões cerâmicas concentradas, típicas do projeto), o n' varia significativamente com a taxa de cisalhamento. Usar um n' global constante para corrigir dados brutos individuais, que cobrem toda a faixa de γ̇, pode introduzir erros sistemáticos nas extremidades da curva.

**Exemplo hipotético:** Se a curva tem n' variando de 0.3 (taxas baixas) a 0.8 (taxas altas), o fator de correção `(3n'+1)/(4n')` varia de 1.58 a 1.06. Um n' global de 0.55 daria fator 1.27 — superestimando a correção nas taxas altas e subestimando nas baixas.

#### Avaliação de Risco

A simplificação é **aceitável para fins de exibição e relatório textual**, desde que o ajuste dos modelos reológicos (o produto final mais importante) seja feito sobre as médias corrigidas com n' local — o que de fato ocorre no código. O risco se torna relevante se o vetor `gd_true_arr` for usado em cálculos posteriores críticos sem essa ressalva.

#### Recomendação

Documentar explicitamente no código e no relatório a distinção entre os dois vetores:

```python
# Adicionar comentário claro:
# ATENÇÃO: gd_true_arr usa n'_global (aproximação para exibição).
# O ajuste dos modelos usa gd_mean (corrigido com n' local, mais preciso).
```

Opcionalmente, aplicar interpolação de n' local também nos dados brutos para maior rigor:

```python
# Alternativa mais rigorosa (opcional):
from scipy.interpolate import interp1d
f_n = interp1d(gd_app_sorted, local_n_primes, bounds_error=False, fill_value=(local_n_primes[0], local_n_primes[-1]))
n_prime_local_brutos = f_n(gd_app_arr)
gd_true_arr = gd_app_arr * ((3 * n_prime_local_brutos + 1) / (4 * n_prime_local_brutos))
```

---

### F-03 🟡 MÉDIO — Incerteza de ρ Ausente na Propagação de u(γ̇)

**Arquivo:** `analise.py`  
**Linhas:** ~418–430 (bloco de propagação de incerteza metrológica)  
**Impacto:** Subestimação da incerteza de γ̇_app, especialmente relevante quando a densidade é medida indiretamente

#### Descrição do Problema

A taxa de cisalhamento aparente é calculada como:

```
γ̇_app = 4Q / (πR³)   onde   Q = m / (ρ · t)
```

Portanto:

```
γ̇_app = 4m / (ρ · t · π · R³)
```

A propagação de incerteza completa (considerando todas as variáveis independentes) é:

```
u(γ̇)/γ̇ = √[ (u_m/m)² + (u_ρ/ρ)² + (u_t/t)² + (3·u_R/R)² ]
```

O código atual implementa:

```python
u_gd_arr = gd_app_arr * np.sqrt(
    (u_m_kg / massas_kg)**2 + (u_t / tempos_arr)**2 + (3 * u_R / R)**2
)
```

O termo `(u_ρ/ρ)²` está ausente.

#### Avaliação Quantitativa

Para a suspensão de caulim estudada (ρ ≈ 1.6–1.9 g/cm³), estimando a incerteza da densidade:

| Método de medição de ρ | u_ρ/ρ estimada | Contribuição para u(γ̇) |
|------------------------|----------------|------------------------|
| Picnômetro calibrado | ~0.3–0.5% | Pequena, desprezível |
| Balança hidrostática | ~0.5–1.0% | Pequena |
| Estimada por formulação | ~2–5% | Não desprezível |

Se a densidade for medida com boa rastreabilidade (picnômetro), o erro de omissão é inferior a 0.5% na incerteza combinada, o que pode ser considerado desprezível na prática. Entretanto, se ρ for estimada indiretamente, o erro pode ser relevante.

#### Recomendação

Adicionar o parâmetro `u_rho_rel` e incluí-lo na propagação:

```python
u_rho_rel = 0.005  # 0.5% — estimativa para picnômetro calibrado (ajustar conforme método)

u_gd_arr = gd_app_arr * np.sqrt(
    (u_m_kg / massas_kg)**2
    + u_rho_rel**2          # novo termo
    + (u_t / tempos_arr)**2
    + (3 * u_R / R)**2
)
```

Documentar no relatório o método de medição de ρ e a incerteza adotada para justificar a magnitude do termo.

---

### F-04 🔵 BAIXO — delta_p Calculado mas Não Utilizado no Cálculo de τ_w

**Arquivo:** `analise.py`  
**Linhas:** 392–393, 705–706  
**Impacto:** Possível confusão sobre qual pressão é usada para calcular τ_w; potencial de erro se o equipamento tiver dois transdutores com leituras divergentes

#### Descrição do Problema

O sistema possui dois transdutores: **Sensor Linha** (pressão upstream, na linha de ar) e **Sensor Pasta** (pressão na câmara de pasta, mais próximo ao capilar). O código calcula a diferença de pressão:

```python
delta_p = p_linha_bar - p_pasta_bar   # calculado
```

Porém, na sequência, o delta_p é armazenado apenas para fins de relatório (`delta_p_list`), e o cálculo de τ_w usa **exclusivamente** a pressão do sensor de pasta:

```python
p_pa = p_pasta_bar * 1e5
tau_w = (p_pa * R) / (2 * L)   # usa apenas p_pasta, não delta_p
```

#### Análise da Escolha

Esta escolha tem **justificativa física sólida**: o sensor de pasta mede a pressão imediatamente antes do capilar, que é a pressão de entrada relevante para a equação de Hagen-Poiseuille. Usar apenas `p_pasta` é **metodologicamente correto**, desde que:

1. O sensor de pasta seja calibrado adequadamente (o código indica que usa calibração de fábrica, o que é razoável).
2. A pressão na saída do capilar seja a pressão atmosférica (assumida implicitamente, válido para extrusão ao ar livre).

#### Problema de Clareza

O `delta_p` é calculado e armazenado mas nunca usado em nenhum cálculo de τ_w — nem na análise principal, nem nas correções. Isso pode:

- Gerar confusão sobre a metodologia adotada
- Levar futuros mantenedores a erroneamente usar `delta_p` no lugar de `p_pasta` por acreditarem que é a variável "correta"
- Mascarar possível intenção original de corrigir perdas de pressão na linha pneumática

#### Recomendação

Adicionar comentário explícito explicando a decisão:

```python
delta_p = p_linha_bar - p_pasta_bar
delta_p_list.append(delta_p)
# NOTA: delta_p é salvo apenas para diagnóstico.
# τ_w é calculado com p_pasta (pressão na câmara), que é a pressão
# de entrada no capilar — grandeza fisicamente correta para a equação
# de Hagen-Poiseuille. A pressão de linha reflete perdas na tubulação
# pneumática e não é usada no cálculo reológico.
```

Ou, se a intenção futura for usar `delta_p` para compensar perdas, implementar essa correção explicitamente e documentá-la.

---

## Resumo das Ações Recomendadas

| Prioridade | ID | Ação | Arquivo | Esforço |
|------------|----|------|---------|---------|
| 🔴 Imediata | F-01 | Alterar `slope / 2.0` para `slope / 4.0` e corrigir docstring | `reologia_corrections.py` | 5 min |
| 🟡 Curto prazo | F-02 | Adicionar comentário diferenciando gd_true_arr (bruto/global) e gd_mean (médias/local) | `analise.py` | 15 min |
| 🟡 Curto prazo | F-03 | Incluir termo u_rho_rel na propagação de incerteza de γ̇ | `analise.py` | 30 min |
| 🔵 Médio prazo | F-04 | Adicionar comentário explicando por que delta_p não é usado no cálculo de τ_w | `analise.py` | 10 min |

---

## Apêndice — Contexto do Equipamento

O reômetro capilar estudado opera com **pressão pneumática** (compressor de ar), ao contrário de reômetros capilares convencionais de laboratório que controlam a taxa de deformação (deslocamento de pistão). Esta diferença implica que:

1. A pressão de entrada é a variável de controle (não a taxa de fluxo), e γ̇_app é uma variável derivada via medição de massa e tempo.
2. A incerteza em γ̇_app é dominada pela incerteza do tempo de extrusão (trigger manual, u_t = 0.2 s), especialmente para extrusões rápidas.
3. A ausência de controle de velocidade de pistão torna a abordagem de medição por massa/tempo necessária — e a implementação está correta para essa configuração.

---

*Revisão realizada por: Claude (Anthropic) — Fevereiro 2026*
