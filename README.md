# 🔬 Sistema de Controle e Análise - Reômetro Capilar

Sistema completo para controle de reômetro capilar com **dois sensores de pressão** (Linha & Pasta), análise reológica, correções de Bagley e Mooney, e comparação de dados.

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
- Carregue o firmware v3.1 no Arduino
- Conecte os sensores de pressão
- Conecte o Arduino via USB

---

## 🖥️ **Como Executar**

O sistema possui uma **interface gráfica moderna** construída com `customtkinter`. Para iniciar a aplicação:

```bash
python gui_main.py
```

> **Nota**: Se houver problemas com o Arduino, você pode desconectá-lo para testar a interface em modo de simulação (requer alteração no código para `MockController` se não conectar automaticamente).

---

## 🌟 **Funcionalidades**

A aplicação é dividida em módulos acessíveis pela barra lateral:

| Módulo | Funcionalidades |
|--------|-----------------|
| **Coleta** | Conexão com Arduino, gráfico em tempo real, coleta de pontos (Pressão/Tempo) e input de massa. |
| **Histórico** | Visualização de todas as amostras salvas no banco de dados SQLite (`reometria.db`). Permite importar dados legados (JSON). |
| **Calibração** | Assistente passo-a-passo para calibrar os sensores de pressão (Linha e Pasta). |
| **Análise** | Processamento reológico completo. Cálculo de tensão/taxa real e aparente. Ajuste de 5 modelos reológicos (Newton, Power Law, Bingham, Herschel-Bulkley, Casson). Exportação de relatórios PDF. |
| **Correções** | Ferramentas avançadas para aplicação das correções de **Bagley** (efeitos de entrada) e **Mooney** (deslizamento na parede). |

### **Recursos Adicionais:**
- **Relatórios PDF Profissionais**: Geração automática de relatórios detalhados com gráficos e estatísticas.
- **Análise Comparativa**: Compare múltiplas amostras (inclusive dados externos de reômetros rotacionais) em um único gráfico.
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
├── legacy/                          # Scripts antigos (versões CLI anteriores)
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

O Arduino Pro Micro usa a tensão USB (AVCC) como referência do ADC. A especificação USB 2.0 permite variação de **4,75 V a 5,25 V** dependendo da fonte (computador, hub, cabo). Isso pode introduzir erro de até **±6,7%** na pressão calculada se a calibração e a medição forem feitas em condições USB diferentes.

**Recomendações:**
- **Sempre calibre os sensores na mesma sessão de medição** (mesmo computador, mesma porta USB, mesmo cabo).
- Não mude de porta USB ou computador entre a calibração e os ensaios.
- Para máxima precisão (ex.: publicação científica), considere instalar uma referência de tensão externa de precisão (LM4040-5.0, ~R$5) no pino AREF do Pro Micro.

---

## 📝 **Licença e Contato**

**Desenvolvido por:** Bruno Egami  
**Versão:** 4.1.1 (Refatorada)  
**Última Atualização:** Abril 2026
