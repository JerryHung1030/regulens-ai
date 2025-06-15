from __future__ import annotations

import json
import threading # For confirm_event
from pathlib import Path
from typing import List, Callable, Dict, Any, Optional, Union

import shutil # For cleaning up temp directories

from app.logger import logger
from app.models.project import CompareProject
from app.models.docs import ControlClause, AuditTask, RawDoc, NormDoc, EmbedSet # Added RawDoc, NormDoc, EmbedSet
from app.models.run_data import ProjectRunData # Import from new module
from app.pipeline_settings import PipelineSettings # Corrected import to app.pipeline_settings
from app.pipeline.llm_utils import call_llm_api

# Import necessary functions from other pipeline modules
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


def load_controls_from_json(controls_json_path: Path) -> List[ControlClause]:
    """
    Loads control clauses from the project's specified controls JSON file.
    The JSON structure is expected to be:
    {
        "name": "Project Name",
        "C001": "第一條 目的\n條文內容...",
        "C002": "第二條 適用範圍\n條文內容...",
        ...
    }
    """
    control_clauses: List[ControlClause] = []
    if not controls_json_path.exists():
        logger.error(f"Controls JSON file not found: {controls_json_path}")
        return control_clauses

    try:
        # 確保使用 UTF-8 編碼讀取檔案
        with open(controls_json_path, 'r', encoding='utf-8') as f:
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
            
            # 創建 ControlClause 物件，包含所有必要的欄位
            clause = ControlClause(
                id=clause_id,
                title=title,
                text=text,
                need_procedure=None,  # 初始值設為 None，將由 pipeline 決定
                tasks=[],  # 初始為空列表，將由 pipeline 填充
                subclauses=[]  # 初始為空列表
            )
            control_clauses.append(clause)
            
    except Exception as e:
        logger.error(f"Error loading controls JSON: {e}")
        
    return control_clauses


