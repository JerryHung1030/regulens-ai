from __future__ import annotations

import json
from typing import Dict, Any, Optional, Union, List
from openai import OpenAI, APIError
from app.logger import logger

# Removed: from app.pipeline_settings import PipelineSettings as it's not directly used for API key in this file anymore.
# API key is now passed as an argument to call_llm_api.

def call_llm_api(
    prompt: str,
    model_name: str,
    api_key: str,
    expected_response_type: str = "boolean"  # "boolean", "json_list", "json_object", "text"
) -> Optional[Union[bool, List[Dict[str, Any]], Dict[str, Any], str]]:
    """
    Helper function to interact with an LLM using OpenAI's API.

    Args:
        prompt: The prompt to send to the LLM.
        model_name: The specific LLM model to use (e.g., "gpt-4o").
        api_key: The OpenAI API key.
        expected_response_type: Defines the expected structure of the LLM's response.
                                "boolean" for Yes/No (e.g., {"requires_procedure": true}).
                                "json_list" for a list of dicts (e.g., {"audit_tasks": [...]}).
                                "json_object" for a generic JSON object (e.g., compliance judgment).
                                "text" for a raw text response.

    Returns:
        The parsed response from the LLM or None if an error occurs.
    """
    logger.info(f"Calling OpenAI API with model: {model_name}")
    logger.debug(f"LLM Prompt:\n{prompt}")

    if not api_key:
        logger.error("OpenAI API key is missing. Cannot make the API call.")
        return None

    client = OpenAI(api_key=api_key)

    system_message_content = "You are an AI assistant helping with compliance audits. Please provide responses in the requested JSON format. All textual content in your response that is intended for human reading (like reasoning or descriptions) should be in Traditional Chinese, using Taiwan-specific terminology (請使用台灣常用的繁體中文)."
    if expected_response_type in ["boolean", "json_list", "json_object"]:
        system_message_content = "Ensure your response is a single, valid JSON object (or list of objects) as described, without any surrounding text or explanations. All textual content within the JSON that is intended for human reading (e.g., audit task sentences, reasoning) should be in Traditional Chinese, using Taiwan-specific terminology (請使用台灣常用的繁體中文)."

    messages = [
        {"role": "system", "content": system_message_content},
        {"role": "user", "content": prompt}
    ]

    try:
        # For newer models that support it, use response_format to enforce JSON output.
        # Example models: gpt-3.5-turbo-1106, gpt-4-turbo-preview
        # This might need adjustment based on the specific model_name used.
        if expected_response_type in ["json_list", "json_object", "boolean"] and ("1106" in model_name or "turbo-preview" in model_name or "gpt-4" in model_name):
            logger.info("Attempting to use JSON response format for the model.")
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2,  # Low temperature for more deterministic/factual output
                response_format={"type": "json_object"},
            )
        else:
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2,
            )
            
        response_content = completion.choices[0].message.content
        logger.debug(f"Raw LLM Response Content: {response_content}")

        if not response_content:
            logger.error("LLM response content is empty.")
            return None

        # Attempt to parse the response content if it's expected to be JSON
        if expected_response_type in ["boolean", "json_list", "json_object"]:
            try:
                parsed_response = json.loads(response_content)
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding LLM JSON response: {e}. Response was: {response_content}")
                # Attempt to extract JSON from potentially markdown-formatted response (e.g. ```json ... ```)
                if "```json" in response_content and "```" in response_content.split("```json")[1]:
                    try:
                        potential_json = response_content.split("```json")[1].split("```")[0].strip()
                        parsed_response = json.loads(potential_json)
                        logger.info("Successfully parsed JSON extracted from markdown code block.")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON even after attempting to extract from markdown. Original error: {e}")
                        return None
                else:
                    return None


        if expected_response_type == "boolean":
            if isinstance(parsed_response, dict) and "requires_procedure" in parsed_response and \
               isinstance(parsed_response["requires_procedure"], bool):
                return parsed_response["requires_procedure"]
            else:
                logger.error(f"LLM response for boolean check doesn't match expected format: {parsed_response}")
                return None
        elif expected_response_type == "json_list":
            if isinstance(parsed_response, dict) and "audit_tasks" in parsed_response and \
               isinstance(parsed_response["audit_tasks"], list):
                return parsed_response["audit_tasks"]
            else: # Sometimes the LLM might return a list directly if prompted well
                if isinstance(parsed_response, list): # If the root is a list
                    logger.info("LLM returned a list directly for json_list expectation.")
                    # Assuming the list contains the expected task dicts.
                    # Add validation here if needed: all(isinstance(item, dict) for item in parsed_response)
                    return parsed_response 
                logger.error(f"LLM response for json_list (audit plan) doesn't match expected format: {parsed_response}")
                return None
        elif expected_response_type == "json_object":
            if isinstance(parsed_response, dict):
                return parsed_response
            else:
                logger.error(f"LLM response for json_object doesn't match expected format: {parsed_response}")
                return None
        elif expected_response_type == "text":
            return response_content.strip() # Return the raw (but stripped) content
        else:
            logger.error(f"Unknown expected_response_type: {expected_response_type}")
            return None

    except APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error calling OpenAI API or processing its response: {e}")
        return None


