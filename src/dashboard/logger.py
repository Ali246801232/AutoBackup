import logging
from pathlib import Path
from datetime import datetime

log_dir = Path(__file__).resolve().parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / f"{datetime.now():%Y-%m-%d_%H-%M-%S}.log"

logger = logging.getLogger("AutoBackup.dashboard")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)7s | %(name)20s | %(filename)10s | %(message)s"
)

file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)