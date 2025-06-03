import collections
from pathlib import Path
from typing import List, Optional, Dict

import pdfkit  # type: ignore # Assuming pdfkit is installed

# Adjust import based on project structure and PYTHONPATH
try:
    from app.models.assessments import PairAssessment, TripleAssessment
    from app.models.docs import NormDoc, EmbedSet
    from app.settings import Settings
    from app.i18n import MESSAGES
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.assessments import PairAssessment, TripleAssessment  # type: ignore
    from app.models.docs import NormDoc, EmbedSet  # type: ignore
    from app.settings import Settings  # type: ignore
    from app.i18n import MESSAGES     # type: ignore


def _get_norm_name(norm_id: str, norm_doc: Optional[NormDoc], default_id: str) -> str:
    """Helper to get original_filename or fallback to the norm_id itself."""
    if norm_doc and norm_doc.metadata:
        return norm_doc.metadata.get("original_filename", default_id)
    return default_id


def _build_markdown_content(
    grouped_assessments: Dict[str, List[PairAssessment]],
    controls_map: Dict[str, NormDoc],
    procedures_map: Dict[str, NormDoc],
    evidences_map: Dict[str, EmbedSet],  # EmbedSet.id (chunk_id) -> EmbedSet
    all_norm_docs_map: Dict[str, NormDoc],  # norm_doc.id -> NormDoc (for all types)
    texts: Dict[str, str]
) -> str:
    md_lines = [f"# {texts['report_title']}"]
    md_lines.append("This report details the assessment of procedures and evidence against defined controls.")

    if not grouped_assessments:
        md_lines.append(f"\n**{texts['summary_no_data']}**")
        return "\n".join(md_lines)

    for control_id, pair_assessments_for_control in grouped_assessments.items():
        control_doc = controls_map.get(control_id)
        control_name = _get_norm_name(control_id, control_doc, control_id)
        control_text = control_doc.text_content if control_doc else f"Control text not found for ID: {control_id}."
        
        md_lines.append(f"\n\n## {texts['section_control'].format(control_name=control_name, control_id=control_id)}")
        md_lines.append(f"**{texts['control_requirement_text']}**\n```text\n{control_text}\n```")

        if not pair_assessments_for_control:
            md_lines.append(f"\n*{texts['no_procedures_assessed']}*")
            continue

        for pair_idx, pair in enumerate(pair_assessments_for_control):
            proc_doc = procedures_map.get(pair.procedure_doc_id)
            proc_name = _get_norm_name(pair.procedure_doc_id, proc_doc, pair.procedure_doc_id)
            proc_text = proc_doc.text_content if proc_doc else f"Procedure text not found for ID: {pair.procedure_doc_id}."
            
            md_lines.append(f"\n### {texts['section_procedure'].format(proc_name=proc_name, proc_id=pair.procedure_doc_id)}")
            md_lines.append(f"**{texts['procedure_text']}**\n```text\n{proc_text}\n```")
            md_lines.append(f"\n**{texts['procedure_assessment_summary']}**")
            md_lines.append(f"- **{texts['overall_aggregated_status']}** `{pair.aggregated_status}`")
            md_lines.append(f"- **{texts['calculated_overall_score']}** `{pair.overall_score if pair.overall_score is not None else texts['n_a']}`")
            md_lines.append(f"\n**{texts['summary_analysis_from_aggregation']}**\n```text\n{pair.summary_analysis}\n```")
            
            if pair.evidence_assessments:
                md_lines.append(f"\n**{texts['detailed_evidence_assessments']}**")
                for i, ta in enumerate(pair.evidence_assessments):
                    evidence_embed_set = evidences_map.get(ta.evidence_chunk_id)  # ta.evidence_chunk_id is the EmbedSet ID
                    evidence_text_snippet = evidence_embed_set.chunk_text if evidence_embed_set else "Evidence text not found for this chunk."
                    
                    # Get the parent NormDoc for the evidence document
                    evidence_norm_doc_id = ta.evidence_doc_id  # This is the ID of the parent NormDoc for the evidence
                    evidence_norm_doc = all_norm_docs_map.get(evidence_norm_doc_id)
                    evidence_name = _get_norm_name(evidence_norm_doc_id, evidence_norm_doc, evidence_norm_doc_id)
                    
                    md_lines.append(f"\n#### {texts['evidence_assessment_n'].format(index=i + 1)}")
                    md_lines.append(f"- {texts['evidence_document_name'].format(evidence_name=evidence_name, evidence_id=evidence_norm_doc_id)}")
                    # Removed line displaying chunk_id explicitly as per requirement
                    md_lines.append(f"  - **{texts['evidence_text_snippet']}**\n    ```text\n    {evidence_text_snippet[:350]}{'...' if len(evidence_text_snippet) > 350 else ''}\n    ```")
                    md_lines.append(f"  - **{texts['status']}** `{ta.status}`")
                    md_lines.append(f"  - **{texts['llm_confidence_score']}** `{ta.score if ta.score is not None else texts['n_a']}`")
                    md_lines.append(f"  - **{texts['llm_analysis']}** {ta.analysis if ta.analysis else texts['n_a']}")
                    if ta.improvement_suggestion:
                        md_lines.append(f"  - **{texts['llm_suggestion']}** {ta.improvement_suggestion}")
            else:
                md_lines.append(f"\n*{texts['no_individual_evidence_assessments']}*")
            
            if pair_idx < len(pair_assessments_for_control) - 1:
                md_lines.append("\n---") 
        md_lines.append("\n--- ---")
        
    return "\n".join(md_lines)


