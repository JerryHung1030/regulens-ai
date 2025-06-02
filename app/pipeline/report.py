import collections
from pathlib import Path
from typing import List, Optional, Dict

import pdfkit # type: ignore # Assuming pdfkit is installed

# Adjust import based on project structure and PYTHONPATH
try:
    from app.models.assessments import PairAssessment, TripleAssessment
    from app.models.docs import NormDoc, EmbedSet 
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.assessments import PairAssessment, TripleAssessment # type: ignore
    from app.models.docs import NormDoc, EmbedSet # type: ignore


def _build_markdown_content(
    grouped_assessments: Dict[str, List[PairAssessment]],
    controls_map: Dict[str, NormDoc],
    procedures_map: Dict[str, NormDoc],
    evidences_map: Dict[str, EmbedSet] # EmbedSet.id -> EmbedSet
) -> str:
    md_lines = ["# Compliance Audit Report"]
    md_lines.append("This report details the assessment of procedures and evidence against defined controls.")

    if not grouped_assessments:
        md_lines.append("\n**No assessment data provided for this report.**")
        return "\n".join(md_lines)

    for control_id, pair_assessments_for_control in grouped_assessments.items():
        control_doc = controls_map.get(control_id)
        control_text = control_doc.text_content if control_doc else f"Control text not found for ID: {control_id}."
        
        md_lines.append(f"\n\n## Control ID: `{control_id}`")
        md_lines.append(f"**Control Requirement Text:**\n```text\n{control_text}\n```")

        if not pair_assessments_for_control:
            md_lines.append("\n*No procedures were assessed under this control.*")
            continue

        for pair in pair_assessments_for_control:
            proc_doc = procedures_map.get(pair.procedure_doc_id)
            proc_text = proc_doc.text_content if proc_doc else f"Procedure text not found for ID: {pair.procedure_doc_id}."
            
            md_lines.append(f"\n### Procedure ID: `{pair.procedure_doc_id}`")
            md_lines.append(f"**Procedure Text:**\n```text\n{proc_text}\n```")
            md_lines.append(f"\n**Procedure Assessment Summary:**")
            md_lines.append(f"- **Overall Aggregated Status:** `{pair.aggregated_status}`")
            md_lines.append(f"- **Calculated Overall Score:** `{pair.overall_score if pair.overall_score is not None else 'N/A'}`")
            md_lines.append(f"\n**Summary Analysis from Aggregation:**\n```text\n{pair.summary_analysis}\n```")
            
            if pair.evidence_assessments:
                md_lines.append("\n**Detailed Evidence Assessments for this Procedure:**")
                for i, ta in enumerate(pair.evidence_assessments):
                    evidence_embed_set = evidences_map.get(ta.evidence_chunk_id)
                    evidence_text = evidence_embed_set.chunk_text if evidence_embed_set else "Evidence text not found for this chunk."
                    
                    md_lines.append(f"\n#### Evidence Assessment {i+1}")
                    md_lines.append(f"- **Evidence Document ID:** `{ta.evidence_doc_id}`")
                    md_lines.append(f"- **Evidence Chunk ID:** `{ta.evidence_chunk_id}`")
                    md_lines.append(f"  - **Evidence Text Snippet:**\n    ```text\n    {evidence_text[:350]}{'...' if len(evidence_text)>350 else ''}\n    ```")
                    md_lines.append(f"  - **Status:** `{ta.status}`")
                    md_lines.append(f"  - **LLM Confidence Score:** `{ta.score if ta.score is not None else 'N/A'}`")
                    md_lines.append(f"  - **LLM Analysis:** {ta.analysis if ta.analysis else 'N/A'}")
                    if ta.improvement_suggestion:
                        md_lines.append(f"  - **LLM Suggestion:** {ta.improvement_suggestion}")
            else:
                md_lines.append("\n*No individual evidence assessments provided for this procedure.*")
            md_lines.append("\n---") # Separator for procedures under the same control
        md_lines.append("\n--- ---") # Separator for controls
        
    return "\n".join(md_lines)

def _convert_markdown_to_pdf(md_file_path: Path, pdf_file_path: Path, css_path: Optional[Path]) -> bool:
    try:
        options = {
            'enable-local-file-access': None, # Allow access to local files (e.g., CSS, images)
            'quiet': '' # Suppress wkhtmltopdf output unless error
        }
        pdfkit_css_arg = str(css_path) if css_path and css_path.exists() else None
        if css_path and not (css_path.exists()):
            print(f"Warning: CSS theme file not found at {css_path}. PDF will be unstyled.")

        pdfkit.from_file(str(md_file_path), str(pdf_file_path), css=pdfkit_css_arg, options=options)
        print(f"PDF report generated successfully: {pdf_file_path}")
        return True
    except OSError as e: 
        if "wkhtmltopdf" in str(e).lower(): # More specific check for wkhtmltopdf
            print(f"ERROR: Could not generate PDF report. `wkhtmltopdf` executable not found or not accessible. Please ensure it is installed and in your system's PATH. Error: {e}")
        else:
            print(f"ERROR: An OS error occurred during PDF generation: {e}")
    except Exception as e: 
        print(f"ERROR: Failed to convert Markdown to PDF using pdfkit. Error: {e}")
    return False

