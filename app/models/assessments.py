from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class TripleAssessment(BaseModel):
    external_regulation_doc_id: str
    procedure_doc_id: str
    evidence_doc_id: str
    external_regulation_chunk_id: Optional[str] = None  # if matching at chunk level
    procedure_chunk_id: Optional[str] = None
    evidence_chunk_id: Optional[str] = None
    status: str  # e.g., "Pass", "Partial", "Fail", "Inconclusive"
    analysis: str  # textual explanation from LLM
    improvement_suggestion: Optional[str] = None  # from LLM
    score: Optional[float] = None  # numeric score if applicable
    llm_raw_output: Optional[Dict[str, Any]] = None  # for debugging


class PairAssessment(BaseModel):
    external_regulation_doc_id: str
    procedure_doc_id: str
    aggregated_status: str
    summary_analysis: str
    evidence_assessments: List[TripleAssessment]  # list of evidence assessments for this pair
    overall_score: Optional[float] = None


class MatchSet(BaseModel):
    query_norm_doc_id: str     # NormDoc ID of the query document
    query_embed_set_id: str    # EmbedSet ID of the query chunk
    query_chunk_text: str      # Text of the query chunk

    matched_norm_doc_id: str   # NormDoc ID of the matched document
    matched_embed_set_id: str  # EmbedSet ID of the matched chunk
    matched_chunk_text: str    # Text of the matched chunk
    
    score: float               # Similarity score (e.g., 1 / (1 + L2_distance))
    # Optional: raw L2 distance if needed for fine-tuning thresholds later
    raw_faiss_distance: Optional[float] = None

    # To identify the relationship (e.g. External Regulation -> Procedure)
    query_doc_type: str 
    matched_doc_type: str
