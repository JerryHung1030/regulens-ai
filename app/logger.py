from __future__ import annotations

from pathlib import Path

from loguru import logger


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logger.add(
    LOG_DIR / "{time:YYYY-MM-DD}.log",
    rotation="12:00",
    retention="7 days",
    enqueue=True,
    level="INFO",
)
