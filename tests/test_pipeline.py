import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY

from app.models.project import CompareProject
from app.models.docs import IndexMeta, EmbedSet, RawDoc, NormDoc  # Added RawDoc, NormDoc
from app.models.assessments import TripleAssessment  # For mock_assess_llm return type
from app.pipeline import PipelineSettings, run_pipeline
from app.settings import Settings


# Helper to create dummy files (can be shared or redefined)
def create_dummy_txt_files(base_path: Path, count: int = 1, prefix: str = "file"):
    base_path.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (base_path / f"{prefix}{i + 1}.txt").write_text(f"dummy content for {prefix}{i + 1}")


@pytest.fixture
def temp_project_for_pipeline(tmp_path: Path) -> CompareProject:
    # Create a fully valid project setup in a temporary directory
    project_name = "TestPipelineProject"

    controls_p = tmp_path / project_name / "controls"
    procedures_p = tmp_path / project_name / "procedures"
    evidences_p = tmp_path / project_name / "evidences"

    create_dummy_txt_files(controls_p, 1, "control")
    create_dummy_txt_files(procedures_p, 1, "procedure")
    create_dummy_txt_files(evidences_p, 1, "evidence")

    project = CompareProject(
        name=project_name,
        controls_dir=controls_p,
        procedures_dir=procedures_p,
        evidences_dir=evidences_p
    )
    assert project.ready  # Pre-condition for pipeline test
    return project


@pytest.fixture
def mock_app_settings(tmp_path):
    # Mocks the app.settings.Settings class
    # This fixture provides a Settings instance that uses a temporary file.
    settings_file = tmp_path / "test_app_settings.json"
    s = Settings()
    s._path = settings_file  # Override internal path to use temp file

    # Pre-populate with some pipeline-relevant settings
    s.set("openai_api_key", "test_api_key_from_settings")
    s.set("embedding_model", "test_embedding_model_from_settings")
    s.set("llm_model", "test_llm_model_from_settings")
    # s.set("some_threshold", "0.75") # Example if this setting was used
    return s


def test_pipeline_settings_from_settings(mock_app_settings: Settings):
    pipeline_settings = PipelineSettings.from_settings(mock_app_settings)

    assert pipeline_settings.openai_api_key == "test_api_key_from_settings"
    assert pipeline_settings.embedding_model == "test_embedding_model_from_settings"
    assert pipeline_settings.llm_model == "test_llm_model_from_settings"
    # assert pipeline_settings.some_threshold == 0.75


def test_pipeline_settings_defaults():
    # Test default values if settings are not present
    empty_settings = Settings()  # Uses default in-memory or non-existent file

    pipeline_settings = PipelineSettings.from_settings(empty_settings)

    assert pipeline_settings.openai_api_key == ""  # Default from dataclass
    assert pipeline_settings.embedding_model == "default_embedding_model"  # Default from dataclass
    assert pipeline_settings.llm_model == "default_llm_model"  # Default from dataclass


