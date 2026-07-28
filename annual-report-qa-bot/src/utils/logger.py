import logging
import os
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Creates and returns a configured logger with the given name.
    Logs are written to the console and to 'logs/app.log'.
    """
    logger = logging.getLogger(name)
    
    # If the logger already has handlers, assume it's configured to avoid duplicate logs
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        # Fallback to console-only logging if file logging fails
        logger.warning(f"Could not setup file logging due to OSError: {e}. Falling back to console-only logging.")

    return logger
