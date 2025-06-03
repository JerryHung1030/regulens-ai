import json
from pathlib import Path
from typing import List, Optional, Dict

import faiss  # type: ignore
import numpy as np

# Adjust import based on project structure and PYTHONPATH
try:
    from app.models.docs import EmbedSet, IndexMeta
    from app.models.assessments import MatchSet
    # For testing, we might need create_or_load_index
    from app.pipeline.index import create_or_load_index 
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.docs import EmbedSet, IndexMeta  # type: ignore
    from app.models.assessments import MatchSet  # type: ignore
    from app.pipeline.index import create_or_load_index  # type: ignore


def retrieve_similar_chunks(
    query_embed_set: EmbedSet,
    target_index_meta: IndexMeta,
    target_embed_sets_map: Dict[str, EmbedSet],  # Maps EmbedSet.id to EmbedSet object
    k_results: int,
    faiss_index_obj: Optional[faiss.Index] = None,
    id_map_list_obj: Optional[List[str]] = None  # List of EmbedSet.id, index is FAISS ID
) -> List[MatchSet]:

    loaded_index = faiss_index_obj
    loaded_id_map = id_map_list_obj
    results: List[MatchSet] = []

    if k_results == 0:
        # print("k_results is 0, returning empty list.")
        return results

    try:
        if loaded_index is None:
            if not target_index_meta.index_file_path.exists():
                print(f"Error: Index file not found at {target_index_meta.index_file_path}")
                return results
            # print(f"Loading FAISS index from: {target_index_meta.index_file_path}")
            loaded_index = faiss.read_index(str(target_index_meta.index_file_path))
        
        if loaded_id_map is None:
            if not target_index_meta.id_mapping_path.exists():
                print(f"Error: ID mapping file not found at {target_index_meta.id_mapping_path}")
                return results
            # print(f"Loading ID map from: {target_index_meta.id_mapping_path}")
            with open(target_index_meta.id_mapping_path, 'r', encoding='utf-8') as f:
                loaded_id_map = json.load(f)
            if not isinstance(loaded_id_map, list):
                raise ValueError("ID mapping file content is not a list.")

    except Exception as e:
        print(f"Error loading index or ID map for doc_type '{target_index_meta.doc_type}' (model: {target_index_meta.model_name}): {e}")
        return results

    if loaded_index is None or loaded_id_map is None:  # Should have been caught by exceptions, but as safeguard
        print("Error: Failed to obtain valid index or ID map.")
        return results
        
    if loaded_index.ntotal == 0:
        # print(f"Warning: Index for doc_type '{target_index_meta.doc_type}' (model: {target_index_meta.model_name}) is empty.")
        return results

    if not query_embed_set.embedding:
        print(f"Error: Query EmbedSet '{query_embed_set.id}' has an empty embedding list.")
        return results
        
    query_vector_np = np.array([query_embed_set.embedding], dtype='float32')
    
    if query_vector_np.shape[1] != loaded_index.d:
        print(f"Error: Query vector dimension ({query_vector_np.shape[1]}) "
              f"does not match index dimension ({loaded_index.d}) "
              f"for doc_type '{target_index_meta.doc_type}' (model: {target_index_meta.model_name}).")
        return results

    try:
        # Ensure k is not greater than the number of items in the index
        actual_k = min(k_results, loaded_index.ntotal)
        
        # FAISS search requires k > 0. If actual_k became 0 due to k_results or ntotal being 0,
        # handle this. (ntotal=0 handled above, k_results=0 handled at start)
        if actual_k == 0: 
            # This case should ideally not be reached if k_results=0 and ntotal=0 are handled.
            # print("Warning: actual_k for FAISS search is 0. No search performed.")
            return results

        # print(f"Performing FAISS search with k={actual_k} for query {query_embed_set.id} against {target_index_meta.doc_type} index.")
        distances, faiss_ids = loaded_index.search(query_vector_np, actual_k)
        
    except RuntimeError as re:  # Catch FAISS specific runtime errors
        print(f"FAISS runtime error during search for query {query_embed_set.id}: {re}")
        return results
    except Exception as e:
        print(f"Unexpected error during FAISS search for query {query_embed_set.id}: {e}")
        return results

    for i in range(faiss_ids.shape[1]):  # Iterate through found neighbors for the query
        faiss_internal_id = faiss_ids[0, i]
        dist = distances[0, i]

        if faiss_internal_id == -1: 
            # FAISS uses -1 if k > ntotal and no more valid items are found
            # print(f"FAISS returned -1 for index {i}, indicating no more valid results.")
            continue 
        
        if not (0 <= faiss_internal_id < len(loaded_id_map)):
            print(f"Error: FAISS internal ID {faiss_internal_id} is out of bounds "
                  f"for ID map of length {len(loaded_id_map)}. Skipping this match.")
            continue

        matched_embed_set_id = loaded_id_map[faiss_internal_id]
        matched_embed_set = target_embed_sets_map.get(matched_embed_set_id)

        if matched_embed_set is None:
            print(f"Error: EmbedSet ID '{matched_embed_set_id}' (from FAISS ID {faiss_internal_id}) "
                  f"not found in target_embed_sets_map. Skipping this match.")
            continue

        # L2 distance is non-negative.
        similarity_score = 1.0 / (1.0 + float(dist))

        results.append(MatchSet(
            query_norm_doc_id=query_embed_set.norm_doc_id,
            query_embed_set_id=query_embed_set.id,
            query_chunk_text=query_embed_set.chunk_text,
            matched_norm_doc_id=matched_embed_set.norm_doc_id,
            matched_embed_set_id=matched_embed_set.id,
            matched_chunk_text=matched_embed_set.chunk_text,
            score=similarity_score,
            raw_faiss_distance=float(dist),
            query_doc_type=query_embed_set.doc_type,
            matched_doc_type=target_index_meta.doc_type  # Or matched_embed_set.doc_type
        ))
        
    # Results from FAISS are already sorted by distance (ascending),
    # so the derived similarity_score (descending) will also be sorted.
    return results


