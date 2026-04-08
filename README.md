# 🔬 Sistema de Controle e Análise - Reômetro Capilar

Sistema para controle de reômetro capilar com **dois sensores de pressão** (Linha & Pasta), análise reológica, correções matemáticas e comparação de dados.

---

## 📋 **Índice**

1. [Requisitos](#requisitos)
2. [Instalação](#instalação)
3. [Como Executar](#como-executar)
4. [Funcionalidades](#funcionalidades)
5. [Estrutura do Projeto](#estrutura-do-projeto)
6. [Solução de Problemas](#solução-de-problemas)

---

## 🔧 **Requisitos**

### **Hardware**
- Arduino com Firmware v3.1 (dual sensor)
- 2x Sensores de pressão (Transdutor 1: Linha, Transdutor 2: Pasta)
- Balança de precisão
- Reômetro capilar com capilares intercambiáveis

### **Software**
- **Python:** 3.8 ou superior
- **Sistema Operacional:** Windows, Linux ou macOS

### **Dependências Python**

Instale todas as dependências necessárias listadas no `requirements.txt`:

```bash
pip install -r requirements.txt
```

As principais bibliotecas utilizadas são: `customtkinter`, `matplotlib`, `pandas`, `scipy`, `pyserial`, `scikit-learn`, `fpdf` e `Pillow`.

---

## 🚀 **Instalação**

### **1. Clone ou Baixe o Repositório**
```bash
git clone https://github.com/bruno-egami/Reometro_Capilar.git
cd Reometro_Capilar
```

### **2. Instale as Dependências**
```bash
pip install -r requirements.txt
```

### **3. Configure o Arduino**
- Conecte o módulo LM4040 ao pino Aref do Arduino
- Conecte os sensores de pressão:
    Sensor 1 (Pasta): Sinal -> A0, VCC -> 5V, GND -> GND
    Sensor 2 (Linha): Sinal -> A1, VCC -> 5V, GND -> GND
- Conecte o Arduino via USB
- Carregue o firmware v3.1 no Arduino

---

## 🖥️ **Como Executar**

O sistema possui uma **interface gráfica** construída com `customtkinter`. Para iniciar a aplicação:

```bash
python gui_main.py
```

> **Nota**: Se houver problemas com o Arduino, você pode desconectá-lo para testar a interface em modo de simulação (requer alteração no código para `MockController` se não conectar automaticamente).

---

## 🌟 **Funcionalidades**

A aplicação é dividida em módulos acessíveis pela barra lateral:

| Módulo | Funcionalidades |
|--------|-----------------|
| **Coleta** | Conexão com Arduino, gráfico de pressão em tempo real, coleta de pontos (Pressão/Tempo) e input de massa. |
| **Histórico** | Visualização de todas as amostras salvas no banco de dados SQLite (`reometria.db`). Permite importar dados legados (JSON). |
| **Calibração** | Assistente passo-a-passo para calibrar os sensores de pressão (Linha e Pasta). |
| **Análise** | Processamento reológico. Cálculo de tensão/taxa de cisalhamento real e aparente. Ajuste de 5 modelos reológicos (Newton, Power Law, Bingham, Herschel-Bulkley, Casson). Exportação de relatórios PDF. |
| **Correções** | Ferramentas para aplicação das correções de **Bagley** (efeitos de entrada) e **Mooney** (deslizamento na parede). |

### **Recursos Adicionais:**
- **Relatórios PDF**: Geração automática de relatórios com gráficos e estatísticas.
- **Análise Comparativa**: Compare múltiplas amostras em um único gráfico.
- **Limpeza de Dados**: Ferramenta visual para detecção e remoção de outliers.

---

## 📁 **Estrutura do Projeto**

O projeto foi refatorado para uma arquitetura modular:

```
Reometro_Capilar/
├── gui_main.py                      # Ponto de entrada da aplicação
├── gui/                             # Pacote da Interface Gráfica
│   ├── app.py                       # Classe principal da aplicação
│   ├── frames/                      # Paineis principais (Abas)
│   │   ├── coleta.py
│   │   ├── historico.py
│   │   ├── calibracao.py
│   │   ├── analise.py
│   │   └── correcoes.py
│   └── windows/                     # Janelas secundárias (Relatórios, Comparativos)
├── modelos_reologicos.py            # Definição matemática dos modelos
├── reologia_fitting.py              # Algoritmos de ajuste de curvas
├── reometer_controller.py           # Comunicação Serial com Arduino
├── database_manager.py              # Gerenciamento do SQLite
├── utils_reologia.py                # Funções utilitárias gerais
├── requirements.txt                 # Lista de dependências
└── reometria.db                     # Banco de dados (criado automaticamente)
```

---

## 🐛 **Solução de Problemas**

### **Erro: "Arduino não detectado"**
1. Verifique se o cabo USB está conectado.
2. Confirme se os drivers do Arduino estão instalados.
3. A aplicação busca automaticamente portas com "Arduino", "USB" ou "CH340" na descrição.

### **Gráficos não aparecem ou travam**
O sistema usa `matplotlib` integrado ao `tkinter`. Se houver problemas de renderização, verifique se a biblioteca `Pillow` está instalada corretamente.

### **⚠️ Calibração e Referência de Tensão (A-01)**

O Arduino Pro Micro usa a tensão USB (AVCC) como referência do ADC. A especificação USB 2.0 permite variação de **4,75 V a 5,25 V** dependendo da fonte (computador, hub, cabo), desta forma, foi utilizada uma referência de tensão externa de precisão (LM4040-4.1v) no pino AREF do Arduino.


--

## 📝 **Licença e Contato**

**Desenvolvido por:** Bruno Egami  
**Versão:** 4.1.1 (Refatorada)  
**Última Atualização:** Abril 2026
