import json
import re
from pathlib import Path
from typing import List, Optional

import faiss  # type: ignore
import numpy as np
import urllib.parse
import base64

# Adjust import based on project structure and PYTHONPATH
try:
    from app.models.docs import EmbedSet, IndexMeta
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.docs import EmbedSet, IndexMeta  # type: ignore


def _sanitize_filename(name: str) -> str:
    """Sanitizes a string to be filesystem-friendly."""
    # 將中文字串轉換為 base64 編碼
    encoded = base64.urlsafe_b64encode(name.encode('utf-8')).decode('ascii')
    # 移除 base64 編碼中的 = 符號
    encoded = encoded.rstrip('=')
    # 確保檔案名稱不會太長
    if len(encoded) > 255:
        encoded = encoded[:255]
    return encoded


def _create_index_files(
    all_embed_sets: List[EmbedSet], 
    index_file_path: Path, 
    id_mapping_file_path: Path,
    doc_type: str,
    embedding_model_name: str,
    vector_dimension: int
) -> Optional[IndexMeta]:
    
    print(f"Creating new FAISS index for doc_type '{doc_type}' (model: {embedding_model_name}) at {index_file_path}...")

    if not all_embed_sets:  # Should be caught earlier, but as a safeguard in helper
        print(f"Error: _create_index_files called with empty all_embed_sets for '{doc_type}'.")
        return None

    embeddings_np = np.array([es.embedding for es in all_embed_sets]).astype('float32')
    
    # Validate dimensions again, though should match vector_dimension argument
    if embeddings_np.ndim != 2 or embeddings_np.shape[1] != vector_dimension:
        print(f"Error: Embeddings have inconsistent dimensions or shape. Expected 2D array with dim {vector_dimension}, got shape {embeddings_np.shape}. Cannot build index.")
        return None

    # This list maps FAISS internal ID (which is the index in this list) to our EmbedSet.id
    faiss_id_to_embedset_id_map: List[str] = [es.id for es in all_embed_sets]
    
    # These are the numerical IDs (0 to N-1) that FAISS will use internally
    numerical_faiss_ids = np.array(range(len(all_embed_sets)), dtype=np.int64)

    try:
        # Using IndexIDMap2 to associate our sequential numerical_faiss_ids with vectors
        # IndexFlatL2 performs exhaustive L2 distance search.
        index = faiss.IndexIDMap2(faiss.IndexFlatL2(vector_dimension))
        index.add_with_ids(embeddings_np, numerical_faiss_ids)

        faiss.write_index(index, str(index_file_path))
        with open(id_mapping_file_path, 'w', encoding='utf-8') as f:
            json.dump(faiss_id_to_embedset_id_map, f, indent=2)  # Store as JSON list

        print(f"Successfully created and saved index for '{doc_type}'. Vectors: {index.ntotal}, Dimension: {index.d}")
        return IndexMeta(
            index_file_path=index_file_path.resolve(),
            id_mapping_path=id_mapping_file_path.resolve(),
            doc_type=doc_type,
            num_vectors=index.ntotal,
            vector_dimension=index.d,
            model_name=embedding_model_name
        )
    except Exception as e:
        print(f"Error creating FAISS index for '{doc_type}': {e}")
        # Clean up partially created files on error
        if index_file_path.exists():
            try:
                index_file_path.unlink()
            except OSError:
                print(f"Warning: Could not delete partial index file {index_file_path}")
        if id_mapping_file_path.exists():
            try:
                id_mapping_file_path.unlink()
            except OSError:
                print(f"Warning: Could not delete partial map file {id_mapping_file_path}")
        return None


