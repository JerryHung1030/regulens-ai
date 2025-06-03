from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Settings:
    """Simple settings manager that persists to JSON.

    The settings are stored in the user's home directory as
    ``~/.regulens-ai.json``.  The file is created automatically
    when the first setting is saved.
    """

    def __init__(self) -> None:
        self._path = Path.home() / ".regulens-ai.json"
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load settings from disk."""
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except Exception:
                self._data = {}

    def _save(self) -> None:
        """Save settings to disk."""
        self._path.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save to disk."""
        self._data[key] = value
        self._save()
