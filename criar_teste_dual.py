#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script temporário para criar arquivo de teste dual sensor
"""

import json
import os

# Lê o arquivo original
origem = 'resultados_testes_reometro/40Cap1_20251026_201152.json'
destino = 'resultados_testes_reometro/TESTE_DUAL_40Cap1_20251122.json'

print(f"Lendo: {origem}")

with open(origem, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total de testes no arquivo original: {len(data.get('testes', []))}")

# Percorre cada teste e duplica a pressão
for teste in data.get('testes', []):
    # Pega a pressão existente
    pressao_original = teste.get('media_pressao_final_ponto_bar', 0.0)
    
    # Cria os novos campos dual sensor com o mesmo valor
    teste['media_pressao_linha_bar'] = pressao_original
    teste['media_pressao_pasta_bar'] = pressao_original
    
    # Adiciona tensões fictícias (baseadas na pressão)
    # Assumindo calibração aproximada de 1bar = 0.004V (250 bar/V)
    teste['media_tensao_linha_V'] = pressao_original * 0.004
    teste['media_tensao_pasta_V'] = pressao_original * 0.004

# Adiciona informação de calibração dual (valores coerentes com a conversão)
data['calibracao_aplicada'] = {
    'linha': {'slope': 250.0, 'intercept': 0.0},
    'pasta': {'slope': 250.0, 'intercept': 0.0},
    'data': '2025-11-22'
}

# Atualiza informações do ensaio
data['id_amostra'] = 'TESTE_DUAL_40Cap1'
data['descricao'] = 'Arquivo de teste com dados dual sensor (Linha=Pasta)'

# Salva novo arquivo
with open(destino, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print(f"\n✓ Arquivo de teste criado: {destino}")
print(f"✓ Total de pontos: {len(data.get('testes', []))}")
print(f"✓ Dual sensor: Linha e Pasta com valores idênticos")
print(f"\nVocê pode usar este arquivo no Script 2 para testar!")
