from __future__ import annotations

import json
import threading # For confirm_event
from pathlib import Path
from typing import List, Callable, Dict, Any, Optional, Union

import shutil # For cleaning up temp directories

from app.logger import logger
from app.models.project import CompareProject
from app.models.docs import ExternalRegulationClause, AuditTask, RawDoc, NormDoc, EmbedSet # Added RawDoc, NormDoc, EmbedSet
from app.models.run_data import ProjectRunData # Import from new module
from app.pipeline_settings import PipelineSettings # Corrected import to app.pipeline_settings
from app.pipeline.llm_utils import call_llm_api

# Import necessary functions from other pipeline modules
from app.app_paths import get_app_data_dir # Added import
from app.pipeline.ingestion import ingest_documents
from app.pipeline.normalize import normalize_document
from app.pipeline.embed import generate_embeddings
from app.pipeline.index import create_or_load_index, IndexMeta # Added IndexMeta
from app.pipeline.retrieve import retrieve_similar_chunks, MatchSet # Added MatchSet
from app.pipeline.cache import CacheService # For embedding caching if generate_embeddings uses it

# Pydantic models for GUI data structures
from pydantic import BaseModel # Ensure pydantic.BaseModel is imported

class AuditTaskUIData(BaseModel):
    id: str
    sentence: str

class AuditPlanClauseUIData(BaseModel):
    type: str = "audit_plan" # To help distinguish this message type in the GUI
    clause_id: str
    clause_title: Optional[str] = None
    tasks: List[AuditTaskUIData] = []
    no_audit_needed: bool = False
    audit_plan_generation_complete: bool = False # Flag to signal end of audit plan generation phase

