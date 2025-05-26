
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

-   Um script em pyton para análise da reologia
    

## Componentes Utilizados

-   **Arduino Pro Micro:** microcontrolador principal
    
-   **HX711:** amplificador de carga de alta precisão
    
-   **Strain Gauges (350 Ω):** sensores para medir a deformação do recipiente
   
-   **Lata de alumínio:** câmara de pressurização
    
-   **Capilar (3 mm x 10 mm):** bico extrusor
    
-   **Balança de precisão:** para aferir a massa extrudada
    
  

## Autor

- [@bruno-egami](https://github.com/bruno-egami)


## Licença


<p xmlns:cc="http://creativecommons.org/ns#" >This work is licensed under <a href="http://creativecommons.org/licenses/by-sa/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">CC BY-SA 4.0<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/sa.svg?ref=chooser-v1"></a></p>