def _convert_markdown_to_pdf(md_file_path: Path, pdf_file_path: Path, css_path: Optional[Path], texts: Dict[str, str]) -> bool:
    try:
        options = {
            'enable-local-file-access': None, 
            'quiet': '' 
        }
        pdfkit_css_arg = str(css_path) if css_path and css_path.exists() else None
        if css_path and not (css_path.exists()):
            print(f"Warning: CSS theme file not found at {css_path}. PDF will be unstyled.") 

        pdfkit.from_file(str(md_file_path), str(pdf_file_path), css=pdfkit_css_arg, options=options)
        print(texts['pdf_report_generated_success'].format(filepath=pdf_file_path))
        return True
    except OSError as e: 
        if "wkhtmltopdf" in str(e).lower():
            print(texts['pdf_generation_failed'].format(error=f"`wkhtmltopdf` not found or accessible. Ensure it's installed and in PATH. Original error: {e}"))
        else:
            print(texts['pdf_generation_failed'].format(error=f"OS error during PDF generation: {e}"))
    except Exception as e: 
        print(texts['pdf_generation_failed'].format(error=f"pdfkit conversion failed: {e}"))
    return False


def generate_report(
    all_pair_assessments: List[PairAssessment],
    controls_map: Dict[str, NormDoc], 
    procedures_map: Dict[str, NormDoc],
    evidences_map: Dict[str, EmbedSet],  # Maps evidence_chunk_id to EmbedSet
    all_norm_docs_map: Dict[str, NormDoc],  # Maps norm_doc.id to NormDoc for all types
    report_output_dir: Path,
    report_filename_base: str = "compliance_audit_report",
    report_theme_css_path: Optional[Path] = None,
    make_pdf: bool = False
) -> Optional[Path]:

    settings = Settings()
    lang = settings.get("language", "en")
    texts = MESSAGES.get(lang, MESSAGES["en"])

    try:
        report_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating report output directory {report_output_dir}: {e}") 
        return None

    grouped_by_control: Dict[str, List[PairAssessment]] = collections.defaultdict(list)
    for pa in all_pair_assessments:
        grouped_by_control[pa.control_doc_id].append(pa)

    if not all_pair_assessments:
        print("No assessments provided to generate report. Report will be minimal.")

    markdown_content = _build_markdown_content(
        grouped_by_control, 
        controls_map, 
        procedures_map, 
        evidences_map,
        all_norm_docs_map,  # Pass the new map
        texts
    )
    
    md_file = report_output_dir / f"{report_filename_base}.md"
    pdf_file = report_output_dir / f"{report_filename_base}.pdf"

    try:
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(texts['md_report_generated_success'].format(filepath=md_file))
    except IOError as e:
        print(f"Error writing Markdown file {md_file}: {e}")
        return None

    if make_pdf:
        pdf_success = _convert_markdown_to_pdf(md_file, pdf_file, report_theme_css_path, texts)
        if not pdf_success:
            print(f"Warning: PDF generation failed or was skipped. The Markdown report is available at {md_file}.")
    else:
        print(f"PDF generation skipped as make_pdf=False. The Markdown report is available at {md_file}")
            
    return md_file


