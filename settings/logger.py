"""Sets up logging."""

import logging
import sys
import time
from logging import Formatter, StreamHandler
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

logging.Formatter.converter = time.gmtime

BASE_DIR = Path(__file__).parent.parent

simple_formatter = Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
)

colored_formatter = Formatter(
    (
        "\u001b[90m%(asctime)s\u001b[0m "
        + "\u001b[34m%(levelname)-8s\u001b[0m "
        + "\u001b[32m%(name)-22s \u001b[0m %(message)s"
    ),
    "%Y-%m-%d %H:%M:%S",
)

console_handler = StreamHandler(sys.stdout)
console_handler.setFormatter(colored_formatter)

file_handler = TimedRotatingFileHandler(
    BASE_DIR / "logs" / "info.log",
    backupCount=30,
    when="midnight",
    encoding="utf-8",
)

file_handler.setFormatter(simple_formatter)
file_handler.suffix = "%Y%m%d"

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)
