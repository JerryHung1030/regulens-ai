import os
from typing import List, Optional

import openai  # type: ignore # Assuming openai is installed, ignore type errors if stubs are missing
import tiktoken
from pydantic import BaseModel

# Adjust import based on project structure and PYTHONPATH
try:
    from app.models.docs import NormDoc, EmbedSet
    from app.pipeline.cache import CacheService
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.docs import NormDoc, EmbedSet  # type: ignore
    from app.pipeline.cache import CacheService  # type: ignore


# Helper for Pydantic list serialization/deserialization with CacheService
class EmbedSetList(BaseModel):
    items: List[EmbedSet]


def _create_text_chunks(text: str, tokenizer: tiktoken.Encoding, max_tokens: int = 400) -> List[str]:
    """
    Splits text into chunks based on a maximum token count.
    """
    if not text.strip():  # Handle empty or whitespace-only text
        return []
        
    tokens = tokenizer.encode(text)
    chunks: List[str] = []
    current_chunk_tokens: List[int] = []

    for token in tokens:
        current_chunk_tokens.append(token)
        if len(current_chunk_tokens) >= max_tokens:
            chunks.append(tokenizer.decode(current_chunk_tokens))
            current_chunk_tokens = []
    
    # Add any remaining tokens as the last chunk
    if current_chunk_tokens:
        chunks.append(tokenizer.decode(current_chunk_tokens))
        
    return chunks


