
import serial
import serial.tools.list_ports
import time
import threading
import math
import logging
from logger_config import logger
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
        self._on_pressure_reading: Optional[Callable[[float, float, float, float], None]] = None 
        self.on_error: Optional[Callable[[str], None]] = None
        self._callback_lock = threading.Lock()
        
        # Calibration Parameters
        # Linha: user-calibrated
        self.calib_slope_linha: float = 1.0
        self.calib_intercept_linha: float = 0.0
        # Pasta: factory calibration (fixed)
        self.calib_slope_pasta: float = FACTORY_PASTA_SLOPE
        self.calib_intercept_pasta: float = FACTORY_PASTA_INTERCEPT
        self.calibration_loaded: bool = True  # Pasta is always calibrated
        self.linha_calibrada: bool = False  # C11: aviso até sensor Linha ser calibrado
        
    @property
    def on_pressure_reading(self) -> Optional[Callable[[float, float, float, float], None]]:
        with self._callback_lock:
            return self._on_pressure_reading
            
    @on_pressure_reading.setter
    def on_pressure_reading(self, callback: Optional[Callable[[float, float, float, float], None]]):
        with self._callback_lock:
            self._on_pressure_reading = callback
        
    def log_message(self, msg: str, level: int = logging.INFO) -> None:
        """Centralized logging for the controller."""
        if level == logging.ERROR:
            logger.error(f"[ReometerController] {msg}")
        elif level == logging.WARNING:
            logger.warning(f"[ReometerController] {msg}")
        else:
            logger.info(f"[ReometerController] {msg}")

    def load_calibration_linha(self, slope_l: float, intercept_l: float) -> None:
        """Loads calibration parameters for Linha sensor only (Pasta uses factory)."""
        self.calib_slope_linha = slope_l
        self.calib_intercept_linha = intercept_l
        self.calibration_loaded = True
        self.linha_calibrada = True
        self.log_message(f"Calibration loaded for Linha: Slope={slope_l}, Intercept={intercept_l}")
    
    def load_calibration(self, slope_l: float, intercept_l: float, slope_p: Optional[float] = None, intercept_p: Optional[float] = None) -> None:
        """
        Legacy method to load calibration parameters.
        Pasta parameters are ignored in this version as it uses factory calibration.
        """
        self.calib_slope_linha = slope_l
        self.calib_intercept_linha = intercept_l
        # Pasta is always factory calibrated, ignore provided values
        self.calibration_loaded = True
        self.linha_calibrada = True
        self.log_message(f"Legacy calibration loaded for Linha: Slope={slope_l}, Intercept={intercept_l}. Pasta uses factory calibration.")

    def find_and_connect(self) -> Tuple[bool, str]:
        """
        Attempts to auto-connect to an Arduino device.
        Scans available COM ports for descriptions containing 'USB', 'ARDUINO', or 'CH340'.
        """
        self.log_message("Searching for Arduino device...")
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Common Arduino descriptions/IDs
            if any(x in p.description.upper() for x in ["USB", "ARDUINO", "CH340"]):
                try:
                    self.log_message(f"Found potential device: {p.device} ({p.description}). Attempting to connect...")
                    success, msg = self.connect(p.device)
                    if success:
                        return True, msg
                except Exception as e:
                    self.log_message(f"Error connecting to {p.device}: {e}", level=logging.ERROR)
                    continue
        self.log_message("No Arduino device found.", level=logging.WARNING)
        return False, "Arduino não encontrado."

    def connect(self, port: str) -> Tuple[bool, str]:
        """
        Connects to a specific serial port.
        Performs a handshake ("PING" -> "ACK_PING_OK") to verify the device.
        """
        try:
            self.log_message(f"Attempting to connect to {port}...")
            self.ser = serial.Serial(port, BAUD_RATE, timeout=TIMEOUT_SERIAL)
            time.sleep(2) # Wait for Arduino reset
            
            if self.ser.is_open:
                self.ser.flushInput()
                self.ser.flushOutput()
                self.ser.write(b"PING\n")
                response = self.ser.readline().decode('utf-8', 'ignore').strip()
                
                if "ACK_PING_OK" in response:
                    self.is_connected = True
                    self.log_message(f"Successfully connected to {port}.")
                    return True, f"Conectado em {port}"
                else:
                    self.disconnect()
                    self.log_message(f"Handshake failed with {port}. Response: '{response}'", level=logging.ERROR)
                    return False, f"Falha no handshake com {port}."
        except Exception as e:
            self.log_message(f"Error connecting to {port}: {e}", level=logging.ERROR)
            return False, str(e)
        self.log_message("Unknown error during connection attempt.", level=logging.ERROR)
        return False, "Erro desconhecido."

    def disconnect(self) -> None:
        """Disconnects the serial port and stops the reading thread."""
        self.stop_reading()
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.log_message(f"Disconnected from {self.ser.port}.")
        self.is_connected = False
        self.ser = None

    def reset_ema(self) -> bool:
        """A-02: Reinicializa o filtro EMA do Arduino para novo ensaio.
        
        Envia RESET_EMA ao firmware, que seta ema_initialized=false.
        A próxima leitura inicializa o EMA com o valor atual dos sensores,
        eliminando o transiente do ensaio anterior.
        """
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b"RESET_EMA\n")
                self.ser.flush()
                resp = self.ser.readline().decode('utf-8', 'ignore').strip()
                if resp == "ACK_RESET_EMA":
                    self.log_message("EMA filter reset successfully.")
                    return True
                else:
                    self.log_message(f"Unexpected RESET_EMA response: '{resp}'", level=logging.WARNING)
                    return False
            except Exception as e:
                self.log_message(f"Error resetting EMA: {e}", level=logging.ERROR)
                return False
        self.log_message("Cannot reset EMA: not connected.", level=logging.WARNING)
        return False

    def start_reading(self) -> bool:
        """
        Starts the background reading thread.
        Returns True if started successfully or already running.
        """
        if not self.is_connected or not self.ser:
            self.log_message("Cannot start reading: Not connected to Arduino.", level=logging.WARNING)
            return False
            
        if self.is_reading:
            self.log_message("Reading already in progress.")
            return True

        self.is_reading = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        self.log_message("Started background reading thread.")
        return True

    def stop_reading(self) -> None:
        """Stops the background reading thread safely."""
        if self.is_reading:
            self.is_reading = False
            if self.read_thread:
                self.read_thread.join(timeout=1.0)
                if self.read_thread.is_alive():
                    self.log_message("Reading thread did not terminate gracefully.", level=logging.WARNING)
                else:
                    self.log_message("Stopped background reading thread.")
            self.read_thread = None
        else:
            self.log_message("Reading is not active.")

    def _safe_callback_emit(self, p1: float, p2: float, v1: float, v2: float):
        """Safely emits the on_pressure_reading callback."""
        cb = self.on_pressure_reading
        if cb:
            try:
                cb(p1, p2, v1, v2)
            except Exception as e:
                self.log_message(f"Error in on_pressure_reading callback: {e}", level=logging.ERROR)
                if self.on_error:
                    self.on_error(f"Callback error: {e}")

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
                        
                        # Emit callback safely
                        self._safe_callback_emit(p_linha, p_pasta, v1, v2)
                except ValueError:
                    self.log_message(f"Could not parse line from Arduino: '{line}'", level=logging.WARNING)
                
                time.sleep(0.1) # Approx 10Hz sampling rate
            except serial.SerialException as e:
                self.log_message(f"Serial communication error: {e}", level=logging.ERROR)
                if self.on_error:
                    self.on_error(str(e))
                self.stop_reading()
                break
            except Exception as e:
                self.log_message(f"An unexpected error occurred in read loop: {e}", level=logging.ERROR)
                if self.on_error:
                    self.on_error(str(e))
                self.stop_reading()
                break

    def _convert_voltage_to_pressure(self, voltage: float, sensor_type: str) -> float:
        """Converts raw voltage to pressure (bar) using loaded calibration."""
        if not self.calibration_loaded:
            self.log_message("Calibration not loaded, returning 0.0 for pressure.", level=logging.WARNING)
            return 0.0
            
        if sensor_type == 'linha':
            p = (self.calib_slope_linha * voltage) + self.calib_intercept_linha
        else:
            p = (self.calib_slope_pasta * voltage) + self.calib_intercept_pasta
            
        return max(p, 0.0)

