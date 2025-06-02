from typing import Optional
from pathlib import Path
from pydantic import BaseModel

class ArchivedPipelineSettings(BaseModel): # Renamed from PipelineSettings
    openai_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4o"
    local_model_path: Optional[Path] = None
    top_k_procedure: int = 5
    top_m_evidence: int = 5
    score_threshold: float = 0.7
    report_theme: str = "default.css"
    language: str = "en"  # for report generation, if needed
