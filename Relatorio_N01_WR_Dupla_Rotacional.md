# Relatório de Problema N-01
## Aplicação Dupla da Correção de Weissenberg-Rabinowitsch em Dados Rotacionais Importados

**Projeto:** Reômetro Capilar com Transdutor de Pressão (v4.1)  
**Arquivo afetado:** `database_manager.py` — função `import_csv_rotacional`  
**Severidade:** 🔴 CRÍTICO  
**Data:** 25 de fevereiro de 2026

---

## 1. Resumo Executivo

A nova função `import_csv_rotacional` converte dados de reômetros rotacionais (ex.: Anton Paar MCR 102) em ensaios capilares sintéticos para que possam ser analisados pelo software. As fórmulas de conversão estão matematicamente corretas. No entanto, a pipeline de análise do módulo `analise.py` aplica **automaticamente** a correção de Weissenberg-Rabinowitsch (W-R) sobre todos os dados — sem distinção entre origem capilar e rotacional.

Como os dados rotacionais já contêm a **taxa de cisalhamento real** (γ̇_real), a aplicação subsequente da W-R os trata erroneamente como taxa **aparente**, introduzindo uma superestimativa sistemática em γ̇ proporcional ao fator `(3n'+1)/(4n')`. Para fluidos pseudoplásticos típicos como o caulim estudado no projeto, o erro em γ̇ atinge **+36%**, gerando um MAPE de **26,6%** na viscosidade comparada ao valor real — invalidando o propósito central da funcionalidade, que é a comparação entre os dois equipamentos.

---

## 2. Fundamentos Teóricos

### 2.1 Por que reômetros rotacionais e capilares tratam γ̇ de forma diferente

Em um **reômetro capilar**, o instrumento não mede a taxa de cisalhamento diretamente — ele mede pressão, massa extrudada e tempo. A taxa calculada a partir dessas grandezas é a **taxa aparente** (γ̇_app), válida para fluido Newtoniano:

```
γ̇_app = 4Q / (πR³)
```

Para fluidos não-Newtonianos, a taxa real na parede é diferente e requer a **correção de Weissenberg-Rabinowitsch**:

```
γ̇_real = γ̇_app × (3n' + 1) / (4n')
```

onde `n' = d(ln τ_w) / d(ln γ̇_app)` é o índice de comportamento de fluxo local.

Em um **reômetro rotacional** com geometria cone-placa ou cilindros coaxiais, a taxa de cisalhamento é determinada diretamente pela geometria e pela velocidade angular do instrumento. O MCR 102 entrega a **taxa real** sem necessidade de correção W-R posterior. O arquivo CSV exportado (colunas Taxa; Tensão; Viscosidade) já contém γ̇_real.

### 2.2 A pipeline de análise do software

O módulo `analise.py` sempre executa W-R sobre os dados que recebe, com o parâmetro `aplicar_weissenberg=True` fixo para a análise padrão:

```python
# analise.py — linha ~282 (hardcoded)
result = self._perform_statistical_analysis(
    self.selected_amostra_id,
    aplicar_weissenberg=True,   # sempre True
    ...
)
```

Dentro de `_perform_statistical_analysis`, a correção é aplicada incondicionalmente a qualquer amostra presente no banco de dados, independente da sua origem:

```python
if aplicar_weissenberg and len(gd_app_mean) >= 3:
    gd_true_sorted = gd_app_sorted * ((3 * local_n_primes + 1) / (4 * local_n_primes))
```

---

## 3. Fluxo do Erro

O diagrama abaixo mostra o caminho dos dados desde o CSV rotacional até o resultado final com o bug ativo:

