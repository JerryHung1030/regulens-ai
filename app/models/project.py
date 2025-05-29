from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from PySide6.QtCore import QObject, Signal


@dataclass
class CompareProject(QObject):
    changed = Signal()
    updated = Signal()
    deleted = Signal()
    name: str
    input_path: Optional[Path] = None  # internal regulation (one)
    ref_paths: List[Path] = field(default_factory=list)  # external regulations
    results: dict[str, str] = field(default_factory=dict)  # ref_path -> markdown

    editor_idx: int = -1  # QStackedWidget index for ProjectEditor
    viewer_idx: int = -1  # index for ResultsViewer

    def __post_init__(self):
        super().__init__()

    def rename(self, new_name: str):
        self.name = new_name
        self.updated.emit()
        self.changed.emit()  # Ensure ProjectEditor and ResultsViewer refresh

    @property
    def ready(self) -> bool:
        return self.input_path is not None and bool(self.ref_paths)

    @property
    def has_results(self) -> bool:
        return bool(self.results)

    def set_input(self, path: Path | None):
        self.input_path = path
        self.results.clear()
        self.changed.emit()

    def set_refs(self, paths: list[Path]):
        self.ref_paths = paths
        self.results.clear()
        self.changed.emit()

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for storage."""
        return {
            "name": self.name,
            "input_path": str(self.input_path) if self.input_path else None,
            "ref_paths": [str(p) for p in self.ref_paths],
            "results": self.results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompareProject":
        """Create project from dictionary."""
        return cls(
            name=data["name"],
            input_path=Path(data["input_path"]) if data["input_path"] else None,
            ref_paths=[Path(p) for p in data["ref_paths"]],
            results=data["results"],
        )