def run_project_pipeline_v1_1(project: CompareProject,
                              settings: PipelineSettings,
                              progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None],
                              cancel_cb: Callable[[], bool],
                              confirm_event: Optional[threading.Event] = None): # New parameter
    """
    Main orchestrator for the V1.1 pipeline.
    """
    logger.info(f"Starting pipeline v1.1 for project: {project.name}")
    progress_callback(0.0, "Initializing pipeline...")

    if not project.controls_json_path or not project.controls_json_path.exists():
        logger.error("Controls JSON path not specified or file does not exist.")
        progress_callback(1.0, "Error: Controls JSON file not found.")
        return

    if not project.run_json_path:
        logger.error("Project run_json_path is not set.")
        progress_callback(1.0, "Error: run.json path not configured for the project.")
        return

    # Load existing run data or initialize if not present/fresh start requested
    # For now, let's assume we always load controls from source JSON and then update from run.json
    # A more sophisticated resume logic might be needed later.
    
    initial_clauses = load_controls_from_json(project.controls_json_path)
    if not initial_clauses:
        progress_callback(1.0, "Error: No control clauses loaded. Stopping pipeline.")
        return

    project_run_data = _load_run_json(project.run_json_path)
    
    if project_run_data:
        logger.info(f"Loaded existing run data from {project.run_json_path}")
        # Merge or update initial_clauses with data from project_run_data
        # This creates a map for quick lookup
        existing_clauses_map = {c.id: c for c in project_run_data.control_clauses}
        final_clauses_for_pipeline: List[ControlClause] = []
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
                
                final_clauses_for_pipeline.append(ControlClause(**updated_data))
            else:
                final_clauses_for_pipeline.append(loaded_clause)
        
        # Add clauses that might be in run.json but not in source (e.g. if source file changed)
        # This logic might need refinement based on how we want to handle discrepancies.
        # For now, source JSON is the master list.
        current_ids_in_source = {c.id for c in final_clauses_for_pipeline}
        for existing_clause in project_run_data.control_clauses:
            if existing_clause.id not in current_ids_in_source:
                logger.warning(f"Clause ID {existing_clause.id} found in run.json but not in source controls. It will be ignored.")

        control_clauses_for_run = final_clauses_for_pipeline

    else:
        logger.info(f"No existing run data found at {project.run_json_path}, or starting fresh.")
        control_clauses_for_run = initial_clauses
        # Initialize ProjectRunData and save it immediately
        project_run_data = ProjectRunData(project_name=project.name, control_clauses=control_clauses_for_run)
        _save_run_json(project_run_data, project.run_json_path)


    if not control_clauses_for_run:
        progress_callback(1.0, "No control clauses to process. Stopping pipeline.")
        return

    # --- Step 1: Need-Check ---
    if cancel_cb():
        progress_callback(1.0, "Pipeline cancelled.")
        return
    progress_callback(0.1, "Starting Step 1: Need-Check...")
    # control_clauses_for_run = execute_need_check_step(control_clauses_for_run, project.run_json_path, settings, cancel_cb)
    # Update run_data and save (within execute_need_check_step or here)
    execute_need_check_step(
        control_clauses=control_clauses_for_run, 
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
    # control_clauses_for_run = execute_audit_plan_step(control_clauses_for_run, project.run_json_path, settings, cancel_cb)
    # Update run_data and save
    execute_audit_plan_step(
        control_clauses=control_clauses_for_run,
        project_run_json_path=project.run_json_path,
        current_project_run_data=project_run_data,
        settings=settings,
        progress_callback=progress_callback,
        cancel_cb=cancel_cb
    )
    logger.info("Step 2: Audit-Plan completed.")

    # --- Pause for user confirmation before Search step ---
    if confirm_event:
        # The audit_plan_generation_complete=True message should have been sent by execute_audit_plan_step
        # The button in UI should be enabled by that signal.
        # Now, wait for the user to press it.
        logger.info("Audit plan generated. Waiting for user confirmation to proceed to Search step...")
        progress_callback(0.6, "等待使用者確認以開始文件檢索...") # Message indicating waiting state
        confirm_event.wait()  # Block until main_window sets the event
        confirm_event.clear() # Clear the event for potential future use
        logger.info("User confirmed. Proceeding with Search step.")
        # Optionally, send another progress message that confirmation received, though next step's start message will also show.
        # progress_callback(0.6, "Confirmation received. Starting Search step...")


    # --- Future Steps (3 & 4) would follow here ---
    # Step 3: Procedure Association (Search)
    if cancel_cb():
        progress_callback(1.0, "Pipeline cancelled.")
        return
    progress_callback(0.6, "Starting Step 3: Search for Procedures...")
    execute_search_step(
        control_clauses=control_clauses_for_run,
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
        control_clauses=control_clauses_for_run,
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
    control_clauses: List[ControlClause],
    project_run_json_path: Path,
    current_project_run_data: ProjectRunData, # To update and save the overall run.json
    settings: PipelineSettings,
    progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None], # For detailed progress
    cancel_cb: Callable[[], bool]
) -> List[ControlClause]:
    """
    Executes Step 1: Need-Check for each control clause.
    Updates need_procedure attribute and saves to run.json progressively.
    """
    total_clauses = len(control_clauses)
    clauses_processed = 0

    for idx, clause in enumerate(control_clauses):
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
            f"Determine if the following control clause requires a detailed audit procedure to verify its implementation. "
            f"Respond with a JSON object containing a single key 'requires_procedure' with a boolean value (true or false).\n\n"
            f"Control Clause Text: \"{clause.text}\""
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
        
        # Update the specific clause in current_project_run_data.control_clauses
        # This assumes current_project_run_data.control_clauses is the same list object
        # or requires finding and updating the clause by ID if it's a copy.
        # For simplicity, if control_clauses is a mutable list shared, direct update works.
        # Otherwise:
        for i, run_clause in enumerate(current_project_run_data.control_clauses):
            if run_clause.id == clause.id:
                current_project_run_data.control_clauses[i] = clause
                break
        _save_run_json(current_project_run_data, project_run_json_path)
        
        base_progress = 0.1
        step_progress_span = 0.2 # Step 1 is 10% to 30%
        current_step_progress = (clauses_processed / total_clauses) * step_progress_span
        progress_callback(base_progress + current_step_progress, f"Need-Check: Clause {clause.id} -> {clause.need_procedure}")

    return control_clauses