if __name__ == '__main__':
    import os
    from unittest.mock import patch, MagicMock

    print("Testing LLM Utils with OpenAI integration...")
    
    # Use a placeholder API key for tests, or skip if not set.
    # In a CI environment, this key might be set, or tests requiring it could be skipped.
    TEST_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-test-placeholder")
    # Ensure tests can run even if no key is available by mocking,
    # but log a warning if a real key isn't found for local testing of actual calls.
    if TEST_API_KEY == "sk-test-placeholder":
        logger.warning("OPENAI_API_KEY environment variable not set. Using a placeholder for tests. Actual API calls will be mocked.")

    # --- Test Case 1: Need-Check (boolean) ---
    @patch('openai.resources.chat.completions.Completions.create')
    def test_need_check_boolean(mock_create_completion):
        print("\nTesting Need-Check (boolean)...")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = json.dumps({"requires_procedure": True})
        mock_create_completion.return_value = mock_response

        prompt_need_check = "Control Clause: Systems must have access control mechanisms."
        # Using a model name that might support JSON mode for testing that path if applicable
        need_check_result = call_llm_api(
            prompt_need_check, 
            "gpt-3.5-turbo-1106", 
            api_key=TEST_API_KEY, 
            expected_response_type="boolean"
        )
        print(f"Need-Check for '{prompt_need_check[:30]}...': {need_check_result} (Expected: True)")
        assert need_check_result is True
        mock_create_completion.assert_called_once()
        # Check if response_format was passed if model implies it
        if "1106" in "gpt-3.5-turbo-1106" or "turbo-preview" in "gpt-3.5-turbo-1106":
             assert "response_format" in mock_create_completion.call_args[1]
             assert mock_create_completion.call_args[1]["response_format"] == {"type": "json_object"}


    # --- Test Case 2: Audit-Plan (json_list) ---
    @patch('openai.resources.chat.completions.Completions.create')
    def test_audit_plan_json_list(mock_create_completion):
        print("\nTesting Audit-Plan (json_list)...")
        mock_response_data = {
            "audit_tasks": [
                {"id": "AT001", "sentence": "Verify policy."},
                {"id": "AT002", "sentence": "Check enforcement."}
            ]
        }
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = json.dumps(mock_response_data)
        mock_create_completion.return_value = mock_response

        prompt_audit_plan = "Control Clause: Systems must have access control mechanisms."
        audit_plan_result = call_llm_api(
            prompt_audit_plan, 
            "gpt-4-turbo-preview", 
            api_key=TEST_API_KEY, 
            expected_response_type="json_list"
        )
        print(f"Audit-Plan for '{prompt_audit_plan[:30]}...': {audit_plan_result} (Expected: List of 2 tasks)")
        assert isinstance(audit_plan_result, list) and len(audit_plan_result) == 2
        if audit_plan_result:
            assert audit_plan_result[0]['id'] == "AT001"
        mock_create_completion.assert_called_once()
        if "turbo-preview" in "gpt-4-turbo-preview": # Check for response_format
            assert "response_format" in mock_create_completion.call_args[1]
            assert mock_create_completion.call_args[1]["response_format"] == {"type": "json_object"}


    # --- Test Case 3: Judge (json_object) ---
    @patch('openai.resources.chat.completions.Completions.create')
    def test_judge_json_object(mock_create_completion):
        print("\nTesting Judge (json_object)...")
        mock_response_data = {"compliant": False, "reasoning": "Evidence missing."}
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = json.dumps(mock_response_data)
        mock_create_completion.return_value = mock_response

        prompt_judge = "Control: Backups. Task: Inspect logs. Evidence: Logs missing."
        judge_result = call_llm_api(
            prompt_judge, 
            "gpt-3.5-turbo", # Older model name, JSON mode might not be used
            api_key=TEST_API_KEY, 
            expected_response_type="json_object"
        )
        print(f"Judge for '{prompt_judge[:30]}...': {judge_result} (Expected: compliant=False)")
        assert isinstance(judge_result, dict) and judge_result.get("compliant") is False
        mock_create_completion.assert_called_once()
        # For a model not explicitly matching "1106" or "turbo-preview", response_format shouldn't be there
        if not ("1106" in "gpt-3.5-turbo" or "turbo-preview" in "gpt-3.5-turbo"):
            assert "response_format" not in mock_create_completion.call_args[1]


    # --- Test Case 4: Text response ---
    @patch('openai.resources.chat.completions.Completions.create')
    def test_text_response(mock_create_completion):
        print("\nTesting Text Response...")
        raw_text = "This is a plain text summary."
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = raw_text
        mock_create_completion.return_value = mock_response

        prompt_text = "Summarize this document."
        text_result = call_llm_api(
            prompt_text,
            "gpt-3.5-turbo",
            api_key=TEST_API_KEY,
            expected_response_type="text"
        )
        print(f"Text result for '{prompt_text[:30]}...': '{text_result}' (Expected: '{raw_text}')")
        assert text_result == raw_text
        mock_create_completion.assert_called_once()


    # --- Test Case 5: API Key Missing ---
    def test_api_key_missing():
        print("\nTesting API Key Missing...")
        prompt_test = "Test prompt"
        result = call_llm_api(
            prompt_test,
            "gpt-3.5-turbo",
            api_key="", # Empty API Key
            expected_response_type="text"
        )
        print(f"Result with missing API key: {result} (Expected: None)")
        assert result is None

    # --- Test Case 6: JSON extraction from markdown code block ---
    @patch('openai.resources.chat.completions.Completions.create')
    def test_json_from_markdown(mock_create_completion):
        print("\nTesting JSON extraction from markdown...")
        mock_response_content = """
Some introductory text.
```json
{
    "requires_procedure": true
}
```
Some concluding text.
"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = mock_response_content
        mock_create_completion.return_value = mock_response

        prompt_need_check = "Control Clause: Systems must have access control mechanisms."
        need_check_result = call_llm_api(
            prompt_need_check,
            "gpt-3.5-turbo", # Model where this behavior might be seen
            api_key=TEST_API_KEY,
            expected_response_type="boolean"
        )
        print(f"Need-Check (markdown extract) for '{prompt_need_check[:30]}...': {need_check_result} (Expected: True)")
        assert need_check_result is True
        mock_create_completion.assert_called_once()

    # Run tests
    test_need_check_boolean()
    test_audit_plan_json_list()
    test_judge_json_object()
    test_text_response()
    test_api_key_missing()
    test_json_from_markdown()
    
    print("\nLLM Utils tests with OpenAI integration completed.")
