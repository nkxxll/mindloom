import logging
from logging.handlers import RotatingFileHandler
import sys

# Inside your setup_logging function:
handler = RotatingFileHandler(
    "app.log",
    maxBytes=1000000, # 1MB
    backupCount=5     # Keep 5 old log files
)

def setup_logging():
    # 1. Create a custom formatter
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 2. Configure the root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            handler,
            logging.StreamHandler(sys.stdout) # Also logs to your terminal
        ]
    )

# Initialize it once
setup_logging()
