import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name="ReometroApp", log_file="reometro.log", level=logging.INFO):
    """Configura e retorna um logger centralizado para o aplicativo."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(level)
        
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(module)s.%(funcName)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger

logger = setup_logger()
