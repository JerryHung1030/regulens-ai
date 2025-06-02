# Standard Library Imports
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
import json
import collections

# Third-party Imports
import faiss # type: ignore

# Project-specific Imports
# Models
from app.settings import Settings # For PipelineSettings.from_settings
from pydantic import BaseModel, Field # For PipelineSettings definition

try:
    from app.models.project import CompareProject
    # from app.models.settings import PipelineSettings # Removed this import
    from app.models.docs import RawDoc, NormDoc, EmbedSet, IndexMeta
    from app.models.assessments import TripleAssessment, PairAssessment, MatchSet
except ImportError: # Fallback for potential execution context issues
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.project import CompareProject # type: ignore
    # from app.models.settings import PipelineSettings # type: ignore # Removed this import
    from app.models.docs import RawDoc, NormDoc, EmbedSet, IndexMeta # type: ignore
    from app.models.assessments import TripleAssessment, PairAssessment, MatchSet # type: ignore

# Define PipelineSettings directly here or import from a dedicated app.pipeline.settings file
class PipelineSettings(BaseModel):
    openai_api_key: str = Field(default="")
    embedding_model: str = Field(default="default_embedding_model") # Matches test default
    llm_model: str = Field(default="default_llm_model") # Matches test default
    # Fields from the original app.models.settings.ArchivedPipelineSettings that might be relevant:
    local_model_path: Optional[Path] = Field(default=None)
    top_k_procedure: int = Field(default=5)
    top_m_evidence: int = Field(default=5)
    score_threshold: float = Field(default=0.7)
    report_theme: str = Field(default="default.css") # Or simply "default"
    language: str = Field(default="en")

    @classmethod
    def from_settings(cls, settings: Settings) -> "PipelineSettings":
        return cls(
            openai_api_key=settings.get("openai_api_key", ""),
            embedding_model=settings.get("embedding_model") or "default_embedding_model",
            llm_model=settings.get("llm_model") or "default_llm_model",
            local_model_path=Path(settings.get("local_model_path")) if settings.get("local_model_path") else None,
            top_k_procedure=int(settings.get("top_k_procedure", 5)),
            top_m_evidence=int(settings.get("top_m_evidence", 5)),
            score_threshold=float(settings.get("score_threshold", 0.7)),
            report_theme=settings.get("report_theme", "default.css"),
            language=settings.get("language", "en")
        )

# Pipeline Modules
from .ingestion import ingest_documents
from .normalize import normalize_document
from .embed import generate_embeddings, EmbedSetList # EmbedSetList for caching lists
from .index import create_or_load_index
from .retrieve import retrieve_similar_chunks
from .judge_llm import assess_triplet_with_llm
from .aggregate import aggregate_assessments_for_pair
from .report import generate_report
from .cache import CacheService


