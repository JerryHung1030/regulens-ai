from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Assuming app.settings.Settings is the correct path to the global Settings class
# If app.settings directly imports Settings from elsewhere, adjust as needed.
# For now, direct relative import might be tricky if app is not consistently in PYTHONPATH
# in all execution contexts (like tests vs. run).
# Using an absolute-like import from app.
from app.settings import Settings


class PipelineSettings(BaseModel):
    openai_api_key: str = Field(default="")
    embedding_model: str = Field(default="default_embedding_model")
    llm_model: str = Field(default="default_llm_model") # General LLM model
    local_model_path: Optional[Path] = Field(default=None)
    top_k_procedure: int = Field(default=5) # Used in old pipeline logic (if ever reactivated)
    top_m_evidence: int = Field(default=5) # Used in old pipeline logic (if ever reactivated)
    score_threshold: float = Field(default=0.7) # Used in old pipeline logic (if ever reactivated)
    report_theme: str = Field(default="default.css")
    language: str = Field(default="en")

    # New fields for pipeline_v1_1
    llm_model_need_check: str = Field(default="default_model_need_check")
    llm_model_audit_plan: str = Field(default="default_model_audit_plan")
    llm_model_judge: str = Field(default="default_model_judge") # For Step 4 of v1.1
    audit_retrieval_top_k: int = Field(default=5)


    @classmethod
    def from_settings(cls, settings: Settings) -> "PipelineSettings":
        """
        Factory method to create PipelineSettings from the global application Settings.
        This allows centralizing how settings are fetched.
        """
        return cls(
            openai_api_key=settings.get("openai_api_key", ""),
            embedding_model=settings.get("embedding_model") or "default_embedding_model",
            llm_model=settings.get("llm_model") or "default_llm_model",
            local_model_path=Path(settings.get("local_model_path")) if settings.get("local_model_path") else None,
            top_k_procedure=int(settings.get("top_k_procedure", 5)),
            top_m_evidence=int(settings.get("top_m_evidence", 5)),
            score_threshold=float(settings.get("score_threshold", 0.7)),
            report_theme=settings.get("report_theme", "default.css"),
            language=settings.get("language", "en"),

            # New settings for v1.1 pipeline from config_default.yaml or user settings
            llm_model_need_check=settings.get("llm.model_need_check", "default_model_need_check"),
            llm_model_audit_plan=settings.get("llm.model_audit_plan", "default_model_audit_plan"),
            llm_model_judge=settings.get("llm.model_judge", "default_model_judge"),
            audit_retrieval_top_k=int(settings.get("audit.retrieval_top_k", 5))
        )

print("app.pipeline_settings.py created with PipelineSettings model.")
