# 🔬 Sistema de Controle e Análise - Reômetro Capilar

Sistema completo para controle de reômetro capilar com **dois sensores de pressão** (Linha & Pasta), análise reológica, correções de Bagley e Mooney, e comparação de dados.

---

## 📋 **Índice**

1. [Requisitos](#requisitos)
2. [Instalação](#instalação)
3. [Estrutura do Sistema](#estrutura-do-sistema)
4. [Fluxo de Trabalho](#fluxo-de-trabalho)
5. [Descrição dos Scripts](#descrição-dos-scripts)
6. [Solução de Problemas](#solução-de-problemas)

---

## 🔧 **Requisitos**

### **Hardware**
- Arduino com Firmware v3.0+ (dual sensor)
- 2x Sensores de pressão (Transdutor 1: Linha, Transdutor 2: Pasta)
- Balança de precisão
- Reômetro capilar com capilares intercambiáveis

### **Software**
- **Python:** 3.8 ou superior
- **Sistema Operacional:** Windows, Linux ou macOS

### **Dependências Python**

Instale todas as dependências necessárias com:

```bash
pip install numpy pandas matplotlib scipy pyserial scikit-learn openpyxl
```

**Lista detalhada de dependências:**

| Biblioteca | Versão Mínima | Finalidade |
|------------|---------------|------------|
| `numpy` | 1.20.0 | Cálculos numéricos e arrays |
| `pandas` | 1.3.0 | Manipulação de dados tabulares |
| `matplotlib` | 3.4.0 | Geração de gráficos |
| `scipy` | 1.7.0 | Ajuste de modelos e interpolação |
| `pyserial` | 3.5 | Comunicação com Arduino |
| `scikit-learn` | 0.24.0 | Análise estatística |
| `openpyxl` | 3.0.0 | Exportação para Excel (opcional) |
| `fpdf2` | 2.0.0 | Geração de relatórios PDF |

**Instalação rápida (copie e cole):**
```bash
pip install numpy>=1.20.0 pandas>=1.3.0 matplotlib>=3.4.0 scipy>=1.7.0 pyserial>=3.5 scikit-learn>=0.24.0 openpyxl>=3.0.0 fpdf2>=2.0.0
```

---

## 🚀 **Instalação**

### **1. Clone ou Baixe o Repositório**
```bash
git clone https://github.com/bruno-egami/Reometro_Capilar.git
cd Reometro_Capilar
```

### **2. Instale as Dependências**
```bash
pip install numpy pandas matplotlib scipy pyserial scikit-learn openpyxl
```

### **3. Configure o Arduino**
- Carregue o firmware v3.0+ no Arduino
- Conecte os sensores de pressão
- Conecte o Arduino via USB

### **4. Teste a Instalação**
```bash
python 0.Launcher.py
```

Se abrir o menu principal, está tudo pronto! ✅

---

## 🖥️ **Aplicação Gráfica (GUI)**

A partir da versão 4.0, o sistema conta com uma **interface gráfica moderna** construída com CustomTkinter:

### **Iniciar a GUI:**
```bash
python gui_main.py
```

### **Funcionalidades da GUI:**

| Aba | Funcionalidades |
|-----|-----------------|
| **Coleta** | Conexão Arduino, gráfico tempo-real, coleta com validação |
| **Histórico** | Visualização de amostras e ensaios salvos no SQLite |
| **Calibração** | Wizard de calibração (sensor Pasta fixo, Linha por referência) |
| **Análise** | 5 modelos reológicos, Weissenberg, R², export PNG/PDF |
| **Correções** | Bagley e Mooney para análise avançada |

### **Sensores de Pressão:**
- **Pasta (Fábrica):** Calibração fixa (P = 2.5V - 1.25)
- **Linha:** Calibrado usando Pasta como referência

### **Dependências Adicionais (GUI):**
```bash
pip install customtkinter fpdf2 pytest
```

---

## 📁 **Estrutura do Sistema**

```
Reometro_Capilar/
├── 0.Launcher.py                    # Menu principal (CLI)
├── gui_main.py                      # Interface gráfica (GUI) ⭐ NOVO
├── 1.Controle_Reometro.py           # Coleta de dados (dual sensor)
├── 1a.Edit-Json-coleta.py           # Edição manual de dados
├── 1b.Pre-analise-filtro.py         # Pré-processamento
├── 2.Analise_reologica.py           # Análise completa + modelos
├── 2b.Tratamento_Estatistico.py     # Estatísticas de múltiplos testes
├── 2cFiltro_Residuos_Modelo.py      # Filtro de outliers
├── 3.Visualizar_resultados.py       # Visualização de gráficos
├── 4.Comparativo-Analises.py        # Comparação capilar vs rotacional
├── 5.Processador_Rotacional_Completo.py  # Dados rotacionais
│
├── modelos_reologicos.py            # Definição dos 5 modelos ⭐ NOVO
├── reologia_fitting.py              # Ajuste e R² ⭐ NOVO
├── reologia_corrections.py          # Bagley/Mooney ⭐ NOVO
├── reometer_controller.py           # Comunicação Arduino ⭐ NOVO
├── database_manager.py              # SQLite manager ⭐ NOVO
├── test_calculos.py                 # Testes unitários (pytest) ⭐ NOVO
│
├── calibracoes_reometro/            # Calibrações salvas
├── resultados_testes_reometro/      # JSONs brutos
├── resultados_analise_reologica/    # CSVs, gráficos, relatórios
├── comparativo_analises/            # Resultados comparativos
└── resultados_processados_interativo/  # Dados rotacionais
```

---

## 🔄 **Fluxo de Trabalho**

### **Workflow Típico:**

```
1. COLETA
   ├─ Script 1: Coleta dados dual sensor
   └─ Script 1a: Remove pontos inválidos (opcional)

2. PRÉ-PROCESSAMENTO
   └─ Script 1b: Gera CSV e JSON processados

3. ANÁLISE
   ├─ Script 2: Ajusta modelos reológicos
   ├─ Script 2c: Remove outliers estatísticos (opcional)
   └─ Script 2b: Média de múltiplos ensaios (opcional)

4. VISUALIZAÇÃO
   ├─ Script 3: Visualiza gráficos individuais
   └─ Script 4: Compara múltiplas análises
```

### **Exemplo Prático:**

1. **Coletar Dados:**
   ```bash
   python 0.Launcher.py
   # Escolha: 1. Controle do Reômetro
   # Siga instruções na tela
   ```

2. **Analisar:**
   ```bash
   # Escolha: 4. Análise Reológica
   # Selecione arquivo JSON gerado
   # Aguarde ajuste de modelos
   ```

3. **Visualizar:**
   ```bash
   # Escolha: 7. Visualizar Resultados
   # Veja gráficos interativos
   ```

---

## 📖 **Descrição dos Scripts**

### **🔵 Coleta e Pré-Processamento**

#### **Script 1: Controle do Reômetro**
- **Função:** Interface com Arduino para coleta de dados
- **Features:**
  - ✅ Dual sensor (Pressão Linha & Pasta)
  - ✅ Calibração independente de sensores
  - ✅ Diagnóstico Delta P em tempo real
  - ✅ Monitor de pressão ao vivo
  - ✅ Continuação de ensaios
- **Entrada:** Comandos do usuário + Arduino serial
- **Saída:** `[amostra]_[timestamp].json`

#### **Script 1a: Editar JSON**
- **Função:** Permite excluir pontos inválidos manualmente
- **Features:**
  - ✅ Exibe tabela completa (P.Linha, P.Pasta, Massa, Tempo)
  - ✅ Exclusão seletiva de pontos
  - ✅ Renumeração automática
- **Entrada:** JSON bruto
- **Saída:** `edit_[arquivo].json`

#### **Script 1b: Pré-Análise**
- **Função:** Processa dados brutos em formato final
- **Features:**
  - ✅ Cálculos reológicos básicos (τ, γ̇, η)
  - ✅ Seleção de fonte de pressão (Linha ou Pasta)
  - ✅ Geração de CSV e JSON final
- **Entrada:** JSON bruto ou editado
- **Saída:** CSV + JSON processados

---

### **🟢 Análise e Modelagem**

#### **Script 2: Análise Reológica**
- **Função:** Análise completa com ajuste de modelos
- **Modelos Suportados:**
  - Newtoniano
  - Lei da Potência (Power Law)
  - Bingham
  - Herschel-Bulkley
  - Casson
- **Correções:**
  - ✅ Bagley (múltiplos L/R)
  - ✅ Mooney (múltiplos diâmetros)
  - ✅ Aplicação de calibrações salvas
- **Gráficos Gerados:**
  1. Curva de fluxo (τ vs γ̇)
  2. n' vs γ̇
  3. Viscosidade vs γ̇
  4. Pressão vs Viscosidade 
  5. Comparativo aparente vs real 
- **Saída:** 
  - CSV com resultados
  - JSON com parâmetros dos modelos
  - Gráficos PNG
  - Relatório TXT completo

#### **Script 2c: Filtro por Resíduos**
- **Função:** Remove outliers baseado em análise de resíduos
- **Features:**
  - ✅ Cálculo automático de resíduos
  - ✅ Limite configurável (multiplicador σ)
  - ✅ Iterativo: visualiza antes de confirmar
  - ✅ Detecção automática de JSON bruto
- **Entrada:** Sessão de análise do Script 2
- **Saída:** `residuos_[arquivo].json` (limpo)

#### **Script 2b: Tratamento Estatístico**
- **Função:** Calcula média e desvio padrão de múltiplos ensaios
- **Features:**
  - ✅ Agrupa ensaios da mesma amostra
  - ✅ Estatísticas completas (média, STD, CV)
  - ✅ Exportação CSV
- **Entrada:** Múltiplos CSVs do Script 2
- **Saída:** CSV com estatísticas

---

### **🟡 Visualização e Comparação**

#### **Script 3: Visualizar Resultados**
- **Função:** Visualização rápida de gráficos
- **Features:**
  - ✅ Suporte a dados individuais e estatísticos
  - ✅ Todos os modelos plotados
  - ✅ Gráficos interativos (zoom, pan)
- **Entrada:** Sessão de análise
- **Saída:** Janelas gráficas

#### **Script 4: Comparativo de Análises**
- **Função:** Compara múltiplas análises (capilar vs rotacional)
- **Features:**
  - ✅ Comparação de N análises
  - ✅ Cálculo de Fcal (fator de calibração)
  - ✅ Análise de discrepância (MAPE)
  - ✅ Média interpolada
  - ✅ Nome personalizado para saída
  - ✅ Relatórios compilados
- **Entrada:** Múltiplas sessões
- **Saída:** Pasta com gráficos + CSVs comparativos

---

### **🟣 Reômetro Rotacional**

#### **Script 5: Processador Rotacional**
- **Função:** Processa dados de reômetros rotacionais comerciais(Anton Paar, etc)
- **Features:**
  - ✅ Importação de formatos variados
  - ✅ Conversão para formato padrão
  - ✅ Integração com Script 4
- **Entrada:** Arquivo de reômetro rotacional
- **Saída:** CSV padronizado

---

## ⚙️ **Configurações Importantes**

### **Fator de Calibração Empírico (Script 2)**
Localização: `2.Analise_reologica.py` - **Linha 34**
```python
FATOR_CALIBRACAO_EMPIRICO_PADRAO = 1.0
```
Altere este valor para aplicar correção global em todos os ensaios.

### **Limites de Diagnóstico Delta P (Script 1)**
Localização: `1.Controle_Reometro.py` - **Linha 23**
```python
DELTA_P_ALERTA_BAR = 2.0  # Alerta se |P.Linha - P.Pasta| > 2 bar
```

---

## 🐛 **Solução de Problemas**

### **Erro: "Arduino não detectado"**
**Solução:**
1. Verifique se Arduino está conectado via USB
2. Confirme porta COM no Gerenciador de Dispositivos (Windows)
3. Teste com: `python -m serial.tools.list_ports`
4. Ajuste porta no Script 1 se necessário

### **Erro: "ModuleNotFoundError"**
**Solução:**
```bash
# Reinstale todas as dependências
pip install --upgrade numpy pandas matplotlib scipy pyserial scikit-learn
```

### **Gráficos não aparecem**
**Solução:**
1. Verifique backend do matplotlib:
   ```python
   import matplotlib
   print(matplotlib.get_backend())
   ```
2. Se necessário, altere para `TkAgg` ou `Qt5Agg`

### **Script 2c não encontra JSON automaticamente**
**Solução:**
- Isso é esperado se o nome da sessão não corresponde ao JSON original
- Basta **selecionar manualmente** o JSON correto na lista
- Para evitar: use nomes originais ao executar Script 2

### **Pressão negativa detectada**
**Solução:**
1. Verifique conexão dos sensores
2. Recalibre os sensores (Script 1, Opção 3)
3. Confirme que Arduino está com firmware v3.0+

---

## 📊 **Dados de Teste**

Um arquivo de teste dual sensor está incluído:
```
resultados_testes_reometro/TESTE_DUAL_40Cap1_20251122.json
```

Use-o para testar o sistema completo sem hardware conectado.

---

## 🔄 **Atualizações Recentes (v4.0)**

### ⭐ Novas Funcionalidades:
- ✅ **Interface Gráfica (GUI)** - CustomTkinter moderno
- ✅ **Banco SQLite** - Persistência local de dados
- ✅ **Calibração Inteligente** - Sensor Pasta como referência
- ✅ **5 Modelos Reológicos** - Com ajuste automático e R²
- ✅ **21 Testes Unitários** - pytest para validação
- ✅ **Documentação de Fórmulas** - Docstrings completas
- ✅ **Relatórios PDF** - Exportação profissional
- ✅ **Tratamento de Erros** - Desconexão Arduino

### v3.1 (Novembro 2025):
- Dual Sensor Completo (Linha & Pasta)
- Diagnóstico Delta P em tempo real
- Gráficos com Modelo

---

## 📝 **Licença e Contato**

**Desenvolvido por:** Bruno Egami  
**Versão:** 4.0  
**Última Atualização:** Fevereiro 2026

Para reportar bugs ou sugerir melhorias, entre em contato ou abra uma issue no repositório.

---

## ⭐ **Dicas Rápidas**

### **Atalhos Úteis:**
- Pressione `Ctrl+C` para interromper qualquer script
- Use `0. Sair` no Launcher para fechar sistema
- Arquivos JSON podem ser editados manualmente em emergências

### **Boas Práticas:**
1. **Sempre calibre** sensores antes de coletar dados
2. **Nomeie amostras** de forma descritiva
3. **Faça backup** de dados importantes
4. **Revise dados** com Script 1a antes de analisar
5. **Use mesmo nome** do JSON ao executar Script 2 (facilita Script 2c)

---

**Sistema Pronto para Uso! Execute `python 0.Launcher.py` para começar.** 🚀
