from logging import getLogger, handlers, Formatter, StreamHandler, DEBUG, INFO, WARNING, ERROR, CRITICAL
import sys
import os
from pathlib import Path
from .config import Config

def set_logger():

    root_logger = getLogger()
    root_logger.setLevel(Config.LOG_LEVEL)
    
    log_path = Path(Config.FILE_NAME)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # File handler
    rotating_handler = handlers.RotatingFileHandler(
        filename=Config.FILE_NAME,
        mode='a',
        maxBytes=1000000,
        backupCount=10,
        encoding='utf-8'
    )

    formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    rotating_handler.setFormatter(formatter)
    root_logger.addHandler(rotating_handler)
    
    # Console handler
    console_handler = StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