def _load_run_json(run_json_path: Path) -> Optional[ProjectRunData]:
    if run_json_path.exists():
        try:
            data = json.loads(run_json_path.read_text(encoding='utf-8'))
            return ProjectRunData.from_dict(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error loading or parsing run.json from {run_json_path}: {e}")
            return None
    return None

def _save_run_json(run_data: ProjectRunData, run_json_path: Path) -> None:
    try:
        run_json_path.parent.mkdir(parents=True, exist_ok=True)
        run_json_path.write_text(json.dumps(run_data.to_dict(), indent=4, ensure_ascii=False), encoding='utf-8')
        logger.info(f"Project run data saved to {run_json_path}")
    except IOError as e:
        logger.error(f"Error saving run.json to {run_json_path}: {e}")


def load_external_regulations_from_json(external_regulations_json_path: Path) -> List[ExternalRegulationClause]:
    """
    Loads external_regulation clauses from the project's specified external_regulations JSON file.
    The JSON structure is expected to be:
    {
        "name": "Project Name",
        "C001": "第一條 目的\n條文內容...",
        "C002": "第二條 適用範圍\n條文內容...",
        ...
    }
    """
    external_regulation_clauses: List[ExternalRegulationClause] = []
    if not external_regulations_json_path.exists():
        logger.error(f"ExternalRegulations JSON file not found: {external_regulations_json_path}")
        return external_regulation_clauses

    try:
        # 確保使用 UTF-8 編碼讀取檔案
        with open(external_regulations_json_path, 'r', encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)
        
        # 處理每個條文
        for clause_id, content in data.items():
            if clause_id == "name":  # 跳過專案名稱
                continue
                
            # 分割標題和內容
            lines = content.split('\n', 1)
            title = lines[0]
            text = lines[1] if len(lines) > 1 else ""
            
            # 創建 ExternalRegulationClause 物件，包含所有必要的欄位
            clause = ExternalRegulationClause(
                id=clause_id,
                title=title,
                text=text,
                need_procedure=None,  # 初始值設為 None，將由 pipeline 決定
                tasks=[],  # 初始為空列表，將由 pipeline 填充
                subclauses=[]  # 初始為空列表
            )
            external_regulation_clauses.append(clause)
            
    except Exception as e:
        logger.error(f"Error loading external_regulations JSON: {e}")
        
    return external_regulation_clauses


def run_project_pipeline_v1_1(project: CompareProject,
                              settings: PipelineSettings,
                              progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None],
                              cancel_cb: Callable[[], bool]):
                              # confirm_event: Optional[threading.Event] = None): # Removed parameter
    """
    Main orchestrator for the V1.1 pipeline.
    """
    logger.info(f"Starting pipeline v1.1 for project: {project.name}")
    progress_callback(0.0, "Initializing pipeline...")

    if not project.external_regulations_json_path or not project.external_regulations_json_path.exists():
        logger.error("ExternalRegulations JSON path not specified or file does not exist.")
        progress_callback(1.0, "Error: ExternalRegulations JSON file not found.")
        return

    if not project.run_json_path:
        logger.error("Project run_json_path is not set.")
        progress_callback(1.0, "Error: run.json path not configured for the project.")
        return

    # Load existing run data or initialize if not present/fresh start requested
    # For now, let's assume we always load external_regulations from source JSON and then update from run.json
    # A more sophisticated resume logic might be needed later.
    
    initial_clauses = load_external_regulations_from_json(project.external_regulations_json_path)
    if not initial_clauses:
        progress_callback(1.0, "Error: No external_regulation clauses loaded. Stopping pipeline.")
        return

    project_run_data = _load_run_json(project.run_json_path)
    
    if project_run_data:
        logger.info(f"Loaded existing run data from {project.run_json_path}")
        # Merge or update initial_clauses with data from project_run_data
        # This creates a map for quick lookup
        existing_clauses_map = {c.id: c for c in project_run_data.external_regulation_clauses}
        final_clauses_for_pipeline: List[ExternalRegulationClause] = []
        for loaded_clause in initial_clauses:
            if loaded_clause.id in existing_clauses_map:
                # Update with potentially modified/populated fields from run.json
                # Pydantic models are immutable by default, so create new instance or use .copy(update=...)
                existing_version = existing_clauses_map[loaded_clause.id]
                updated_data = loaded_clause.model_dump() # Start with fresh data from source JSON
                
                # Overwrite with fields that were populated by the pipeline if they exist in run.json
                # This ensures that if source text changes, it's picked up, but pipeline results are preserved.
                if existing_version.need_procedure is not None:
                    updated_data['need_procedure'] = existing_version.need_procedure
                if existing_version.tasks: # If tasks list is not empty
                    updated_data['tasks'] = [task.model_dump() for task in existing_version.tasks]
                
                final_clauses_for_pipeline.append(ExternalRegulationClause(**updated_data))
            else:
                final_clauses_for_pipeline.append(loaded_clause)
        
        # Add clauses that might be in run.json but not in source (e.g. if source file changed)
        # This logic might need refinement based on how we want to handle discrepancies.
        # For now, source JSON is the master list.
        current_ids_in_source = {c.id for c in final_clauses_for_pipeline}
        for existing_clause in project_run_data.external_regulation_clauses:
            if existing_clause.id not in current_ids_in_source:
                logger.warning(f"Clause ID {existing_clause.id} found in run.json but not in source external_regulations. It will be ignored.")

        external_regulation_clauses_for_run = final_clauses_for_pipeline

    else:
        logger.info(f"No existing run data found at {project.run_json_path}, or starting fresh.")
        external_regulation_clauses_for_run = initial_clauses
        # Initialize ProjectRunData and save it immediately
        project_run_data = ProjectRunData(project_name=project.name, external_regulation_clauses=external_regulation_clauses_for_run)
        _save_run_json(project_run_data, project.run_json_path)


    if not external_regulation_clauses_for_run:
        progress_callback(1.0, "No external_regulation clauses to process. Stopping pipeline.")
        return

    # --- Step 1: Need-Check ---
    if cancel_cb():
        progress_callback(1.0, "Pipeline cancelled.")
        return
    progress_callback(0.1, "Starting Step 1: Need-Check...")
    # external_regulation_clauses_for_run = execute_need_check_step(external_regulation_clauses_for_run, project.run_json_path, settings, cancel_cb)
    # Update run_data and save (within execute_need_check_step or here)
    execute_need_check_step(
        external_regulation_clauses=external_regulation_clauses_for_run, 
        project_run_json_path=project.run_json_path,
        current_project_run_data=project_run_data, # Pass the main run data object
        settings=settings, 
        progress_callback=progress_callback, # Pass down for finer-grained progress
        cancel_cb=cancel_cb
    )
    # _save_run_json is now called within execute_need_check_step after each update.
    logger.info("Step 1: Need-Check completed.")


    # --- Step 2: Audit-Plan ---
    if cancel_cb():
        progress_callback(1.0, "Pipeline cancelled.")
        return
    progress_callback(0.3, "Starting Step 2: Audit-Plan...")
    # external_regulation_clauses_for_run = execute_audit_plan_step(external_regulation_clauses_for_run, project.run_json_path, settings, cancel_cb)
    # Update run_data and save
    execute_audit_plan_step(
        external_regulation_clauses=external_regulation_clauses_for_run,
        project_run_json_path=project.run_json_path,
        current_project_run_data=project_run_data,
        settings=settings,
        progress_callback=progress_callback,
        cancel_cb=cancel_cb
    )
    logger.info("Step 2: Audit-Plan completed.")

    # --- Pause for user confirmation before Search step --- # REMOVED
    # if confirm_event:
        # The audit_plan_generation_complete=True message should have been sent by execute_audit_plan_step
        # The button in UI should be enabled by that signal.
        # Now, wait for the user to press it.
        # logger.info("Audit plan generated. Waiting for user confirmation to proceed to Search step...")
        # progress_callback(0.6, "等待使用者確認以開始文件檢索...") # Message indicating waiting state
        # confirm_event.wait()  # Block until main_window sets the event
        # confirm_event.clear() # Clear the event for potential future use
        # logger.info("User confirmed. Proceeding with Search step.")
        # Optionally, send another progress message that confirmation received, though next step's start message will also show.
        # progress_callback(0.6, "Confirmation received. Starting Search step...")

    # --- Future Steps (3 & 4) would follow here ---
    # Step 3: Procedure Association (Search)
    if cancel_cb():
        progress_callback(1.0, "Pipeline cancelled.")
        return
    progress_callback(0.6, "Starting Step 3: Search for Procedures...")
    execute_search_step(
        external_regulation_clauses=external_regulation_clauses_for_run,
        project=project, # Pass the whole project for paths
        current_project_run_data=project_run_data,
        settings=settings,
        progress_callback=progress_callback,
        cancel_cb=cancel_cb
    )
    logger.info("Step 3: Search completed.")


    # Step 4: Evidence Assessment (Judge)
    if cancel_cb():
        progress_callback(1.0, "Pipeline cancelled.")
        return
    progress_callback(0.8, "Starting Step 4: Judging Compliance...")
    execute_judge_step(
        external_regulation_clauses=external_regulation_clauses_for_run,
        project_run_json_path=project.run_json_path, # For saving progress
        current_project_run_data=project_run_data,
        settings=settings,
        progress_callback=progress_callback,
        cancel_cb=cancel_cb
    )
    logger.info("Step 4: Judging completed.")

    progress_callback(1.0, "Pipeline v1.1 completed successfully.")
    logger.info(f"Pipeline v1.1 finished for project: {project.name}")

