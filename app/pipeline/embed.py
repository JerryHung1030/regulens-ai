import os
import traceback # Add this import
from typing import List, Optional

import openai  # type: ignore # Assuming openai is installed, ignore type errors if stubs are missing
import tiktoken
from pydantic import BaseModel

from app.logger import logger # Add this import

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
        logger.info(f"Loaded embeddings from cache for NormDoc: {norm_doc.id} (Model: {embedding_model_name}, Chunks: {max_tokens_per_chunk})")
        return cached_embed_set_list.items

    logger.info(f"Generating embeddings for NormDoc: {norm_doc.id} (Model: {embedding_model_name}, Chunks: {max_tokens_per_chunk})...")
    all_embed_sets: List[EmbedSet] = []

    try:
        logger.info(f"Attempting to generate embeddings for NormDoc ID: {norm_doc.id} using model: {embedding_model_name}")
        if openai_api_key:
            logger.debug("OpenAI API key is provided directly to the function.")
        else:
            logger.debug("OpenAI API key is NOT provided directly; relying on environment variable OPENAI_API_KEY.")
        
        client = openai.OpenAI(api_key=openai_api_key) 
        
        try:
            tokenizer = tiktoken.get_encoding("cl100k_base")
            logger.debug("Successfully loaded tiktoken tokenizer 'cl100k_base'.")
        except Exception as e:
            logger.error(f"Failed to get tiktoken encoding 'cl100k_base': {e}\n{traceback.format_exc()}")
            cache_service.save_json(doc_embeddings_cache_key, EmbedSetList(items=[]))
            return []

        text_chunks = _create_text_chunks(norm_doc.text_content, tokenizer, max_tokens=max_tokens_per_chunk)
        total_chunks = len(text_chunks)

        if total_chunks == 0 and norm_doc.text_content.strip():
            logger.warning(f"Warning: No text chunks generated for non-empty NormDoc: {norm_doc.id}. Content: '{norm_doc.text_content[:100]}...'")
        elif total_chunks == 0:
            logger.info(f"NormDoc {norm_doc.id} has no text content to embed.")
            cache_service.save_json(doc_embeddings_cache_key, EmbedSetList(items=[]))
            return []

        for i, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():
                logger.debug(f"Skipping empty chunk {i} for NormDoc {norm_doc.id}")
                # total_chunks -= 1 # This adjustment can be problematic if many are skipped.
                                  # Better to rely on the initial total_chunks for EmbedSet metadata.
                continue

            processed_chunk_text = chunk_text.replace("\n", " ")
            logger.debug(f"Embedding chunk {i+1}/{total_chunks} for NormDoc ID: {norm_doc.id}. Chunk preview (first 70 chars): '{processed_chunk_text[:70]}...'")

            try:
                response = client.embeddings.create(
                    input=[processed_chunk_text],
                    model=embedding_model_name
                )
            except openai.APIError as e_api:
                logger.error(f"OpenAI APIError during client.embeddings.create for NormDoc {norm_doc.id}, chunk {i}: {e_api}\n{traceback.format_exc()}")
                logger.error(f"Problematic chunk text (newline-replaced): '{processed_chunk_text}'")
                raise 
            except Exception as e_generic_create:
                logger.error(f"Generic error during client.embeddings.create for NormDoc {norm_doc.id}, chunk {i}: {e_generic_create}\n{traceback.format_exc()}")
                logger.error(f"Problematic chunk text (newline-replaced): '{processed_chunk_text}'")
                raise

            embedding_vector = response.data[0].embedding
            embed_set_id_suffix = f"chunk_{i}_{embedding_model_name}_tokens{max_tokens_per_chunk}"
            embed_set_id = cache_service.generate_key(norm_doc.id, embed_set_id_suffix)
            
            embed_set = EmbedSet(
                id=embed_set_id,
                norm_doc_id=norm_doc.id,
                chunk_text=chunk_text,
                embedding=embedding_vector,
                chunk_index=i,
                total_chunks=total_chunks,
                doc_type=norm_doc.doc_type
            )
            all_embed_sets.append(embed_set)

    except openai.APIConnectionError as e:
        logger.error(f"OpenAI API Connection Error for {norm_doc.id}: {e}\n{traceback.format_exc()}")
        return []
    except openai.RateLimitError as e:
        logger.error(f"OpenAI API Rate Limit Exceeded for {norm_doc.id}: {e}\n{traceback.format_exc()}")
        return all_embed_sets
    except openai.AuthenticationError as e:
        logger.error(f"OpenAI API Authentication Error: {e}. Check your API key.\n{traceback.format_exc()}")
        return []
    except openai.APIError as e:
        logger.error(f"OpenAI API error while processing {norm_doc.id}: {e}\n{traceback.format_exc()}")
        return all_embed_sets
    except Exception as e:
        logger.error(f"An unexpected error occurred during embedding generation for {norm_doc.id}: {e}\n{traceback.format_exc()}")
        return []

    if all_embed_sets:
        cache_service.save_json(doc_embeddings_cache_key, EmbedSetList(items=all_embed_sets))
        logger.info(f"Saved {len(all_embed_sets)} embeddings to cache for NormDoc: {norm_doc.id}")
    elif total_chunks > 0:
        logger.warning(f"No embeddings were successfully generated for NormDoc: {norm_doc.id}, though chunks were present.")

    return all_embed_sets