```
CSV Rotacional (MCR 102)
  └─ gd_rotacional = γ̇_REAL  (ex: 100 s⁻¹)
  └─ tau_rotacional = τ_real  (ex: 208 Pa)

        ↓  import_csv_rotacional()

Banco de dados (ensaios sintéticos)
  └─ pressao_pasta_bar ← inversão correta de τ_real
  └─ massa_g           ← inversão correta de γ̇_real (tratado como γ̇_APP)

        ↓  _perform_statistical_analysis()

Recálculo de γ̇_app e τ_w
  └─ gd_app = gd_rotacional    ← round-trip correto ✓
  └─ tau_w  = tau_rotacional   ← round-trip correto ✓

        ↓  Correção W-R (ERRO)

Resultado final
  └─ gd_true = gd_rotacional × (3n'+1)/(4n')
             = 100 × 1.363 = 136.3 s⁻¹  ← ERRADO (deveria ser 100 s⁻¹)
  └─ τ_w mantida = 208 Pa               ← correto
  └─ η_result = 208 / 136.3 = 1.53 Pa.s ← ERRADO (real: 208/100 = 2.08 Pa.s)
```

---

## 4. Quantificação do Erro

A simulação completa foi realizada com um fluido Herschel-Bulkley sintético com parâmetros representativos das suspensões de caulim estudadas no artigo (τ₀ = 50 Pa, K = 10 Pa·sⁿ, n = 0,6).

### 4.1 Erro em γ̇ e viscosidade ponto a ponto

| γ̇ real (s⁻¹) | τ (Pa) | γ̇ resultante (s⁻¹) | Erro γ̇ | η real (Pa·s) | η resultante (Pa·s) | Erro η |
|-------------:|-------:|--------------------:|-------:|-------------:|--------------------:|-------:|
| 5 | 76,3 | 6,81 | +36,3% | 15,253 | 11,192 | −26,6% |
| 10 | 89,8 | 13,63 | +36,3% | 8,981 | 6,590 | −26,6% |
| 20 | 110,3 | 27,26 | +36,3% | 5,517 | 4,048 | −26,6% |
| 50 | 154,6 | 68,14 | +36,3% | 3,091 | 2,268 | −26,6% |
| 100 | 208,5 | 136,3 | +36,3% | 2,085 | 1,530 | −26,6% |
| 200 | 290,2 | 272,6 | +36,3% | 1,451 | 1,065 | −26,6% |
| 500 | 466,3 | 681,4 | +36,3% | 0,933 | 0,684 | −26,6% |
| 1000 | 681,0 | 1362,9 | +36,3% | 0,681 | 0,500 | −26,6% |

> **n' estimado da curva: 0,408 → fator W-R: 1,363 → MAPE na viscosidade: 26,6%**

