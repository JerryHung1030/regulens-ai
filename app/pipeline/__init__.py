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
    llm_model: str = Field(default="default_llm_model")
    local_model_path: Optional[Path] = Field(default=None)
    top_k_procedure: int = Field(default=5)
    top_m_evidence: int = Field(default=5)
    score_threshold: float = Field(default=0.7)
    report_theme: str = Field(default="default.css")
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
from .embed import generate_embeddings
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
    progress_callback: Optional[Callable[[int, int, str, int], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None
) -> Optional[Path]:
    """
    Runs the full compliance assessment pipeline.
    Supports progress updates and cancellation.
    """

    def _update_progress(current_step: int, total_steps: int, message: str):
        if progress_callback:
            percent_complete = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            percent_complete = min(percent_complete, 100)
            progress_callback(current_step, total_steps, message, percent_complete)
        print(f"Progress: {current_step}/{total_steps} - {message}")

    total_pipeline_stages = 8
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
        if not evidence_raw_docs:
            _update_progress(current_stage_num, total_pipeline_stages, "Warning: No evidence documents were ingested.")
    else:
        _update_progress(current_stage_num, total_pipeline_stages, "Warning: Evidences directory not specified or does not exist. Proceeding without evidence.")

    # --- Stage B: Normalization ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 3/8: Normalizing documents...")
    
    control_norm_docs: List[NormDoc] = [normalize_document(doc) for doc in control_raw_docs]
    procedure_norm_docs: List[NormDoc] = [normalize_document(doc) for doc in procedure_raw_docs]
    evidence_norm_docs: List[NormDoc] = [normalize_document(doc) for doc in evidence_raw_docs]

    # Create comprehensive list and populate project's unified norm_map
    all_normalized_docs: List[NormDoc] = control_norm_docs + procedure_norm_docs + evidence_norm_docs
    project.populate_norm_map(all_normalized_docs)

    # Local maps for generate_report and other pipeline stages if they specifically need them
    controls_norm_map: Dict[str, NormDoc] = {doc.id: doc for doc in control_norm_docs}
    procedures_norm_map: Dict[str, NormDoc] = {doc.id: doc for doc in procedure_norm_docs}
    # The lines assigning to project.control_norm_docs_map and project.procedure_norm_docs_map are removed
    # as project._norm_map is now the source of truth, populated by project.populate_norm_map().

    # --- Stage C: Embedding ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 4/8: Generating embeddings...")
    
    all_embed_sets_map: Dict[str, EmbedSet] = {}  # Maps chunk_id to EmbedSet
    control_embed_sets_all: List[EmbedSet] = []
    for doc in control_norm_docs:
        embeds = generate_embeddings(doc, cache_service, settings.openai_api_key, settings.embedding_model)
        control_embed_sets_all.extend(embeds)
        for es in embeds:
            all_embed_sets_map[es.id] = es

    procedure_embed_sets_all: List[EmbedSet] = []
    for doc in procedure_norm_docs:
        embeds = generate_embeddings(doc, cache_service, settings.openai_api_key, settings.embedding_model)
        procedure_embed_sets_all.extend(embeds)
        for es in embeds:
            all_embed_sets_map[es.id] = es
        
    evidence_embed_sets_all: List[EmbedSet] = []
    for doc in evidence_norm_docs:
        embeds = generate_embeddings(doc, cache_service, settings.openai_api_key, settings.embedding_model)
        evidence_embed_sets_all.extend(embeds)
        for es in embeds:
            all_embed_sets_map[es.id] = es

    if not control_embed_sets_all or not procedure_embed_sets_all:
        _update_progress(current_stage_num, total_pipeline_stages, "CRITICAL ERROR: Failed to generate embeddings for controls or procedures.")
        return None
    if not evidence_embed_sets_all and evidence_raw_docs:
        _update_progress(current_stage_num, total_pipeline_stages, "Warning: Failed to generate embeddings for evidence documents.")

    # --- Stage D: Indexing ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 5/8: Creating/loading vector indexes...")

    control_idx_meta = create_or_load_index(control_embed_sets_all, index_root_dir, "control", settings.embedding_model)
    procedure_idx_meta = create_or_load_index(procedure_embed_sets_all, index_root_dir, "procedure", settings.embedding_model)
    evidence_idx_meta = create_or_load_index(evidence_embed_sets_all, index_root_dir, "evidence", settings.embedding_model)

    if not control_idx_meta or not procedure_idx_meta:
        _update_progress(current_stage_num, total_pipeline_stages, "CRITICAL ERROR: Failed to create/load indexes for controls or procedures.")
        return None
    if not evidence_idx_meta and evidence_embed_sets_all:
        _update_progress(current_stage_num, total_pipeline_stages, "Warning: Failed to create/load index for evidence. Evidence matching may be impacted.")

    try:
        # control_faiss_index = faiss.read_index(str(control_idx_meta.index_file_path)) if control_idx_meta else None
        # with open(control_idx_meta.id_mapping_path, 'r') as f:
        #     control_id_map = json.load(f) if control_idx_meta else []
        
        procedure_faiss_index = faiss.read_index(str(procedure_idx_meta.index_file_path)) if procedure_idx_meta else None
        with open(procedure_idx_meta.id_mapping_path, 'r') as f:
            procedure_id_map = json.load(f) if procedure_idx_meta else []

        evidence_faiss_index = faiss.read_index(str(evidence_idx_meta.index_file_path)) if evidence_idx_meta and evidence_idx_meta.index_file_path.exists() else None
        evidence_id_map: List[str] = []
        if evidence_idx_meta and evidence_idx_meta.id_mapping_path.exists():
            with open(evidence_idx_meta.id_mapping_path, 'r') as f:
                evidence_id_map = json.load(f)
            
    except Exception as e:
        _update_progress(current_stage_num, total_pipeline_stages, f"CRITICAL ERROR: Failed to load FAISS index objects or ID maps: {e}")
        return None

    # --- Stage E, F, G (Loop): Retrieval, Judging, Aggregation Prep ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 6/8: Performing retrieval and LLM assessments...")
    
    all_triple_assessments_list: List[TripleAssessment] = []
    num_control_chunks = len(control_embed_sets_all)

    for i, query_control_es in enumerate(control_embed_sets_all):
        if cancel_cb and cancel_cb():
            _update_progress(current_stage_num, total_pipeline_stages, "Operation cancelled by user.")
            raise RuntimeError("Cancelled by user during Stage 6: Retrieval and LLM assessments.")
        
        _update_progress(
            current_stage_num,
            total_pipeline_stages,
            f"Stage 6/{total_pipeline_stages}: Processing Control Chunk {query_control_es.id} ({i + 1}/{num_control_chunks})"
        )

        if not procedure_faiss_index or not procedure_id_map:
            _update_progress(current_stage_num, total_pipeline_stages, "Warning: Skipping procedure matching for control chunk due to missing procedure index.")
            continue

        proc_matches: List[MatchSet] = retrieve_similar_chunks(
            query_embed_set=query_control_es,
            target_index_meta=procedure_idx_meta,  # type: ignore
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

            if not evidence_faiss_index or not evidence_id_map or not evidence_idx_meta or not evidence_embed_sets_all:
                assessment = assess_triplet_with_llm(
                    control_doc_id=query_control_es.norm_doc_id,
                    procedure_doc_id=matched_proc_es.norm_doc_id,
                    evidence_doc_id="N/A_NoEvidenceIndex",
                    control_chunk_id=query_control_es.id,
                    procedure_chunk_id=matched_proc_es.id,
                    evidence_chunk_id="N/A_NoEvidenceIndex",
                    control_chunk_text=query_control_es.chunk_text,
                    procedure_chunk_text=matched_proc_es.chunk_text,
                    evidence_chunk_text="No specific evidence chunk applicable due to missing evidence index or data.",
                    cache_service=cache_service, openai_api_key=settings.openai_api_key,
                    llm_model_name=settings.llm_model, cancel_cb=cancel_cb
                )
                if assessment: 
                    all_triple_assessments_list.append(assessment)
                if cancel_cb and cancel_cb(): 
                    raise RuntimeError("Cancelled by user (LLM assessment, no evidence index).")
                continue

            evid_matches: List[MatchSet] = retrieve_similar_chunks(
                query_embed_set=matched_proc_es,
                target_index_meta=evidence_idx_meta,  # type: ignore
                target_embed_sets_map=all_embed_sets_map,
                k_results=settings.top_m_evidence,
                faiss_index_obj=evidence_faiss_index,
                id_map_list_obj=evidence_id_map
            )

            if not evid_matches:
                assessment = assess_triplet_with_llm(
                    control_doc_id=query_control_es.norm_doc_id,
                    procedure_doc_id=matched_proc_es.norm_doc_id,
                    evidence_doc_id="N/A_NoMatchingEvidence",
                    control_chunk_id=query_control_es.id, procedure_chunk_id=matched_proc_es.id,
                    evidence_chunk_id="N/A_NoMatchingEvidence", control_chunk_text=query_control_es.chunk_text,
                    procedure_chunk_text=matched_proc_es.chunk_text,
                    evidence_chunk_text="No specific evidence chunk found to be relevant after search.",
                    cache_service=cache_service, openai_api_key=settings.openai_api_key,
                    llm_model_name=settings.llm_model, cancel_cb=cancel_cb
                )
                if assessment: 
                    all_triple_assessments_list.append(assessment)
                if cancel_cb and cancel_cb(): 
                    raise RuntimeError("Cancelled by user (LLM assessment, no matching evidence).")
                continue

            for evid_match in evid_matches:
                if cancel_cb and cancel_cb(): 
                    raise RuntimeError("Cancelled by user (before individual evidence LLM).")
                matched_evid_es = all_embed_sets_map.get(evid_match.matched_embed_set_id)
                if not matched_evid_es:
                    print(f"Warning: Matched evidence EmbedSet ID {evid_match.matched_embed_set_id} not found. Skipping.")
                    continue
                
                assessment = assess_triplet_with_llm(
                    control_doc_id=query_control_es.norm_doc_id, procedure_doc_id=matched_proc_es.norm_doc_id,
                    evidence_doc_id=matched_evid_es.norm_doc_id, control_chunk_id=query_control_es.id,
                    procedure_chunk_id=matched_proc_es.id, evidence_chunk_id=matched_evid_es.id,
                    control_chunk_text=query_control_es.chunk_text, procedure_chunk_text=matched_proc_es.chunk_text,
                    evidence_chunk_text=matched_evid_es.chunk_text, cache_service=cache_service,
                    openai_api_key=settings.openai_api_key, llm_model_name=settings.llm_model, cancel_cb=cancel_cb
                )
                if assessment: 
                    all_triple_assessments_list.append(assessment)
                if cancel_cb and cancel_cb(): 
                    raise RuntimeError("Cancelled by user (LLM assessment with evidence).")

    # --- Stage G (Post-Loop): Aggregation ---
    if cancel_cb and cancel_cb():
        _update_progress(current_stage_num, total_pipeline_stages, "Operation cancelled before Aggregation.")
        raise RuntimeError("Cancelled by user before Stage 7: Aggregation.")
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 7/8: Aggregating assessments...")
    
    all_pair_assessments: List[PairAssessment] = []
    grouped_triples: Dict[Tuple[str, str], List[TripleAssessment]] = collections.defaultdict(list)
    for ta in all_triple_assessments_list:
        grouped_triples[(ta.control_doc_id, ta.procedure_doc_id)].append(ta)

    # Create the all_norm_docs_map for aggregation step from the project's populated map
    # This ensures aggregate_assessments_for_pair can access original filenames
    # We assume project._norm_map is populated correctly by project.populate_norm_map()
    # For safety, construct it from the lists if direct access to _norm_map is not desired here.
    # However, project.populate_norm_map implies it's ready.
    # Let's create the map from all_normalized_docs list for clarity here.
    all_docs_for_aggregation_map: Dict[str, NormDoc] = {doc.id: doc for doc in all_normalized_docs}

    for (c_doc_id, p_doc_id), group_of_triples in grouped_triples.items():
        pair_assessment = aggregate_assessments_for_pair(
            c_doc_id, p_doc_id, group_of_triples, all_docs_for_aggregation_map  # Pass the map here
        )
        all_pair_assessments.append(pair_assessment)

    project.set_results(all_pair_assessments)
    if not all_pair_assessments:
        _update_progress(current_stage_num, total_pipeline_stages, f"Info: Pipeline for project '{project.name}' completed with no detailed assessment results to report.")
    
    # --- Stage H: Report Generation ---
    current_stage_num += 1
    _update_progress(current_stage_num, total_pipeline_stages, "Stage 8/8: Generating report...")
    
    report_filename_base = f"{project_name_safe}_audit_report_{run_timestamp}"
    css_path_to_use: Optional[Path] = None
    if settings.report_theme and settings.report_theme.strip().lower() not in ["", "default.css", "none"]:
        potential_css_path = Path(settings.report_theme)
        if potential_css_path.exists() and potential_css_path.is_file():
            css_path_to_use = potential_css_path.resolve()
            _update_progress(current_stage_num, total_pipeline_stages, f"Stage 8/{total_pipeline_stages}: Using custom report theme: {css_path_to_use}")
        else:
            _update_progress(current_stage_num, total_pipeline_stages, f"Stage 8/{total_pipeline_stages}: Warning - Custom report theme '{settings.report_theme}' not found. Using default.")
    
    if cancel_cb and cancel_cb():
        _update_progress(current_stage_num, total_pipeline_stages, "Operation cancelled before Report Generation.")
        raise RuntimeError("Cancelled by user before Stage 8: Report Generation.")

    # This map is for generate_report, which expects a map of all NormDocs
    # It was previously passed to aggregate_assessments_for_pair as all_docs_for_aggregation_map
    # Re-affirming its name for clarity when passing to generate_report.
    all_norm_docs_for_report_map = all_docs_for_aggregation_map

    markdown_report_path = generate_report(
        all_pair_assessments=all_pair_assessments,
        controls_map=controls_norm_map,  # Still needed by generate_report for specific control NormDocs
        procedures_map=procedures_norm_map,  # Still needed for specific procedure NormDocs
        evidences_map=all_embed_sets_map,
        all_norm_docs_map=all_norm_docs_for_report_map,  # Pass the map of all NormDocs
        report_output_dir=output_dir,
        report_filename_base=report_filename_base,
        report_theme_css_path=css_path_to_use,
        make_pdf=False,
        language=settings.language
    )

    if markdown_report_path:
        _update_progress(total_pipeline_stages, total_pipeline_stages, f"Pipeline completed. Report generated: {markdown_report_path}")
        project.report_path = markdown_report_path
    else:
        _update_progress(total_pipeline_stages, total_pipeline_stages, "Pipeline completed, but report generation failed.")

    return markdown_report_path


if __name__ == '__main__':
    print("Pipeline __init__.py executed. To run the pipeline, import and call `run_pipeline` with appropriate Project and Settings objects.")
    pass
