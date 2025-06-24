import sys
import os
from pathlib import Path
import json
from typing import List, Optional, Union, Callable, Dict, Any
from unittest.mock import patch, MagicMock # Import MagicMock for mocking modules

# Add the /app directory to sys.path to allow imports from app.*
sys.path.insert(0, "/app")

# --- Minimal CompareProject definition to avoid PySide6 dependency ---
class HeadlessCompareProject:
    def __init__(self, name: str):
        self.name: str = name
        self.external_regulations_json_path: Optional[Path] = None
        self.procedure_doc_paths: List[Path] = []
        self.run_json_path: Optional[Path] = None
        self.base_dir: Optional[Path] = None

    def get_document_paths_by_type(self, doc_type: str) -> List[Path]:
        if doc_type == "procedure":
            return self.procedure_doc_paths
        return []

# --- Configuration ---
project_name = "sample2_符合規範Demo"
external_regulations_json_path = Path(f"sample_data/{project_name}/external_regulations/external.json")
procedure_doc_paths = [Path(f"sample_data/{project_name}/procedures/internal.txt")]
temp_run_dir = Path("temp_test_run")
run_json_path = temp_run_dir / f"{project_name}_run.json"

# Placeholder for AuditPlanClauseUIData, will be properly typed after import
def my_progress_callback(percent: float, message_data: any):
    if type(message_data).__qualname__ == 'AuditPlanClauseUIData': # Check type by name
        print(f"Progress: {percent*100:.0f}% - AuditPlanData: clause_id={message_data.clause_id}, tasks_count={len(message_data.tasks)}, completed={message_data.audit_plan_generation_complete}")
    elif isinstance(message_data, str):
        print(f"Progress: {percent*100:.0f}% - {message_data}")
    else:
        print(f"Progress: {percent*100:.0f}% - Type: {type(message_data)}")

def my_cancel_cb() -> bool:
    return False

def main():
    # --- Mock PySide6 before any problematic app imports ---
    mock_pyside = MagicMock()
    sys.modules['PySide6'] = mock_pyside
    sys.modules['PySide6.QtCore'] = MagicMock()
    sys.modules['PySide6.QtGui'] = MagicMock() 
    sys.modules['PySide6.QtWidgets'] = MagicMock()
    
    from app.pipeline_settings import PipelineSettings

    temp_run_dir.mkdir(parents=True, exist_ok=True)

    if run_json_path.exists():
        run_json_path.unlink()
        print(f"Cleared existing run file: {run_json_path}")

    project_instance = HeadlessCompareProject(name=project_name)
    project_instance.external_regulations_json_path = external_regulations_json_path
    project_instance.procedure_doc_paths = procedure_doc_paths
    project_instance.run_json_path = run_json_path
    project_instance.base_dir = Path(f"sample_data/{project_name}")

    print(f"Project Name: {project_instance.name}")
    print(f"External Regulations JSON Path: {project_instance.external_regulations_json_path}")
    # ... (other print statements)


    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = "sk-test-placeholder-please-replace"
        print("WARNING: OPENAI_API_KEY environment variable not set. Using a placeholder API key. LLM calls will likely fail.")
    else:
        print("Using OpenAI API key from environment variable.")

    settings = PipelineSettings(
        openai_api_key=api_key,
        embedding_model="text-embedding-ada-002",
        local_model_path=None,
        language="zh",
        llm_model_need_check="gpt-3.5-turbo",
        llm_model_audit_plan="gpt-4-turbo-preview",
        llm_model_judge="gpt-4-turbo-preview",
        audit_retrieval_top_k=3
    )
    print(f"Pipeline Settings: {settings.model_dump_json(indent=2)}")

    print("\n--- Starting Pipeline Execution ---")
    
    # Corrected patch: Replace the class app.models.project.CompareProject with HeadlessCompareProject
    patcher = patch('app.models.project.CompareProject', HeadlessCompareProject)
    
    try:
        mock_compare_project_class_actual = patcher.start() # This will be HeadlessCompareProject
        
        from app.pipeline.pipeline_v1_1 import run_project_pipeline_v1_1, AuditPlanClauseUIData
        
        run_project_pipeline_v1_1(project_instance, settings, my_progress_callback, my_cancel_cb)
        print("--- Pipeline Execution Finished ---")
    except Exception as e:
        print(f"--- Pipeline Execution Failed ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        patcher.stop() 

    if run_json_path.exists():
        print(f"\n--- Contents of {run_json_path} ---")
        with open(run_json_path, 'r', encoding='utf-8') as f:
            print(f.read())
    else:
        print(f"\n--- {run_json_path} was not created. ---")

if __name__ == "__main__":
    main()