# Placeholder for PipelineSettings if it's not defined elsewhere yet
# This should ideally be in app.settings or a dedicated models file.
# from pydantic import BaseModel
# class PipelineSettings(BaseModel):
#     llm_model_need_check: str = "default_need_check_model"
#     llm_model_audit_plan: str = "default_audit_plan_model"
#     llm_model_judge: str = "default_judge_model" # For future step
#     # Add other settings as needed, e.g., API keys, base URLs for LLMs
#     # retrieval_top_k: int = 5 # Example from previous settings
#     # audit_retrieval_top_k: int # This was added to config_default.yaml
#     # llm_model_need_check: str
#     # llm_model_audit_plan: str
#     # llm_model_judge: str

# Need to define execute_need_check_step and execute_audit_plan_step
# Also, the LLM interaction helper.
# These will be added in subsequent steps.

def execute_need_check_step(
    external_regulation_clauses: List[ExternalRegulationClause],
    project_run_json_path: Path,
    current_project_run_data: ProjectRunData, # To update and save the overall run.json
    settings: PipelineSettings,
    progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None], # For detailed progress
    cancel_cb: Callable[[], bool]
) -> List[ExternalRegulationClause]:
    """
    Executes Step 1: Need-Check for each external_regulation clause.
    Updates need_procedure attribute and saves to run.json progressively.
    """
    total_clauses = len(external_regulation_clauses)
    clauses_processed = 0

    for idx, clause in enumerate(external_regulation_clauses):
        if cancel_cb():
            logger.info("Need-Check step cancelled.")
            break # Exit loop if cancellation requested

        if clause.need_procedure is not None: # Already processed
            logger.debug(f"Skipping Need-Check for clause {clause.id} as it's already determined.")
            clauses_processed +=1
            # Update progress based on overall pipeline percentage for this step (e.g. Step 1 is 0.1 to 0.3)
            base_progress = 0.1 
            step_progress_span = 0.2 # Step 1 contributes 20% of total progress
            current_step_progress = (clauses_processed / total_clauses) * step_progress_span
            progress_callback(base_progress + current_step_progress, f"Need-Check: Clause {clause.id} (skipped)")
            continue

        logger.info(f"Performing Need-Check for clause: {clause.id} - {clause.text[:50]}...")
        
        # Construct prompt for LLM
        # Basic prompt, can be enhanced with more context or specific instructions
        prompt = (
            f"Determine if the following external_regulation clause requires a detailed audit procedure to verify its implementation. "
            f"Respond with a JSON object containing a single key 'requires_procedure' with a boolean value (true or false).\n\n"
            f"ExternalRegulation Clause Text: \"{clause.text}\""
        )

        llm_response = call_llm_api(
            prompt=prompt,
            model_name=settings.llm_model_need_check,
            api_key=settings.openai_api_key,
            expected_response_type="boolean"
        )

        if llm_response is not None and isinstance(llm_response, bool):
            clause.need_procedure = llm_response
            logger.info(f"Need-Check for clause {clause.id}: {llm_response}")
        else:
            clause.need_procedure = None # Mark as undetermined on error
            logger.error(f"Failed to determine need_procedure for clause {clause.id}. LLM response: {llm_response}")
            # Optionally, implement retry logic or specific error handling here

        clauses_processed +=1
        
        # Update the specific clause in current_project_run_data.external_regulation_clauses
        # This assumes current_project_run_data.external_regulation_clauses is the same list object
        # or requires finding and updating the clause by ID if it's a copy.
        # For simplicity, if external_regulation_clauses is a mutable list shared, direct update works.
        # Otherwise:
        for i, run_clause in enumerate(current_project_run_data.external_regulation_clauses):
            if run_clause.id == clause.id:
                current_project_run_data.external_regulation_clauses[i] = clause
                break
        _save_run_json(current_project_run_data, project_run_json_path)
        
        base_progress = 0.1
        step_progress_span = 0.2 # Step 1 is 10% to 30%
        current_step_progress = (clauses_processed / total_clauses) * step_progress_span
        progress_callback(base_progress + current_step_progress, f"Need-Check: Clause {clause.id} -> {clause.need_procedure}")

    return external_regulation_clauses