def generate_embeddings(
    norm_doc: NormDoc, 
    cache_service: CacheService, 
    openai_api_key: Optional[str] = None,
    embedding_model_name: str = "text-embedding-3-large",  # Default from settings
    max_tokens_per_chunk: int = 200  # Changed default
) -> List[EmbedSet]:
    
    # Generate a cache key for the entire norm_doc's set of embeddings,
    # including model name and chunk size in the key for specificity.
    doc_embeddings_cache_key_suffix = f"full_embeddings_set_{embedding_model_name}_tokens{max_tokens_per_chunk}"
    doc_embeddings_cache_key = cache_service.generate_key(norm_doc.id, doc_embeddings_cache_key_suffix)
    
    cached_embed_set_list = cache_service.load_json(doc_embeddings_cache_key, EmbedSetList)
    if cached_embed_set_list:
        # print(f"Loaded embeddings from cache for NormDoc: {norm_doc.id} (Model: {embedding_model_name}, Chunks: {max_tokens_per_chunk})")
        return cached_embed_set_list.items

    # print(f"Generating embeddings for NormDoc: {norm_doc.id} (Model: {embedding_model_name}, Chunks: {max_tokens_per_chunk})...")
    all_embed_sets: List[EmbedSet] = []

    try:
        # Use provided API key or fall back to environment variable
        # The OpenAI client handles None api_key by checking the env var itself.
        client = openai.OpenAI(api_key=openai_api_key) 
        
        # Ensure tokenizer is available
        try:
            tokenizer = tiktoken.get_encoding("cl100k_base")  # Common for new OpenAI models
        except Exception as e:
            print(f"Failed to get tiktoken encoding: {e}")
            # Depending on policy, could raise or return empty. Returning empty for now.
            return []

        text_chunks = _create_text_chunks(norm_doc.text_content, tokenizer, max_tokens=max_tokens_per_chunk)
        total_chunks = len(text_chunks)

        if total_chunks == 0 and norm_doc.text_content.strip():
            print(f"Warning: No text chunks generated for non-empty NormDoc: {norm_doc.id}. Content: '{norm_doc.text_content[:100]}...'")
            # This might happen if content is too short or only whitespace after normalization
        elif total_chunks == 0:  # Content was empty or only whitespace
            print(f"NormDoc {norm_doc.id} has no text content to embed.")
            # Cache an empty list to prevent re-processing
            cache_service.save_json(doc_embeddings_cache_key, EmbedSetList(items=[]))
            return []

        for i, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():  # Skip empty chunks if any were produced
                # print(f"Skipping empty chunk {i} for NormDoc {norm_doc.id}")
                total_chunks -= 1  # Adjust total_chunks if we skip one. This might be tricky if done often. # Better to ensure _create_text_chunks doesn't produce empty strings if possible.
                continue

            # OpenAI API recommends replacing newlines for better performance/results
            processed_chunk_text = chunk_text.replace("\n", " ")

            response = client.embeddings.create(
                input=[processed_chunk_text],  # API expects a list of strings
                model=embedding_model_name
            )
            embedding_vector = response.data[0].embedding

            embed_set_id_suffix = f"chunk_{i}_{embedding_model_name}_tokens{max_tokens_per_chunk}"
            embed_set_id = cache_service.generate_key(norm_doc.id, embed_set_id_suffix)
            
            embed_set = EmbedSet(
                id=embed_set_id,
                norm_doc_id=norm_doc.id,
                chunk_text=chunk_text,  # Store original chunk text, not the newline-replaced one
                embedding=embedding_vector,
                chunk_index=i,
                total_chunks=total_chunks,  # Use the initially calculated total_chunks
                doc_type=norm_doc.doc_type
            )
            all_embed_sets.append(embed_set)

    except openai.APIConnectionError as e:
        print(f"OpenAI API Connection Error for {norm_doc.id}: {e}")
        return []  # Cannot proceed
    except openai.RateLimitError as e:
        print(f"OpenAI API Rate Limit Exceeded for {norm_doc.id}: {e}")
        # Could implement retry logic here. For PoC, return processed so far or empty.
        return all_embed_sets  # Return what we have
    except openai.AuthenticationError as e:
        print(f"OpenAI API Authentication Error: {e}. Check your API key.")
        return []  # Cannot proceed
    except openai.APIError as e:  # Catch other OpenAI API errors
        print(f"OpenAI API error while processing {norm_doc.id}: {e}")
        return all_embed_sets  # Return what we have
    except Exception as e:  # Catch any other unexpected errors
        print(f"An unexpected error occurred during embedding generation for {norm_doc.id}: {e}")
        return []  # Or all_embed_sets if partial is acceptable

    # Cache the full list of EmbedSet objects for the document if any were generated
    if all_embed_sets:
        cache_service.save_json(doc_embeddings_cache_key, EmbedSetList(items=all_embed_sets))
        # print(f"Saved {len(all_embed_sets)} embeddings to cache for NormDoc: {norm_doc.id}")
    elif total_chunks > 0:  # If there were chunks but something went wrong mid-way and all_embed_sets is empty
        print(f"No embeddings were successfully generated for NormDoc: {norm_doc.id}, though chunks were present.")
    # If total_chunks was 0, already handled.

    return all_embed_sets


