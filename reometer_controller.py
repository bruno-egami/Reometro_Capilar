import serial
import serial.tools.list_ports
import time
import threading
import numpy as np
from typing import Optional, Callable, Tuple, Any

# Constants from original script
BAUD_RATE = 115200
TIMEOUT_SERIAL = 2

# Factory Calibration for Pasta Sensor (0 bar = 0.5V, 5 bar = 2.5V, 10 bar = 4.5V)
# Linear: P (bar) = 2.5 * V - 1.25
FACTORY_PASTA_SLOPE = 2.5  # bar/V
FACTORY_PASTA_INTERCEPT = -1.25  # bar

class ReometerController:
    """
    Controller class manages the serial communication with the Arduino for the Capillary Rheometer.
    It handles connection establishment, background data reading, and sensor calibration application.
    
    Attributes:
        ser (Optional[serial.Serial]): The serial connection object.
        is_connected (bool): Connection status flag.
        is_reading (bool): Data reading loop active flag.
        read_thread (Optional[threading.Thread]): Background thread for data reading.
        on_pressure_reading (Optional[Callable]): Callback for new pressure data (p_linha, p_pasta, v1, v2).
        on_error (Optional[Callable]): Callback for error reporting.
    """
    def __init__(self) -> None:
        self.ser: Optional[serial.Serial] = None
        self.is_connected: bool = False
        self.is_reading: bool = False
        self.read_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_pressure_reading: Optional[Callable[[float, float, float, float], None]] = None 
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Calibration Parameters
        # Linha: user-calibrated
        self.calib_slope_linha: float = 1.0
        self.calib_intercept_linha: float = 0.0
        # Pasta: factory calibration (fixed)
        self.calib_slope_pasta: float = FACTORY_PASTA_SLOPE
        self.calib_intercept_pasta: float = FACTORY_PASTA_INTERCEPT
        self.calibration_loaded: bool = True  # Pasta is always calibrated

    def load_calibration_linha(self, slope_l: float, intercept_l: float) -> None:
        """Loads calibration parameters for Linha sensor only (Pasta uses factory)."""
        self.calib_slope_linha = slope_l
        self.calib_intercept_linha = intercept_l
        self.calibration_loaded = True
    
    def load_calibration(self, slope_l: float, intercept_l: float, slope_p: Optional[float] = None, intercept_p: Optional[float] = None) -> None:
        """
        Legacy method to load calibration parameters.
        Pasta parameters are ignored in this version as it uses factory calibration.
        """
        self.calib_slope_linha = slope_l
        self.calib_intercept_linha = intercept_l
        # Pasta is always factory calibrated, ignore provided values
        self.calibration_loaded = True

    def find_and_connect(self) -> Tuple[bool, str]:
        """
        Attempts to auto-connect to an Arduino device.
        Scans available COM ports for descriptions containing 'USB', 'ARDUINO', or 'CH340'.
        """
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Common Arduino descriptions/IDs
            if any(x in p.description.upper() for x in ["USB", "ARDUINO", "CH340"]):
                try:
                    return self.connect(p.device)
                except Exception:
                    continue
        return False, "Arduino não encontrado."

    def connect(self, port: str) -> Tuple[bool, str]:
        """
        Connects to a specific serial port.
        Performs a handshake ("PING" -> "ACK_PING_OK") to verify the device.
        """
        try:
            self.ser = serial.Serial(port, BAUD_RATE, timeout=TIMEOUT_SERIAL)
            time.sleep(2) # Wait for Arduino reset
            
            if self.ser.is_open:
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

    def disconnect(self) -> None:
        """Disconnects the serial port and stops the reading thread."""
        self.stop_reading()
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.is_connected = False
        self.ser = None

    def start_reading(self) -> bool:
        """
        Starts the background reading thread.
        Returns True if started successfully or already running.
        """
        if not self.is_connected or not self.ser:
            return False
            
        if self.is_reading:
            return True

        self.is_reading = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        return True

    def stop_reading(self) -> None:
        """Stops the background reading thread safely."""
        self.is_reading = False
        if self.read_thread:
            self.read_thread.join(timeout=1.0)
            self.read_thread = None

    def _read_loop(self) -> None:
        """
        Internal loop running in a background thread.
        continuously requests voltage readings from the Arduino (READ_VOLTAGE command).
        """
        while self.is_reading and self.ser and self.ser.is_open:
            try:
                # Command to request voltage
                self.ser.write(b"READ_VOLTAGE\n")
                self.ser.flush()
                
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

    def _convert_voltage_to_pressure(self, voltage: float, sensor_type: str) -> float:
        """Converts raw voltage to pressure (bar) using loaded calibration."""
        if not self.calibration_loaded:
            return 0.0
            
        if sensor_type == 'linha':
            p = (self.calib_slope_linha * voltage) + self.calib_intercept_linha
        else:
            p = (self.calib_slope_pasta * voltage) + self.calib_intercept_pasta
            
        return max(p, 0.0)

# Mock Controller for Testing without Hardware
class MockSerial:
    def isOpen(self) -> bool: return True
    def close(self) -> None: pass
    def flushInput(self) -> None: pass
    def flushOutput(self) -> None: pass
    def write(self, b: bytes) -> None: pass
    def readline(self) -> bytes: return b""
    @property
    def in_waiting(self) -> int: return 0

class MockReometerController(ReometerController):
    """Mock implementation of ReometerController for testing without physical hardware."""
    def connect(self, port: str = "MockPort") -> Tuple[bool, str]:
        self.is_connected = True
        self.ser = MockSerial() # type: ignore
        return True, "Conectado (Mock)"
        
    def find_and_connect(self) -> Tuple[bool, str]:
        return self.connect()

    def _read_loop(self) -> None:
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
    
    def print_pressure(p1: float, p2: float, v1: float, v2: float) -> None:
        print(f"L: {p1:.2f} bar | P: {p2:.2f} bar")
        
    controller.on_pressure_reading = print_pressure
    controller.load_calibration(100.0, 0, 100.0, 0)
    
    controller.start_reading()
    time.sleep(3)
    controller.stop_reading()
