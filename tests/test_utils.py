import unittest
import os
import shutil
import numpy as np
from utils_reologia import format_float_for_table, CONSTANTS, selecionar_arquivo

class TestUtilsReologia(unittest.TestCase):
    def test_constants(self):
        self.assertIn('INPUT_BASE_FOLDER', CONSTANTS)
        self.assertIn('STATISTICAL_OUTPUT_FOLDER', CONSTANTS)

    def test_format_float(self):
        self.assertEqual(format_float_for_table(0.123456), "0.1235")
        self.assertEqual(format_float_for_table(1e-5), "1e-05")
        self.assertEqual(format_float_for_table(np.nan), "NaN")

    # Não vamos testar selecionar_arquivo interativamente aqui, apenas a importação e existência
    def test_selecionar_arquivo_exists(self):
        self.assertTrue(callable(selecionar_arquivo))

if __name__ == '__main__':
    unittest.main()
