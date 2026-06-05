import logging
import os
from logging.handlers import RotatingFileHandler
from config.settings import LOGGING_CONFIG


def setup_logger(name='predictive_maintenance'):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOGGING_CONFIG['level']))

    log_dir = LOGGING_CONFIG['log_dir']
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, LOGGING_CONFIG['log_file'])

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOGGING_CONFIG['max_bytes'],
        backupCount=LOGGING_CONFIG['backup_count'],
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
