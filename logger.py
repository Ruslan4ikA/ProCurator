"""Модуль логирования."""
import logging, os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"curator_{datetime.now().strftime('%Y-%m')}.log"

logger = logging.getLogger("curator_ai")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    logger.addHandler(ch)

def get_recent_logs(n: int = 150) -> list:
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        result = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            level = "info"
            if "[ERROR]" in line:   level = "error"
            elif "[WARNING]" in line: level = "warning"
            elif "[DEBUG]" in line:  level = "debug"
            result.append({"text": line, "level": level})
        return result
    except Exception:
        return []
