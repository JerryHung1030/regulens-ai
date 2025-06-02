import pytest
import json
from pathlib import Path
from datetime import datetime # Added
from app.stores.project_store import ProjectStore
from app.models.project import CompareProject
from unittest.mock import patch

@pytest.fixture
def mock_home_dir(tmp_path: Path) -> Path:
    # Create a fake .config/regulens-ai structure within tmp_path
    fake_dot_config = tmp_path / ".config" / "regulens-ai"
    fake_dot_config.mkdir(parents=True, exist_ok=True)

    # Also create the base for sample_data if ProjectStore tries to write there
    fake_regulens_ai_user_data = tmp_path / "regulens-ai" # This is for sample_data
    fake_regulens_ai_user_data.mkdir(parents=True, exist_ok=True)

    return tmp_path

def test_project_store_creates_samples_on_fresh_start(mock_home_dir: Path):
    # Patch Path.home() to return our mock_home_dir
    with patch('pathlib.Path.home', return_value=mock_home_dir):
        # The ProjectStore._PATH will now point inside mock_home_dir/.config/regulens-ai/projects.json
        # The sample data will now point inside mock_home_dir/regulens-ai/sample_data/...

        projects_json_path = mock_home_dir / ".config" / "regulens-ai" / "projects.json"
        assert not projects_json_path.exists() # Pre-condition: projects.json does not exist

        store = ProjectStore() # This should trigger sample creation

        assert len(store.projects) == 2
        project1 = store.get_project_by_name("強密碼合規範例")
        project2 = store.get_project_by_name("風險清冊範例")

        assert project1 is not None
        assert project1.is_sample is True
        assert project1.controls_dir == mock_home_dir / "regulens-ai" / "sample_data" / "sample1" / "controls"

        assert project2 is not None
        assert project2.is_sample is True
        assert project2.procedures_dir == mock_home_dir / "regulens-ai" / "sample_data" / "sample2" / "procedures"

        # Verify that projects.json was created and contains the sample projects
        assert projects_json_path.exists()
        with open(projects_json_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert len(saved_data) == 2
        assert saved_data[0]["name"] == "強密碼合規範例"
        assert saved_data[1]["name"] == "風險清冊範例"

        # Verify that sample files were created
        sample1_control_file = mock_home_dir / "regulens-ai" / "sample_data" / "sample1" / "controls" / "control1.txt"
        sample2_evid_file = mock_home_dir / "regulens-ai" / "sample_data" / "sample2" / "evidences" / "evidenceA.txt"

        assert sample1_control_file.exists()
        assert sample1_control_file.read_text(encoding="utf-8").startswith("This is a sample file.")
        assert sample2_evid_file.exists()
        assert sample2_evid_file.read_text(encoding="utf-8").startswith("This is a sample file.")

def test_project_store_loads_existing_projects_and_does_not_create_samples(mock_home_dir: Path):
    projects_json_path = mock_home_dir / ".config" / "regulens-ai" / "projects.json"

    # Pre-populate projects.json with some data
    existing_project_data = [
        {
            "name": "My Existing Project",
            "controls_dir": str(mock_home_dir / "my_controls"), # Store as string
            "procedures_dir": None,
            "evidences_dir": None,
            "report_path": None,
            "is_sample": False,
            "created_at": datetime.now().isoformat()
        }
    ]
    with open(projects_json_path, "w", encoding="utf-8") as f:
        json.dump(existing_project_data, f)

    with patch('pathlib.Path.home', return_value=mock_home_dir):
        store = ProjectStore()

        assert len(store.projects) == 1
        loaded_project = store.get_project_by_name("My Existing Project")
        assert loaded_project is not None
        assert loaded_project.is_sample is False
        assert loaded_project.controls_dir == mock_home_dir / "my_controls"

        # Ensure sample data files were NOT created in this case (unless project store always creates them, which it shouldn't if not fresh)
        # The _ensure_sample_data_files_exist is called by _create_sample_projects_and_data,
        # which should only be called on a fresh start.
        sample1_control_file = mock_home_dir / "regulens-ai" / "sample_data" / "sample1" / "controls" / "control1.txt"
        assert not sample1_control_file.exists()