def execute_audit_plan_step(
    external_regulation_clauses: List[ExternalRegulationClause],
    project_run_json_path: Path,
    current_project_run_data: ProjectRunData,
    settings: PipelineSettings,
    progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None],
    cancel_cb: Callable[[], bool]
) -> List[ExternalRegulationClause]:
    """
    Executes Step 2: Audit-Plan for each relevant external_regulation clause.
    Generates audit tasks and saves to run.json progressively.
    """
    base_progress = 0.3  # Progress before this step starts
    step_progress_span = 0.3  # This step spans from 30% to 60%

    total_clauses_in_step = len(external_regulation_clauses)
    clauses_iterated_in_step = 0

    if total_clauses_in_step == 0:
        logger.info("No external_regulation clauses to process for audit planning.")
        progress_callback(base_progress + step_progress_span, "Audit-Plan: No external_regulation clauses")
        # Send completion signal even if no clauses
        final_completion_message = AuditPlanClauseUIData(
            clause_id="summary",
            clause_title="Audit Plan Generation Summary",
            audit_plan_generation_complete=True
        )
        progress_callback(base_progress + step_progress_span, final_completion_message)
        return external_regulation_clauses

    for clause in external_regulation_clauses:
        if cancel_cb():
            logger.info("Audit-Plan step cancelled.")
            break
        
        clauses_iterated_in_step += 1
        current_progress_within_step = (clauses_iterated_in_step / total_clauses_in_step) * step_progress_span
        overall_progress = base_progress + current_progress_within_step

        if not clause.need_procedure:
            logger.debug(f"Clause {clause.id} does not require an audit procedure.")
            message = AuditPlanClauseUIData(
                clause_id=clause.id,
                clause_title=clause.title,
                no_audit_needed=True
            )
            progress_callback(overall_progress, message)
            continue

        if clause.tasks:  # Already has tasks from a previous run
            logger.debug(f"Skipping Audit-Plan generation for clause {clause.id} as tasks already exist.")
            ui_tasks = [AuditTaskUIData(id=t.id, sentence=t.sentence) for t in clause.tasks]
            message = AuditPlanClauseUIData(
                clause_id=clause.id,
                clause_title=clause.title,
                tasks=ui_tasks,
                no_audit_needed=False
            )
            progress_callback(overall_progress, message)
            continue

        logger.info(f"Performing Audit-Plan for clause: {clause.id} - {clause.title[:50]}...")

        prompt = (
            f"Act as an auditor validating compliance for the external_regulation clause: '{clause.text}'.\n"
            f"Your goal is to generate **one or more effective search queries (audit task sentences)** to find supporting evidence in internal documentation.\n"
            f"Each query should be precise and target text that directly confirms, defines, or exemplifies a specific aspect of the external_regulation clause.\n"
            f"If the external_regulation clause has multiple distinct components or requirements, generate a separate, focused query for each.\n"
            f"For example, if a clause states 'A is X and B is Y', you might generate one query for 'A is X' and another for 'B is Y'.\n"
            f"Return a JSON object containing a single key 'audit_tasks'. The value of 'audit_tasks' must be a list of dictionaries.\n"
            f"Each dictionary in the list must have an 'id' (e.g., 'task_001', 'task_002', ...) and a 'sentence' (your generated search query for that specific aspect).\n"
            f"Ensure IDs are unique for tasks generated for the same clause (e.g., task_001, task_002).\n\n"
            f"ExternalRegulation Clause Text: \"{clause.text}\""
        )

        llm_response = call_llm_api(
            prompt=prompt,
            model_name=settings.llm_model_audit_plan,
            api_key=settings.openai_api_key,
            expected_response_type="json_object" # Expecting a JSON object with 'audit_tasks' key
        )

        clause.tasks = [] # Initialize/clear tasks for this clause before processing LLM response

        if llm_response and isinstance(llm_response, dict) and 'audit_tasks' in llm_response:
            tasks_data = llm_response['audit_tasks']
            if isinstance(tasks_data, list):
                if not tasks_data: # LLM returned an empty list of tasks
                    logger.info(f"LLM returned an empty list of audit tasks for clause {clause.id}.")
                    # clause.tasks remains empty, which is the correct state.
                else:
                    for task_idx, task_data in enumerate(tasks_data):
                        if isinstance(task_data, dict) and "id" in task_data and "sentence" in task_data:
                            try:
                                audit_task = AuditTask(id=str(task_data["id"]), sentence=str(task_data["sentence"]))
                                clause.tasks.append(audit_task)
                            except Exception as e: # Pydantic validation error or other issues
                                logger.error(f"Error creating AuditTask from data {task_data} for clause {clause.id}, task index {task_idx}: {e}")
                        else:
                            logger.error(f"Invalid task data format in list for clause {clause.id}, task index {task_idx}: {task_data}")
                    
                    if clause.tasks: # Log only if tasks were successfully created
                        task_ids = ", ".join([t.id for t in clause.tasks])
                        logger.info(f"Audit-Plan for clause {clause.id} generated {len(clause.tasks)} tasks: {task_ids}")
                    else: # Tasks list is empty due to errors in processing individual task data
                        logger.error(f"No valid audit tasks were processed for clause {clause.id} from LLM response, though tasks data was present.")

            else:
                logger.error(f"LLM response for clause {clause.id} has 'audit_tasks' but it's not a list: {tasks_data}")
                # clause.tasks remains empty
        else:
            logger.error(f"Failed to generate audit tasks or invalid JSON object structure for clause {clause.id}. LLM response: {llm_response}")
            # clause.tasks remains empty
            
        # Update and save run.json
        for i, run_clause in enumerate(current_project_run_data.external_regulation_clauses):
            if run_clause.id == clause.id:
                current_project_run_data.external_regulation_clauses[i] = clause
                break
        _save_run_json(current_project_run_data, project_run_json_path)

        ui_tasks = [AuditTaskUIData(id=t.id, sentence=t.sentence) for t in clause.tasks]
        message = AuditPlanClauseUIData(
            clause_id=clause.id,
            clause_title=clause.title,
            tasks=ui_tasks,
            no_audit_needed=False # It needed a procedure, tasks may or may not have been generated
        )
        progress_callback(overall_progress, message)

    # After the loop, send a final message to indicate audit plan generation phase is complete
    final_completion_message = AuditPlanClauseUIData(
        clause_id="summary", # Using "summary" or a special ID for this signal
        clause_title="Audit Plan Generation Summary", # Optional: A title for this summary message
        audit_plan_generation_complete=True
    )
    # Ensure this final message is sent at the end progress point of this step
    progress_callback(base_progress + step_progress_span, final_completion_message)
        
    return external_regulation_clauses


