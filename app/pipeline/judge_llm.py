import json
import os
import re
from typing import Optional, Dict, Any

from app.logger import logger

import openai # type: ignore
from pydantic import BaseModel, ValidationError

# Adjust import based on project structure and PYTHONPATH
try:
    from app.models.assessments import TripleAssessment
    from app.pipeline.cache import CacheService
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from app.models.assessments import TripleAssessment # type: ignore
    from app.pipeline.cache import CacheService # type: ignore

# Helper Pydantic model for LLM's expected JSON structure for validation
class LLMJudgeResponse(BaseModel):
    status: str
    analysis: str
    improvement_suggestion: Optional[str] = None
    confidence_score: float

    # Ensure status is one of the allowed values
    @classmethod
    def model_validator(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        status = values.get('status')
        if status not in ["Pass", "Partial", "Fail", "Inconclusive"]:
            raise ValueError(f"Invalid status: {status}. Must be one of 'Pass', 'Partial', 'Fail', 'Inconclusive'.")
        
        confidence = values.get('confidence_score')
        if not (0.0 <= confidence <= 1.0) : # type: ignore
            raise ValueError(f"Invalid confidence_score: {confidence}. Must be between 0.0 and 1.0.")
        return values


def assess_triplet_with_llm(
    control_doc_id: str, procedure_doc_id: str, evidence_doc_id: str,
    control_chunk_id: str, procedure_chunk_id: str, evidence_chunk_id: str,
    control_chunk_text: str, procedure_chunk_text: str, evidence_chunk_text: str,
    cache_service: CacheService,
    openai_api_key: Optional[str] = None,
    llm_model_name: str = "gpt-4o" # Default model
) -> Optional[TripleAssessment]:

    # Create a robust cache key. Consider hashing parts if they are very long.
    # For now, use model name and the three text snippets.
    cache_key_parts = [
        "llm_judge_assessment_v1", # Added version to allow future prompt changes
        llm_model_name, 
        control_chunk_text, 
        procedure_chunk_text, 
        evidence_chunk_text
    ]
    cache_key = cache_service.generate_key(*cache_key_parts)

    cached_assessment = cache_service.load_json(cache_key, TripleAssessment)
    if cached_assessment:
        # print(f"Loaded LLM assessment from cache for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}")
        return cached_assessment

    # print(f"Performing LLM assessment for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id} using {llm_model_name}...")

    llm_response_content_str: Optional[str] = None # For use in error messages if JSON parsing fails
    try:
        client = openai.OpenAI(api_key=openai_api_key if openai_api_key else os.environ.get("OPENAI_API_KEY"))

        system_prompt = ("You are an expert compliance auditor. Analyze the provided Control, Procedure, and Evidence excerpts. "
                         "Determine if the Evidence sufficiently demonstrates that the Procedure implements the Control requirement. "
                         "Respond strictly in JSON format with the fields: 'status', 'analysis', 'improvement_suggestion', and 'confidence_score'.")
        
        user_prompt = f"""
Please assess the following documents:

Control Requirement Excerpt:
```text
{control_chunk_text}
```

Procedure Step Excerpt:
```text
{procedure_chunk_text}
```

Evidence Item Excerpt:
```text
{evidence_chunk_text}
```

Based on your analysis, provide a JSON response with the following fields:
- "status": Choose one from "Pass", "Partial", "Fail", "Inconclusive".
- "analysis": Your detailed reasoning for the status provided. Be specific.
- "improvement_suggestion": (Optional) If status is "Partial" or "Fail", suggest concrete improvements for the procedure or evidence. Max 2-3 sentences. If status is "Pass" or "Inconclusive", this can be null or omitted.
- "confidence_score": A float between 0.0 and 1.0 indicating your confidence in this assessment.
"""
        
        response = client.chat.completions.create(
            model=llm_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}, # For compatible models like gpt-4o and gpt-3.5-turbo-1106+
            temperature=0.2 # Lower temperature for more deterministic, factual output
        )

        llm_response_content_str = response.choices[0].message.content

        if llm_response_content_str:
            # Remove potential markdown fences and leading/trailing whitespace
            if llm_response_content_str.startswith("```json"):
                llm_response_content_str = llm_response_content_str[7:]
            if llm_response_content_str.startswith("```"): # If just ``` not ```json
                llm_response_content_str = llm_response_content_str[3:]
            if llm_response_content_str.endswith("```"):
                llm_response_content_str = llm_response_content_str[:-3]
            llm_response_content_str = llm_response_content_str.strip()

        if not llm_response_content_str:
            logger.error(f"LLM returned empty content after stripping for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}.")
            return None

        llm_json_output: Dict[str, Any] = json.loads(llm_response_content_str)

        # Validate with Pydantic model
        parsed_llm_response = LLMJudgeResponse(**llm_json_output)
            
        assessment = TripleAssessment(
            control_doc_id=control_doc_id,
            procedure_doc_id=procedure_doc_id,
            evidence_doc_id=evidence_doc_id,
            control_chunk_id=control_chunk_id,
            procedure_chunk_id=procedure_chunk_id,
            evidence_chunk_id=evidence_chunk_id,
            status=parsed_llm_response.status,
            analysis=parsed_llm_response.analysis,
            improvement_suggestion=parsed_llm_response.improvement_suggestion,
            score=parsed_llm_response.confidence_score, # Using confidence_score as main score
            llm_raw_output=llm_json_output 
        )

        cache_service.save_json(cache_key, assessment)
        # print(f"Saved LLM assessment to cache for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}")
        return assessment

    except openai.APIConnectionError as e:
        logger.error(f"OpenAI API Connection Error during LLM assessment for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}: {e}")
    except openai.RateLimitError as e:
        logger.error(f"OpenAI API Rate Limit Exceeded during LLM assessment for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}: {e}")
    except openai.AuthenticationError as e:
        logger.error(f"OpenAI API Authentication Error for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}: {e}. Check your API key.")
    except openai.APIError as e: # Catch other OpenAI API errors
        logger.error(f"OpenAI API error during LLM assessment for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from LLM response for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}: {e}. Response: '{llm_response_content_str}'")
    except ValidationError as e: # Pydantic validation error
        logger.error(f"LLM response JSON schema validation error for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}: {e}. Response: '{llm_response_content_str}'")
    except Exception as e:
        logger.error(f"Unexpected error during LLM assessment for C:{control_chunk_id}, P:{procedure_chunk_id}, E:{evidence_chunk_id}: {e}", exc_info=True)
    
    return None

