# Standard Library Imports
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
import json
import collections

# Third-party Imports
import faiss  # type: ignore

# Project-specific Imports
# Models
from app.settings import Settings  # For PipelineSettings.from_settings
from pydantic import BaseModel, Field  # For PipelineSettings definition

try:
    from app.models.project import CompareProject
    from app.models.docs import RawDoc, NormDoc, EmbedSet
    from app.models.assessments import TripleAssessment, PairAssessment, MatchSet
except ImportError:  # Fallback for potential execution context issues
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.project import CompareProject  # type: ignore
    from app.models.docs import RawDoc, NormDoc, EmbedSet  # type: ignore
    from app.models.assessments import TripleAssessment, PairAssessment, MatchSet  # type: ignore


class PipelineSettings(BaseModel):
    openai_api_key: str = Field(default="")
    embedding_model: str = Field(default="default_embedding_model")
    llm_model: str = Field(default="default_llm_model") # General LLM model, might be repurposed or removed if specific ones cover all cases
    local_model_path: Optional[Path] = Field(default=None)
    top_k_procedure: int = Field(default=5) # Used in old pipeline logic
    top_m_evidence: int = Field(default=5) # Used in old pipeline logic
    score_threshold: float = Field(default=0.7) # Used in old pipeline logic
    report_theme: str = Field(default="default.css")
    language: str = Field(default="en")

    # New fields for pipeline_v1_1
    llm_model_need_check: str = Field(default="default_model_need_check")
    llm_model_audit_plan: str = Field(default="default_model_audit_plan")
    llm_model_judge: str = Field(default="default_model_judge") # For future Step 4 of v1.1
    audit_retrieval_top_k: int = Field(default=5)


    @classmethod
    def from_settings(cls, settings: Settings) -> "PipelineSettings":
        # Assuming settings.get can fetch flat keys or we adjust here
        # For keys like "llm.model_need_check" from config_default.yaml,
        # the global Settings class would need to handle the dot notation
        # or we fetch them individually.
        return cls(
            openai_api_key=settings.get("openai_api_key", ""),
            embedding_model=settings.get("embedding_model") or "default_embedding_model",
            llm_model=settings.get("llm_model") or "default_llm_model", # General model
            local_model_path=Path(settings.get("local_model_path")) if settings.get("local_model_path") else None,
            top_k_procedure=int(settings.get("top_k_procedure", 5)),
            top_m_evidence=int(settings.get("top_m_evidence", 5)),
            score_threshold=float(settings.get("score_threshold", 0.7)),
            report_theme=settings.get("report_theme", "default.css"),
            language=settings.get("language", "en"),

            # New settings for v1.1 pipeline
            # The keys used in settings.get() should match what's in config_default.yaml or user's .regulens-ai.json
            llm_model_need_check=settings.get("llm.model_need_check", "default_model_need_check"),
            llm_model_audit_plan=settings.get("llm.model_audit_plan", "default_model_audit_plan"),
            llm_model_judge=settings.get("llm.model_judge", "default_model_judge"),
            audit_retrieval_top_k=int(settings.get("audit.retrieval_top_k", 5))
        )


# Pipeline Modules
from .ingestion import ingest_documents # Still used by old pipeline logic if retained
from .normalize import normalize_document # Still used by old pipeline logic if retained
from .embed import generate_embeddings # Still used by old pipeline logic
from .index import create_or_load_index # Still used by old pipeline logic
from .retrieve import retrieve_similar_chunks # Still used by old pipeline logic
from .judge_llm import assess_triplet_with_llm # Old assessment logic
from .aggregate import aggregate_assessments_for_pair # Old aggregation
from .report import generate_report # Old report generation
from .cache import CacheService # Still potentially useful

# Import the new pipeline orchestrator
from .pipeline_v1_1 import run_project_pipeline_v1_1


