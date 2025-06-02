from typing import List, Optional, Dict  # Added Dict
import numpy as np 

try:
    from app.models.assessments import TripleAssessment, PairAssessment
    from app.models.docs import NormDoc  # Added
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.assessments import TripleAssessment, PairAssessment  # type: ignore
    from app.models.docs import NormDoc  # type: ignore # Added


def _get_doc_name(doc_id: str, norm_docs_map: Dict[str, NormDoc], default_prefix: str = "ID") -> str:
    """Helper to get original_filename or fallback to the doc_id."""
    doc = norm_docs_map.get(doc_id)
    if doc and doc.metadata and doc.metadata.get("original_filename"):
        return doc.metadata["original_filename"]
    return f"{default_prefix} {doc_id}"


def aggregate_assessments_for_pair(
    control_doc_id: str, 
    procedure_doc_id: str, 
    triple_assessments: List[TripleAssessment],
    all_norm_docs_map: Dict[str, NormDoc]  # Added
) -> PairAssessment:

    control_name = _get_doc_name(control_doc_id, all_norm_docs_map, "Control")
    procedure_name = _get_doc_name(procedure_doc_id, all_norm_docs_map, "Procedure")

    if not triple_assessments:
        return PairAssessment(
            control_doc_id=control_doc_id,
            procedure_doc_id=procedure_doc_id,
            aggregated_status="NoEvidence",
            summary_analysis=f"No evidence items were provided or assessed for Control '{control_name}' (`{control_doc_id}`) and Procedure '{procedure_name}' (`{procedure_doc_id}`).",
            evidence_assessments=[],
            overall_score=None
        )

    statuses = [ta.status for ta in triple_assessments]
    scores = [ta.score for ta in triple_assessments if ta.score is not None]

    if "Fail" in statuses:
        aggregated_status = "Fail"
    elif "Partial" in statuses:
        aggregated_status = "Partial"
    elif all(s == "Pass" for s in statuses):
        aggregated_status = "Pass"
    else: 
        aggregated_status = "Inconclusive"

    overall_score_value: Optional[float] = float(np.mean(scores)) if scores else None
        
    summary_lines = [
        f"Overall assessment for Control '{control_name}' (`{control_doc_id}`) and Procedure '{procedure_name}' (`{procedure_doc_id}`): {aggregated_status}.",
    ]
    
    if aggregated_status != "NoEvidence":
        summary_lines.append("Summary of evidence findings based on available assessments:")

    fail_assessments = [ta for ta in triple_assessments if ta.status == "Fail"]
    partial_assessments = [ta for ta in triple_assessments if ta.status == "Partial"]

    if fail_assessments:
        assessments_to_summarize = fail_assessments
        summary_lines.append("Key 'Fail' findings:")
    elif partial_assessments:
        assessments_to_summarize = partial_assessments
        summary_lines.append("Key 'Partial' findings:")
    else:
        assessments_to_summarize = triple_assessments
        if aggregated_status == "Pass":
            summary_lines.append("All evidence items were assessed as 'Pass'.")
        elif aggregated_status == "Inconclusive":
            summary_lines.append("Evidence items were assessed as 'Inconclusive' or a mix not leading to a 'Pass'.")

    max_detailed_lines = 3 
    detailed_lines_count = 0

    for ta in assessments_to_summarize:
        if detailed_lines_count >= max_detailed_lines and assessments_to_summarize is triple_assessments:
            summary_lines.append(f"- ... and {len(triple_assessments) - detailed_lines_count} more assessment(s). See individual assessments for full details.")
            break

        status_icon = "ℹ️"
        if ta.status == "Pass": 
            status_icon = "✅"
        elif ta.status == "Partial": 
            status_icon = "⚠️"
        elif ta.status == "Fail": 
            status_icon = "❌"
        elif ta.status == "Inconclusive": 
            status_icon = "❓"

        analysis_text = ta.analysis if ta.analysis else "N/A"
        if len(analysis_text) > 150: 
            analysis_text = analysis_text[:147] + "..."
        
        suggestion_text = ta.improvement_suggestion if ta.improvement_suggestion else "N/A"
        if len(suggestion_text) > 100 and suggestion_text != "N/A": 
            suggestion_text = suggestion_text[:97] + "..."

        evidence_name = _get_doc_name(ta.evidence_doc_id, all_norm_docs_map, "Evidence")
        
        evidence_summary = f"- {status_icon} **Evidence:** '{evidence_name}' (`{ta.evidence_doc_id}`), Chunk: `{ta.evidence_chunk_id}`\n  - **Status:** {ta.status}\n  - **Analysis:** {analysis_text}"
        if suggestion_text != "N/A":
            evidence_summary += f"\n  - **Suggestion:** {suggestion_text}"
        
        summary_lines.append(evidence_summary)
        detailed_lines_count += 1
            
    summary_analysis_str = "\n".join(summary_lines)

    return PairAssessment(
        control_doc_id=control_doc_id,
        procedure_doc_id=procedure_doc_id,
        aggregated_status=aggregated_status,
        summary_analysis=summary_analysis_str,
        evidence_assessments=triple_assessments,
        overall_score=overall_score_value
    )