def execute_search_step(
    external_regulation_clauses: List[ExternalRegulationClause],
    project: CompareProject,
    current_project_run_data: ProjectRunData,
    settings: PipelineSettings,
    progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None],
    cancel_cb: Callable[[], bool]
):
    """
    Executes Step 3: Search for relevant procedure chunks for each audit task.
    """
    logger.info("Starting Search Step: Processing procedure documents...")
    if not project.procedure_doc_paths:  # 改為更通用的名稱
        logger.warning("No procedure document paths found in project. Skipping search step.")
        progress_callback(0.8, "Search: No procedure documents to process.")
        return

    # --- Procedure Document Processing ---
    raw_docs_procedures: List[RawDoc] = ingest_documents(project.procedure_doc_paths, "procedure")
    if not raw_docs_procedures:
        logger.warning("No raw procedure documents were ingested. Skipping search step.")
        progress_callback(0.8, "Search: No procedure documents ingested.")
        return
    
    norm_docs_procedures: List[NormDoc] = [normalize_document(doc) for doc in raw_docs_procedures]
    
    # Store NormDoc original filenames for later reference in task.top_k
    norm_doc_id_to_filename: Dict[str, str] = {nd.id: nd.metadata.get("original_filename", "Unknown Filename") for nd in norm_docs_procedures}

    # Initialize CacheService for embeddings if needed by generate_embeddings
    # This path should ideally be configurable or derived from project structure
    # cache_service = CacheService(Path(f"projects/{project.name}/cache/embeddings")) # Old way
    cache_service = CacheService(project_name=project.name) # New way

    all_proc_embed_sets: List[EmbedSet] = []
    for norm_doc in norm_docs_procedures:
        if cancel_cb(): break
        api_key = getattr(settings, 'openai_api_key', '')
        embeds = generate_embeddings(norm_doc, cache_service, api_key, settings.embedding_model)
        all_proc_embed_sets.extend(embeds)
    
    if cancel_cb() or not all_proc_embed_sets:
        logger.info("Search step cancelled or no procedure embeddings generated.")
        progress_callback(0.8, "Search: Cancelled or no procedure embeddings.")
        return

    # Create temporary FAISS index for procedures
    # Create temporary FAISS index for procedures
    import hashlib # Ensure hashlib is imported
    # import tempfile # Ensure tempfile is imported (though we are moving away from it) -> No longer needed for path
    # Import get_app_data_dir if not already imported at the top -> Handled by global import

    project_path_hash = hashlib.md5(str(project.run_json_path.parent).encode('utf-8')).hexdigest()
    
    # Modify this part for the FAISS index directory
    # temp_index_dir = Path(tempfile.gettempdir()) / f"regulens_temp_index_{project_path_hash}" # Old way
    temp_index_dir = get_app_data_dir() / "cache" / "faiss_index" / f"project_{project_path_hash}" # New way
    temp_index_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Creating FAISS index for procedures at {temp_index_dir}...")
    proc_index_meta: Optional[IndexMeta] = create_or_load_index(
        all_proc_embed_sets, temp_index_dir, f"procedures_{project_path_hash}", settings.embedding_model
    )

    if not proc_index_meta:
        logger.error("Failed to create procedure FAISS index. Aborting search step.")
        progress_callback(0.8, "Search: Failed to create procedure index.")
        # Clean up the new directory if creation fails
        if temp_index_dir.exists():
            try:
                shutil.rmtree(temp_index_dir) 
            except OSError as e:
                logger.error(f"Error removing FAISS index directory {temp_index_dir} after creation failure: {e}")
        return

    # --- Iterate through Audit Tasks ---
    total_tasks_to_search = sum(len(c.tasks) for c in external_regulation_clauses if c.need_procedure and c.tasks)
    tasks_searched = 0
    
    # Create a map of all EmbedSets for easy lookup by retrieve_similar_chunks
    all_embed_sets_map: Dict[str, EmbedSet] = {es.id: es for es in all_proc_embed_sets}


    for clause_idx, clause in enumerate(external_regulation_clauses):
        if not clause.need_procedure or not clause.tasks:
            continue
        if cancel_cb(): break

        for task_idx, task in enumerate(clause.tasks):
            if cancel_cb(): break
            
            # TODO: Should check if task.top_k is already populated and not empty.
            # The current model has default_factory=list, so it's always a list.
            # We should perhaps initialize it to None to distinguish.
            if task.top_k and len(task.top_k) > 0: 
                logger.debug(f"Skipping search for task '{task.id}' as top_k evidence already exists.")
                tasks_searched += 1
                # Update progress
                base_progress = 0.6 # Search step is 60-80%
                step_progress_span = 0.2
                current_task_progress = (tasks_searched / total_tasks_to_search) * step_progress_span if total_tasks_to_search > 0 else 0
                progress_callback(base_progress + current_task_progress, f"Search: Task {task.id} (skipped)")
                continue

            logger.info(f"Searching for task: {task.id} - {task.sentence[:50]}...")

            # Embed the task sentence. This needs a way to embed a single string.
            # Reusing generate_embeddings for a single, temporary NormDoc.
            # This is a bit hacky; a dedicated embed_single_text function would be cleaner.
            temp_task_norm_doc = NormDoc(id=f"task_{task.id}_query", raw_doc_id="task_query", 
                                         text_content=task.sentence, sections=[], metadata={}, doc_type="task_query_text")
            task_embed_sets = generate_embeddings(temp_task_norm_doc, cache_service, api_key, settings.embedding_model)
            
            if not task_embed_sets:
                logger.error(f"Failed to generate embedding for task: {task.id}")
                tasks_searched += 1
                continue
            
            task_embedding = task_embed_sets[0] # Assuming one EmbedSet for the short sentence

            matches: List[MatchSet] = retrieve_similar_chunks(
                query_embed_set=task_embedding,
                target_index_meta=proc_index_meta,
                target_embed_sets_map=all_embed_sets_map, # Map of EmbedSet.id to EmbedSet for procedure chunks
                k_results=settings.audit_retrieval_top_k,
                # faiss_index_obj and id_map_list_obj are loaded by retrieve_similar_chunks
            )
            
            task.top_k = [] # Clear previous results if any, or initialize
            for match in matches:
                matched_embed_set = all_embed_sets_map.get(match.matched_embed_set_id)
                if matched_embed_set:
                    source_filename = norm_doc_id_to_filename.get(matched_embed_set.norm_doc_id, "Unknown Source TXT")
                    # Page number might be in matched_embed_set.metadata if populated during embedding/chunking
                    page_no = matched_embed_set.metadata.get("page_number", "N/A") # Example key
                    task.top_k.append({
                        "excerpt": matched_embed_set.chunk_text,
                        "source_txt": source_filename,
                        "page_no": page_no,
                        "score": match.score
                    })
            
            logger.info(f"Found {len(task.top_k)} evidence snippets for task {task.id}")
            tasks_searched += 1

            # Update and save run.json (after each task or each clause)
            # For now, saving after each task to ensure progress is kept.
            # This might be too frequent for large projects.
            current_project_run_data.external_regulation_clauses[clause_idx] = clause # Ensure the main list is updated
            _save_run_json(current_project_run_data, project.run_json_path)

            base_progress = 0.6 # Search step is 60-80%
            step_progress_span = 0.2
            current_task_progress = (tasks_searched / total_tasks_to_search) * step_progress_span if total_tasks_to_search > 0 else 0
            progress_callback(base_progress + current_task_progress, f"Search: Task {task.id} ({len(task.top_k)} found)")

    # Clean up temporary FAISS index directory
    try:
        shutil.rmtree(temp_index_dir)
        logger.info(f"Removed temporary index directory: {temp_index_dir}")
    except OSError as e:
        logger.error(f"Error removing temporary index directory {temp_index_dir}: {e}")


