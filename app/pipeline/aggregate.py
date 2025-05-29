from typing import List, Optional, Dict # Dict not used here but often useful
import numpy as np 

# Adjust import based on project structure and PYTHONPATH
try:
    from app.models.assessments import TripleAssessment, PairAssessment
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.assessments import TripleAssessment, PairAssessment # type: ignore


def aggregate_assessments_for_pair(
    control_doc_id: str, 
    procedure_doc_id: str, 
    triple_assessments: List[TripleAssessment]
) -> PairAssessment: # Ensure it always returns a PairAssessment

    if not triple_assessments:
        return PairAssessment(
            control_doc_id=control_doc_id,
            procedure_doc_id=procedure_doc_id,
            aggregated_status="NoEvidence", # Specific status for this case
            summary_analysis=f"No evidence items were provided or assessed for Control ID '{control_doc_id}' and Procedure ID '{procedure_doc_id}'.",
            evidence_assessments=[],
            overall_score=None
        )

    statuses = [ta.status for ta in triple_assessments]
    # Filter out None scores before calculation
    scores = [ta.score for ta in triple_assessments if ta.score is not None]

    # Determine aggregated_status based on priority
    if "Fail" in statuses:
        aggregated_status = "Fail"
    elif "Partial" in statuses:
        aggregated_status = "Partial"
    elif all(s == "Pass" for s in statuses): # Requires at least one "Pass" and all to be "Pass"
        aggregated_status = "Pass"
    # Handles cases where there might be a mix of "Pass" and "Inconclusive", or only "Inconclusive"
    elif "Pass" in statuses and "Inconclusive" in statuses:
        aggregated_status = "Partial" # Or could be "Inconclusive with Pass items" - "Partial" implies some level of success.
                                      # Let's refine: if Pass exists, and no Fail/Partial, but some Inconclusive, it's still largely a Pass scenario.
                                      # Re-evaluating this logic:
                                      # If only Pass and Inconclusive, this is better than "Partial".
                                      # Let's stick to the original hierarchy: Fail > Partial > All Pass > Inconclusive.
                                      # If it's a mix of Pass & Inconclusive, "Inconclusive" seems more appropriate than "Partial".
                                      # If all are "Inconclusive", then "Inconclusive".
    # If not all Pass (meaning some might be Inconclusive, assuming no Fail/Partial handled above)
    # or if only Inconclusive items are present.
    else: 
        aggregated_status = "Inconclusive"


    # Calculate overall_score
    overall_score_value: Optional[float] = None
    if scores:
        # Using np.mean, ensuring it handles empty list gracefully (though 'if scores:' covers this)
        overall_score_value = float(np.mean(scores)) if scores else None
        
    # Create summary_analysis
    summary_lines = [
        f"Overall assessment for Control ID '{control_doc_id}' and Procedure ID '{procedure_doc_id}': {aggregated_status}.",
    ]
    
    if aggregated_status != "NoEvidence":
        summary_lines.append("Summary of evidence findings based on available assessments:")

    # Determine which assessments to highlight in the summary
    # Prioritize showing details from "Fail" assessments, then "Partial"
    # If neither, show details from all (up to a limit)
    
    fail_assessments = [ta for ta in triple_assessments if ta.status == "Fail"]
    partial_assessments = [ta for ta in triple_assessments if ta.status == "Partial"]

    # Decide which list of assessments to iterate over for summary details
    if fail_assessments:
        assessments_to_summarize = fail_assessments
        summary_lines.append("Key 'Fail' findings:")
    elif partial_assessments:
        assessments_to_summarize = partial_assessments
        summary_lines.append("Key 'Partial' findings:")
    else: # No 'Fail' or 'Partial', summarize from all (e.g., 'Pass' or 'Inconclusive')
        assessments_to_summarize = triple_assessments
        if aggregated_status == "Pass":
             summary_lines.append("All evidence items were assessed as 'Pass'.")
        elif aggregated_status == "Inconclusive":
             summary_lines.append("Evidence items were assessed as 'Inconclusive' or a mix not leading to a 'Pass'.")


    # Limit the number of detailed lines in the summary to keep it concise
    max_detailed_lines = 3 
    detailed_lines_count = 0

    for ta in assessments_to_summarize:
        if detailed_lines_count >= max_detailed_lines and assessments_to_summarize is triple_assessments:
            summary_lines.append(f"  ... and {len(triple_assessments) - detailed_lines_count} more assessment(s). See individual assessments for full details.")
            break

        analysis_snippet = ta.analysis if ta.analysis else "N/A"
        if len(analysis_snippet) > 150: # Truncate long analyses for summary
            analysis_snippet = analysis_snippet[:147] + "..."
        
        suggestion_snippet = ""
        if ta.improvement_suggestion:
            suggestion_snippet = f" Suggestion: {ta.improvement_suggestion}"
            if len(suggestion_snippet) > 100: # Truncate long suggestions
                 suggestion_snippet = suggestion_snippet[:97] + "..."
        
        summary_lines.append(
            f"- Evidence (Doc: {ta.evidence_doc_id}, Chunk: {ta.evidence_chunk_id}): Status '{ta.status}'. Analysis: {analysis_snippet}{suggestion_snippet}"
        )
        detailed_lines_count += 1
            
    summary_analysis_str = "\n".join(summary_lines)

    return PairAssessment(
        control_doc_id=control_doc_id,
        procedure_doc_id=procedure_doc_id,
        aggregated_status=aggregated_status,
        summary_analysis=summary_analysis_str,
        evidence_assessments=triple_assessments, # Store all original triple assessments
        overall_score=overall_score_value
    )

