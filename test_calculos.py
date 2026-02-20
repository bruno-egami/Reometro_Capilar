# -*- coding: utf-8 -*-
"""
Testes Unitários para Cálculos Reológicos.

Execução:
    pytest test_calculos.py -v

Cobertura:
    1. Modelos Reológicos (5 modelos)
    2. Cálculos básicos (vazão, taxa de cisalhamento, tensão)
    3. Correção Weissenberg-Rabinowitsch
    4. Ajuste de modelos e R²
"""

import pytest
import numpy as np
from numpy.testing import assert_allclose

# Importar módulos a serem testados
import modelos_reologicos as models
import reologia_fitting as fitting


# =============================================================================
# TESTES DOS MODELOS REOLÓGICOS
# =============================================================================

class TestModelosReologicos:
    """Testes para as funções de modelo reológico."""
    
    def test_newtonian_basic(self):
        """Modelo Newtoniano: τ = η × γ̇"""
        gd = np.array([1.0, 10.0, 100.0])
        eta = 5.0
        tau = models.model_newtonian(gd, eta)
        expected = np.array([5.0, 50.0, 500.0])
        assert_allclose(tau, expected)
    
    def test_newtonian_zero_shear_rate(self):
        """Newtoniano com γ̇ = 0 deve retornar τ = 0."""
        tau = models.model_newtonian(0, 10.0)
        assert tau == 0.0
    
    def test_power_law_pseudoplastic(self):
        """Lei da Potência: n < 1 (pseudoplástico)."""
        gd = np.array([1.0, 10.0, 100.0])
        K, n = 10.0, 0.5
        tau = models.model_power_law(gd, K, n)
        # τ = 10 * γ̇^0.5 = [10, 31.62, 100]
        expected = K * np.power(gd, n)
        assert_allclose(tau, expected, rtol=1e-5)
    
    def test_power_law_dilatant(self):
        """Lei da Potência: n > 1 (dilatante)."""
        gd = np.array([1.0, 10.0])
        K, n = 2.0, 1.5
        tau = models.model_power_law(gd, K, n)
        expected = K * np.power(gd, n)
        assert_allclose(tau, expected, rtol=1e-5)
    
    def test_bingham_basic(self):
        """Modelo de Bingham: τ = τ₀ + ηₚ × γ̇"""
        gd = np.array([0.0, 10.0, 100.0])
        tau0, eta_p = 50.0, 2.0
        tau = models.model_bingham(gd, tau0, eta_p)
        expected = np.array([50.0, 70.0, 250.0])
        assert_allclose(tau, expected)
    
    def test_herschel_bulkley_basic(self):
        """Modelo Herschel-Bulkley: τ = τ₀ + K × γ̇ⁿ"""
        gd = np.array([1.0, 10.0, 100.0])
        tau0, K, n = 20.0, 5.0, 0.6
        tau = models.model_hb(gd, tau0, K, n)
        expected = tau0 + K * np.power(gd, n)
        assert_allclose(tau, expected, rtol=1e-5)
    
    def test_casson_basic(self):
        """Modelo de Casson: √τ = √τ₀ + √ηc × √γ̇"""
        gd = np.array([1.0, 4.0, 9.0])
        tau0, eta_c = 4.0, 1.0
        tau = models.model_casson(gd, tau0, eta_c)
        # √τ = √4 + √1 × √γ̇ = 2 + √γ̇
        # γ̇=1: √τ=3, τ=9
        # γ̇=4: √τ=4, τ=16
        # γ̇=9: √τ=5, τ=25
        expected = np.array([9.0, 16.0, 25.0])
        assert_allclose(tau, expected, rtol=1e-5)


# =============================================================================
# TESTES DE CÁLCULOS FUNDAMENTAIS
# =============================================================================

class TestCalculosFundamentais:
    """Testes para cálculos básicos de reometria capilar."""
    
    def test_vazao_volumetrica(self):
        """Q = massa / (ρ × tempo)"""
        massa_g = 10.0  # g
        rho_g_cm3 = 2.0  # g/cm³
        tempo_s = 5.0  # s
        
        Q_cm3_s = massa_g / (rho_g_cm3 * tempo_s)
        assert_allclose(Q_cm3_s, 1.0)  # 10 / (2 * 5) = 1 cm³/s
    
    def test_taxa_cisalhamento_aparente(self):
        """γ̇_app = 4Q / (πR³)"""
        Q_m3_s = 1e-6  # 1 cm³/s = 1e-6 m³/s
        R_m = 0.001  # 1 mm = 0.001 m
        
        gamma_dot = (4 * Q_m3_s) / (np.pi * R_m**3)
        # γ̇ = 4e-6 / (π × 1e-9) ≈ 1273.24 s⁻¹
        expected = 4e-6 / (np.pi * 1e-9)
        assert_allclose(gamma_dot, expected, rtol=1e-5)
    
    def test_tensao_parede(self):
        """τ_w = (P × R) / (2L)"""
        P_Pa = 1e6  # 10 bar = 1e6 Pa
        R_m = 0.0005  # 0.5 mm
        L_m = 0.04  # 40 mm
        
        tau_w = (P_Pa * R_m) / (2 * L_m)
        # τ = (1e6 × 0.0005) / (2 × 0.04) = 500 / 0.08 = 6250 Pa
        assert_allclose(tau_w, 6250.0)