# Mock Controller for Testing without Hardware
class MockSerial:
    port = "MockPort"
    def isOpen(self) -> bool: return True
    @property
    def is_open(self) -> bool: return True
    def close(self) -> None: pass
    def flush(self) -> None: pass
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
        self.log_message("Mock connection established.")
        return True, "Conectado (Mock)"
        
    def find_and_connect(self) -> Tuple[bool, str]:
        return self.connect()

    def _read_loop(self) -> None:
        t = 0
        while self.is_reading:
            # Generate fake sine wave pressure
            p_linha = 5.0 + 2.0 * math.sin(t * 0.1)
            p_pasta = 4.8 + 1.9 * math.sin(t * 0.1)
            v1 = (p_linha - self.calib_intercept_linha) / self.calib_slope_linha if self.calib_slope_linha else 0
            v2 = (p_pasta - self.calib_intercept_pasta) / self.calib_slope_pasta if self.calib_slope_pasta else 0
            
            self._safe_callback_emit(p_linha, p_pasta, v1, v2)
            
            time.sleep(0.1)
            t += 1

if __name__ == "__main__":
    # Test Mock Controller
    controller = MockReometerController()
    success, msg = controller.connect()
    logger.info(f"Connection result: {msg}")
    
    def print_pressure(p1: float, p2: float, v1: float, v2: float) -> None:
        logger.info(f"L: {p1:.2f} bar | P: {p2:.2f} bar | V1: {v1:.3f}V | V2: {v2:.3f}V")
        
    controller.on_pressure_reading = print_pressure
    controller.load_calibration(100.0, 0, 100.0, 0)
    
    controller.start_reading()
    time.sleep(3)
    controller.stop_reading()