def generate_report(
    all_pair_assessments: List[PairAssessment],
    controls_map: Dict[str, NormDoc], 
    procedures_map: Dict[str, NormDoc],
    evidences_map: Dict[str, EmbedSet], 
    report_output_dir: Path,
    report_filename_base: str = "compliance_audit_report", # Default filename base
    report_theme_css_path: Optional[Path] = None,
    make_pdf: bool = False  # 新增參數，預設為 False
) -> Optional[Path]:

    try:
        report_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating report output directory {report_output_dir}: {e}")
        return None

    grouped_by_control: Dict[str, List[PairAssessment]] = collections.defaultdict(list)
    for pa in all_pair_assessments:
        grouped_by_control[pa.control_doc_id].append(pa)

    if not all_pair_assessments: # Check if original list is empty, not just grouped_by_control
        print("No assessments provided to generate report. Report will be minimal.")
        # Still generate a report saying no data, as _build_markdown_content handles empty grouped_assessments.

    markdown_content = _build_markdown_content(grouped_by_control, controls_map, procedures_map, evidences_map)
    
    md_file = report_output_dir / f"{report_filename_base}.md"
    pdf_file = report_output_dir / f"{report_filename_base}.pdf"

    try:
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"Markdown report generated successfully: {md_file}")
    except IOError as e:
        print(f"Error writing Markdown file {md_file}: {e}")
        return None # Cannot proceed if Markdown file fails

    # 只在 make_pdf 為 True 時才嘗試生成 PDF
    if make_pdf:
        pdf_success = _convert_markdown_to_pdf(md_file, pdf_file, report_theme_css_path)
        if not pdf_success:
            print(f"Warning: PDF generation failed or was skipped. The Markdown report is available at {md_file}.")
    else:
        print(f"PDF generation skipped as make_pdf=False. The Markdown report is available at {md_file}")
            
    return md_file # Return path to MD file as primary output