if __name__ == '__main__':
    from pathlib import Path

    print("Starting LLM Judge module test...")
    # Setup a temporary cache directory
    cache_dir_test_llm_judge = Path("temp_llm_judge_cache_dir")
    cache_dir_test_llm_judge.mkdir(parents=True, exist_ok=True)
    cs_for_llm_test = CacheService(cache_dir_test_llm_judge)
    
    # Check for OpenAI API key
    api_key_env = os.environ.get("OPENAI_API_KEY")

    if not api_key_env:
        print("\nWARNING: OPENAI_API_KEY environment variable not set. Live API call test will be skipped.")
    else:
        print(f"\nFound OPENAI_API_KEY. Will attempt live API call with model 'gpt-3.5-turbo'.")
        # Using a cheaper/faster model for testing. 
        # The prompt is designed for gpt-4o's capabilities, so gpt-3.5-turbo might not perform as well or follow JSON format as strictly.
        # For production, ensure the model used matches the prompt's expectations.
        # Using VCRpy would be ideal for CI/CD and repeatable tests.
        test_llm_model = "gpt-3.5-turbo" 
        
        print("\n--- Test 1: Perform LLM Assessment (Live API Call) ---")
        assessment_res = assess_triplet_with_llm(
            control_doc_id="CID_001", procedure_doc_id="PID_001", evidence_doc_id="EID_001",
            control_chunk_id="CCHK_001", procedure_chunk_id="PCHK_001", evidence_chunk_id="ECHK_001",
            control_chunk_text="The system must enforce multi-factor authentication for all administrative accounts.",
            procedure_chunk_text="Procedure: Admin users are required to configure an OTP token during their first login. Subsequent logins prompt for username, password, and OTP.",
            evidence_chunk_text="Evidence: System logs show admin 'johndoe' logged in using password and OTP. Screenshot of MFA configuration page available at link XYZ.",
            cache_service=cs_for_llm_test,
            openai_api_key=api_key_env,
            llm_model_name=test_llm_model 
        )

        if assessment_res:
            print("\nLLM Assessment Result (Test 1):")
            print(assessment_res.model_dump_json(indent=2))
            assert assessment_res.status in ["Pass", "Partial", "Fail", "Inconclusive"]
            assert 0.0 <= assessment_res.score <= 1.0 # type: ignore
            print("Live API call test passed.")
            
            print("\n--- Test 2: Load LLM Assessment from Cache ---")
            cached_assessment_res = assess_triplet_with_llm(
                control_doc_id="CID_001", procedure_doc_id="PID_001", evidence_doc_id="EID_001",
                control_chunk_id="CCHK_001", procedure_chunk_id="PCHK_001", evidence_chunk_id="ECHK_001",
                control_chunk_text="The system must enforce multi-factor authentication for all administrative accounts.",
                procedure_chunk_text="Procedure: Admin users are required to configure an OTP token during their first login. Subsequent logins prompt for username, password, and OTP.",
                evidence_chunk_text="Evidence: System logs show admin 'johndoe' logged in using password and OTP. Screenshot of MFA configuration page available at link XYZ.",
                cache_service=cs_for_llm_test,
                openai_api_key=api_key_env,
                llm_model_name=test_llm_model 
            )
            assert cached_assessment_res is not None, "Cached assessment retrieval FAILED."
            if cached_assessment_res:
                print("Cached LLM Assessment Result (Test 2):")
                print(cached_assessment_res.model_dump_json(indent=2))
                assert cached_assessment_res.analysis == assessment_res.analysis # Key check for cache hit
                assert cached_assessment_res.llm_raw_output == assessment_res.llm_raw_output
                print("Cache hit test passed.")
        else:
            print("LLM Assessment (Test 1) FAILED or returned None.")

    # Clean up temporary cache directory
    try:
        import shutil
        if cache_dir_test_llm_judge.exists():
            # print(f"\nCleaning up temporary LLM judge cache directory: {cache_dir_test_llm_judge}")
            shutil.rmtree(cache_dir_test_llm_judge)
    except Exception as e_clean:
        print(f"Error cleaning up test LLM judge cache directory {cache_dir_test_llm_judge}: {e_clean}")

    print("\nLLM Judge module test finished.")
