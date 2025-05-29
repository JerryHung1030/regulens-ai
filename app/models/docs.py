from typing import List, Dict, Any
from pathlib import Path
from pydantic import BaseModel

class RawDoc(BaseModel):
    id: str  # e.g., SHA256 of content or unique identifier
    source_path: Path
    content: str
    metadata: Dict[str, Any]  # e.g., page numbers for PDF, original filename
    doc_type: str  # e.g., "control", "procedure", "evidence"

class NormDoc(BaseModel):
    id: str  # can be same as RawDoc id or derived
    raw_doc_id: str
    text_content: str  # cleaned and normalized text
    sections: List[str]  # identified sections/chapters, if any
    metadata: Dict[str, Any]  # updated metadata
    doc_type: str

class EmbedSet(BaseModel):
    id: str  # e.g., hash of the NormDoc id + chunk index
    norm_doc_id: str
    chunk_text: str
    embedding: List[float]
    chunk_index: int
    total_chunks: int
    doc_type: str

class IndexMeta(BaseModel):
    index_file_path: Path  # Path to the .faiss file
    id_mapping_path: Path  # Path to the JSON file mapping FAISS index IDs to custom IDs (e.g., EmbedSet IDs)
    doc_type: str          # Type of documents indexed (e.g., "control", "procedure", "evidence")
    num_vectors: int       # Number of vectors in the index
    vector_dimension: int  # Dimension of the vectors (e.g., 1536 for text-embedding-ada-002, 3072 for text-embedding-3-large)
    model_name: str        # Name of the embedding model used to create these vectors (e.g., "text-embedding-3-large")
