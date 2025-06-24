from __future__ import annotations

from typing import List, Dict, Any, Optional
from app.models.docs import ExternalRegulationClause

class ProjectRunData:
    def __init__(self, 
                 project_name: str, 
                 external_regulation_clauses: List[ExternalRegulationClause],
                 external_regulations_file_timestamp: Optional[float] = None,
                 procedure_files_timestamps: Optional[Dict[str, float]] = None
                ):
        self.project_name = project_name
        self.external_regulation_clauses: List[ExternalRegulationClause] = external_regulation_clauses
        self.external_regulations_file_timestamp: Optional[float] = external_regulations_file_timestamp
        self.procedure_files_timestamps: Optional[Dict[str, float]] = procedure_files_timestamps if procedure_files_timestamps is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "external_regulation_clauses": [cc.model_dump() for cc in self.external_regulation_clauses],
            "external_regulations_file_timestamp": self.external_regulations_file_timestamp,
            "procedure_files_timestamps": self.procedure_files_timestamps
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectRunData:
        clauses_data = data.get("external_regulation_clauses", [])
        external_regulation_clauses = [ExternalRegulationClause(**cc_data) for cc_data in clauses_data]
        return cls(
            project_name=data.get("project_name", "Unknown Project"), 
            external_regulation_clauses=external_regulation_clauses,
            external_regulations_file_timestamp=data.get("external_regulations_file_timestamp"),
            procedure_files_timestamps=data.get("procedure_files_timestamps")
        )