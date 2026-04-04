import numpy as np
import unittest
from modelos_reologicos import MODELS, model_newtonian, model_power_law, model_bingham, model_hb, model_casson

class TestModelosReologicos(unittest.TestCase):
    def test_imports(self):
        self.assertIn("Newtoniano", MODELS)
        self.assertIn("Lei da Potência", MODELS)
        self.assertIn("Bingham", MODELS)
        self.assertIn("Herschel-Bulkley", MODELS)
        self.assertIn("Casson", MODELS)

    def test_newtonian(self):
        gd = np.array([1.0, 2.0, 3.0])
        eta = 2.0
        expected = eta * gd
        np.testing.assert_array_almost_equal(model_newtonian(gd, eta), expected)

    def test_power_law(self):
        gd = np.array([1.0, 2.0, 3.0])
        K = 2.0
        n = 0.5
        expected = K * np.power(gd, n)
        np.testing.assert_array_almost_equal(model_power_law(gd, K, n), expected)

    def test_bingham(self):
        gd = np.array([1.0, 2.0, 3.0])
        t0 = 1.0
        ep = 2.0
        expected = t0 + ep * gd
        np.testing.assert_array_almost_equal(model_bingham(gd, t0, ep), expected)

    def test_hb(self):
        gd = np.array([1.0, 2.0, 3.0])
        t0 = 1.0
        K = 2.0
        n = 0.5
        expected = t0 + K * np.power(gd, n)
        np.testing.assert_array_almost_equal(model_hb(gd, t0, K, n), expected)

    def test_casson(self):
        gd = np.array([1.0, 2.0, 3.0])
        tau0 = 1.0
        eta = 2.0
        expected = (np.sqrt(tau0) + np.sqrt(eta) * np.sqrt(gd))**2
        np.testing.assert_array_almost_equal(model_casson(gd, tau0, eta), expected)

if __name__ == '__main__':
    unittest.main()
