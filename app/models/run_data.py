from __future__ import annotations

from typing import List, Dict, Any
from app.models.docs import ControlClause

class ProjectRunData:
    def __init__(self, project_name: str, control_clauses: List[ControlClause]):
        self.project_name = project_name
        self.control_clauses: List[ControlClause] = control_clauses

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "control_clauses": [cc.model_dump() for cc in self.control_clauses]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectRunData:
        clauses_data = data.get("control_clauses", [])
        control_clauses = [ControlClause(**cc_data) for cc_data in clauses_data]
        return cls(project_name=data.get("project_name", "Unknown Project"), control_clauses=control_clauses) 