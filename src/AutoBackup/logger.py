import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone


logs_dir = Path(__file__).resolve().parent.parent.parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

log_file = logs_dir / f"{datetime.now():%Y-%m-%d_%H-%M-%S}.log"


formatter = logging.Formatter(
    "%(asctime)s | %(levelname)7s | %(name)20s | %(filename)10s | %(message)s"
)


file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

def get_logger(name: str = "AutoBackup") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger


MAX_LOG_AGE = timedelta(days=30)
def cleanup_logs():
    now = datetime.now(timezone.utc)
    for f in logs_dir.iterdir():
        if f.is_file() and f.suffix == ".log":
            try:
                file_dt = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if now - file_dt > MAX_LOG_AGE:
                    f.unlink()
            except Exception:
                pass
