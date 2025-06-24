import sys
import os
from pathlib import Path
import json
from typing import List, Optional, Any
from unittest.mock import patch, MagicMock

# Ensure /app is in path for imports
sys.path.insert(0, "/app")

# --- HeadlessCompareProject Definition ---
class HeadlessCompareProject:
    def __init__(self, name: str):
        self.name: str = name
        self.external_regulations_json_path: Optional[Path] = None
        self.procedure_doc_paths: List[Path] = []
        self.run_json_path: Optional[Path] = None
        self.base_dir: Optional[Path] = None # For potential relative path calculations

    def get_document_paths_by_type(self, doc_type: str) -> List[Path]:
        if doc_type == "procedure":
            return self.procedure_doc_paths
        return []

# --- Configuration ---
PROJECT_NAME = "sample2_符合規範Demo"
External RegulationS_JSON_PATH = Path(f"sample_data/{PROJECT_NAME}/external_regulations/external.json")
PROCEDURE_DOC_PATHS = [Path(f"sample_data/{PROJECT_NAME}/procedures/internal.txt")] # Original
TEMP_RUN_DIR = Path("temp_test_run")
RUN_JSON_PATH = TEMP_RUN_DIR / "sample2_demo_run_step5.json"

# --- Callback Functions ---
def my_progress_callback(percent: float, message_data: Any):
    # Check type by name to avoid early import of AuditPlanClauseUIData
    if type(message_data).__qualname__ == 'AuditPlanClauseUIData':
        print(f"Progress: {percent*100:.0f}% - AuditPlan: Clause {message_data.clause_id}, Tasks: {len(message_data.tasks)}, AllPlanDone: {message_data.audit_plan_generation_complete}")
    elif isinstance(message_data, str):
        print(f"Progress: {percent*100:.0f}% - {message_data}")
    else:
        print(f"Progress: {percent*100:.0f}% - Type: {type(message_data)}")

def my_cancel_cb() -> bool:
    return False

# --- Main Execution Logic ---
def main():
    # 1. Mock PySide6 modules
    sys.modules['PySide6'] = MagicMock()
    sys.modules['PySide6.QtCore'] = MagicMock()
    sys.modules['PySide6.QtGui'] = MagicMock()
    sys.modules['PySide6.QtWidgets'] = MagicMock()

    # These can be imported after PySide6 is mocked
    from app.pipeline_settings import PipelineSettings
    
    # 2. Prepare Project Directory and run.json
    TEMP_RUN_DIR.mkdir(parents=True, exist_ok=True)
    if RUN_JSON_PATH.exists():
        RUN_JSON_PATH.unlink()
        print(f"Cleared existing run file: {RUN_JSON_PATH}")

    # 3. Setup Project
    project_instance = HeadlessCompareProject(name=PROJECT_NAME)
    project_instance.external_regulations_json_path = External RegulationS_JSON_PATH
    project_instance.procedure_doc_paths = PROCEDURE_DOC_PATHS
    project_instance.run_json_path = RUN_JSON_PATH
    project_instance.base_dir = Path(f"sample_data/{PROJECT_NAME}")
    
    print(f"Project Name: {project_instance.name}")
    print(f"External Regulations JSON: {project_instance.external_regulations_json_path}")
    print(f"Procedures: {project_instance.procedure_doc_paths}")
    print(f"Run JSON Output: {project_instance.run_json_path}")

    # 4. Setup Pipeline Settings
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = "sk-test-placeholder-for-step5-run" # Placeholder
        print("WARNING: OPENAI_API_KEY environment variable not set. Using a placeholder. LLM calls will likely fail or produce dummy output.")
    else:
        print("Using OpenAI API key from environment variable.")

    settings = PipelineSettings(
        openai_api_key=api_key,
        embedding_model="text-embedding-ada-002",
        language="zh", # Data is in Chinese
        llm_model_need_check="gpt-3.5-turbo",
        llm_model_audit_plan="gpt-3.5-turbo", # Changed for multi-task generation
        llm_model_judge="gpt-4",          # Stronger model for clause-level judging
        audit_retrieval_top_k=3
    )
    print(f"Pipeline Settings: {settings.model_dump_json(indent=2)}")

    # 5. Patch CompareProject and Run Pipeline
    # The 'new' argument takes the class that will replace the target.
    project_patcher = patch('app.models.project.CompareProject', new=HeadlessCompareProject)
    
    print("\n--- Starting Pipeline Execution ---")
    try:
        # Start patching. Any import of 'app.models.project.CompareProject' will get HeadlessCompareProject.
        active_patch = project_patcher.start()
        
        # Import pipeline function *after* patch is active
        from app.pipeline.pipeline_v1_1 import run_project_pipeline_v1_1
        
        run_project_pipeline_v1_1(project_instance, settings, my_progress_callback, my_cancel_cb)
        print("--- Pipeline Execution Finished ---")
    except Exception as e:
        print(f"--- Pipeline Execution Failed ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        project_patcher.stop() # Ensure patch is stopped

    # 6. Output and Verification
    if RUN_JSON_PATH.exists():
        print(f"\n--- Contents of {RUN_JSON_PATH} ---")
        run_data_content = RUN_JSON_PATH.read_text(encoding='utf-8')
        print(run_data_content)
        
        print("\n--- Verification Data ---")
        try:
            run_data_json = json.loads(run_data_content)
            for clause_data in run_data_json.get("external_regulation_clauses", []):
                clause_id = clause_data.get("id")
                if clause_id in ["C001", "C002"]:
                    tasks = clause_data.get("tasks", [])
                    print(f"\nClause ID: {clause_id}")
                    print(f"  Number of Audit Tasks Generated: {len(tasks)}")
                    
                    clause_compliant = clause_data.get("metadata", {}).get("clause_compliant")
                    clause_desc = clause_data.get("metadata", {}).get("clause_compliance_description", "N/A")
                    clause_sugg = clause_data.get("metadata", {}).get("clause_improvement_suggestions", "N/A")
                    
                    print(f"  Clause Compliant Status: {clause_compliant}")
                    print(f"  Clause Compliance Description: {clause_desc[:200]}...") # Print snippet
                    print(f"  Clause Improvement Suggestions: {clause_sugg[:200]}...") # Print snippet
                    
                    # Also show task-level propagation for one task if exists
                    if tasks:
                        first_task = tasks[0]
                        print(f"  First Task ({first_task.get('id')}) Compliant (propagated): {first_task.get('compliant')}")
                        print(f"  First Task Compliance Description (propagated): {first_task.get('metadata',{}).get('compliance_description','N/A')[:100]}...")

        except json.JSONDecodeError:
            print("Error: Could not parse run.json for verification.")
        except Exception as e:
            print(f"Error during verification data extraction: {e}")
            
    else:
        print(f"\n--- {RUN_JSON_PATH} was not created. ---")

if __name__ == "__main__":
    main()
