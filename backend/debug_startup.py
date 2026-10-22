import sys
import logging
import os

# Set up logging to a file
logging.basicConfig(
    filename='startup_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger('debug_startup')

try:
    logger.info("Starting debug import...")
    from app.main import app
    logger.info("Import successful!")
    print("SUCCESS")
except Exception as e:
    logger.exception("Import failed!")
    print(f"ERROR: {e}")