def execute_judge_step(
    external_regulation_clauses: List[ExternalRegulationClause],
    project_run_json_path: Path,
    current_project_run_data: ProjectRunData,
    settings: PipelineSettings,
    progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None],
    cancel_cb: Callable[[], bool]
):
    """
    Executes Step 4: Judge compliance for each ExternalRegulationClause based on aggregated evidence from its tasks.
    """
    logger.info("Starting Judge Step (Clause-level)...")
    
    clauses_to_judge = []
    for clause in external_regulation_clauses:
        # Only judge if it needs a procedure, has tasks, and hasn't been judged at clause-level yet.
        if clause.need_procedure and clause.tasks and clause.metadata.get('clause_compliant') is None:
            # Further check if there's any evidence in any task.
            # If all tasks have no top_k, we might still "judge" it as non-compliant due to lack of evidence.
            clauses_to_judge.append(clause)

    if not clauses_to_judge:
        logger.info("No clauses require judging.")
        progress_callback(1.0, "Judge: No clauses to judge.") # Assuming Judge is 80-100%
        return

    judged_clauses_count = 0
    total_clauses_to_judge_count = len(clauses_to_judge)
    base_progress = 0.8  # Judge step starts at 80%
    step_progress_span = 0.2 # Judge step spans 20% of total progress

    for clause_idx_in_main_list, clause in enumerate(current_project_run_data.external_regulation_clauses): # Iterate with index for saving
        # Find the clause in our filtered list
        current_clause_to_process = next((c for c in clauses_to_judge if c.id == clause.id), None)
        if not current_clause_to_process:
            # This clause from the main list either didn't need judging or wasn't in clauses_to_judge
            continue

        if cancel_cb():
            logger.info("Judge step cancelled.")
            break
        
        logger.info(f"Judging clause: {clause.id} - {clause.title[:50]}...")

        # 1. Collect all evidence for the clause
        all_evidence_texts = []
        for task_idx, task in enumerate(clause.tasks):
            if task.top_k:
                for ev_idx, ev_item in enumerate(task.top_k):
                    # Using a more detailed evidence header
                    evidence_header = f"Evidence for Task '{task.id}' ({task.sentence[:30]}...), Snippet {ev_idx+1}"
                    evidence_detail = f"(Source: {ev_item.get('source_txt', 'N/A')}, Page: {ev_item.get('page_no', 'N/A')}, Score: {ev_item.get('score', 0.0):.2f})"
                    all_evidence_texts.append(f"{evidence_header} {evidence_detail}:\n{ev_item.get('excerpt', '')}")
        
        if not all_evidence_texts:
            evidence_prompt_str = "No evidence was retrieved for this external_regulation clause through any of its audit tasks."
            logger.info(f"No evidence found for clause {clause.id}. Proceeding with judgment based on lack of evidence.")
        else:
            evidence_prompt_str = "\n\n".join(all_evidence_texts)

        # 2. Construct Clause-Level Prompt
        prompt = (
            f"Your task is to determine if the provided 'Aggregated Evidence' (extracted from internal company documents) adequately demonstrates "
            f"that the company has a documented procedure or policy in place that corresponds to the 'ExternalRegulation Clause' (from external regulations). "
            f"Focus strictly on whether the internal documentation addresses the requirements of the external_regulation clause from a documentation standpoint, "
            f"not on whether the procedures are perfectly implemented in practice.\n\n"
            
            f"ExternalRegulation Clause ID: {clause.id}\n"
            f"ExternalRegulation Clause Text (External Regulation): \"{clause.text}\"\n\n"
            f"Aggregated Evidence (from Internal Company Documents):\n{evidence_prompt_str}\n\n"
            
            f"Respond with a JSON object containing the following keys:\n"
            f"1. 'compliant': boolean (Set to true if the internal documentation, as shown in the 'Aggregated Evidence', adequately documents a procedure or policy that addresses the 'ExternalRegulation Clause'. Set to false otherwise, including if evidence is insufficient or irrelevant).\n"
            f"2. 'compliance_description': string (Explain how the provided 'Aggregated Evidence' demonstrates documented compliance or where the internal documentation falls short in addressing the 'ExternalRegulation Clause'. Quote or refer to specific parts of the evidence if helpful to illustrate the connection or gap).\n"
            f"3. 'improvement_suggestions': string (If 'compliant' is false, or if documentation only partially addresses the clause, suggest specific additions or changes to the internal documentation to make it fully address the 'ExternalRegulation Clause'. If 'compliant' is true and documentation is comprehensive for this clause, state that no further documentation improvements are suggested based on the provided evidence for this specific clause.)\n\n"
            
            f"**Your entire assessment for the ExternalRegulation Clause must be derived SOLELY from the text presented in the 'Aggregated Evidence' section above.**\n"
            f"Based *only* on the provided 'Aggregated Evidence', does the internal documentation show a corresponding procedure or policy for the 'ExternalRegulation Clause'? Provide your assessment in the specified JSON format."
        )

        llm_response = call_llm_api(
            prompt=prompt,
            model_name=settings.llm_model_judge,
            api_key=settings.openai_api_key,
            expected_response_type="json_object"
        )

        # 3. Process LLM Response and Store Judgment
        clause_compliant_status = None
        clause_compliance_desc = "Error: Failed to get valid compliance description from LLM for clause."
        clause_improvement_sugg = "Error: Failed to get valid improvement suggestions from LLM for clause."

        if llm_response and isinstance(llm_response, dict) and "compliant" in llm_response:
            clause_compliant_status = llm_response.get("compliant")
            clause_compliance_desc = llm_response.get("compliance_description", "")
            clause_improvement_sugg = llm_response.get("improvement_suggestions", "")

            if not clause_compliance_desc:
                logger.warning(f"LLM response for clause {clause.id} is missing 'compliance_description'. Storing as empty string.")
            if not clause_improvement_sugg:
                logger.warning(f"LLM response for clause {clause.id} is missing 'improvement_suggestions'. Storing as empty string.")
            
            logger.info(f"Judgment for clause {clause.id}: Compliant={clause_compliant_status}")
            logger.debug(f"Clause {clause.id} - Compliance Description: {clause_compliance_desc[:100]}...")
            logger.debug(f"Clause {clause.id} - Improvement Suggestions: {clause_improvement_sugg[:100]}...")
        else:
            logger.error(f"Failed to judge compliance for clause {clause.id}. LLM response: {llm_response}")

        clause.metadata['clause_compliant'] = clause_compliant_status
        clause.metadata['clause_compliance_description'] = clause_compliance_desc
        clause.metadata['clause_improvement_suggestions'] = clause_improvement_sugg

        # 4. Propagate Judgment to Tasks
        for task in clause.tasks:
            task.compliant = clause_compliant_status
            task.metadata["compliance_description"] = clause_compliance_desc
            task.metadata["improvement_suggestions"] = clause_improvement_sugg
            task.metadata.pop("judge_reasoning", None) # Remove old task-specific key if it exists
        
        current_project_run_data.external_regulation_clauses[clause_idx_in_main_list] = clause # Update in main list
        _save_run_json(current_project_run_data, project_run_json_path)
        
        judged_clauses_count += 1
        current_clause_progress = (judged_clauses_count / total_clauses_to_judge_count) * step_progress_span
        progress_callback(base_progress + current_clause_progress, f"Judge: Clause {clause.id} -> Compliant={clause_compliant_status}")