# Mock generate_embeddings to prevent actual embedding calls and content validation issues
@patch('app.pipeline.embed.generate_embeddings')
@patch('time.sleep', MagicMock())  # Mock time.sleep to speed up test
def test_run_pipeline_basic_execution(
    mock_generate_embeddings: MagicMock,
    temp_project_for_pipeline: CompareProject,
    mock_app_settings: Settings
):
    project = temp_project_for_pipeline
    pipeline_settings = PipelineSettings.from_settings(mock_app_settings)

    # Configure the mock for generate_embeddings
    # It needs to return a list of EmbedSet objects.
    # Let's create some dummy EmbedSet instances for the mock to return.
    # This needs to align with what the pipeline expects after calling generate_embeddings.
    # generate_embeddings is called for controls, procedures, and evidences.

    dummy_control_embed_set = [
        MagicMock(spec=EmbedSet, id="ctrl_es_1", norm_doc_id="ctrl_doc_1", chunk_text="Control chunk 1", embedding=[0.1] * 10, chunk_index=0, total_chunks=1, doc_type="control")
    ]
    dummy_procedure_embed_set = [
        MagicMock(spec=EmbedSet, id="proc_es_1", norm_doc_id="proc_doc_1", chunk_text="Procedure chunk 1", embedding=[0.2] * 10, chunk_index=0, total_chunks=1, doc_type="procedure")
    ]
    dummy_evidence_embed_set = [
        MagicMock(spec=EmbedSet, id="evid_es_1", norm_doc_id="evid_doc_1", chunk_text="Evidence chunk 1", embedding=[0.3] * 10, chunk_index=0, total_chunks=1, doc_type="evidence")
    ]

    # Set up the side_effect to return different values for different calls if needed,
    # or a default if the calls are indistinguishable for the mock without more setup.
    # For simplicity, assume it's called 3 times (controls, procedures, evidences)
    # and we can make it return the respective list.
    mock_generate_embeddings.side_effect = [
        dummy_control_embed_set,  # First call (controls)
        dummy_procedure_embed_set,  # Second call (procedures)
        dummy_evidence_embed_set   # Third call (evidences)
    ]

    # and assess_triplet_with_llm to avoid their external dependencies and ensure the pipeline runs further.
    with patch('app.pipeline.ingestion.ingest_documents') as mock_ingest_documents, \
         patch('app.pipeline.normalize.normalize_document') as mock_normalize_document, \
         patch('app.pipeline.index.create_or_load_index') as mock_create_index, \
         patch('app.pipeline.retrieve.retrieve_similar_chunks') as mock_retrieve_similar_chunks, \
         patch('app.pipeline.judge_llm.assess_triplet_with_llm') as mock_assess_llm, \
         patch('app.pipeline.report.generate_report') as mock_generate_report, \
         patch('faiss.read_index', MagicMock()):

        # 1. Mock for ingest_documents
        raw_doc_mock_ctrl = MagicMock(spec=RawDoc, id="rd_ctrl_1", text_content="Control content")
        raw_doc_mock_proc = MagicMock(spec=RawDoc, id="rd_proc_1", text_content="Procedure content")
        raw_doc_mock_evid = MagicMock(spec=RawDoc, id="rd_evid_1", text_content="Evidence content")
        mock_ingest_documents.side_effect = [
            [raw_doc_mock_ctrl], [raw_doc_mock_proc], [raw_doc_mock_evid]
        ]

        # 2. Mock for normalize_document
        norm_doc_mock_ctrl = MagicMock(spec=NormDoc, id="norm_ctrl_1", text_chunks=['Normalized control'])
        norm_doc_mock_proc = MagicMock(spec=NormDoc, id="norm_proc_1", text_chunks=['Normalized procedure'])
        norm_doc_mock_evid = MagicMock(spec=NormDoc, id="norm_evid_1", text_chunks=['Normalized evidence'])
        mock_normalize_document.side_effect = [norm_doc_mock_ctrl, norm_doc_mock_proc, norm_doc_mock_evid]

        # 3. Mock for generate_embeddings (already an arg, use mock_generate_embeddings)
        # Ensure EmbedSet mocks have `embedding` attribute as a list of floats
        embed_set_mock_c = MagicMock(spec=EmbedSet, id='ctrl_es_1', norm_doc_id='norm_ctrl_1', embedding=[0.1] * 10, chunk_text='Normalized control')
        embed_set_mock_p = MagicMock(spec=EmbedSet, id='proc_es_1', norm_doc_id='norm_proc_1', embedding=[0.2] * 10, chunk_text='Normalized procedure')
        embed_set_mock_e = MagicMock(spec=EmbedSet, id='evid_es_1', norm_doc_id='norm_evid_1', embedding=[0.3] * 10, chunk_text='Normalized evidence')
        mock_generate_embeddings.side_effect = [
            [embed_set_mock_c], [embed_set_mock_p], [embed_set_mock_e]
        ]

        # 4. Mock for create_or_load_index
        index_meta_mock = MagicMock(spec=IndexMeta)
        index_meta_mock.index_file_path = project.controls_dir.parent / "dummy.faiss"
        index_meta_mock.id_mapping_path = project.controls_dir.parent / "dummy_map.json"
        index_meta_mock.vector_dimension = 10
        index_meta_mock.num_vectors = 1
        mock_create_index.return_value = index_meta_mock

        # 5. Mock for retrieve_similar_chunks
        # This function is called for procedures against controls, and evidences against procedures.
        # It should return List[MatchSet]
        match_set_mock = MagicMock(matched_embed_set_id="some_id", score=0.85)
        mock_retrieve_similar_chunks.return_value = [match_set_mock]

        # 6. Mock for assess_triplet_with_llm
        assessment_mock = MagicMock(spec=TripleAssessment)  # Use actual class for spec if possible
        assessment_mock.score = 0.9
        assessment_mock.judgment = "Compliant"
        assessment_mock.reasoning = "Mocked assessment"
        # Populate other fields if `aggregate_assessments_for_pair` needs them
        assessment_mock.control_doc_id = "norm_ctrl_1"
        assessment_mock.procedure_doc_id = "norm_proc_1"

        mock_assess_llm.return_value = assessment_mock

        # 7. Mock for generate_report
        expected_report_path = Path(project.controls_dir.parent / "reports" / "test_report.md")
        mock_generate_report.return_value = expected_report_path

        # Ensure report_path is None initially
        original_report_path = project.report_path
        assert original_report_path is None

        run_pipeline(project, pipeline_settings)

    # Verify project.report_path is populated by the mocked generate_report
    assert project.report_path == expected_report_path

    # Check that mocks were called (examples)
    mock_ingest_documents.assert_any_call(project.controls_dir, "control")
    mock_ingest_documents.assert_any_call(project.procedures_dir, "procedure")
    # mock_ingest_documents.assert_any_call(project.evidences_dir, "evidence") # if evidences_dir is set

    mock_normalize_document.assert_any_call(raw_doc_mock_ctrl)  # Example check
    mock_generate_embeddings.assert_any_call(norm_doc_mock_ctrl, ANY, ANY, ANY)  # ANY for cache_service, api_key, model

    mock_create_index.assert_any_call([embed_set_mock_c], ANY, "control", ANY)

    # assess_triplet_with_llm is called inside loops, checking call_count or specific args could be complex here
    # For simplicity, check if it was called at least once if matches were found
    if mock_retrieve_similar_chunks.return_value:  # If retrieve found matches
        mock_assess_llm.assert_called()

    mock_generate_report.assert_called_once()
    # We can also assert some arguments passed to generate_report if needed