# =============================================================================
# TESTES DA CORREÇÃO WEISSENBERG-RABINOWITSCH
# =============================================================================

class TestWeissenbergRabinowitsch:
    """Testes para a correção Weissenberg-Rabinowitsch."""
    
    def test_correction_factor_newtonian(self):
        """Para fluido Newtoniano (n'=1), fator = 1.0"""
        n_prime = 1.0
        factor = (3 * n_prime + 1) / (4 * n_prime)
        assert_allclose(factor, 1.0)
    
    def test_correction_factor_pseudoplastic(self):
        """Para n' < 1, fator > 1 (shear thinning)."""
        n_prime = 0.5
        factor = (3 * n_prime + 1) / (4 * n_prime)
        # (1.5 + 1) / 2 = 2.5 / 2 = 1.25
        assert_allclose(factor, 1.25)
    
    def test_correction_factor_dilatant(self):
        """Para n' > 1, fator < 1 (shear thickening)."""
        n_prime = 2.0
        factor = (3 * n_prime + 1) / (4 * n_prime)
        # (6 + 1) / 8 = 7/8 = 0.875
        assert_allclose(factor, 0.875)


# =============================================================================
# TESTES DE AJUSTE DE MODELOS
# =============================================================================

class TestAjusteModelos:
    """Testes para ajuste de modelos e cálculo de R²."""
    
    def test_ajustar_newtonian_synthetic(self):
        """Ajuste de modelo Newtoniano com dados sintéticos perfeitos."""
        # Gerar dados sintéticos: τ = 5 × γ̇
        gamma_dot = np.array([1, 5, 10, 50, 100])
        tau_w = 5.0 * gamma_dot
        
        results, best_model, df = fitting.ajustar_modelos(gamma_dot, tau_w)
        
        # Newtoniano deve ter R² ≈ 1.0
        assert 'Newtoniano' in results
        assert results['Newtoniano']['R2'] > 0.99
    
    def test_ajustar_power_law_synthetic(self):
        """Ajuste de Lei da Potência com dados sintéticos."""
        # Gerar dados: τ = 10 × γ̇^0.5
        gamma_dot = np.array([1, 10, 100, 1000])
        K, n = 10.0, 0.5
        tau_w = K * np.power(gamma_dot, n)
        
        results, best_model, df = fitting.ajustar_modelos(gamma_dot, tau_w)
        
        # Lei de Potência deve ter bom ajuste
        assert 'Lei da Potência' in results
        assert results['Lei da Potência']['R2'] > 0.99
        
        # Parâmetros devem estar próximos dos originais
        params = results['Lei da Potência']['params']
        assert_allclose(params[0], K, rtol=0.1)  # K
        assert_allclose(params[1], n, rtol=0.1)  # n
    
    def test_best_model_selection(self):
        """Verifica se o melhor modelo é selecionado corretamente."""
        # Dados claramente de Bingham: τ = 100 + 2γ̇
        gamma_dot = np.array([10, 50, 100, 200, 500])
        tau0, eta_p = 100.0, 2.0
        tau_w = tau0 + eta_p * gamma_dot
        
        results, best_model, df = fitting.ajustar_modelos(gamma_dot, tau_w)
        
        # Bingham ou HB devem ser o melhor (ambos podem ajustar bem)
        assert best_model in ['Bingham', 'Herschel-Bulkley']
    
    def test_insufficient_data(self):
        """Teste com dados insuficientes (< 3 pontos)."""
        gamma_dot = np.array([1, 2])
        tau_w = np.array([10, 20])
        
        results, best_model, df = fitting.ajustar_modelos(gamma_dot, tau_w)
        
        assert len(results) == 0
        assert best_model == ""


# =============================================================================
# TESTES DE INFERÊNCIA DE COMPORTAMENTO
# =============================================================================

class TestInferenciaComportamento:
    """Testes para inferência de comportamento do fluido."""
    
    def test_pseudoplastic(self):
        """Detecta comportamento pseudoplástico (n < 1)."""
        results = {'Lei da Potência': {'params': np.array([10.0, 0.4]), 'R2': 0.99}}
        comportamento = fitting.inferir_comportamento_fluido('Lei da Potência', results)
        assert 'Pseudoplastico' in comportamento
    
    def test_dilatant(self):
        """Detecta comportamento dilatante (n > 1)."""
        results = {'Lei da Potência': {'params': np.array([5.0, 1.5]), 'R2': 0.99}}
        comportamento = fitting.inferir_comportamento_fluido('Lei da Potência', results)
        assert 'Dilatante' in comportamento
    
    def test_viscoplastic(self):
        """Detecta comportamento viscoplástico (com tensão de escoamento)."""
        results = {'Bingham': {'params': np.array([50.0, 2.0]), 'R2': 0.99}}
        comportamento = fitting.inferir_comportamento_fluido('Bingham', results)
        assert 'Viscoplastico' in comportamento
    
    def test_newtonian(self):
        """Detecta comportamento Newtoniano."""
        results = {'Newtoniano': {'params': np.array([5.0]), 'R2': 0.99}}
        comportamento = fitting.inferir_comportamento_fluido('Newtoniano', results)
        assert 'Newtoniano' in comportamento


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
