# HX711-4xSG350
Sistema de aquisição de dados para leitura de pressão em uma lata de alumínio utilizando um módulo HX711 e 4 Strain Gauges de 350ohm.

- O monitor serial apresenta leitura de pressão em PSI e Bar.
- No boot, foi configurado 1 min para establização do sistema, para pular clicar em enviar;

Ajustes possíveis para outras configurações:
- coeficiente: multiplicador para ajustes após regressão (ema_mvRead1 * coeficiente = pressão em bar);
- offset: ajuste de offset para pressão inicial diferente de 0;
- alpha: fator de suavização do filtro EMA;
- warmup_minutes: tempo de aquecimento, em minutos, para estabilização (utilizdo inicialmente para tentar reduzir a variação dos resistores fixos)

Obs: nos primeiros testes tentei utilizar resistores fixos de baixa precisão, em esquema de 1/4 e 1/2 de ponte de wheatstone, contudo a resistência dos mesmos variavam muito gerando ruídos e desbalanceamento da ponte dificultando a precisão dos dados. A solução encontrada foi montar um esquema de ponte completa, utilizando 4 Strain Gauges para montar a ponte.

## Autor

- [@bruno-egami](https://github.com/bruno-egami)


## Licença


<p xmlns:cc="http://creativecommons.org/ns#" >This work is licensed under <a href="http://creativecommons.org/licenses/by-sa/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">CC BY-SA 4.0<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/sa.svg?ref=chooser-v1"></a></p>