def create_or_load_index(
    all_embed_sets: List[EmbedSet], 
    index_dir: Path, 
    doc_type: str, 
    embedding_model_name: str,
    force_recreate: bool = False
) -> Optional[IndexMeta]:

    if not all_embed_sets:
        print(f"Warning: No embed sets provided for doc_type '{doc_type}' (model: {embedding_model_name}). Cannot build or load index.")
        return None

    index_dir.mkdir(parents=True, exist_ok=True)

    safe_model_name = _sanitize_filename(embedding_model_name)
    base_filename = f"{doc_type}_{safe_model_name}"
    index_file_path = index_dir / f"{base_filename}.faiss"
    id_mapping_file_path = index_dir / f"{base_filename}_map.json"

    # Determine vector dimension from the first EmbedSet
    # Assuming all embeddings in the list have the same dimension, which should be guaranteed by earlier steps.
    if not all_embed_sets[0].embedding:  # Check if the first embedding list is empty
        print(f"Error: First EmbedSet for '{doc_type}' has an empty embedding list. Cannot determine vector dimension.")
        return None
    vector_dimension = len(all_embed_sets[0].embedding)
    if vector_dimension == 0:  # Check if dimension is zero
        print(f"Error: Vector dimension for '{doc_type}' is 0. Cannot build index.")
        return None

    if not force_recreate and index_file_path.exists() and id_mapping_file_path.exists():
        print(f"Attempting to load existing index for '{doc_type}' (model: {embedding_model_name}) from {index_file_path}")
        try:
            index = faiss.read_index(str(index_file_path))
            # Load the ID mapping (maps FAISS internal ID -> EmbedSet.id)
            with open(id_mapping_file_path, 'r', encoding='utf-8') as f:
                loaded_id_map = json.load(f) 
            
            if not isinstance(loaded_id_map, list):
                raise ValueError("ID mapping file is not a list as expected.")

            if index.d != vector_dimension:
                print(f"Warning: Index dimension mismatch. Loaded index has dimension {index.d}, "
                      f"but current embeddings have dimension {vector_dimension}. Recreating index.")
                return _create_index_files(all_embed_sets, index_file_path, id_mapping_file_path, doc_type, embedding_model_name, vector_dimension)

            if index.ntotal != len(loaded_id_map):
                print(f"Warning: Index vector count ({index.ntotal}) does not match ID map length ({len(loaded_id_map)}). Recreating index.")
                return _create_index_files(all_embed_sets, index_file_path, id_mapping_file_path, doc_type, embedding_model_name, vector_dimension)
            
            # Basic check: Ensure all EmbedSet IDs from input are in the loaded map if counts match.
            # This isn't a perfect check for content match but adds some safety.
            # More robust would be to check if the set of IDs is identical.
            current_ids = {es.id for es in all_embed_sets}
            if set(loaded_id_map) != current_ids:
                print("Warning: Current EmbedSet IDs differ from loaded ID map. Recreating index.")
                return _create_index_files(
                    all_embed_sets, index_file_path, id_mapping_file_path,
                    doc_type, embedding_model_name, vector_dimension
                )

            print(f"Successfully loaded index for '{doc_type}'. Vectors: {index.ntotal}, Dimension: {index.d}")
            return IndexMeta(
                index_file_path=index_file_path.resolve(),
                id_mapping_path=id_mapping_file_path.resolve(),
                doc_type=doc_type,
                num_vectors=index.ntotal,
                vector_dimension=index.d,
                model_name=embedding_model_name 
            )
        except Exception as e:
            print(f"Error loading existing index for '{doc_type}': {e}. Will attempt to recreate.")
            # Fall through to recreate by calling _create_index_files

    return _create_index_files(all_embed_sets, index_file_path, id_mapping_file_path, doc_type, embedding_model_name, vector_dimension)