def test_run_pipeline_project_not_ready(tmp_path: Path, mock_app_settings: Settings):
    # Create a project that is NOT ready
    not_ready_project = CompareProject(
        name="NotReadyProject",
        controls_dir=tmp_path / "not_ready_controls"  # Dir might not exist or have no .txt
    )
    assert not not_ready_project.ready  # Pre-condition

    pipeline_settings = PipelineSettings.from_settings(mock_app_settings)

    # Store original report_path (should be None)
    original_report_path = not_ready_project.report_path

    run_pipeline(not_ready_project, pipeline_settings)

    # Verify that report_path was NOT changed because pipeline should skip
    assert not_ready_project.report_path == original_report_path

    # Verify no report file was created (assuming report path would be under tmp_path if created)
    # This is a bit indirect; ideally, check if any file named like "report_NotReadyProject_..." exists.
    # For simplicity, if report_path is still None, that's a strong indicator.
    # If pipeline created a report in a default location despite project not being ready, this would fail.
    # The current placeholder run_pipeline returns early if not project.ready.

    # Check if any .md files were created in a potential report directory (if one was made by mistake)
    # This depends on where run_pipeline attempts to save reports.
    # Our placeholder saves relative to project.controls_dir.parent / "reports"
    # If controls_dir is "tmp_path/not_ready_controls", parent is "tmp_path"
    potential_report_dir = tmp_path / "reports"
    if potential_report_dir.exists():
        md_files = list(potential_report_dir.glob("*.md"))
        assert not md_files, "No report should be generated for a non-ready project"

    # A more direct check could be to mock project.report_path assignment or file creation
    # to ensure it's not called, but current placeholder is simple enough.


# --- Tests for _get_doc_name from app.pipeline.aggregate ---
# Note: _get_doc_name is in aggregate.py, but testing here as it's pipeline related util.
# If test_aggregate.py existed, it would go there.
from app.pipeline.aggregate import _get_doc_name


def test_get_doc_name_found_with_filename():
    norm_doc = NormDoc(id="doc1", raw_doc_id="raw1", text_content="Test", metadata={"original_filename": "MyFile.txt"}, doc_type="control")
    norm_docs_map = {"doc1": norm_doc}
    result = _get_doc_name("doc1", norm_docs_map, "Control")
    assert result == "MyFile.txt"


def test_get_doc_name_found_no_filename():
    norm_doc = NormDoc(id="doc2", raw_doc_id="raw2", text_content="Test", metadata={}, doc_type="control")  # No original_filename
    norm_docs_map = {"doc2": norm_doc}
    result = _get_doc_name("doc2", norm_docs_map, "Control")
    assert result == "Control doc2"  # Fallback to "Prefix doc_id"


def test_get_doc_name_found_empty_metadata():
    norm_doc = NormDoc(id="doc3", raw_doc_id="raw3", text_content="Test", metadata=None, doc_type="control")  # Metadata is None
    norm_docs_map = {"doc3": norm_doc}
    result = _get_doc_name("doc3", norm_docs_map, "Procedure")
    assert result == "Procedure doc3"


def test_get_doc_name_not_found():
    norm_docs_map = {}  # Empty map
    result = _get_doc_name("doc4_not_in_map", norm_docs_map, "Evidence")
    assert result == "Evidence doc4_not_in_map"


def test_get_doc_name_doc_is_none_in_map():
    # Though map values should ideally be NormDoc, test robustness
    norm_docs_map = {"doc5": None}
    result = _get_doc_name("doc5", norm_docs_map, "Control")
    assert result == "Control doc5"


def test_get_doc_name_empty_map_and_id_not_found():
    norm_docs_map = {}
    result = _get_doc_name("doc6", norm_docs_map, "DefaultPrefix")
    assert result == "DefaultPrefix doc6"


# Further tests could include:
# - Mocking specific steps of a more detailed pipeline (_step1_load_data, etc.)
# - Testing behavior with different pipeline_settings values if they influence control flow
# - Testing error handling within the pipeline if it had try-except blocks for specific operations