def execute_audit_plan_step(
    control_clauses: List[ControlClause],
    project_run_json_path: Path,
    current_project_run_data: ProjectRunData,
    settings: PipelineSettings,
    progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None],
    cancel_cb: Callable[[], bool]
) -> List[ControlClause]:
    """
    Executes Step 2: Audit-Plan for each relevant control clause.
    Generates audit tasks and saves to run.json progressively.
    """
    base_progress = 0.3  # Progress before this step starts
    step_progress_span = 0.3  # This step spans from 30% to 60%

    total_clauses_in_step = len(control_clauses)
    clauses_iterated_in_step = 0

    if total_clauses_in_step == 0:
        logger.info("No control clauses to process for audit planning.")
        progress_callback(base_progress + step_progress_span, "Audit-Plan: No control clauses")
        # Send completion signal even if no clauses
        final_completion_message = AuditPlanClauseUIData(
            clause_id="summary",
            clause_title="Audit Plan Generation Summary",
            audit_plan_generation_complete=True
        )
        progress_callback(base_progress + step_progress_span, final_completion_message)
        return control_clauses

    for clause in control_clauses:
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
            f"Generate **one** concise and precise audit task (sentence) to verify the implementation of the following control clause. "
            f"The task should be suitable for information retrieval against a knowledge base of audit procedures. "
            f"Return a JSON object containing a single key 'audit_tasks', which is a list containing **a single dictionary**. "
            f"The dictionary should have an 'id' (e.g., 'task_001') and a 'sentence' (the audit task text).\n\n"
            f"Control Clause Text: \"{clause.text}\""
        )

        llm_response = call_llm_api(
            prompt=prompt,
            model_name=settings.llm_model_audit_plan,
            api_key=settings.openai_api_key,
            expected_response_type="json_list"  # Keep this as json_list, we'll validate the contents
        )

        clause.tasks = [] # Initialize tasks as empty list for this clause
        if llm_response and isinstance(llm_response, list) and len(llm_response) > 0:
            if len(llm_response) > 1:
                logger.warning(f"LLM returned {len(llm_response)} tasks for clause {clause.id}, but expected only one. Using the first task.")
            
            first_task_data = llm_response[0]
            if isinstance(first_task_data, dict) and "id" in first_task_data and "sentence" in first_task_data:
                try:
                    single_task = AuditTask(id=str(first_task_data["id"]), sentence=str(first_task_data["sentence"]))
                    clause.tasks = [single_task] # Assign as a list with one task
                    logger.info(f"Audit-Plan for clause {clause.id} generated 1 task: {single_task.id}")
                except Exception as e: # Pydantic validation error
                    logger.error(f"Error creating AuditTask from data {first_task_data} for clause {clause.id}: {e}")
                    # clause.tasks remains empty
            else:
                logger.error(f"Invalid task data format from LLM for clause {clause.id}: {first_task_data}")
                # clause.tasks remains empty
        else:
            logger.error(f"Failed to generate audit tasks or empty list returned for clause {clause.id}. LLM response: {llm_response}")
            # clause.tasks remains empty
            
        # Update and save run.json
        for i, run_clause in enumerate(current_project_run_data.control_clauses):
            if run_clause.id == clause.id:
                current_project_run_data.control_clauses[i] = clause
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
        
    return control_clauses


