"""Sets up logging."""

import logging
import sys
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

simple_formatter = Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
)

colored_formatter = Formatter(
    (
        "\u001b[30m%(asctime)s\u001b[0m "
        + "\u001b[34m%(levelname)-8s\u001b[0m "
        + "\u001b[32m%(name)-15s \u001b[0m %(message)s"
    ),
    "%Y-%m-%d %H:%M:%S",
)

console_handler = StreamHandler(sys.stdout)
console_handler.setFormatter(colored_formatter)

file_handler = RotatingFileHandler(
    BASE_DIR / "logs" / "info.log",
    mode="a",
    maxBytes=500000,
    backupCount=10,
    encoding="utf-8",
)

file_handler.setFormatter(simple_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)
