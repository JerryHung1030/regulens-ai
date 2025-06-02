from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from threading import Lock

from PySide6.QtCore import QObject, Signal

from app.models.assessments import PairAssessment
from .docs import NormDoc  # Ensure NormDoc is imported

# Not using @dataclass anymore, fields will be initialized in __init__


class CompareProject(QObject):
    changed = Signal()
    updated = Signal()
    deleted = Signal()

    # Fields definition with type hints
    name: str
    results: List[PairAssessment]
    controls_dir: Optional[Path]
    procedures_dir: Optional[Path]
    evidences_dir: Optional[Path]
    report_path: Optional[Path]  # Path to the main Markdown report
    is_sample: bool
    created_at: datetime

    editor_idx: int  # QStackedWidget index for ProjectEditor
    viewer_idx: int  # index for ResultsViewer

    def __init__(self, name: str,
                 controls_dir: Optional[Path] = None,
                 procedures_dir: Optional[Path] = None,
                 evidences_dir: Optional[Path] = None,
                 report_path: Optional[Path] = None,
                 is_sample: bool = False,
                 created_at: Optional[datetime] = None,  # Allow None for default now()
                 editor_idx: int = -1,
                 viewer_idx: int = -1,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.name = name
        self.results: List[PairAssessment] = []
        self._results_lock = Lock()
        self.controls_dir = controls_dir
        self.procedures_dir = procedures_dir
        self.evidences_dir = evidences_dir
        self.report_path = report_path
        self.is_sample = is_sample
        self.created_at = created_at if created_at is not None else datetime.now()
        self.editor_idx = editor_idx
        self.viewer_idx = viewer_idx
        
        # New attributes for storing normalized document maps
        self.control_norm_docs_map: Dict[str, NormDoc] = {}
        self.procedure_norm_docs_map: Dict[str, NormDoc] = {}

    def get_norm_doc_info(self, doc_id: str) -> dict:
        norm_doc = None
        # Check procedure_norm_docs_map first as it's more likely for tab titles
        if hasattr(self, 'procedure_norm_docs_map') and self.procedure_norm_docs_map and doc_id in self.procedure_norm_docs_map:
            norm_doc = self.procedure_norm_docs_map[doc_id]
        elif hasattr(self, 'control_norm_docs_map') and self.control_norm_docs_map and doc_id in self.control_norm_docs_map:
            norm_doc = self.control_norm_docs_map[doc_id]
        
        if not norm_doc:
            return {}

        return {
            "original_filename": norm_doc.metadata.get("original_filename") if norm_doc.metadata else None,
            "raw_doc_id": norm_doc.raw_doc_id
        }

    def rename(self, new_name: str):
        self.name = new_name
        self.updated.emit()
        self.changed.emit()  # Ensure ProjectEditor and ResultsViewer refresh

    @property
    def ready(self) -> bool:
        """
        Checks if all required directories are set, exist, and contain at least one .txt file.
        """
        def check_dir(dir_path: Optional[Path]) -> bool:
            if dir_path is None or not dir_path.exists() or not dir_path.is_dir():
                return False
            try:
                # Check for at least one .txt file
                for item in dir_path.iterdir():
                    if item.is_file() and item.suffix.lower() == ".txt":
                        return True
                return False  # No .txt file found
            except OSError:  # Catch potential errors like permission denied
                return False

        return (check_dir(self.controls_dir) and 
                check_dir(self.procedures_dir) and 
                check_dir(self.evidences_dir))

    @property
    def has_results(self) -> bool:
        with self._results_lock:
            return bool(self.results)

    def set_results(self, assessments: List[PairAssessment]):
        with self._results_lock:
            self.results = assessments
        self.updated.emit()  # Or a more specific signal if appropriate

    def get_results(self) -> List[PairAssessment]:
        with self._results_lock:
            # Return a copy to allow safe iteration outside the lock
            return list(self.results)

    def set_controls_dir(self, path: Path | None):
        self.controls_dir = path
        with self._results_lock:
            self.results = []
        # self.report_path = None # Keep this if report_path is still used distinctly
        self.changed.emit()

    def set_procedures_dir(self, path: Path | None):
        self.procedures_dir = path
        with self._results_lock:
            self.results = []
        # self.report_path = None # Keep this if report_path is still used distinctly
        self.changed.emit()

    def set_evidences_dir(self, path: Path | None):
        self.evidences_dir = path
        with self._results_lock:
            self.results = []
        # self.report_path = None # Keep this if report_path is still used distinctly
        self.changed.emit()

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for storage."""
        return {
            "name": self.name,
            "controls_dir": str(self.controls_dir) if self.controls_dir else None,
            "procedures_dir": str(self.procedures_dir) if self.procedures_dir else None,
            "evidences_dir": str(self.evidences_dir) if self.evidences_dir else None,
            "report_path": str(self.report_path) if self.report_path else None,
            "is_sample": self.is_sample,
            "created_at": self.created_at.isoformat(),
            # editor_idx and viewer_idx are runtime state, typically not persisted
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompareProject":
        """Create project from dictionary."""
        created_at_str = data.get("created_at")
        created_at_dt = None
        if created_at_str:
            try:
                created_at_dt = datetime.fromisoformat(created_at_str)
            except ValueError:  # Handle potential malformed ISO strings if any
                created_at_dt = datetime.now()  # Fallback or log error
        else:  # For older projects saved without created_at
            created_at_dt = datetime.now()

        return cls(
            name=data["name"],
            controls_dir=Path(data["controls_dir"]) if data["controls_dir"] else None,
            procedures_dir=Path(data["procedures_dir"]) if data["procedures_dir"] else None,
            evidences_dir=Path(data["evidences_dir"]) if data["evidences_dir"] else None,
            report_path=Path(data["report_path"]) if data["report_path"] else None,
            is_sample=data.get("is_sample", False),  # Default to False if not present
            created_at=created_at_dt,
            # editor_idx and viewer_idx could be loaded if saved, or use defaults
        )