if __name__ == '__main__':
    from app.models.docs import NormDoc, EmbedSet 
    
    print("--- Test Report Generation Module (with Original Filenames) ---")
    temp_report_output_dir = Path("temp_report_generation_output_filenames")
    
    # Create dummy NormDoc data with metadata
    c1_meta = {"original_filename": "ControlPolicy_Passwords.txt"}
    c1 = NormDoc(id="CTRL_001", raw_doc_id="raw_c1", text_content="Control 001: Passwords.", sections=[], metadata=c1_meta, doc_type="control")
    
    p1_c1_meta = {"original_filename": "Procedure_AD_Password_Change.txt"}
    p1_c1 = NormDoc(id="PROC_A_001", raw_doc_id="raw_p1c1", text_content="Procedure for CTRL_001.", sections=[], metadata=p1_c1_meta, doc_type="procedure")

    # Evidence NormDocs (parent documents for EmbedSets)
    ev_doc_x01_meta = {"original_filename": "Evidence_AD_Policy_Screenshot.png"}
    ev_doc_x01 = NormDoc(id="EVID_DOC_X01", raw_doc_id="raw_ev_x01", text_content="Parent evidence doc for AD policy screenshot.", sections=[], metadata=ev_doc_x01_meta, doc_type="evidence_parent")
    
    ev_doc_x02_meta = {"original_filename": "Evidence_SystemLog_Snippet.log"}
    ev_doc_x02 = NormDoc(id="EVID_DOC_X02", raw_doc_id="raw_ev_x02", text_content="Parent evidence doc for system log.", sections=[], metadata=ev_doc_x02_meta, doc_type="evidence_parent")

    # EmbedSets (evidence chunks) - link to parent NormDoc via norm_doc_id
    e1_p1 = EmbedSet(id="EVID_CHUNK_001", norm_doc_id=ev_doc_x01.id, chunk_text="AD GPO screenshot...", embedding=[], chunk_index=0, total_chunks=1, doc_type="evidence")
    e2_p1 = EmbedSet(id="EVID_CHUNK_002", norm_doc_id=ev_doc_x02.id, chunk_text="System log snippet...", embedding=[], chunk_index=0, total_chunks=1, doc_type="evidence")

    # Triple Assessments - use evidence_doc_id which is the parent NormDoc ID
    ta1_p1e1 = TripleAssessment(control_doc_id=c1.id, procedure_doc_id=p1_c1.id, evidence_doc_id=ev_doc_x01.id, control_chunk_id="cchk1", procedure_chunk_id="pchk1", evidence_chunk_id=e1_p1.id, status="Pass", analysis="AD Policy screenshot aligns.", score=0.95, llm_raw_output={})
    ta2_p1e2 = TripleAssessment(control_doc_id=c1.id, procedure_doc_id=p1_c1.id, evidence_doc_id=ev_doc_x02.id, control_chunk_id="cchk1", procedure_chunk_id="pchk1", evidence_chunk_id=e2_p1.id, status="Partial", analysis="Log shows change.", score=0.6, llm_raw_output={})

    # Pair Assessments
    pair_p1_c1 = PairAssessment(control_doc_id=c1.id, procedure_doc_id=p1_c1.id, aggregated_status="Partial", summary_analysis="Overall Partial for PROC_A_001.", evidence_assessments=[ta1_p1e1, ta2_p1e2], overall_score=0.775)

    all_pairs_list = [pair_p1_c1]
    controls_data_map = {c1.id: c1}
    procedures_data_map = {p1_c1.id: p1_c1}
    evidences_embed_map = {e1_p1.id: e1_p1, e2_p1.id: e2_p1}  # chunk_id -> EmbedSet

    # New all_norm_docs_map
    all_norm_docs_data_map = {
        c1.id: c1, 
        p1_c1.id: p1_c1,
        ev_doc_x01.id: ev_doc_x01,
        ev_doc_x02.id: ev_doc_x02
    }

    dummy_css_path = temp_report_output_dir / "dummy_theme.css"
    try:
        temp_report_output_dir.mkdir(parents=True, exist_ok=True)
        with open(dummy_css_path, "w", encoding="utf-8") as f_css:
            f_css.write("body { font-family: sans-serif; }")
        print(f"Created dummy CSS theme: {dummy_css_path}")
    except IOError:
        print(f"Could not create dummy CSS file at {dummy_css_path}, will test without styling.")
        dummy_css_path = None

    print("\n--- Test: Generate Full Report with Original Filenames (MD only) ---")
    report_md_file_path = generate_report(
        all_pair_assessments=all_pairs_list, 
        controls_map=controls_data_map, 
        procedures_map=procedures_data_map, 
        evidences_map=evidences_embed_map,  # This is EmbedSet map
        all_norm_docs_map=all_norm_docs_data_map,  # New map
        report_output_dir=temp_report_output_dir,
        report_filename_base="full_audit_report_filenames_test",
        report_theme_css_path=dummy_css_path if dummy_css_path and dummy_css_path.exists() else None,
        make_pdf=False
    )

    if report_md_file_path and report_md_file_path.exists():
        print(f"Markdown report generated: {report_md_file_path}")
        # You can open and verify the content includes original filenames.
        with open(report_md_file_path, "r", encoding="utf-8") as f_rep:
            content = f_rep.read()
            assert "ControlPolicy_Passwords.txt" in content
            assert "Procedure_AD_Password_Change.txt" in content
            assert "Evidence_AD_Policy_Screenshot.png" in content
            assert "Evidence_SystemLog_Snippet.log" in content
            assert "Evidence Chunk ID:" not in content  # Check that chunk ID label is removed
            assert "Evidence Text Snippet:" in content
        print("Report content preliminarily verified for original filenames.")

    else:
        print("Full report generation FAILED or MD file not created.")
    
    # Clean up
    try:
        import shutil
        if temp_report_output_dir.exists():
            shutil.rmtree(temp_report_output_dir)
    except Exception as e_clean:
        print(f"Error cleaning up test report output directory {temp_report_output_dir}: {e_clean}")

    print("\nReport generation module test finished.")