def execute_search_step(
    control_clauses: List[ControlClause],
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
    cache_service = CacheService(Path(f"projects/{project.name}/cache/embeddings"))

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
    # Use base64 encoded name for the temp directory to avoid path issues
    import base64
    safe_project_name = base64.urlsafe_b64encode(project.name.encode('utf-8')).decode('ascii').rstrip('=')
    temp_index_dir = project.run_json_path.parent / f"temp_index_cache_{safe_project_name}"
    temp_index_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Creating FAISS index for procedures at {temp_index_dir}...")
    proc_index_meta: Optional[IndexMeta] = create_or_load_index(
        all_proc_embed_sets, temp_index_dir, f"procedures_{safe_project_name}", settings.embedding_model
    )

    if not proc_index_meta:
        logger.error("Failed to create procedure FAISS index. Aborting search step.")
        progress_callback(0.8, "Search: Failed to create procedure index.")
        shutil.rmtree(temp_index_dir) # Clean up
        return

    # --- Iterate through Audit Tasks ---
    total_tasks_to_search = sum(len(c.tasks) for c in control_clauses if c.need_procedure and c.tasks)
    tasks_searched = 0
    
    # Create a map of all EmbedSets for easy lookup by retrieve_similar_chunks
    all_embed_sets_map: Dict[str, EmbedSet] = {es.id: es for es in all_proc_embed_sets}


    for clause_idx, clause in enumerate(control_clauses):
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
            current_project_run_data.control_clauses[clause_idx] = clause # Ensure the main list is updated
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
    control_clauses: List[ControlClause],
    project_run_json_path: Path,
    current_project_run_data: ProjectRunData,
    settings: PipelineSettings,
    progress_callback: Callable[[float, Union[str, AuditPlanClauseUIData]], None],
    cancel_cb: Callable[[], bool]
):
    """
    Executes Step 4: Judge compliance for each audit task with evidence.
    """
    logger.info("Starting Judge Step...")
    
    tasks_to_judge = []
    for clause in control_clauses:
        if clause.need_procedure and clause.tasks:
            for task in clause.tasks:
                # Only judge if top_k evidence exists and compliance not yet determined
                if task.top_k and task.compliant is None: 
                    tasks_to_judge.append((clause, task)) # Store as (clause, task) tuple

    if not tasks_to_judge:
        logger.info("No tasks require judging.")
        progress_callback(1.0, "Judge: No tasks to judge.") # Assuming Judge is 80-100%
        return

    judged_tasks_count = 0
    total_tasks_to_judge_count = len(tasks_to_judge)

    for clause_idx_in_main_list, (clause, task) in enumerate(tasks_to_judge): # Iterate over a copy
        if cancel_cb():
            logger.info("Judge step cancelled.")
            break
        
        logger.info(f"Judging task: {task.id} for clause {clause.id} - {task.sentence[:50]}...")

        evidence_texts = [f"Evidence {i+1} (Source: {ev.get('source_txt', 'N/A')}, Page: {ev.get('page_no', 'N/A')}):\n{ev.get('excerpt', '')}" 
                          for i, ev in enumerate(task.top_k or [])]
        evidence_prompt_str = "\n\n".join(evidence_texts) if evidence_texts else "No evidence found."

        prompt = (
            f"Assess compliance for the given control clause and audit task, based on the provided evidence excerpts.\n\n"
            f"Control Clause: \"{clause.text}\"\n\n"
            f"Audit Task: \"{task.sentence}\"\n\n"
            f"Evidence:\n{evidence_prompt_str}\n\n"
            f"Is the control effectively implemented as verified by the audit task and supported by the evidence? "
            f"Respond with a JSON object containing a 'compliant' (boolean) key and an optional 'reasoning' (string) key."
        )

        llm_response = call_llm_api(
            prompt=prompt,
            model_name=settings.llm_model_judge,
            api_key=settings.openai_api_key,
            expected_response_type="json_object"
        )

        if llm_response and isinstance(llm_response, dict) and "compliant" in llm_response:
            task.compliant = llm_response["compliant"]
            if "reasoning" in llm_response:
                task.metadata["judge_reasoning"] = llm_response["reasoning"]
            logger.info(f"Judgment for task {task.id}: Compliant={task.compliant}")
        else:
            task.compliant = None # Mark as undetermined on error
            logger.error(f"Failed to judge compliance for task {task.id}. LLM response: {llm_response}")

        judged_tasks_count += 1
        
        # Update original clause in current_project_run_data by finding it (or its task)
        # This is a bit complex if the list passed to this function is not the one in current_project_run_data
        # Assuming current_project_run_data.control_clauses is the source of truth that needs updating.
        for i_main, main_clause in enumerate(current_project_run_data.control_clauses):
            if main_clause.id == clause.id:
                for j_main, main_task in enumerate(main_clause.tasks):
                    if main_task.id == task.id:
                        current_project_run_data.control_clauses[i_main].tasks[j_main] = task
                        break
                break
        _save_run_json(current_project_run_data, project_run_json_path)
        
        base_progress = 0.8 # Judge step is 80-100%
        step_progress_span = 0.2
        current_task_progress = (judged_tasks_count / total_tasks_to_judge_count) * step_progress_span
        progress_callback(base_progress + current_task_progress, f"Judge: Task {task.id} -> Compliant={task.compliant}")


if __name__ == '__main__':
    # This is a basic test runner.
    # In a real scenario, CompareProject and PipelineSettings would be instantiated properly.
    
    # Create a dummy project
    mock_project_dir = Path("temp_pipeline_test_project")
    mock_project_dir.mkdir(parents=True, exist_ok=True)
    
    mock_controls_data = {
        "name": "Test Controls",
        "C001": "第一條 目的\n條文內容...",
        "C002": "第二條 適用範圍\n條文內容..."
    }
    controls_json_file = mock_project_dir / "controls.json"
    controls_json_file.write_text(json.dumps(mock_controls_data, indent=4, ensure_ascii=False), encoding='utf-8')

    # Dummy run.json (optional, to test loading)
    # mock_run_data = {
    #     "project_name": "TestProject",
    #     "control_clauses": [
    #         {"id": "CTRL001", "text": "Systems must have access control mechanisms.", "need_procedure": True, "tasks": [], "metadata":{}},
    #     ]
    # }
    # run_json_file = mock_project_dir / "run.json"
    # run_json_file.write_text(json.dumps(mock_run_data, indent=4))


    test_project = CompareProject(name="TestProject")
    test_project.controls_json_path = controls_json_file
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
    print(f"Controls JSON: {test_project.controls_json_path}")
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

# Ensure ControlClause model is updated to include need_procedure: Optional[bool] = None
# and tasks: List[AuditTask] = Field(default_factory=list)
# This needs to be done in app/models/docs.py
# Example:
# class ControlClause(BaseModel):
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
