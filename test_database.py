import unittest
import os
import sqlite3
from database_manager import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        # Use an in-memory database for testing
        self.db_name = "test_reometria.db"
        self.db = DatabaseManager(self.db_name)

    def tearDown(self):
        self.db.close()
        # Ensure connection is truly closed by Python garbage collector or explicit delete
        del self.db
        if os.path.exists(self.db_name):
            try:
                os.remove(self.db_name)
            except PermissionError:
                pass # Ignore if still locked, not critical for test logic

    def test_add_get_amostra(self):
        amostra_id = self.db.add_amostra("Sample A", "Desc A", 1.0, 40.0, 1.2)
        self.assertIsNotNone(amostra_id)
        
        amostra = self.db.get_amostra_by_name("Sample A")
        self.assertIsNotNone(amostra)
        self.assertEqual(amostra["nome"], "Sample A")
        self.assertEqual(amostra["d_capilar_mm"], 1.0)

    def test_add_duplicate_amostra(self):
        self.db.add_amostra("Sample B", "Desc B", 1.0, 40.0, 1.2)
        amostra_id_2 = self.db.add_amostra("Sample B", "Desc B", 1.0, 40.0, 1.2)
        self.assertIsNone(amostra_id_2) # Should fail due to UNIQUE constraint

    def test_add_ensaio(self):
        amostra_id = self.db.add_amostra("Sample C", "Desc C", 1.0, 40.0, 1.2)
        self.db.add_ensaio(amostra_id, 1, 10.0, 9.0, 5.0, 30.0, 0.5, 0.45)
        
        df = self.db.get_ensaios_by_amostra(amostra_id)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["pressao_linha_bar"], 10.0)

    def test_add_calibracao(self):
        calib_id = self.db.add_calibracao(1.0, 0.0, 1.0, 0.0)
        self.assertIsNotNone(calib_id)
        
        latest = self.db.get_latest_calibracao()
        self.assertEqual(latest["id"], calib_id)

    def test_origem_default_capilar(self):
        """N-01: Samples created via add_amostra default to origem='capilar'."""
        amostra_id = self.db.add_amostra("Sample_Origem", "Test origem", 1.0, 40.0, 1.2)
        self.assertIsNotNone(amostra_id)
        
        amostra = self.db.get_amostra_by_name("Sample_Origem")
        self.assertEqual(amostra['origem'], 'capilar')

    def test_origem_in_list_amostras(self):
        """N-01: list_amostras returns the 'origem' field."""
        self.db.add_amostra("Sample_List", "Test list", 1.0, 40.0, 1.2)
        amostras = self.db.list_amostras()
        self.assertTrue(len(amostras) > 0)
        self.assertIn('origem', amostras[0])

if __name__ == '__main__':
    unittest.main()