if __name__ == '__main__':
    from pathlib import Path
    # This import is for the test only, assuming models.docs is findable
    # from app.models.docs import NormDoc 
    # from app.pipeline.cache import CacheService

    print("Starting embedding module test...")
    # Setup a temporary cache directory - THIS LOGIC CHANGES
    # cache_dir = Path("temp_cache_embed_test") # Old way
    # cache_dir.mkdir(parents=True, exist_ok=True) # Old way
    # cs = CacheService(cache_dir) # Old way

    # New way: Instantiate CacheService with a project name for testing
    test_project_name = "embed_module_test_project"
    cs = CacheService(project_name=test_project_name)
    print(f"Using cache directory for testing: {cs.cache_dir}")

    # Sample NormDoc
    sample_norm_doc_content = (
        "This is a test document. It has several sentences. "
        "Tiktoken will count these tokens. OpenAI will embed them. "
        "This is a longer sentence to make up tokens for a text chunk "
        "for testing purposes for the embedding model. "
        "Let's add another sentence to ensure we get at least two chunks, "
        "hopefully. Maybe even more if the token limit is small. This should be enough text."
    )
    sample_norm_doc = NormDoc(
        id="test_norm_doc_main_001", 
        raw_doc_id="raw_main_001", 
        text_content=sample_norm_doc_content,
        sections=["Intro", "Body"], 
        metadata={"source": "test_data"}, 
        doc_type="external_regulation"
    )
    
    sample_empty_norm_doc = NormDoc(
        id="test_norm_doc_empty_002",
        raw_doc_id="raw_empty_002",
        text_content="   ",  # Whitespace only
        sections=[],
        metadata={},
        doc_type="procedure"
    )

    # Check for OpenAI API key
    api_key_from_env = os.environ.get("OPENAI_API_KEY")
    if not api_key_from_env:
        print("\nWARNING: OPENAI_API_KEY environment variable not set. Live API call tests will be skipped.")
        print("This test will only check chunking and caching of empty/mock data if applicable.")
    else:
        print("\nFound OPENAI_API_KEY. Will attempt live API calls with model 'text-embedding-3-small' for cost/speed.")
        # Using a smaller model for tests to reduce cost/time if this key is for a paid account.
        # For actual use, "text-embedding-3-large" is in the function signature.
        test_embedding_model = "text-embedding-3-small" 
        test_max_tokens = 50  # Smaller token count for testing chunking

        print(f"\n--- Testing with NormDoc ID: {sample_norm_doc.id} ---")
        embeddings_list = generate_embeddings(
            sample_norm_doc, 
            cs, 
            openai_api_key=api_key_from_env, 
            embedding_model_name=test_embedding_model,
            max_tokens_per_chunk=test_max_tokens
        )

        if embeddings_list:
            print(f"Generated {len(embeddings_list)} embedding sets.")
            print(f"First embedding set: ID={embeddings_list[0].id}, Chunks={embeddings_list[0].total_chunks}, Vec Dim={len(embeddings_list[0].embedding)}")
            assert embeddings_list[0].total_chunks == len(embeddings_list)
            
            print("\nRunning again to test caching...")
            embeddings_list_cached = generate_embeddings(
                sample_norm_doc, 
                cs, 
                openai_api_key=api_key_from_env,
                embedding_model_name=test_embedding_model,
                max_tokens_per_chunk=test_max_tokens
            )
            assert len(embeddings_list_cached) == len(embeddings_list)
            if embeddings_list_cached:  # Ensure it's not empty before indexing
                assert embeddings_list_cached[0].id == embeddings_list[0].id
            print("Caching test passed for main doc.")
        else:
            print(f"Embedding generation failed or returned empty for {sample_norm_doc.id}.")

        print(f"\n--- Testing with empty NormDoc ID: {sample_empty_norm_doc.id} ---")
        empty_embeddings_list = generate_embeddings(
            sample_empty_norm_doc,
            cs,
            openai_api_key=api_key_from_env,
            embedding_model_name=test_embedding_model,
            max_tokens_per_chunk=test_max_tokens
        )
        assert len(empty_embeddings_list) == 0, f"Expected 0 embeddings for empty doc, got {len(empty_embeddings_list)}"
        print("Empty document test passed (returned 0 embeddings).")
        
        # Test caching for empty doc
        print("\nRunning empty doc again to test caching of empty result...")
        empty_embeddings_list_cached = generate_embeddings(
            sample_empty_norm_doc,
            cs,
            openai_api_key=api_key_from_env,
            embedding_model_name=test_embedding_model,
            max_tokens_per_chunk=test_max_tokens
        )
        assert len(empty_embeddings_list_cached) == 0
        print("Caching test passed for empty doc.")

    # Clean up temporary cache directory used by __main__
    try:
        import shutil
        # The cache_dir is now cs.cache_dir, which is inside the app data structure
        # Example: get_app_data_dir() / "cache" / "embeddings" / test_project_name
        if cs.cache_dir.exists():
            # print(f"\nCleaning up temporary cache directory: {cs.cache_dir}")
            shutil.rmtree(cs.cache_dir) 
            # Potentially remove parent directories if they are empty and were created by this test
            # For simplicity, just removing the project-specific cache here.
    except Exception as e:
        print(f"Error cleaning up cache directory {cs.cache_dir}: {e}")

    print("\nEmbedding module test finished.")