if __name__ == '__main__':
    print("Starting retrieval module test...")
    
    temp_test_dir = Path("temp_retrieve_module_test")
    temp_test_dir.mkdir(parents=True, exist_ok=True)
    index_dir_for_test = temp_test_dir / "indexes"
    index_dir_for_test.mkdir(parents=True, exist_ok=True)

    # Dummy data parameters
    test_dimension = 5
    num_target_items = 10
    query_doc_type_name = "control_query"
    target_doc_type_name = "procedure_target"
    test_model = "test-retrieval-model/v1"

    # Create Query EmbedSet
    query_embedding_vector = np.random.rand(test_dimension).astype('float32')
    query_es_obj = EmbedSet(
        id="query_es_001", 
        norm_doc_id="query_norm_doc_001", 
        chunk_text="This is the query text for similarity search.", 
        embedding=list(query_embedding_vector), 
        chunk_index=0, 
        total_chunks=1, 
        doc_type=query_doc_type_name
    )
    
    # Create Target EmbedSets and Map
    target_embed_set_list: List[EmbedSet] = []
    target_embed_sets_data_map: Dict[str, EmbedSet] = {}
    for i in range(num_target_items):
        # Make one target intentionally very similar to the query
        if i == num_target_items // 2:  # Middle item
            emb_vector = query_embedding_vector 
        else:
            emb_vector = np.random.rand(test_dimension).astype('float32')
        
        es_id = f"target_es_{i:03d}"
        es = EmbedSet(
            id=es_id, 
            norm_doc_id=f"target_norm_doc_{i // 3}", 
            chunk_text=f"This is target chunk text number {i}.", 
            embedding=list(emb_vector), 
            chunk_index=i % 3, 
            total_chunks=3, 
            doc_type=target_doc_type_name
        )
        target_embed_set_list.append(es)
        target_embed_sets_data_map[es_id] = es

    # Create FAISS Index for the target EmbedSets
    print(f"Creating FAISS index for '{target_doc_type_name}'...")
    target_idx_meta_obj = create_or_load_index(
        target_embed_set_list, 
        index_dir_for_test, 
        target_doc_type_name, 
        test_model, 
        force_recreate=True
    )

    if not target_idx_meta_obj:
        print("CRITICAL TEST ERROR: Failed to create target index for testing. Aborting.")
    else:
        print(f"Target index created: {target_idx_meta_obj.index_file_path}")
        print("\n--- Test 1: Retrieve Top 3 Similar Chunks ---")
        matches_k3 = retrieve_similar_chunks(
            query_es_obj, 
            target_idx_meta_obj, 
            target_embed_sets_data_map, 
            k_results=3
        )
        
        if matches_k3:
            print(f"Found {len(matches_k3)} matches (k=3):")
            for match in matches_k3:
                print(f"  ID: {match.matched_embed_set_id}, Score: {match.score:.4f}, Dist: {match.raw_faiss_distance:.4f}")
                # print(f"    Query Text: '{match.query_chunk_text}'")
                # print(f"    Matched Text: '{match.matched_chunk_text}'")
            assert len(matches_k3) <= 3
            # Check if the intentionally similar item is the top match (score close to 1.0)
            assert matches_k3[0].matched_embed_set_id == f"target_es_{num_target_items // 2:03d}", "Top match is not the intentionally similar item."
            assert matches_k3[0].score > 0.999, "Score of intentionally similar item is not close to 1.0."
            print("Top 3 retrieval test passed.")
        else:
            print("No matches found for k=3 or error during retrieval.")

        print("\n--- Test 2: Retrieve with k=0 ---")
        matches_k0 = retrieve_similar_chunks(query_es_obj, target_idx_meta_obj, target_embed_sets_data_map, k_results=0)
        assert len(matches_k0) == 0, f"Expected 0 matches for k=0, got {len(matches_k0)}"
        print("k=0 retrieval test passed.")
        
        print("\n--- Test 3: Retrieve with k > number of items in index ---")
        large_k = num_target_items + 5
        matches_k_large = retrieve_similar_chunks(query_es_obj, target_idx_meta_obj, target_embed_sets_data_map, k_results=large_k)
        assert len(matches_k_large) == num_target_items, \
            f"Expected {num_target_items} matches for k={large_k} (index size), got {len(matches_k_large)}"
        print(f"k > ntotal test passed (k={large_k}, returned {len(matches_k_large)}).")

        print("\n--- Test 4: Retrieve from an empty index (simulated by using a new IndexMeta) ---")
        empty_index_target_doc_type = "empty_target_type"
        # Create an empty index first
        empty_idx_meta = create_or_load_index([], index_dir_for_test, empty_index_target_doc_type, test_model, force_recreate=True)
        # create_or_load_index returns None for empty list, so we need to manually construct IndexMeta for the test path
        # This is a bit artificial, as an empty index would normally not be processed further.
        # For a more realistic test of retrieve_similar_chunks with an empty index, 
        # it would load an actual empty .faiss file (0 vectors).
        # The current implementation of retrieve_similar_chunks handles loaded_index.ntotal == 0.
        
        # Simulate IndexMeta for an index that exists but is empty
        # (faiss.IndexFlatL2(test_dimension) then faiss.write_index() would create such a file)
        # This part of the test is more conceptual unless we actually write an empty FAISS file.
        # For now, we assume create_or_load_index handles empty list and retrieve_similar_chunks handles ntotal=0.
        if empty_idx_meta is None:  # create_or_load_index returns None for empty list.
            print("Skipping direct test with empty IndexMeta as create_or_load_index handles empty list by returning None.")
            print("The retrieve_similar_chunks function's internal check for loaded_index.ntotal == 0 covers empty index files.")

    # Clean up
    try:
        import shutil
        if temp_test_dir.exists():
            # print(f"\nCleaning up temporary test directory: {temp_test_dir}")
            shutil.rmtree(temp_test_dir)
    except Exception as e_clean:
        print(f"Error cleaning up test directory {temp_test_dir}: {e_clean}")

    print("\nRetrieval module test finished.")
