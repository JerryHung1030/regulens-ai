from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any

from PySide6.QtCore import QObject, Signal
# Not using @dataclass anymore, fields will be initialized in __init__

class CompareProject(QObject):
    changed = Signal()
    updated = Signal()
    deleted = Signal()

    # Fields definition with type hints
    name: str
    controls_dir: Optional[Path]
    procedures_dir: Optional[Path]
    evidences_dir: Optional[Path]
    report_path: Optional[Path] # Path to the main Markdown report

    editor_idx: int  # QStackedWidget index for ProjectEditor
    viewer_idx: int  # index for ResultsViewer

    def __init__(self, name: str,
                 controls_dir: Optional[Path] = None,
                 procedures_dir: Optional[Path] = None,
                 evidences_dir: Optional[Path] = None,
                 report_path: Optional[Path] = None,
                 editor_idx: int = -1,
                 viewer_idx: int = -1,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.name = name
        self.controls_dir = controls_dir
        self.procedures_dir = procedures_dir
        self.evidences_dir = evidences_dir
        self.report_path = report_path
        self.editor_idx = editor_idx
        self.viewer_idx = viewer_idx

    def rename(self, new_name: str):
        self.name = new_name
        self.updated.emit()
        self.changed.emit()  # Ensure ProjectEditor and ResultsViewer refresh

    @property
    def ready(self) -> bool:
        return self.controls_dir is not None and \
               self.procedures_dir is not None and \
               self.evidences_dir is not None

    @property
    def has_results(self) -> bool:
        # This might need to be updated based on how results are handled with report_path
        return self.report_path is not None and self.report_path.exists()

    def set_controls_dir(self, path: Path | None):
        self.controls_dir = path
        self.report_path = None # Clear old results when inputs change
        self.changed.emit()

    def set_procedures_dir(self, path: Path | None):
        self.procedures_dir = path
        self.report_path = None # Clear old results
        self.changed.emit()

    def set_evidences_dir(self, path: Path | None):
        self.evidences_dir = path
        self.report_path = None # Clear old results
        self.changed.emit()

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for storage."""
        return {
            "name": self.name,
            "controls_dir": str(self.controls_dir) if self.controls_dir else None,
            "procedures_dir": str(self.procedures_dir) if self.procedures_dir else None,
            "evidences_dir": str(self.evidences_dir) if self.evidences_dir else None,
            "report_path": str(self.report_path) if self.report_path else None,
            # editor_idx and viewer_idx are runtime state, typically not persisted
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompareProject":
        """Create project from dictionary."""
        return cls(
            name=data["name"],
            controls_dir=Path(data["controls_dir"]) if data["controls_dir"] else None,
            procedures_dir=Path(data["procedures_dir"]) if data["procedures_dir"] else None,
            evidences_dir=Path(data["evidences_dir"]) if data["evidences_dir"] else None,
            report_path=Path(data["report_path"]) if data["report_path"] else None,
            # editor_idx and viewer_idx could be loaded if saved, or use defaults
        )