if __name__ == '__main__':
    print("--- Test Aggregation Logic (with Original Filenames) ---")
    
    # Dummy NormDocs with metadata for filenames
    control_doc = NormDoc(id="c1", raw_doc_id="raw_c1", text_content="Control Text 1", metadata={"original_filename": "ControlPolicy_Access.txt"}, doc_type="control")
    procedure_doc = NormDoc(id="p1", raw_doc_id="raw_p1", text_content="Procedure Text 1", metadata={"original_filename": "Procedure_User_Onboarding.docx"}, doc_type="procedure")
    evidence_doc1 = NormDoc(id="e1", raw_doc_id="raw_e1", text_content="Evidence Text 1", metadata={"original_filename": "Evidence_Screenshot_AD.png"}, doc_type="evidence_parent")
    evidence_doc2 = NormDoc(id="e2", raw_doc_id="raw_e2", text_content="Evidence Text 2", metadata={"original_filename": "Evidence_Logfile.csv"}, doc_type="evidence_parent")
    evidence_doc3 = NormDoc(id="e3", raw_doc_id="raw_e3", text_content="Evidence Text 3", metadata={"original_filename": "Evidence_HR_Record.pdf"}, doc_type="evidence_parent")
    evidence_doc4 = NormDoc(id="e4", raw_doc_id="raw_e4", text_content="Evidence Text 4", metadata={"original_filename": "Evidence_Config_Server.ini"}, doc_type="evidence_parent")
    evidence_doc5 = NormDoc(id="e5", raw_doc_id="raw_e5", text_content="Evidence Text 5", metadata={"original_filename": "Evidence_Photo_Datacenter.jpg"}, doc_type="evidence_parent")
    evidence_doc6 = NormDoc(id="e6", raw_doc_id="raw_e6", text_content="Evidence Text 6", metadata={"original_filename": "Evidence_Interview_Notes.txt"}, doc_type="evidence_parent")

    all_docs_map = {
        "c1": control_doc, "p1": procedure_doc,
        "e1": evidence_doc1, "e2": evidence_doc2, "e3": evidence_doc3,
        "e4": evidence_doc4, "e5": evidence_doc5, "e6": evidence_doc6
    }

    # Sample TripleAssessments (using the NormDoc IDs from above)
    ta_c1p1_e1_pass = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e1", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk1", status="Pass", analysis="Evidence e1 clearly supports.", score=0.9, llm_raw_output={})
    ta_c1p1_e2_pass = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e2", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk2", status="Pass", analysis="Evidence e2 is also sufficient.", score=0.95, llm_raw_output={})
    ta_c1p1_e3_partial = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e3", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk3", status="Partial", analysis="Evidence e3 lacks detail.", improvement_suggestion="Provide logs.", score=0.6, llm_raw_output={})
    ta_c1p1_e4_fail = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e4", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk4", status="Fail", analysis="Evidence e4 contradicts.", improvement_suggestion="Ensure procedure followed.", score=0.2, llm_raw_output={})
    ta_c1p1_e5_inconclusive = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e5", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk5", status="Inconclusive", analysis="Evidence e5 blurry.", score=0.5, llm_raw_output={})
    ta_c1p1_e6_inconclusive_no_score = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e6", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk6", status="Inconclusive", analysis="Evidence e6 unrelated.", score=None, llm_raw_output={})

    # Test case 1: All Pass
    pair_all_pass = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e1_pass, ta_c1p1_e2_pass], all_docs_map)
    print(f"\nTest Case: All Pass\n  Status: {pair_all_pass.aggregated_status}, Score: {pair_all_pass.overall_score:.3f}")
    print(f"  Summary:\n{pair_all_pass.summary_analysis}\n")
    assert pair_all_pass.aggregated_status == "Pass"
    assert "Control 'ControlPolicy_Access.txt'" in pair_all_pass.summary_analysis
    assert "Procedure 'Procedure_User_Onboarding.docx'" in pair_all_pass.summary_analysis
    assert "Evidence: 'Evidence_Screenshot_AD.png'" in pair_all_pass.summary_analysis
    assert "Evidence: 'Evidence_Logfile.csv'" in pair_all_pass.summary_analysis

    # Test case 2: Mix with Partial
    pair_with_partial = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e1_pass, ta_c1p1_e3_partial], all_docs_map)
    print(f"Test Case: With Partial\n  Status: {pair_with_partial.aggregated_status}, Score: {pair_with_partial.overall_score:.3f}")
    print(f"  Summary:\n{pair_with_partial.summary_analysis}\n")
    assert pair_with_partial.aggregated_status == "Partial"
    assert "Evidence: 'Evidence_HR_Record.pdf'" in pair_with_partial.summary_analysis
    assert "Key 'Partial' findings:" in pair_with_partial.summary_analysis

    # Test case 3: Mix with Fail
    pair_with_fail = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e1_pass, ta_c1p1_e3_partial, ta_c1p1_e4_fail], all_docs_map)
    print(f"Test Case: With Fail\n  Status: {pair_with_fail.aggregated_status}, Score: {pair_with_fail.overall_score:.3f}")
    print(f"  Summary:\n{pair_with_fail.summary_analysis}\n")
    assert pair_with_fail.aggregated_status == "Fail"
    assert "Evidence: 'Evidence_Config_Server.ini'" in pair_with_fail.summary_analysis
    assert "Key 'Fail' findings:" in pair_with_fail.summary_analysis

    # Test case 4: Only Inconclusive
    pair_inconclusive_mix = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e5_inconclusive, ta_c1p1_e6_inconclusive_no_score], all_docs_map)
    print(f"Test Case: Only Inconclusive (mixed scores)\n  Status: {pair_inconclusive_mix.aggregated_status}, Score: {pair_inconclusive_mix.overall_score}")
    print(f"  Summary:\n{pair_inconclusive_mix.summary_analysis}\n")
    assert pair_inconclusive_mix.aggregated_status == "Inconclusive"
    assert "Evidence: 'Evidence_Photo_Datacenter.jpg'" in pair_inconclusive_mix.summary_analysis
    assert "Evidence: 'Evidence_Interview_Notes.txt'" in pair_inconclusive_mix.summary_analysis
    assert "Evidence items were assessed as 'Inconclusive'" in pair_inconclusive_mix.summary_analysis

    # Test case 5: Empty list
    pair_empty = aggregate_assessments_for_pair("c1", "p1", [], all_docs_map)
    print(f"Test Case: Empty List\n  Status: {pair_empty.aggregated_status}, Score: {pair_empty.overall_score}")
    print(f"  Summary:\n{pair_empty.summary_analysis}\n")
    assert pair_empty.aggregated_status == "NoEvidence"
    assert "No evidence items were provided" in pair_empty.summary_analysis
    assert "Control 'ControlPolicy_Access.txt'" in pair_empty.summary_analysis  # Check names even in NoEvidence case
    assert "Procedure 'Procedure_User_Onboarding.docx'" in pair_empty.summary_analysis

    print("\nAggregation logic tests (with filenames) passed.")