if __name__ == '__main__':
    print("Starting FAISS index module test...")
    # Create a temporary directory for cache/indexes
    test_cache_dir = Path("temp_cache_index_test")
    test_index_dir = test_cache_dir / "indexes"
    test_index_dir.mkdir(parents=True, exist_ok=True)
    
    # Dummy EmbedSet objects
    dummy_embed_sets_list: List[EmbedSet] = []
    test_dimension = 8  # Small dimension for testing
    num_dummy_vectors = 20
    doc_type_test = "control_test"
    model_name_test = "test-embedding-model/v1"  # With slash for sanitizer testing

    for i in range(num_dummy_vectors):
        dummy_embed_sets_list.append(EmbedSet(
            id=f"embed_set_control_{i}",
            norm_doc_id=f"norm_doc_control_{i // 3}",
            chunk_text=f"This is chunk text for control document {i // 3}, chunk index {i % 3}.",
            embedding=list(np.random.rand(test_dimension).astype('float32')),
            chunk_index=i % 3,
            total_chunks=3,
            doc_type=doc_type_test
        ))

    print(f"\n--- Test 1: Create New Index (doc_type: {doc_type_test}, model: {model_name_test}) ---")
    index_meta_created = create_or_load_index(
        dummy_embed_sets_list, 
        test_index_dir, 
        doc_type_test, 
        model_name_test, 
        force_recreate=True
    )

    if index_meta_created:
        print(f"IndexMeta created: {index_meta_created.model_dump_json(indent=2)}")
        assert index_meta_created.num_vectors == num_dummy_vectors
        assert index_meta_created.vector_dimension == test_dimension
        assert index_meta_created.doc_type == doc_type_test
        assert index_meta_created.model_name == model_name_test
        assert index_meta_created.index_file_path.exists()
        assert index_meta_created.id_mapping_path.exists()
        
        # Verify map content
        with open(index_meta_created.id_mapping_path, 'r') as f_map:
            id_map = json.load(f_map)
            assert len(id_map) == num_dummy_vectors
            assert id_map[0] == dummy_embed_sets_list[0].id
            assert id_map[-1] == dummy_embed_sets_list[-1].id
        print("Initial creation test passed.")
    else:
        print("Initial index creation FAILED.")
        exit(1)  # Stop test if initial creation fails

    print("\n--- Test 2: Load Existing Index ---")
    index_meta_loaded = create_or_load_index(
        dummy_embed_sets_list,  # Provide same data for validation checks
        test_index_dir, 
        doc_type_test, 
        model_name_test, 
        force_recreate=False
    )

    assert index_meta_loaded is not None, "Loading existing index FAILED."
    if index_meta_loaded:
        print(f"IndexMeta loaded: {index_meta_loaded.model_dump_json(indent=2)}")
        assert index_meta_loaded.num_vectors == index_meta_created.num_vectors
        assert index_meta_loaded.vector_dimension == index_meta_created.vector_dimension
        assert index_meta_loaded.index_file_path == index_meta_created.index_file_path
        print("Loading existing index test passed.")

    print("\n--- Test 3: Force Recreate Index ---")
    # Optionally modify data slightly if we wanted to test if content changes,
    # but force_recreate should rebuild regardless.
    index_meta_recreated = create_or_load_index(
        dummy_embed_sets_list, 
        test_index_dir, 
        doc_type_test, 
        model_name_test, 
        force_recreate=True
    )
    assert index_meta_recreated is not None, "Force recreate FAILED."
    if index_meta_recreated:
        print(f"IndexMeta recreated: {index_meta_recreated.model_dump_json(indent=2)}")
        assert index_meta_recreated.num_vectors == num_dummy_vectors  # Should be same if data is same
        print("Force recreate test passed.")

    print("\n--- Test 4: Empty EmbedSet List ---")
    empty_result_meta = create_or_load_index([], test_index_dir, "empty_doc_type", model_name_test)
    assert empty_result_meta is None
    print("Empty EmbedSet list test passed (returned None).")

    print("\n--- Test 5: Dimension Mismatch on Load (Simulated) ---")
    # Create a new list with different dimension
    dummy_embed_sets_dim_mismatch = [
        EmbedSet(id="dim_mismatch_1", norm_doc_id="nd1", chunk_text="c1", embedding=[1.0, 2.0], chunk_index=0, total_chunks=1, doc_type=doc_type_test)
    ]
    # This should trigger recreation because current data (dim_mismatch) has different dim than saved index
    index_meta_dim_mismatch = create_or_load_index(
        dummy_embed_sets_dim_mismatch,
        test_index_dir,
        doc_type_test,  # Same doc_type, so it finds the old index
        model_name_test,
        force_recreate=False 
    )
    assert index_meta_dim_mismatch is not None, "Dimension mismatch test FAILED to recreate."
    if index_meta_dim_mismatch:
        assert index_meta_dim_mismatch.vector_dimension == 2  # New dimension
        assert index_meta_dim_mismatch.num_vectors == 1
        print("Dimension mismatch load test passed (recreated index with new dimension).")

    # Clean up temporary directory
    try:
        import shutil
        if test_cache_dir.exists():
            # print(f"\nCleaning up temporary cache directory: {test_cache_dir}")
            shutil.rmtree(test_cache_dir)
    except Exception as e_clean:
        print(f"Error cleaning up test directory {test_cache_dir}: {e_clean}")

    print("\nFAISS index module test finished.")
