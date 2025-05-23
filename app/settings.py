from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_PATH = Path.home() / ".regulens-ai.json"


class Settings:
    """Very small settings handler stored as JSON."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_PATH
        self.data: Dict[str, Any] = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
