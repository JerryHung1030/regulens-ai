from __future__ import annotations

from typing import List, Dict, Any
from app.models.docs import ExternalRegulationClause

class ProjectRunData:
    def __init__(self, project_name: str, external_regulation_clauses: List[ExternalRegulationClause]):
        self.project_name = project_name
        self.external_regulation_clauses: List[ExternalRegulationClause] = external_regulation_clauses

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "external_regulation_clauses": [cc.model_dump() for cc in self.external_regulation_clauses]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectRunData:
        clauses_data = data.get("external_regulation_clauses", [])
        external_regulation_clauses = [ExternalRegulationClause(**cc_data) for cc_data in clauses_data]
        return cls(project_name=data.get("project_name", "Unknown Project"), external_regulation_clauses=external_regulation_clauses) 