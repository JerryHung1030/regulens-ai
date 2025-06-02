from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from threading import Lock

from PySide6.QtCore import QObject, Signal

from app.models.assessments import PairAssessment
from .docs import NormDoc


class CompareProject(QObject):
    changed = Signal()
    updated = Signal()
    deleted = Signal()

    name: str
    results: List[PairAssessment]
    controls_dir: Optional[Path]
    procedures_dir: Optional[Path]
    evidences_dir: Optional[Path]
    report_path: Optional[Path]
    is_sample: bool
    created_at: datetime
    editor_idx: int
    viewer_idx: int
    
    _norm_map: Dict[str, NormDoc]  # For storing all types of NormDocs

    def __init__(self, name: str,
                 controls_dir: Optional[Path] = None,
                 procedures_dir: Optional[Path] = None,
                 evidences_dir: Optional[Path] = None,
                 report_path: Optional[Path] = None,
                 is_sample: bool = False,
                 created_at: Optional[datetime] = None,
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
        
        self._norm_map: Dict[str, NormDoc] = {}  # Unified map for all NormDocs

    def populate_norm_map(self, norm_docs: List[NormDoc]) -> None:
        """
        Populates the internal map of norm_id to NormDoc object.
        This map can store controls, procedures, and evidence documents if needed,
        as long as they are passed in norm_docs.
        """
        for norm_doc in norm_docs:
            if norm_doc and norm_doc.id:  # Ensure norm_doc and its id are valid
                self._norm_map[norm_doc.id] = norm_doc
        # Optionally, emit a signal if other parts of the UI need to know the map is updated.
        # self.updated.emit() # Or a new specific signal e.g., norm_map_updated

    def get_norm_metadata(self, norm_id: str) -> dict:
        """
        Retrieves the metadata for a given norm_id from the _norm_map.
        """
        norm_doc = self._norm_map.get(norm_id)
        if norm_doc and hasattr(norm_doc, 'metadata') and norm_doc.metadata is not None:
            return norm_doc.metadata
        return {}

    def rename(self, new_name: str):
        self.name = new_name
        self.updated.emit()
        self.changed.emit()

    @property
    def ready(self) -> bool:
        def check_dir(dir_path: Optional[Path]) -> bool:
            if dir_path is None or not dir_path.exists() or not dir_path.is_dir():
                return False
            try:
                for item in dir_path.iterdir():
                    if item.is_file() and item.suffix.lower() == ".txt":
                        return True
                return False
            except OSError:
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
        self.updated.emit()

    def get_results(self) -> List[PairAssessment]:
        with self._results_lock:
            return list(self.results)

    def set_controls_dir(self, path: Path | None):
        self.controls_dir = path
        with self._results_lock:
            self.results = []
        self.changed.emit()

    def set_procedures_dir(self, path: Path | None):
        self.procedures_dir = path
        with self._results_lock:
            self.results = []
        self.changed.emit()

    def set_evidences_dir(self, path: Path | None):
        self.evidences_dir = path
        with self._results_lock:
            self.results = []
        self.changed.emit()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "controls_dir": str(self.controls_dir) if self.controls_dir else None,
            "procedures_dir": str(self.procedures_dir) if self.procedures_dir else None,
            "evidences_dir": str(self.evidences_dir) if self.evidences_dir else None,
            "report_path": str(self.report_path) if self.report_path else None,
            "is_sample": self.is_sample,
            "created_at": self.created_at.isoformat(),
            # _norm_map is runtime data, typically not persisted directly with project settings.
            # It would be repopulated on project load by re-running normalization or loading cached NormDocs.
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompareProject":
        created_at_str = data.get("created_at")
        created_at_dt = None
        if created_at_str:
            try:
                created_at_dt = datetime.fromisoformat(created_at_str)
            except ValueError:
                created_at_dt = datetime.now()
        else:
            created_at_dt = datetime.now()

        project = cls(  # Create instance first
            name=data["name"],
            controls_dir=Path(data["controls_dir"]) if data["controls_dir"] else None,
            procedures_dir=Path(data["procedures_dir"]) if data["procedures_dir"] else None,
            evidences_dir=Path(data["evidences_dir"]) if data["evidences_dir"] else None,
            report_path=Path(data["report_path"]) if data["report_path"] else None,
            is_sample=data.get("is_sample", False),
            created_at=created_at_dt,
        )
        # Note: self._norm_map is not populated here. It should be populated after loading,
        # typically by passing the loaded/normalized NormDoc objects to populate_norm_map().
        return project