# Main Pipeline Orchestration Function
def run_pipeline(
    project: CompareProject, 
    settings: PipelineSettings, 
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Optional[Path]:
    """
    Runs the full compliance assessment pipeline.
    """

    def _update_progress(current_step: int, total_steps: int, message: str):
        if progress_callback:
            progress_callback(current_step, total_steps, message)
        print(f"Progress: {current_step}/{total_steps} - {message}") # Also print to console

    total_pipeline_stages = 8 # A-H
    current_stage_num = 0

    # 1. Setup
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 1/8: Initializing pipeline and services...")
    
    cache_service = CacheService(Path("cache"))
    
    run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    project_name_safe = project.name.replace(' ', '_').replace('/', '_') if project.name else "default_project"
    output_dir = Path("output") / f"{project_name_safe}_{run_timestamp}"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _update_progress(current_stage_num, total_pipeline_stages, f"CRITICAL ERROR: Could not create output directory {output_dir}: {e}")
        return None
        
    index_root_dir = cache_service.cache_dir / "indexes"
    index_root_dir.mkdir(parents=True, exist_ok=True)

    # --- Stage A: Ingestion ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 2/8: Ingesting documents...")

    if not project.controls_dir or not project.controls_dir.exists():
        _update_progress(current_stage_num, total_pipeline_stages, "CRITICAL ERROR: Controls directory not specified or does not exist.")
        return None
    control_raw_docs: List[RawDoc] = ingest_documents(project.controls_dir, "control")
    if not control_raw_docs:
        _update_progress(current_stage_num, total_pipeline_stages, "CRITICAL ERROR: No control documents were ingested.")
        return None

    if not project.procedures_dir or not project.procedures_dir.exists():
        _update_progress(current_stage_num, total_pipeline_stages, "CRITICAL ERROR: Procedures directory not specified or does not exist.")
        return None
    procedure_raw_docs: List[RawDoc] = ingest_documents(project.procedures_dir, "procedure")
    if not procedure_raw_docs:
        _update_progress(current_stage_num, total_pipeline_stages, "CRITICAL ERROR: No procedure documents were ingested.")
        return None

    evidence_raw_docs: List[RawDoc] = []
    if project.evidences_dir and project.evidences_dir.exists():
        evidence_raw_docs = ingest_documents(project.evidences_dir, "evidence")
        if not evidence_raw_docs: # Warning, not critical if some C-P pairs might not need evidence directly
            _update_progress(current_stage_num, total_pipeline_stages, "Warning: No evidence documents were ingested.")
    else:
        _update_progress(current_stage_num, total_pipeline_stages, "Warning: Evidences directory not specified or does not exist. Proceeding without evidence.")

    # --- Stage B: Normalization ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 3/8: Normalizing documents...")
    
    control_norm_docs: List[NormDoc] = [normalize_document(doc) for doc in control_raw_docs]
    procedure_norm_docs: List[NormDoc] = [normalize_document(doc) for doc in procedure_raw_docs]
    evidence_norm_docs: List[NormDoc] = [normalize_document(doc) for doc in evidence_raw_docs]

    controls_norm_map: Dict[str, NormDoc] = {doc.id: doc for doc in control_norm_docs}
    procedures_norm_map: Dict[str, NormDoc] = {doc.id: doc for doc in procedure_norm_docs}
    # evidence_norm_map is not strictly needed if we use evidence_embed_sets_map later for text

    # --- Stage C: Embedding ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 4/8: Generating embeddings...")
    
    all_embed_sets_map: Dict[str, EmbedSet] = {}
    control_embed_sets_all: List[EmbedSet] = []
    for doc in control_norm_docs:
        embeds = generate_embeddings(doc, cache_service, settings.openai_api_key, settings.embedding_model)
        control_embed_sets_all.extend(embeds)
        for es in embeds: all_embed_sets_map[es.id] = es

    procedure_embed_sets_all: List[EmbedSet] = []
    for doc in procedure_norm_docs:
        embeds = generate_embeddings(doc, cache_service, settings.openai_api_key, settings.embedding_model)
        procedure_embed_sets_all.extend(embeds)
        for es in embeds: all_embed_sets_map[es.id] = es
        
    evidence_embed_sets_all: List[EmbedSet] = []
    for doc in evidence_norm_docs: # If evidence_norm_docs is empty, this loop is skipped
        embeds = generate_embeddings(doc, cache_service, settings.openai_api_key, settings.embedding_model)
        evidence_embed_sets_all.extend(embeds)
        for es in embeds: all_embed_sets_map[es.id] = es

    if not control_embed_sets_all or not procedure_embed_sets_all:
        _update_progress(current_stage_num, total_pipeline_stages, "CRITICAL ERROR: Failed to generate embeddings for controls or procedures.")
        return None
    if not evidence_embed_sets_all and evidence_raw_docs: # if raw evidence existed but no embeddings
         _update_progress(current_stage_num, total_pipeline_stages, "Warning: Failed to generate embeddings for evidence documents.")
         # Pipeline can proceed, but LLM might not have evidence text for some assessments.

    # --- Stage D: Indexing ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 5/8: Creating/loading vector indexes...")

    control_idx_meta = create_or_load_index(control_embed_sets_all, index_root_dir, "control", settings.embedding_model)
    procedure_idx_meta = create_or_load_index(procedure_embed_sets_all, index_root_dir, "procedure", settings.embedding_model)
    evidence_idx_meta = create_or_load_index(evidence_embed_sets_all, index_root_dir, "evidence", settings.embedding_model) # Optional for some flows

    if not control_idx_meta or not procedure_idx_meta:
        _update_progress(current_stage_num, total_pipeline_stages, "CRITICAL ERROR: Failed to create/load indexes for controls or procedures.")
        return None
    if not evidence_idx_meta and evidence_embed_sets_all: # If there were evidence embeddings but index failed
        _update_progress(current_stage_num, total_pipeline_stages, "Warning: Failed to create/load index for evidence. Evidence matching may be impacted.")

    # Load FAISS indexes and ID maps into memory
    try:
        control_faiss_index = faiss.read_index(str(control_idx_meta.index_file_path)) if control_idx_meta else None
        with open(control_idx_meta.id_mapping_path, 'r') as f: control_id_map = json.load(f) if control_idx_meta else []
        
        procedure_faiss_index = faiss.read_index(str(procedure_idx_meta.index_file_path)) if procedure_idx_meta else None
        with open(procedure_idx_meta.id_mapping_path, 'r') as f: procedure_id_map = json.load(f) if procedure_idx_meta else []

        evidence_faiss_index = faiss.read_index(str(evidence_idx_meta.index_file_path)) if evidence_idx_meta and evidence_idx_meta.index_file_path.exists() else None
        evidence_id_map: List[str] = []
        if evidence_idx_meta and evidence_idx_meta.id_mapping_path.exists():
            with open(evidence_idx_meta.id_mapping_path, 'r') as f: evidence_id_map = json.load(f)
            
    except Exception as e:
        _update_progress(current_stage_num, total_pipeline_stages, f"CRITICAL ERROR: Failed to load FAISS index objects or ID maps: {e}")
        return None

    # --- Stage E, F, G (Loop): Retrieval, Judging, Aggregation Prep ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 6/8: Performing retrieval and LLM assessments...")
    
    all_triple_assessments_list: List[TripleAssessment] = []
    
    # Estimate total steps for this stage
    # Each control chunk search for procedures is one "major" step in this part of the loop.
    # Further evidence searches and LLM calls happen within that.
    num_control_chunks = len(control_embed_sets_all)
    total_main_loop_steps = num_control_chunks 
    current_main_loop_step = 0

    for i, query_control_es in enumerate(control_embed_sets_all):
        _update_progress(
            i + 1, 
            total_main_loop_steps, 
            f"Processing Control Chunk {query_control_es.id} ({i+1}/{num_control_chunks})"
        )

        if not procedure_faiss_index or not procedure_id_map: # Should have been caught by CRITICAL ERROR above
             _update_progress(current_stage_num, total_pipeline_stages, "Skipping procedure matching for control chunk due to missing procedure index.")
             continue

        proc_matches: List[MatchSet] = retrieve_similar_chunks(
            query_embed_set=query_control_es,
            target_index_meta=procedure_idx_meta, # type: ignore
            target_embed_sets_map=all_embed_sets_map,
            k_results=settings.top_k_procedure,
            faiss_index_obj=procedure_faiss_index,
            id_map_list_obj=procedure_id_map
        )

        for proc_match in proc_matches:
            matched_proc_es = all_embed_sets_map.get(proc_match.matched_embed_set_id)
            if not matched_proc_es:
                print(f"Warning: Matched procedure EmbedSet ID {proc_match.matched_embed_set_id} not found in map. Skipping.")
                continue

            # If no evidence index or no evidence embeddings, we can't find evidence matches
            if not evidence_faiss_index or not evidence_id_map or not evidence_idx_meta or not evidence_embed_sets_all:
                # Create an assessment based on Control-Procedure only
                # print(f"Note: No evidence index/data available for C:{query_control_es.id} P:{matched_proc_es.id}. Assessing C-P pair directly.")
                assessment = assess_triplet_with_llm(
                    control_doc_id=query_control_es.norm_doc_id, procedure_doc_id=matched_proc_es.norm_doc_id, evidence_doc_id="N/A_NoEvidenceIndex",
                    control_chunk_id=query_control_es.id, procedure_chunk_id=matched_proc_es.id, evidence_chunk_id="N/A_NoEvidenceIndex",
                    control_chunk_text=query_control_es.chunk_text, procedure_chunk_text=matched_proc_es.chunk_text, evidence_chunk_text="No specific evidence chunk applicable due to missing evidence index or data.",
                    cache_service=cache_service, openai_api_key=settings.openai_api_key, llm_model_name=settings.llm_model
                )
                if assessment:
                    all_triple_assessments_list.append(assessment)
                continue # Move to next procedure match

            # Proceed with evidence matching
            evid_matches: List[MatchSet] = retrieve_similar_chunks(
                query_embed_set=matched_proc_es,
                target_index_meta=evidence_idx_meta, # type: ignore
                target_embed_sets_map=all_embed_sets_map,
                k_results=settings.top_m_evidence,
                faiss_index_obj=evidence_faiss_index,
                id_map_list_obj=evidence_id_map
            )

            if not evid_matches:
                # print(f"Note: No evidence chunks found similar to P-Chunk:{matched_proc_es.id} for C-Chunk:{query_control_es.id}. Assessing C-P-NoSpecificEvidence.")
                assessment = assess_triplet_with_llm(
                    control_doc_id=query_control_es.norm_doc_id, procedure_doc_id=matched_proc_es.norm_doc_id, evidence_doc_id="N/A_NoMatchingEvidence",
                    control_chunk_id=query_control_es.id, procedure_chunk_id=matched_proc_es.id, evidence_chunk_id="N/A_NoMatchingEvidence",
                    control_chunk_text=query_control_es.chunk_text, procedure_chunk_text=matched_proc_es.chunk_text, evidence_chunk_text="No specific evidence chunk found to be relevant after search.",
                    cache_service=cache_service, openai_api_key=settings.openai_api_key, llm_model_name=settings.llm_model
                )
                if assessment:
                    all_triple_assessments_list.append(assessment)
                continue # Move to next procedure match


            for evid_match in evid_matches:
                matched_evid_es = all_embed_sets_map.get(evid_match.matched_embed_set_id)
                if not matched_evid_es:
                    print(f"Warning: Matched evidence EmbedSet ID {evid_match.matched_embed_set_id} not found in map. Skipping.")
                    continue
                
                assessment = assess_triplet_with_llm(
                    control_doc_id=query_control_es.norm_doc_id,
                    procedure_doc_id=matched_proc_es.norm_doc_id,
                    evidence_doc_id=matched_evid_es.norm_doc_id,
                    control_chunk_id=query_control_es.id,
                    procedure_chunk_id=matched_proc_es.id,
                    evidence_chunk_id=matched_evid_es.id,
                    control_chunk_text=query_control_es.chunk_text,
                    procedure_chunk_text=matched_proc_es.chunk_text,
                    evidence_chunk_text=matched_evid_es.chunk_text,
                    cache_service=cache_service,
                    openai_api_key=settings.openai_api_key,
                    llm_model_name=settings.llm_model
                )
                if assessment:
                    all_triple_assessments_list.append(assessment)
        
        current_main_loop_step +=1 # Update progress based on outer loop (control chunks)
        # More granular progress can be added inside the loops if progress_callback is very responsive

    # --- Stage G (Post-Loop): Aggregation ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 7/8: Aggregating assessments...")
    
    all_pair_assessments: List[PairAssessment] = []
    # Group TripleAssessments by (control_doc_id, procedure_doc_id)
    grouped_triples: Dict[Tuple[str, str], List[TripleAssessment]] = collections.defaultdict(list)
    for ta in all_triple_assessments_list:
        grouped_triples[(ta.control_doc_id, ta.procedure_doc_id)].append(ta)

    for (c_doc_id, p_doc_id), group_of_triples in grouped_triples.items():
        pair_assessment = aggregate_assessments_for_pair(c_doc_id, p_doc_id, group_of_triples)
        if pair_assessment: # aggregate_assessments_for_pair always returns a PairAssessment
            all_pair_assessments.append(pair_assessment)
    
    # --- Stage H: Report Generation ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 8/8: Generating report...")
    
    report_filename_base = f"{project_name_safe}_audit_report_{run_timestamp}"
    
    # Handle report theme CSS path
    css_path_to_use: Optional[Path] = None
    if settings.report_theme and settings.report_theme.strip().lower() not in ["", "default.css", "none"]:
        # Assuming settings.report_theme could be a relative or absolute path string
        potential_css_path = Path(settings.report_theme)
        if potential_css_path.exists() and potential_css_path.is_file():
            css_path_to_use = potential_css_path.resolve()
            _update_progress(current_stage_num, total_pipeline_stages, f"Stage 8/8: Using custom report theme: {css_path_to_use}")
        else:
            _update_progress(current_stage_num, total_pipeline_stages, f"Stage 8/8: Warning - Custom report theme '{settings.report_theme}' not found or not a file. Using default styling.")

    markdown_report_path = generate_report(
        all_pair_assessments=all_pair_assessments,
        controls_map=controls_norm_map,
        procedures_map=procedures_norm_map,
        evidences_map=all_embed_sets_map, # Pass the map of all EmbedSets
        report_output_dir=output_dir,
        report_filename_base=report_filename_base,
        report_theme_css_path=css_path_to_use
    )

    if markdown_report_path:
        _update_progress(total_pipeline_stages, total_pipeline_stages, f"Pipeline completed. Report generated: {markdown_report_path}")
        project.report_path = markdown_report_path # Update project object with report path
    else:
        _update_progress(total_pipeline_stages, total_pipeline_stages, "Pipeline completed, but report generation failed.")

    return markdown_report_path

if __name__ == '__main__':
    # This is a placeholder for a test execution.
    # Setting up a full CompareProject and PipelineSettings for a direct run here is complex.
    # This would typically be tested via a UI or a dedicated test script that prepares these objects.
    print("Pipeline __init__.py executed. To run the pipeline, import and call `run_pipeline` with appropriate Project and Settings objects.")
    
    # Example of how one might set up a test (conceptual, requires valid paths and API keys):
    # from app.models.project import CompareProject
    # from app.models.settings import PipelineSettings
    # from pathlib import Path

    # test_project = CompareProject(name="Test_Pipeline_Run")
    # test_project.controls_dir = Path("path/to/your/test_controls") # Needs actual files
    # test_project.procedures_dir = Path("path/to/your/test_procedures") # Needs actual files
    # test_project.evidences_dir = Path("path/to/your/test_evidences") # Needs actual files

    # test_settings = PipelineSettings(
    #     openai_api_key="sk-your_key_here_or_set_env_var", # Best to use env var
    #     embedding_model="text-embedding-3-small", # Faster/cheaper for test
    #     llm_model="gpt-3.5-turbo", # Faster/cheaper for test
    #     top_k_procedure=2,
    #     top_m_evidence=2,
    #     # report_theme = "path/to/custom.css" # Optional
    # )

    # def my_progress_callback(current, total, message):
    #     print(f"PROGRESS: {current}/{total} - {message}")

    # if test_project.controls_dir.exists() and test_project.procedures_dir.exists():
    #     print(f"Attempting to run pipeline for project: {test_project.name}")
    #     final_report_path = run_pipeline(test_project, test_settings, my_progress_callback)
    #     if final_report_path:
    #         print(f"Pipeline finished. Report at: {final_report_path}")
    #     else:
    #         print("Pipeline run failed or did not produce a report.")
    # else:
    #     print(f"Please ensure test directories exist:\n"
    #           f"Controls: {test_project.controls_dir.resolve()}\n"
    #           f"Procedures: {test_project.procedures_dir.resolve()}")

    pass
