
# Reômetro Capilar com Arduino e HX711

Este projeto tem como objetivo a construção de um reômetro capilar de baixo custo, utilizando um sistema de aquisição baseado em Arduino e o amplificador de carga HX711. O sistema permite a medição indireta da viscosidade de suspensões cerâmicas (barbotinas) a partir da vazão de escoamento sob pressão controlada.

## Visão Geral do Sistema

O sistema é composto por:

-   Um cilindro (lata de alumínio) preenchido com a barbotina
    
-   Um bico extrusor capilar (diâmetro: 3 mm, comprimento: 10 mm)
    
-   Um manômetro para controle de pressão aplicada
    
-   Quatro extensômetros colados na lata para formar uma ponte de Wheatstone
    
-   Um módulo HX711 para leitura de variações de tensão
    
-   Um Arduino que processa os dados e calcula a viscosidade
    

## Componentes Utilizados

-   **Arduino Pro Micro:** microcontrolador principal
    
-   **HX711:** amplificador de carga de alta precisão
    
-   **Strain Gauges (350 Ω):** sensores para medir a deformação do recipiente
   
-   **Lata de alumínio:** câmara de pressurização
    
-   **Capilar (3 mm x 10 mm):** bico extrusor
    
-   **Balança de precisão:** para aferir a massa extrudada
    

## Funcionamento Geral

1.  O sistema é inicializado e passa por um tempo de "aquecimento" (estabilização).
    
2.  O usuário aplica uma pressão conhecida com base no manômetro (1 a 5 bar).
    
3.  A barbotina é extrudada por um bico capilar.
    
4.  Após um tempo definido (ex: 30 s), o sistema é pausado.
    
5.  O usuário informa a massa extrudada.
    
6.  A viscosidade é calculada automaticamente.
    

## Equações Utilizadas

A viscosidade é determinada pela equação de Hagen-Poiseuille:

```
η = (π * R^4 * ΔP) / (8 * Q * L)

```

Onde:

-   η = viscosidade (Pa.s)
    
-   R = raio do capilar (m)
    
-   ΔP = pressão aferida pelos extensômetros (Pa)
    
-   Q = vazão volumétrica (m³/s)
    
-   L = comprimento do capilar (m)
    

A vazão é obtida por:

```
Q = massa / (densidade * tempo)

```

## Variáveis do Código

-   `alpha`: fator de suavização do filtro EMA
    
-   `coeficiente`: fator de conversão mV/bar (calibrado experimentalmente)
    
-   `offset`: correção de leitura sem carga
    
-   `mvRead1`: leitura bruta do HX711 (em mV)
    
-   `ema_mvRead1`: leitura filtrada
    
-   `pressure_bar`: pressão convertida (em bar)
    
-   `density`: densidade fornecida pelo usuário (g/cm³)
    
-   `mass`: massa extrudada (g)
    
-   `eta`: viscosidade calculada (Pa.s)
    

## Exemplo de Saída
------ Sistema de Reômetro Capilar ------

Insira a densidade da barbotina (g/cm³): 1.75

Preparando teste com 5 pressões: 1, 2, 3, 4, 5 bar

Tempo de extrusão configurado: 10 segundos

>>> Pressurize o sistema para 1 bar.

Remova o excesso de barbotina do bico.

Teste iniciará em 3 segundos...

Iniciando extrusão...

Aguardando 10 segundos...

Teste finalizado para 1 bar.

Insira a massa extrudada (em gramas): 2.7

>>> Pressurize o sistema para 2 bar.

Remova o excesso de barbotina do bico.

Teste iniciará em 3 segundos...

Iniciando extrusão...

Aguardando 10 segundos...

Teste finalizado para 2 bar.

Insira a massa extrudada (em gramas): 8.1

(... repete até 5 bar ...)

>Resultados calculados: Pressão (bar) | Massa (g) | Volume (cm³) | Vazão (cm³/s) | Taxa de Cisalhamento (1/s) | Viscosidade (Pa.s)

1             | 2.7       | 1.54         | 0.15          | 424.4                       | 68.1

2             | 8.1       | 4.63         | 0.46          | 424.4                       | 43.5

(...)

>>Fim dos testes.

## Autor

- [@bruno-egami](https://github.com/bruno-egami)


## Licença


<p xmlns:cc="http://creativecommons.org/ns#" >This work is licensed under <a href="http://creativecommons.org/licenses/by-sa/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">CC BY-SA 4.0<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/sa.svg?ref=chooser-v1"></a></p>
