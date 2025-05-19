# Reômetro capilar utilizando módulo HX711 + 4xSG350
Sistema para análise de reologia de pastas utilizando uma lata de alumínio, um módulo HX711 e 4 Strain Gauges de 350ohm.

Exemplo de interação:

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

>>> Resultados calculados:
Pressão (bar) | Massa (g) | Volume (cm³) | Vazão (cm³/s) | Taxa de Cisalhamento (1/s) | Viscosidade (Pa.s)
-------------------------------------------------------------------------------------------------------------
1             | 2.7       | 1.54         | 0.15          | 424.4                       | 68.1
2             | 8.1       | 4.63         | 0.46          | 424.4                       | 43.5
(...)

Fim dos testes.