if __name__ == '__main__':
    # This is a basic test runner.
    # In a real scenario, CompareProject and PipelineSettings would be instantiated properly.
    
    # Create a dummy project
    mock_project_dir = Path("temp_pipeline_test_project")
    mock_project_dir.mkdir(parents=True, exist_ok=True)
    
    mock_external_regulations_data = {
        "name": "Test ExternalRegulations",
        "C001": "第一條 目的\n條文內容...",
        "C002": "第二條 適用範圍\n條文內容..."
    }
    external_regulations_json_file = mock_project_dir / "external_regulations.json"
    external_regulations_json_file.write_text(json.dumps(mock_external_regulations_data, indent=4, ensure_ascii=False), encoding='utf-8')

    # Dummy run.json (optional, to test loading)
    # mock_run_data = {
    #     "project_name": "TestProject",
    #     "external_regulation_clauses": [
    #         {"id": "CTRL001", "text": "Systems must have access external_regulation mechanisms.", "need_procedure": True, "tasks": [], "metadata":{}},
    #     ]
    # }
    # run_json_file = mock_project_dir / "run.json"
    # run_json_file.write_text(json.dumps(mock_run_data, indent=4))


    test_project = CompareProject(name="TestProject")
    test_project.external_regulations_json_path = external_regulations_json_file
    test_project.run_json_path = mock_project_dir / "run.json" # Important: set this path

    # Dummy settings
    # Ensure PipelineSettings is defined or imported correctly
    # For this test, if PipelineSettings is not fully defined, we might need a mock or partial definition.
    # Assuming a basic definition for now:
    class MockPipelineSettings:
        llm_model_need_check: str = "mock_need_check_model"
        llm_model_audit_plan: str = "mock_audit_plan_model"
        llm_model_judge: str = "mock_judge_model"
        openai_api_key: str = "sk-test-placeholder-main-pipeline" # Add placeholder for tests
        embedding_model: str = "text-embedding-ada-002" # Add placeholder
        audit_retrieval_top_k: int = 3 # Add placeholder

    test_settings = MockPipelineSettings()

    def mock_progress_callback(progress: float, message: Union[str, AuditPlanClauseUIData]):
        if isinstance(message, str):
            print(f"Progress: {progress*100:.0f}% - {message}")
        else: # It's an AuditPlanClauseUIData object
            print(f"Progress: {progress*100:.0f}% - Audit Plan Data: {message.model_dump_json(indent=2)}")


    def mock_cancel_cb() -> bool:
        return False

    print(f"--- Running Test Pipeline for Project: {test_project.name} ---")
    print(f"ExternalRegulations JSON: {test_project.external_regulations_json_path}")
    print(f"Run JSON: {test_project.run_json_path}")
    
    # Clean up previous run.json if it exists to test initialization
    if test_project.run_json_path.exists():
        test_project.run_json_path.unlink()

    # For testing the confirmation event, create a dummy event
    dummy_confirm_event = threading.Event()
    
    # To test the blocking, you'd typically run the pipeline in a separate thread
    # and then set the event from the main thread after a delay.
    # For this simple __main__, we can just set it immediately after starting if we want it to proceed,
    # or set up a concurrent way to trigger it.
    
    # Example: Start pipeline then set event after a few seconds (requires threading for run_project_pipeline_v1_1)
    # For non-threaded __main__ test, it will block indefinitely if confirm_event is passed and not set.
    # So, either pass None, or ensure it's set.
    
    # Let's test by passing None first, meaning no blocking.
    print("--- Running Test Pipeline (no confirmation wait) ---")
    run_project_pipeline_v1_1(test_project, test_settings, mock_progress_callback, mock_cancel_cb, confirm_event=None)
    print("--- Test Pipeline Run (no confirmation wait) Finished ---")

    # To test with confirmation:
    # 1. Re-init run.json if needed
    if test_project.run_json_path.exists():
         test_project.run_json_path.unlink()
    # 2. Define a simple target for a thread
    pipeline_thread = threading.Thread(target=run_project_pipeline_v1_1, 
                                       args=(test_project, test_settings, mock_progress_callback, mock_cancel_cb, dummy_confirm_event))
    
    print("\n--- Running Test Pipeline (with confirmation wait in 3s) ---")
    pipeline_thread.start()
    
    # Simulate waiting for a bit, then confirming
    time_to_wait = 3 # seconds
    print(f"Simulating user action: Confirming in {time_to_wait} seconds...")
    import time
    time.sleep(time_to_wait)
    dummy_confirm_event.set()
    
    pipeline_thread.join() # Wait for the pipeline thread to complete
    print("--- Test Pipeline Run (with confirmation wait) Finished ---")

    # Corrected indentation for this block
    if test_project.run_json_path.exists():
        print("Contents of run.json:")
        print(test_project.run_json_path.read_text())
    
    # shutil.rmtree(mock_project_dir) # Clean up
    print(f"Test artifacts in {mock_project_dir}")