# Main Pipeline Orchestration Function
def run_pipeline(
    project: CompareProject,
    # The 'settings' parameter here is the global Settings object, not PipelineSettings
    global_app_settings: Settings,
    progress_callback: Optional[Callable[[float, str], None]] = None, # Changed signature for v1.1
    cancel_cb: Optional[Callable[[], bool]] = None
) -> Optional[Path]: # Return type might change depending on what v1.1 returns (e.g., path to run.json or report)
    """
    Runs the full compliance assessment pipeline.
    Determines which pipeline version to run based on project structure.
    """
    
    # Instantiate the Pydantic PipelineSettings model from the global Settings
    # This now happens inside this run_pipeline function.
    pipeline_settings = PipelineSettings.from_settings(global_app_settings)

    # Decision logic for pipeline version can be added here.
    # For now, directly calling pipeline_v1_1 if controls_json_path is set.
    if project.controls_json_path and project.run_json_path:
        logger.info(f"Detected controls_json_path, running pipeline_v1_1 for project: {project.name}")
        
        # Adapt progress_callback if necessary or pass directly
        # The new pipeline_v1_1 expects progress_callback: Callable[[float, str], None]
        # The old one was: Callable[[int, int, str, int], None]
        # For simplicity, we'll assume the UI can handle the new float-based progress.
        
        # Ensure the global_app_settings (type Settings) is converted to pipeline_settings (type PipelineSettings)
        # This is now done above with PipelineSettings.from_settings()

        run_project_pipeline_v1_1(
            project=project,
            settings=pipeline_settings, # Pass the Pydantic model instance
            progress_callback=progress_callback if progress_callback else lambda p, m: print(f"Progress: {p*100:.0f}% - {m}"),
            cancel_cb=cancel_cb if cancel_cb else lambda: False
        )
        # pipeline_v1_1 manages its own run.json and doesn't return a report path directly in the same way.
        # The 'report_path' on the project might be set by other means or a future step in v1.1.
        # For now, returning the run_json_path as an indicator of completion.
        return project.run_json_path
    else:
        # Fallback to old pipeline logic (commented out for now as requested)
        logger.info(f"Falling back to legacy pipeline for project: {project.name}")
        # _update_progress callback for the old pipeline:
        def _legacy_update_progress(current_step: int, total_steps: int, message: str):
            if progress_callback: # Check if the provided callback matches old style
                # This is tricky because signatures differ. We might need to adapt or log.
                # For now, let's assume if a progress_callback is given, it's for the new style.
                # So, we'd have to translate if we want to use it for old style.
                # Or, the old pipeline part just prints to console.
                new_style_progress = float(current_step / total_steps) if total_steps > 0 else 0.0
                progress_callback(new_style_progress, f"Legacy: {message}")
            print(f"Legacy Progress: {current_step}/{total_steps} - {message}")

        # --- OLD PIPELINE LOGIC (commented out as per focus on v1.1 integration) ---
        # total_pipeline_stages = 8
        # current_stage_num = 0
        # _legacy_update_progress(current_stage_num, total_pipeline_stages, "Stage 1/8: Initializing legacy pipeline...")
        # cache_service = CacheService(Path("cache"))
        # run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # project_name_safe = project.name.replace(' ', '_').replace('/', '_') if project.name else "default_project"
        # output_dir = Path("output") / f"{project_name_safe}_{run_timestamp}"
        # try:
        #     output_dir.mkdir(parents=True, exist_ok=True)
        # except OSError as e:
        #     _legacy_update_progress(current_stage_num, total_pipeline_stages, f"CRITICAL ERROR: Could not create output directory {output_dir}: {e}")
        #     return None
        # index_root_dir = cache_service.cache_dir / "indexes"
        # index_root_dir.mkdir(parents=True, exist_ok=True)
        # ... (rest of the old pipeline stages: Ingestion, Normalization, Embedding, Indexing, etc.) ...
        # ... This would involve using project.controls_dir, project.procedures_dir etc. ...
        # ... and the original `ingest_documents` that takes a directory.
        # _legacy_update_progress(total_pipeline_stages, total_pipeline_stages, "Legacy pipeline finished (mocked).")
        # return output_dir / "some_legacy_report.md" # Example
        logger.warning("Legacy pipeline path is currently commented out. No operation performed.")
        if progress_callback:
            progress_callback(1.0, "Legacy pipeline path not implemented/active.")
        return None


if __name__ == '__main__':
    print("Pipeline __init__.py executed. To run the pipeline, import and call `run_pipeline` with appropriate Project and Settings objects.")
    pass
