from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel # Added import

# Add this import
from app.app_paths import get_app_data_dir

class Settings:
    """Simple settings manager that persists to JSON.

    The settings are stored in the user's home directory as
    ``~/.regulens-ai.json``.  The file is created automatically
    when the first setting is saved.
    """

    def __init__(self) -> None:
        # Modify this line
        self._path = get_app_data_dir() / "settings.json"
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
        if key == "theme":
            return self._data.get(key, "system")
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save to disk."""
        self._data[key] = value
        self._save()

# The PipelineSettings class definition has been moved to app.pipeline.__init__.py
# to keep it co-located with the pipeline logic that uses it and to avoid circular dependencies.
# It can be imported from there if needed elsewhere in the `app.settings` module,
# though typically it's instantiated and used closer to the pipeline invocation.
