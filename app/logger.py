from __future__ import annotations
from pathlib import Path
from loguru import logger
from app.app_paths import get_app_data_dir

LOG_DIR = get_app_data_dir() / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.add(
    LOG_DIR / "{time:YYYY-MM-DD}.log",
    rotation="12:00",
    retention="7 days",
    enqueue=True,
    level="DEBUG",
)
