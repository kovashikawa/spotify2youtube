import logging
import sys

def setup_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Sets up and returns a logger with the specified name and level.
    
    Args:
        name (str): The name of the logger. If None, configures the root logger.
        level (int): Logging level (e.g., logging.INFO, logging.DEBUG).
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent adding multiple handlers to the same logger.
    if not logger.handlers:
        # Create a stream handler to output logs to stdout.
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        
        # Define a consistent log message format.
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Set up the root logger for the entire repository.
setup_logger(name=None, level=logging.INFO)