if __name__ == '__main__':
    from app.models.docs import NormDoc, EmbedSet 
    
    print("--- Test Report Generation Module ---")
    temp_report_output_dir = Path("temp_report_generation_output")
    
    # Create dummy data for testing
    # Controls
    c1 = NormDoc(id="CTRL_001", raw_doc_id="raw_c1", text_content="Control 001: All systems must use strong, unique passwords changed every 90 days.", sections=["Password Policy"], metadata={}, doc_type="control")
    c2 = NormDoc(id="CTRL_002", raw_doc_id="raw_c2", text_content="Control 002: Physical access to data centers must be restricted to authorized personnel only.", sections=["Physical Security"], metadata={}, doc_type="control")
    
    # Procedures
    p1_c1 = NormDoc(id="PROC_A_001", raw_doc_id="raw_p1c1", text_content="Procedure for CTRL_001: Users are forced to change passwords via system prompt. Complexity rules are enforced by AD policy GRP-SYS-PW.", sections=[], metadata={}, doc_type="procedure")
    p2_c2 = NormDoc(id="PROC_B_001", raw_doc_id="raw_p2c2", text_content="Procedure for CTRL_002: Access is managed by key card system. Logs are reviewed monthly.", sections=[], metadata={}, doc_type="procedure")

    # Evidence EmbedSets (chunk text is key)
    e1_p1 = EmbedSet(id="EVID_CHUNK_001", norm_doc_id="EVID_DOC_X01", chunk_text="Active Directory Group Policy GRP-SYS-PW screenshot showing password length 12, complexity enabled, max age 90 days.", embedding=[], chunk_index=0, total_chunks=1, doc_type="evidence")
    e2_p1 = EmbedSet(id="EVID_CHUNK_002", norm_doc_id="EVID_DOC_X02", chunk_text="System log snippet: User 'testuser' password change forced on 2023-03-15.", embedding=[], chunk_index=0, total_chunks=1, doc_type="evidence")
    e3_p2 = EmbedSet(id="EVID_CHUNK_003", norm_doc_id="EVID_DOC_Y01", chunk_text="Key card access log for DC-01, dated 2023-04-01, showing authorized entries only.", embedding=[], chunk_index=0, total_chunks=1, doc_type="evidence")

    # Triple Assessments
    ta1_p1e1 = TripleAssessment(control_doc_id="CTRL_001", procedure_doc_id="PROC_A_001", evidence_doc_id="EVID_DOC_X01", control_chunk_id="cchk1", procedure_chunk_id="pchk1", evidence_chunk_id="EVID_CHUNK_001", status="Pass", analysis="AD Policy screenshot aligns with control.", score=0.95, llm_raw_output={})
    ta2_p1e2 = TripleAssessment(control_doc_id="CTRL_001", procedure_doc_id="PROC_A_001", evidence_doc_id="EVID_DOC_X02", control_chunk_id="cchk1", procedure_chunk_id="pchk1", evidence_chunk_id="EVID_CHUNK_002", status="Partial", analysis="Log shows password change, but not complexity enforcement at that point.", improvement_suggestion="Provide evidence of complexity check during change.", score=0.6, llm_raw_output={})
    ta3_p2e3 = TripleAssessment(control_doc_id="CTRL_002", procedure_doc_id="PROC_B_001", evidence_doc_id="EVID_DOC_Y01", control_chunk_id="cchk2", procedure_chunk_id="pchk2", evidence_chunk_id="EVID_CHUNK_003", status="Pass", analysis="Key card logs confirm restricted access.", score=0.9, llm_raw_output={})

    # Pair Assessments
    pair_p1_c1 = PairAssessment(control_doc_id="CTRL_001", procedure_doc_id="PROC_A_001", aggregated_status="Partial", summary_analysis="Overall Partial for PROC_A_001 due to one evidence item needing more detail.", evidence_assessments=[ta1_p1e1, ta2_p1e2], overall_score=0.775)
    pair_p2_c2 = PairAssessment(control_doc_id="CTRL_002", procedure_doc_id="PROC_B_001", aggregated_status="Pass", summary_analysis="Overall Pass for PROC_B_001, evidence is sufficient.", evidence_assessments=[ta3_p2e3], overall_score=0.9)

    all_pairs_list = [pair_p1_c1, pair_p2_c2]
    controls_data_map = {"CTRL_001": c1, "CTRL_002": c2}
    procedures_data_map = {"PROC_A_001": p1_c1, "PROC_B_001": p2_c2}
    evidences_data_map = {"EVID_CHUNK_001": e1_p1, "EVID_CHUNK_002": e2_p1, "EVID_CHUNK_003": e3_p2}

    # Test with a CSS file (optional, create a dummy one for testing if not present)
    dummy_css_path = temp_report_output_dir / "dummy_theme.css"
    try:
        with open(dummy_css_path, "w") as f_css:
            f_css.write("body { font-family: sans-serif; color: #333; } h1 { color: navy; }")
        print(f"Created dummy CSS theme: {dummy_css_path}")
    except IOError:
        print(f"Could not create dummy CSS file at {dummy_css_path}, will test without styling.")
        dummy_css_path = None


    print("\n--- Test 1: Generate Full Report ---")
    report_md_file_path = generate_report(
        all_pair_assessments=all_pairs_list, 
        controls_map=controls_data_map, 
        procedures_map=procedures_data_map, 
        evidences_map=evidences_data_map,
        report_output_dir=temp_report_output_dir,
        report_filename_base="full_audit_report_test",
        report_theme_css_path=dummy_css_path if dummy_css_path and dummy_css_path.exists() else None
    )

    if report_md_file_path and report_md_file_path.exists():
        print(f"Markdown report generated: {report_md_file_path}")
        # Check for PDF (may not exist if wkhtmltopdf is missing)
        report_pdf_file_path = temp_report_output_dir / "full_audit_report_test.pdf"
        if report_pdf_file_path.exists():
            print(f"PDF also generated: {report_pdf_file_path}")
        else:
            print("PDF not generated (this might be expected if wkhtmltopdf is not installed/configured).")
    else:
        print("Full report generation FAILED or MD file not created.")

    print("\n--- Test 2: Generate Report with No Assessments ---")
    report_empty_md_path = generate_report(
        all_pair_assessments=[], 
        controls_map=controls_data_map, # Maps might still have data
        procedures_map=procedures_data_map, 
        evidences_map=evidences_data_map,
        report_output_dir=temp_report_output_dir,
        report_filename_base="empty_assessments_report_test"
    )
    if report_empty_md_path and report_empty_md_path.exists():
        print(f"Report for empty assessments generated: {report_empty_md_path}")
        with open(report_empty_md_path, "r") as f_empty_rep:
            content = f_empty_rep.read()
            assert "No assessment data provided" in content # Check for specific message
        print("Empty assessments report content verified.")
    else:
        print("Report generation for empty assessments FAILED or MD file not created.")

    # Clean up
    try:
        import shutil
        if temp_report_output_dir.exists():
            # print(f"\nCleaning up temporary report output directory: {temp_report_output_dir}")
            shutil.rmtree(temp_report_output_dir)
    except Exception as e_clean:
        print(f"Error cleaning up test report output directory {temp_report_output_dir}: {e_clean}")

    print("\nReport generation module test finished.")
