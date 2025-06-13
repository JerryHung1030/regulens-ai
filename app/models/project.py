from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from threading import Lock

from PySide6.QtCore import QObject, Signal

from app.models.assessments import PairAssessment # Old results structure
from .docs import NormDoc
# Import ProjectRunData for the new results structure
from app.pipeline.pipeline_v1_1 import ProjectRunData


class CompareProject(QObject):
    changed = Signal()
    updated = Signal()
    deleted = Signal()

    name: str
    results: List[PairAssessment]
    controls_json_path: Optional[Path]  # Changed from controls_dir
    procedure_pdf_paths: List[Path]  # Changed from procedures_dir
    run_json_path: Optional[Path]  # Added
    report_path: Optional[Path]
    is_sample: bool
    created_at: datetime
    editor_idx: int
    viewer_idx: int
    
    _norm_map: Dict[str, NormDoc]  # For storing all types of NormDocs
    project_run_data: Optional[ProjectRunData] = None # New attribute for v1.1 pipeline results

    def __init__(self, name: str,
                 controls_json_path: Optional[Path] = None,
                 procedure_pdf_paths: Optional[List[Path]] = None,
                 run_json_path: Optional[Path] = None,
                 report_path: Optional[Path] = None, # This might be deprecated if new pipeline handles reports differently
                 is_sample: bool = False,
                 created_at: Optional[datetime] = None,
                 editor_idx: int = -1,
                 viewer_idx: int = -1,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.name = name
        self.results: List[PairAssessment] = []
        self._results_lock = Lock()
        self.controls_json_path = controls_json_path
        self.procedure_pdf_paths = procedure_pdf_paths if procedure_pdf_paths is not None else []

        # Initialize run_json_path with a default if not provided
        if run_json_path is None:
            # Assuming a base directory for projects, e.g., 'projects_data' or similar
            # This base path might need to be configurable globally or passed in.
            # For now, using a relative path:
            self.run_json_path = Path(f"projects/{self.name}/run.json")
        else:
            self.run_json_path = run_json_path

        self.report_path = report_path
        self.is_sample = is_sample
        self.created_at = created_at if created_at is not None else datetime.now()
        self.editor_idx = editor_idx
        self.viewer_idx = viewer_idx
        self.project_run_data = None # Initialize as None
        
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
        # Updated readiness check
        controls_ready = self.controls_json_path is not None and self.controls_json_path.exists() and self.controls_json_path.is_file()
        procedures_ready = bool(self.procedure_pdf_paths) and all(p.exists() and p.is_file() for p in self.procedure_pdf_paths)
        # run_json_path is optional for readiness, so we don't check for its existence here.
        # If it becomes mandatory, add:
        # run_json_ready = self.run_json_path is not None and self.run_json_path.exists() and self.run_json_path.is_file()
        # and include run_json_ready in the return statement.
        return controls_ready and procedures_ready

    @property
    def has_results(self) -> bool:
        # For v1.1 pipeline, "results" means run.json exists and is valid, or project_run_data is loaded.
        # The old `self.results` (List[PairAssessment]) might still be used by older pipeline versions.
        if self.project_run_data is not None and self.project_run_data.control_clauses:
            return True
        if self.run_json_path and self.run_json_path.exists() and self.run_json_path.is_file():
            # Basic check for existence and being a file.
            # A more robust check would try to load/validate its content.
            try:
                with open(self.run_json_path, 'r') as f:
                    content = f.read()
                    return bool(content.strip() and content.strip() != "{}") # Non-empty JSON
            except Exception:
                return False # Error reading implies no valid results

        # Fallback to old results structure if new one is not present
        with self._results_lock:
            return bool(self.results)

    def set_results(self, assessments: List[PairAssessment]): # This is for the old pipeline's results
        with self._results_lock:
            self.results = assessments
        self.updated.emit()

    def get_results(self) -> List[PairAssessment]:
        with self._results_lock:
            return list(self.results)

    def set_controls_json_path(self, path: Path | None):  # Changed
        self.controls_json_path = path
        with self._results_lock:
            self.results = []
        self.changed.emit()

    def set_procedure_pdf_paths(self, paths: List[Path] | None):  # Changed
        self.procedure_pdf_paths = paths if paths is not None else []
        with self._results_lock:
            self.results = []
        self.changed.emit()

    def set_run_json_path(self, path: Path | None):  # Added
        self.run_json_path = path
        with self._results_lock:
            self.results = []
        self.changed.emit()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "controls_json_path": str(self.controls_json_path) if self.controls_json_path else None,  # Changed
            "procedure_pdf_paths": [str(p) for p in self.procedure_pdf_paths],  # Changed
            "run_json_path": str(self.run_json_path) if self.run_json_path else None,  # Added
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

        procedure_paths_str = data.get("procedure_pdf_paths", [])
        procedure_pdf_paths = [Path(p) for p in procedure_paths_str] if procedure_paths_str else []

        project = cls(  # Create instance first
            name=data["name"],
            controls_json_path=Path(data["controls_json_path"]) if data.get("controls_json_path") else None,  # Changed
            procedure_pdf_paths=procedure_pdf_paths,  # Changed
            run_json_path=Path(data["run_json_path"]) if data.get("run_json_path") else None,  # Added
            report_path=Path(data["report_path"]) if data.get("report_path") else None,
            is_sample=data.get("is_sample", False),
            created_at=created_at_dt,
        )
        # Note: self._norm_map is not populated here. It should be populated after loading,
        # typically by passing the loaded/normalized NormDoc objects to populate_norm_map().
        return project
