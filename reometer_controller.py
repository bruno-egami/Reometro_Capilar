import serial
import serial.tools.list_ports
import time
import threading
import numpy as np

# Constants from original script
BAUD_RATE = 115200
TIMEOUT_SERIAL = 2

# Factory Calibration for Pasta Sensor (0 bar = 0.5V, 5 bar = 2.5V, 10 bar = 4.5V)
# Linear: P (bar) = 2.5 * V - 1.25
FACTORY_PASTA_SLOPE = 2.5  # bar/V
FACTORY_PASTA_INTERCEPT = -1.25  # bar

class ReometerController:
    def __init__(self):
        self.ser = None
        self.is_connected = False
        self.is_reading = False
        self.read_thread = None
        
        # Callbacks
        self.on_pressure_reading = None # func(p_linha, p_pasta)
        self.on_error = None # func(error_message)
        
        # Calibration Parameters
        # Linha: user-calibrated
        self.calib_slope_linha = 1.0
        self.calib_intercept_linha = 0.0
        # Pasta: factory calibration (fixed)
        self.calib_slope_pasta = FACTORY_PASTA_SLOPE
        self.calib_intercept_pasta = FACTORY_PASTA_INTERCEPT
        self.calibration_loaded = True  # Pasta is always calibrated

    def load_calibration_linha(self, slope_l, intercept_l):
        """Loads calibration parameters for Linha sensor only (Pasta uses factory)."""
        self.calib_slope_linha = slope_l
        self.calib_intercept_linha = intercept_l
        self.calibration_loaded = True
    
    def load_calibration(self, slope_l, intercept_l, slope_p=None, intercept_p=None):
        """Legacy: Loads calibration parameters. Pasta params are ignored (factory)."""
        self.calib_slope_linha = slope_l
        self.calib_intercept_linha = intercept_l
        # Pasta is always factory calibrated, ignore provided values
        self.calibration_loaded = True

    def find_and_connect(self):
        """Attempts to auto-connect to Arduino."""
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Common Arduino descriptions/IDs
            if any(x in p.description.upper() for x in ["USB", "ARDUINO", "CH340"]):
                try:
                    return self.connect(p.device)
                except Exception:
                    continue
        return False, "Arduino não encontrado."

    def connect(self, port):
        """Connects to a specific port."""
        try:
            self.ser = serial.Serial(port, BAUD_RATE, timeout=TIMEOUT_SERIAL)
            time.sleep(2) # Wait for Arduino reset
            
            if self.ser.isOpen():
                self.ser.flushInput()
                self.ser.flushOutput()
                self.ser.write(b"PING\n")
                response = self.ser.readline().decode('utf-8', 'ignore').strip()
                
                if "ACK_PING_OK" in response:
                    self.is_connected = True
                    return True, f"Conectado em {port}"
                else:
                    self.disconnect()
                    return False, f"Falha no handshake com {port}."
        except Exception as e:
            return False, str(e)
        return False, "Erro desconhecido."

    def disconnect(self):
        """Disconnects serial port and stops reading."""
        self.stop_reading()
        if self.ser and self.ser.isOpen():
            self.ser.close()
        self.is_connected = False
        self.ser = None

    def start_reading(self):
        """Starts the background reading thread."""
        if not self.is_connected or not self.ser:
            return False
            
        if self.is_reading:
            return True

        self.is_reading = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        return True

    def stop_reading(self):
        """Stops the background reading thread."""
        self.is_reading = False
        if self.read_thread:
            self.read_thread.join(timeout=1.0)
            self.read_thread = None

    def _read_loop(self):
        """Internal loop running in a thread."""
        while self.is_reading and self.ser and self.ser.isOpen():
            try:
                # Command to request voltage
                self.ser.write(b"READ_VOLTAGE\n")
                self.ser.flush()
                
                # Simple non-blocking read line with timeout logic handling in serial
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', 'ignore').strip()
                    if not line: continue
                    
                    try:
                        # Format: "V1;V2" e.g. "0.004;0.002"
                        parts = line.split(';')
                        if len(parts) == 2:
                            v1 = float(parts[0])
                            v2 = float(parts[1])
                            
                            # Apply calibration
                            p_linha = self._convert_voltage_to_pressure(v1, 'linha')
                            p_pasta = self._convert_voltage_to_pressure(v2, 'pasta')
                            
                            # Emit callback
                            if self.on_pressure_reading:
                                self.on_pressure_reading(p_linha, p_pasta, v1, v2)
                    except ValueError:
                        pass
                
                time.sleep(0.1) # Approx 10Hz sampling rate
            except Exception as e:
                if self.on_error:
                    self.on_error(str(e))
                self.stop_reading()
                break

    def _convert_voltage_to_pressure(self, voltage, sensor_type):
        """Converts voltage to pressure using loaded calibration."""
        if not self.calibration_loaded:
            return 0.0
            
        if sensor_type == 'linha':
            p = (self.calib_slope_linha * voltage) + self.calib_intercept_linha
        else:
            p = (self.calib_slope_pasta * voltage) + self.calib_intercept_pasta
            
        return max(p, 0.0)

# Mock Controller for Testing without Hardware
class MockSerial:
    def isOpen(self): return True
    def close(self): pass
    def flushInput(self): pass
    def flushOutput(self): pass
    def write(self, b): pass
    def readline(self): return b""
    @property
    def in_waiting(self): return 0

class MockReometerController(ReometerController):
    def connect(self, port="MockPort"):
        self.is_connected = True
        self.ser = MockSerial()
        return True, "Conectado (Mock)"
        
    def find_and_connect(self):
        return self.connect()

    def _read_loop(self):
        t = 0
        while self.is_reading:
            # Generate fake sine wave pressure
            import math
            p_linha = 5.0 + 2.0 * math.sin(t * 0.1)
            p_pasta = 4.8 + 1.9 * math.sin(t * 0.1)
            v1 = (p_linha - self.calib_intercept_linha) / self.calib_slope_linha if self.calib_slope_linha else 0
            v2 = (p_pasta - self.calib_intercept_pasta) / self.calib_slope_pasta if self.calib_slope_pasta else 0
            
            if self.on_pressure_reading:
                self.on_pressure_reading(p_linha, p_pasta, v1, v2)
            
            time.sleep(0.1)
            t += 1

if __name__ == "__main__":
    # Test Mock Controller
    controller = MockReometerController()
    success, msg = controller.connect()
    print(msg)
    
    def print_pressure(p1, p2, v1, v2):
        print(f"L: {p1:.2f} bar | P: {p2:.2f} bar")
        
    controller.on_pressure_reading = print_pressure
    controller.load_calibration(100.0, 0, 100.0, 0)
    
    controller.start_reading()
    time.sleep(3)
    controller.stop_reading()