if __name__ == '__main__':
    from pathlib import Path
    # This import is for the test only, assuming models.docs is findable
    # from app.models.docs import NormDoc 
    # from app.pipeline.cache import CacheService

    logger.info("Starting embedding module test...")
    # Setup a temporary cache directory - THIS LOGIC CHANGES
    # cache_dir = Path("temp_cache_embed_test") # Old way
    # cache_dir.mkdir(parents=True, exist_ok=True) # Old way
    # cs = CacheService(cache_dir) # Old way

    # New way: Instantiate CacheService with a project name for testing
    test_project_name = "embed_module_test_project"
    cs = CacheService(project_name=test_project_name)
    logger.info(f"Using cache directory for testing: {cs.cache_dir}")

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
        logger.warning("\nOPENAI_API_KEY environment variable not set. Live API call tests will be skipped.")
        logger.info("This test will only check chunking and caching of empty/mock data if applicable.")
    else:
        logger.info("\nFound OPENAI_API_KEY. Will attempt live API calls with model 'text-embedding-3-small' for cost/speed.")
        test_embedding_model = "text-embedding-3-small" 
        test_max_tokens = 50

        logger.info(f"\n--- Testing with NormDoc ID: {sample_norm_doc.id} ---")
        embeddings_list = generate_embeddings(
            sample_norm_doc, 
            cs, 
            openai_api_key=api_key_from_env, 
            embedding_model_name=test_embedding_model,
            max_tokens_per_chunk=test_max_tokens
        )

        if embeddings_list:
            logger.info(f"Generated {len(embeddings_list)} embedding sets.")
            logger.info(f"First embedding set: ID={embeddings_list[0].id}, Chunks={embeddings_list[0].total_chunks}, Vec Dim={len(embeddings_list[0].embedding)}")
            assert embeddings_list[0].total_chunks == len(embeddings_list)
            
            logger.info("\nRunning again to test caching...")
            embeddings_list_cached = generate_embeddings(
                sample_norm_doc, 
                cs, 
                openai_api_key=api_key_from_env,
                embedding_model_name=test_embedding_model,
                max_tokens_per_chunk=test_max_tokens
            )
            assert len(embeddings_list_cached) == len(embeddings_list)
            if embeddings_list_cached:
                assert embeddings_list_cached[0].id == embeddings_list[0].id
            logger.info("Caching test passed for main doc.")
        else:
            logger.warning(f"Embedding generation failed or returned empty for {sample_norm_doc.id}.")

        logger.info(f"\n--- Testing with empty NormDoc ID: {sample_empty_norm_doc.id} ---")
        empty_embeddings_list = generate_embeddings(
            sample_empty_norm_doc,
            cs,
            openai_api_key=api_key_from_env,
            embedding_model_name=test_embedding_model,
            max_tokens_per_chunk=test_max_tokens
        )
        assert len(empty_embeddings_list) == 0, f"Expected 0 embeddings for empty doc, got {len(empty_embeddings_list)}"
        logger.info("Empty document test passed (returned 0 embeddings).")
        
        logger.info("\nRunning empty doc again to test caching of empty result...")
        empty_embeddings_list_cached = generate_embeddings(
            sample_empty_norm_doc,
            cs,
            openai_api_key=api_key_from_env,
            embedding_model_name=test_embedding_model,
            max_tokens_per_chunk=test_max_tokens
        )
        assert len(empty_embeddings_list_cached) == 0
        logger.info("Caching test passed for empty doc.")

    try:
        import shutil
        if cs.cache_dir.exists():
            # logger.info(f"\nCleaning up temporary cache directory: {cs.cache_dir}") # Optional: can be verbose for tests
            shutil.rmtree(cs.cache_dir) 
    except Exception as e:
        logger.error(f"Error cleaning up cache directory {cs.cache_dir}: {e}")

    logger.info("\nEmbedding module test finished.")