if __name__ == '__main__':
    print("--- Test Aggregation Logic ---")
    
    # Sample TripleAssessments
    ta_c1p1_e1_pass = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e1", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk1", status="Pass", analysis="Evidence e1 clearly supports the procedure.", score=0.9, llm_raw_output={})
    ta_c1p1_e2_pass = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e2", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk2", status="Pass", analysis="Evidence e2 is also sufficient and aligns perfectly.", score=0.95, llm_raw_output={})
    ta_c1p1_e3_partial = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e3", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk3", status="Partial", analysis="Evidence e3 is mostly okay but lacks detail on point X.", improvement_suggestion="Provide logs for point X.", score=0.6, llm_raw_output={})
    ta_c1p1_e4_fail = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e4", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk4", status="Fail", analysis="Evidence e4 contradicts the procedure regarding step Y.", improvement_suggestion="Ensure procedure step Y is followed or update procedure.", score=0.2, llm_raw_output={})
    ta_c1p1_e5_inconclusive = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e5", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk5", status="Inconclusive", analysis="Evidence e5 is blurry and unreadable.", score=0.5, llm_raw_output={}) # Score is present
    ta_c1p1_e6_inconclusive_no_score = TripleAssessment(control_doc_id="c1", procedure_doc_id="p1", evidence_doc_id="e6", control_chunk_id="c_chk1", procedure_chunk_id="p_chk1", evidence_chunk_id="e_chk6", status="Inconclusive", analysis="Evidence e6 seems unrelated.", score=None, llm_raw_output={})


    # Test case 1: All Pass
    pair_all_pass = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e1_pass, ta_c1p1_e2_pass])
    print(f"\nTest Case: All Pass\n  Status: {pair_all_pass.aggregated_status}, Score: {pair_all_pass.overall_score:.3f}")
    print(f"  Summary:\n{pair_all_pass.summary_analysis}\n")
    assert pair_all_pass.aggregated_status == "Pass"
    assert pair_all_pass.overall_score is not None and abs(pair_all_pass.overall_score - 0.925) < 0.001

    # Test case 2: Mix with Partial (Pass, Partial)
    pair_with_partial = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e1_pass, ta_c1p1_e3_partial])
    print(f"Test Case: With Partial\n  Status: {pair_with_partial.aggregated_status}, Score: {pair_with_partial.overall_score:.3f}")
    print(f"  Summary:\n{pair_with_partial.summary_analysis}\n")
    assert pair_with_partial.aggregated_status == "Partial"
    assert pair_with_partial.overall_score is not None and abs(pair_with_partial.overall_score - 0.75) < 0.001

    # Test case 3: Mix with Fail (Pass, Partial, Fail)
    pair_with_fail = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e1_pass, ta_c1p1_e3_partial, ta_c1p1_e4_fail])
    print(f"Test Case: With Fail\n  Status: {pair_with_fail.aggregated_status}, Score: {pair_with_fail.overall_score:.3f}")
    print(f"  Summary:\n{pair_with_fail.summary_analysis}\n")
    assert pair_with_fail.aggregated_status == "Fail"
    assert pair_with_fail.overall_score is not None and abs(pair_with_fail.overall_score - (0.9 + 0.6 + 0.2) / 3) < 0.001

    # Test case 4: Only Inconclusive (one with score, one without)
    pair_inconclusive_mix = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e5_inconclusive, ta_c1p1_e6_inconclusive_no_score])
    print(f"Test Case: Only Inconclusive (mixed scores)\n  Status: {pair_inconclusive_mix.aggregated_status}, Score: {pair_inconclusive_mix.overall_score}") # score can be None or float
    print(f"  Summary:\n{pair_inconclusive_mix.summary_analysis}\n")
    assert pair_inconclusive_mix.aggregated_status == "Inconclusive"
    assert pair_inconclusive_mix.overall_score == 0.5 # Only ta5 has a score

    # Test case 5: Empty list
    pair_empty = aggregate_assessments_for_pair("c1", "p1", [])
    print(f"Test Case: Empty List\n  Status: {pair_empty.aggregated_status}, Score: {pair_empty.overall_score}")
    print(f"  Summary:\n{pair_empty.summary_analysis}\n")
    assert pair_empty.aggregated_status == "NoEvidence"
    assert pair_empty.overall_score is None
    
    # Test case 6: Mix of Pass and Inconclusive
    pair_pass_inconclusive = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e1_pass, ta_c1p1_e5_inconclusive])
    print(f"Test Case: Pass and Inconclusive\n  Status: {pair_pass_inconclusive.aggregated_status}, Score: {pair_pass_inconclusive.overall_score:.3f}")
    print(f"  Summary:\n{pair_pass_inconclusive.summary_analysis}\n")
    # Based on refined logic: Fail > Partial > All Pass > Inconclusive. Mix of Pass and Inconclusive should be Inconclusive.
    assert pair_pass_inconclusive.aggregated_status == "Inconclusive" 
    assert pair_pass_inconclusive.overall_score is not None and abs(pair_pass_inconclusive.overall_score - (0.9 + 0.5) / 2) < 0.001

    # Test case 7: All Inconclusive (multiple items)
    pair_all_inconclusive = aggregate_assessments_for_pair("c1", "p1", [ta_c1p1_e5_inconclusive, ta_c1p1_e5_inconclusive]) # Using same item twice for simplicity
    print(f"Test Case: All Inconclusive (multiple)\n  Status: {pair_all_inconclusive.aggregated_status}, Score: {pair_all_inconclusive.overall_score:.3f}")
    print(f"  Summary:\n{pair_all_inconclusive.summary_analysis}\n")
    assert pair_all_inconclusive.aggregated_status == "Inconclusive"
    assert pair_all_inconclusive.overall_score == 0.5


    print("\nAggregation logic tests passed.")
