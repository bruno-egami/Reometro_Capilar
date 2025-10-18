
Reômetro-capilar
# Reômetro Capilar com Arduino e HX711

Este projeto tem como objetivo a construção de um reômetro capilar de baixo custo, utilizando um sistema de aquisição baseado em Arduino e o amplificador de carga HX711. O sistema permite a medição indireta da viscosidade de suspensões cerâmicas (barbotinas) a partir da vazão de escoamento sob pressão controlada.

## Visão Geral do Sistema

O sistema é composto por:

-   Um reometro feito de lata de alumínio (clindro pressurizado), um cilindro preenchido com a barbotina (tubo PVC DN50) e acessórios e conectores impressos;
-   Um conjunto de capilares;
-   Um manômetro e registro para controle de pressão aplicada;
-   Quatro extensômetros colados na lata para formar uma ponte de Wheatstone;
-   Um módulo HX711 para leitura de variações de tensão;
-   Um Arduino Pro Micro para captura da pressão aplicada;
-   Um conjunto de 3 scripts para: controle do reômetro, análise da reologia e visualização dos resultados.
    
## Para detalhes de funcionamento do script, consultar o [manual-script.pdf](https://github.com/bruno-egami/HX711-4xSG350/blob/Re%C3%B4metro-capilar/Manual-script.pdf) 

![IMG_20250606_171945](https://github.com/user-attachments/assets/cc85b93a-2951-4d13-8ee7-6c99c91f86a4)
![IMG_20250606_171950](https://github.com/user-attachments/assets/cbc964eb-d97a-4bdc-abda-90f719cd5c21)
![IMG_20250606_172243](https://github.com/user-attachments/assets/54ac21ec-ef49-402a-87b2-62799fe38bc8)
![IMG_20250606_172301](https://github.com/user-attachments/assets/a16172e3-aad1-4c6e-a952-342d01da55ca)


## Autor

- [@bruno-egami](https://github.com/bruno-egami)


## Licença


<p xmlns:cc="http://creativecommons.org/ns#" >This work is licensed under <a href="http://creativecommons.org/licenses/by-sa/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">CC BY-SA 4.0<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/sa.svg?ref=chooser-v1"></a></p>