# Ensure ExternalRegulationClause model is updated to include need_procedure: Optional[bool] = None
# and tasks: List[AuditTask] = Field(default_factory=list)
# This needs to be done in app/models/docs.py
# Example:
# class ExternalRegulationClause(BaseModel):
#     id: str
#     text: str
#     metadata: Dict[str, Any] = Field(default_factory=dict)
#     need_procedure: Optional[bool] = None
#     tasks: List[AuditTask] = Field(default_factory=list)

# Similarly, AuditTask if not fully defined:
# class AuditTask(BaseModel):
#     id: str
#     sentence: str # Or 'text' or 'description'
#     # other fields like status, findings from original request can be added
#     metadata: Dict[str, Any] = Field(default_factory=dict)

# PipelineSettings also needs to be formally defined, likely in app.settings.py or a new app.models.settings.py
# For example, in app.settings.py:
# from pydantic import BaseModel
# class PipelineSettings(BaseModel):
#     llm_model_need_check: str
#     llm_model_audit_plan: str
#     llm_model_judge: str
#     audit_retrieval_top_k: int
#     # Potentially other LLM related settings like API keys, base URLs etc.
#
# And ensure these settings are loaded from config_default.yaml or another config source.
# The main application would be responsible for creating and passing PipelineSettings instance.

print("app.pipeline.pipeline_v1_1.py created/updated.")
