import unittest
import time
import threading
from reometer_controller import MockReometerController

class TestReometerController(unittest.TestCase):
    def setUp(self):
        self.controller = MockReometerController()
        self.readings = []
        
    def tearDown(self):
        self.controller.disconnect()
        
    def on_pressure_callback(self, p1, p2, v1, v2):
        self.readings.append((p1, p2))

    def test_connection(self):
        success, msg = self.controller.find_and_connect()
        self.assertTrue(success)
        self.assertTrue(self.controller.is_connected)
        
    def test_reading_loop(self):
        # Connect
        self.controller.connect()
        
        # Setup callback
        self.controller.on_pressure_reading = self.on_pressure_callback
        
        # Start reading
        started = self.controller.start_reading()
        self.assertTrue(started)
        self.assertTrue(self.controller.is_reading)
        
        # Wait for some readings
        time.sleep(1.0)
        
        # Stop
        self.controller.stop_reading()
        self.assertFalse(self.controller.is_reading)
        
        # Verify we got data
        self.assertTrue(len(self.readings) > 0)
        print(f"Captured {len(self.readings)} readings.")
        
    def test_calibration_application(self):
        # Set a specific calibration: V=1 -> P=10
        # Slope = 10, Intercept = 0
        self.controller.load_calibration(10.0, 0.0, 10.0, 0.0)
        self.controller.calibration_loaded = True
        
        # Manually invoke hidden conversion method to test logic
        p_linha = self.controller._convert_voltage_to_pressure(1.0, 'linha')
        self.assertEqual(p_linha, 10.0)

if __name__ == '__main__':
    unittest.main()
