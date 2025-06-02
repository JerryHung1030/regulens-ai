import pytest
from pathlib import Path
from app.models.project import CompareProject
from datetime import datetime

# Helper function to create dummy files and directories
def create_dummy_files(base_path: Path, structure: dict):
    for dir_name, files in structure.items():
        dir_path = base_path / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        for file_name in files:
            (dir_path / file_name).write_text(f"dummy content for {file_name}")

@pytest.fixture
def temp_project_dirs(tmp_path: Path) -> dict[str, Path]:
    # Create distinct base directories for controls, procedures, evidences
    # to avoid interference if a single tmp_path was used directly in CompareProject
    # and then a sub-directory was deleted.
    # Using tmp_path ensures cleanup after tests.

    # Structure:
    # tmp_path/
    #   project_root_A/  (for one project setup)
    #     controls/
    #     procedures/
    #     evidences/
    #   project_root_B/  (for another project setup, if needed)
    #     ...

    # For a single project test, we can create subdirs directly in tmp_path for simplicity
    # if CompareProject is instantiated with these specific paths.

    # Let's create one set of directories for a typical test case
    controls_dir = tmp_path / "controls"
    procedures_dir = tmp_path / "procedures"
    evidences_dir = tmp_path / "evidences"

    return {
        "controls": controls_dir,
        "procedures": procedures_dir,
        "evidences": evidences_dir
    }

def test_project_ready_all_valid(temp_project_dirs):
    create_dummy_files(temp_project_dirs["controls"], {"": ["control1.txt"]})
    create_dummy_files(temp_project_dirs["procedures"], {"": ["proc1.txt"]})
    create_dummy_files(temp_project_dirs["evidences"], {"": ["evid1.txt"]})

    project = CompareProject(
        name="TestReady",
        controls_dir=temp_project_dirs["controls"],
        procedures_dir=temp_project_dirs["procedures"],
        evidences_dir=temp_project_dirs["evidences"]
    )
    assert project.ready is True

def test_project_ready_no_controls_dir(temp_project_dirs):
    create_dummy_files(temp_project_dirs["procedures"], {"": ["proc1.txt"]})
    create_dummy_files(temp_project_dirs["evidences"], {"": ["evid1.txt"]})
    project = CompareProject(
        name="TestNoControlsDir",
        controls_dir=None,
        procedures_dir=temp_project_dirs["procedures"],
        evidences_dir=temp_project_dirs["evidences"]
    )
    assert project.ready is False

def test_project_ready_procedures_dir_not_exists(temp_project_dirs):
    create_dummy_files(temp_project_dirs["controls"], {"": ["control1.txt"]})
    # procedures_dir is set but not created
    create_dummy_files(temp_project_dirs["evidences"], {"": ["evid1.txt"]})
    project = CompareProject(
        name="TestProcDirNotExists",
        controls_dir=temp_project_dirs["controls"],
        procedures_dir=temp_project_dirs["procedures"], # Path exists, but no files created inside yet
        evidences_dir=temp_project_dirs["evidences"]
    )
    # Correction: The fixture creates the path. We need to test for a path that *doesn't* exist.
    # Or, more accurately for this test, a path that exists but has no .txt files.
    # The original intent might have been a non-existent path. Let's clarify.
    # If `procedures_dir` itself doesn't exist, `check_dir` handles it.
    # If it exists but is empty, `check_dir` also handles it.

    # This test will check for an existing but empty procedures_dir (no .txt files)
    temp_project_dirs["procedures"].mkdir(parents=True, exist_ok=True) # Ensure it exists
    assert project.ready is False

    # Test for a truly non-existent path
    project = CompareProject(
        name="TestProcDirTrulyNotExists",
        controls_dir=temp_project_dirs["controls"],
        procedures_dir=temp_project_dirs["procedures"] / "subfolder_not_real", # This path won't exist
        evidences_dir=temp_project_dirs["evidences"]
    )
    assert project.ready is False


def test_project_ready_evidences_dir_no_txt_files(temp_project_dirs):
    create_dummy_files(temp_project_dirs["controls"], {"": ["control1.txt"]})
    create_dummy_files(temp_project_dirs["procedures"], {"": ["proc1.txt"]})
    temp_project_dirs["evidences"].mkdir(parents=True, exist_ok=True) # Exists but empty
    (temp_project_dirs["evidences"] / "some_other_file.md").write_text("not a txt")

    project = CompareProject(
        name="TestEvidNoTxt",
        controls_dir=temp_project_dirs["controls"],
        procedures_dir=temp_project_dirs["procedures"],
        evidences_dir=temp_project_dirs["evidences"]
    )
    assert project.ready is False

def test_project_ready_one_dir_valid_others_not(temp_project_dirs):
    create_dummy_files(temp_project_dirs["controls"], {"": ["control1.txt"]})
    # procedures_dir is None, evidences_dir is empty
    temp_project_dirs["evidences"].mkdir(parents=True, exist_ok=True)

    project = CompareProject(
        name="TestOnlyControlsValid",
        controls_dir=temp_project_dirs["controls"],
        procedures_dir=None,
        evidences_dir=temp_project_dirs["evidences"]
    )
    assert project.ready is False

def test_project_ready_with_non_file_in_dir(temp_project_dirs):
    create_dummy_files(temp_project_dirs["controls"], {"": ["control1.txt"]})
    create_dummy_files(temp_project_dirs["procedures"], {"": ["proc1.txt"]})
    # Create a subdirectory instead of a file in evidences_dir
    (temp_project_dirs["evidences"] / "a_folder").mkdir(parents=True, exist_ok=True)
    # Ensure parent directory for nested.txt exists
    (temp_project_dirs["evidences"] / "another_folder").mkdir(parents=True, exist_ok=True)
    (temp_project_dirs["evidences"] / "another_folder" / "nested.txt").write_text("nested txt") # this won't be found by current iterdir

    project_with_subdir_issue = CompareProject(
        name="TestEvidSubdirOnly",
        controls_dir=temp_project_dirs["controls"],
        procedures_dir=temp_project_dirs["procedures"],
        evidences_dir=temp_project_dirs["evidences"]
    )
    # The current `ready` property's `check_dir` uses `iterdir()` which is not recursive.
    # So, `nested.txt` won't make `evidences_dir` ready.
    # If `evidences_dir` also had a direct .txt file, it would be ready.
    assert project_with_subdir_issue.ready is False

    # Add a .txt file at the top level of evidences_dir to make it ready
    (temp_project_dirs["evidences"] / "evidence_top.txt").write_text("top level evidence")
    project_with_top_txt = CompareProject(
        name="TestEvidTopTxt",
        controls_dir=temp_project_dirs["controls"],
        procedures_dir=temp_project_dirs["procedures"],
        evidences_dir=temp_project_dirs["evidences"]
    )
    assert project_with_top_txt.ready is True

# Test for is_sample and created_at (ensure they exist and can be set)
def test_project_creation_extra_fields():
    now = datetime.now()
    project = CompareProject(
        name="TestExtraFields",
        is_sample=True,
        created_at=now
    )
    assert project.name == "TestExtraFields"
    assert project.is_sample is True
    assert project.created_at == now
    assert project.ready is False # No dirs set

    project_default_extras = CompareProject(name="TestDefaultExtras")
    assert project_default_extras.is_sample is False
    assert (datetime.now() - project_default_extras.created_at).total_seconds() < 1 # Should be very recent
    assert project_default_extras.ready is False