O erro é constante ao longo de toda a faixa de γ̇ pois o fator W-R é calculado como uma média global (n' global).

### 4.2 Impacto nos parâmetros dos modelos ajustados

| Parâmetro | Valor real | Ajuste correto | Ajuste com erro N-01 | Desvio |
|-----------|----------:|---------------:|---------------------:|-------:|
| τ₀ (Pa) | 50,00 | 50,00 | 50,00 | 0,0% |
| K (Pa·sⁿ) | 10,000 | 10,000 | 8,305 | **−17,0%** |
| n (−) | 0,6000 | 0,6000 | 0,6000 | 0,0% |

O índice de consistência K fica subestimado em **17%** — erro diretamente proporcional ao fator W-R aplicado indevidamente. τ₀ e n são preservados pois o deslocamento horizontal de γ̇ afeta principalmente a escala de K.

### 4.3 Impacto na comparação capilar vs. rotacional

O objetivo central de importar dados rotacionais é comparar os dois equipamentos no mesmo gráfico. Com o bug ativo, o rotacional importado aparece deslocado horizontalmente para a direita no gráfico τ vs. γ̇, criando uma divergência artificial entre os instrumentos — mesmo que o material seja idêntico.

```
Curva capilar:              τ = 50 + 10 × γ̇^0,6   (correto)
Curva rotacional importada: τ = 50 + 10 × γ̇^0,6   (mas γ̇ está +36,3% errado)
  → Parecem fluidos diferentes
  → MAPE na viscosidade: 26,6%  (deveria ser ~0%)
```

Esta distorção pode induzir a conclusões equivocadas de que o reômetro capilar subestima γ̇ em relação ao MCR 102, quando na verdade o erro é introduzido pelo software.

### 4.4 Sensibilidade por tipo de fluido

| Tipo de fluido | n' típico | Fator W-R | Erro em γ̇ |
|---------------|----------:|----------:|----------:|
| Newtoniano | 1,00 | 1,000 | 0,0% |
| Suspensão diluída | 0,80 | 1,063 | +6,3% |
| Caulim 60% (típico do projeto) | 0,60 | 1,167 | +16,7% |
| Caulim com tau0 elevado | ~0,41 | 1,363 | **+36,3%** |
| Pasta concentrada | 0,30 | 1,583 | +58,3% |

> Nota: o n' efetivo estimado pela regressão log-log é menor que o n' real quando há tensão de escoamento (τ₀ > 0), o que amplifica o fator W-R incorretamente aplicado, agravando o erro nos fluidos viscoplásticos.

---

## 5. Limitação Adicional: Estimativa de n' com Tensão de Escoamento

A Correção W-R usa n' estimado numericamente como `d(ln τ)/d(ln γ̇_app)`. Para fluidos com tensão de escoamento (Bingham, Herschel-Bulkley), a regressão log-log **não fornece o n' real**, pois `ln(τ₀ + K·γ̇ⁿ) ≠ n·ln(γ̇)`. A tabela abaixo quantifica o erro da estimativa:

| Modelo | τ₀ (Pa) | n real | n' estimado (log-log) | Erro em wr |
|--------|--------:|-------:|----------------------:|-----------:|
| Power Law puro | 0 | 0,6 | 0,6000 | 0,0% |
| Herschel-Bulkley | 20 | 0,6 | 0,5036 | +6,8% |
| Herschel-Bulkley | 100 | 0,6 | 0,3324 | **+28,8%** |
| Bingham | 50 | 1,0 | 0,68 | significativo |

Isso significa que, mesmo que a Opção A (pré-compensação por n' estimado) fosse implementada, ela ainda introduziria erros residuais para fluidos com tensão de escoamento elevada — exatamente as pastas cerâmicas concentradas que são o objeto de estudo do projeto.

---

## 6. Raiz do Problema

O problema tem origem arquitetural: o banco de dados não registra a **origem** dos dados (capilar vs. rotacional). Do ponto de vista de `analise.py`, todos os registros são tratados de forma idêntica — a W-R sempre é aplicada.

A função `import_csv_rotacional` foi implementada com a premissa implícita de que os dados do CSV rotacional são taxas **aparentes**, o que é incorreto. O comentário no código reforça essa confusão:

```python
# database_manager.py, linha 485
# Inverse formulas from analise.py:
# gd_app = (4 * Q_m3s) / (np.pi * R**3) => Q_m3s = gd_app * math.pi * R**3 / 4.0
```

A variável é chamada `gd_app` no loop de importação, mas recebe o valor de `rates[i]`, que é a taxa **real** do rotacional.

---

## 7. Soluções Propostas

### Opção A — Pré-compensação na importação (sem alterar banco de dados)

A ideia é importar γ̇ já dividido pelo fator W-R, de modo que quando a análise multiplicar por W-R, o resultado final seja o γ̇ original do rotacional.

```python
# database_manager.py — dentro do loop de import_csv_rotacional

# Estima n' da curva rotacional por regressão log-log
from scipy.stats import linregress
mask = (rates > 0) & (stresses > 0)
slope_n, *_ = linregress(np.log(rates[mask]), np.log(stresses[mask]))
n_prime_est = np.clip(slope_n, 0.1, 2.0)
wr_factor = (3 * n_prime_est + 1) / (4 * n_prime_est)

# Importa gd_app = gd_rotacional / wr_factor
# Assim: análise calcula gd_true = gd_app * wr_factor = gd_rotacional  ✓
for i in range(len(rates)):
    gd_app_import = rates[i] / wr_factor   # ← única linha alterada
    Q_m3s = (gd_app_import * math.pi * R**3) / 4.0
    ...
```

**Vantagens:** nenhuma alteração no banco de dados ou em `analise.py`.  
**Desvantagens:** a estimativa de n' por regressão log-log é imprecisa para fluidos com tensão de escoamento (Bingham, HB). Quanto maior τ₀, maior o erro residual. Para o caulim do projeto (HB com τ₀ elevado), o erro residual pode chegar a **+28,8%** no fator W-R, o que é melhor que os +36,3% do bug atual, mas ainda não é zero.

---

### Opção B — Flag de origem no banco de dados ✅ Recomendada

Adiciona uma coluna `origem` na tabela `amostras` e pula a W-R para amostras rotacionais.

**Passo 1 — Migration do banco de dados** (`database_manager.py`):

```python
# No bloco de migration existente (após as linhas ~104–110):
cursor.execute("PRAGMA table_info(amostras)")
cols = [row[1] for row in cursor.fetchall()]
if 'origem' not in cols:
    cursor.execute("ALTER TABLE amostras ADD COLUMN origem TEXT DEFAULT 'capilar'")
    self.conn.commit()
    print("Migração: coluna 'origem' adicionada à tabela amostras.")
```

**Passo 2 — Marcar a amostra na importação** (`database_manager.py`):

```python
# Em import_csv_rotacional, substituir o INSERT de amostras:
cursor.execute('''
    INSERT INTO amostras (nome, descricao, d_capilar_mm, l_capilar_mm, densidade_g_cm3, origem)
    VALUES (?, ?, ?, ?, ?, ?)
''', (nome, descricao, d_capilar, l_capilar, densidade, 'rotacional'))  # ← adiciona 'rotacional'
```

**Passo 3 — Ler a origem na análise** (`analise.py`):

```python
# Em _perform_statistical_analysis, ao carregar a amostra:
amostra = next((a for a in amostras if a['id'] == amostra_id), None)
origem = amostra.get('origem', 'capilar')

# E ao chamar a W-R:
if aplicar_weissenberg and origem != 'rotacional' and len(gd_app_mean) >= 3:
    # ... correção W-R apenas para dados capilares
```

**Passo 4 — Indicar na interface** (`analise.py` e relatórios):

```python
# No texto de resultado:
if origem == 'rotacional':
    results_txt += "Origem: Reômetro Rotacional (W-R não aplicada — taxa já é real)\n"
```

**Vantagens:** erro final = 0%, solução permanente e extensível, dados preservados com rastreabilidade de origem.  
**Custo estimado:** ~2 horas de implementação.

---

## 8. Recomendação Final

A **Opção B** é a solução recomendada. A Opção A apenas atenua o problema e introduz erros residuais que crescem com a tensão de escoamento do fluido — justamente o parâmetro mais relevante das pastas cerâmicas concentradas estudadas no projeto.

| Critério | Opção A (pré-compensação) | Opção B (flag de origem) |
|----------|:-------------------------:|:------------------------:|
| Erro residual em γ̇ | Depende de τ₀ (0% a ~29%) | 0% |
| Alteração no banco | Não | Sim (migration simples) |
| Alteração em `analise.py` | Não | Sim (3 linhas) |
| Rastreabilidade de origem | Não | Sim |
| Robustez para τ₀ elevado | Baixa | Total |
| Esforço de implementação | ~30 min | ~2 h |

Enquanto a correção definitiva (Opção B) não é implementada, **o uso da funcionalidade `import_csv_rotacional` deve ser suspenso** para evitar que resultados incorretos sejam incluídos em análises comparativas ou no artigo científico em andamento.

---

*Relatório elaborado por: Claude (Anthropic) — Fevereiro 2026*
