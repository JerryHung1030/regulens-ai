from __future__ import annotations

import json
from typing import Dict, Any, Optional, Union # Added Union
from app.settings import PipelineSettings # Assuming this will hold API keys/endpoints if needed
from app.logger import logger

# Placeholder for actual LLM client libraries (e.g., OpenAI, Anthropic, Gemini)
# from openai import OpenAI

def call_llm_api(
    prompt: str,
    model_name: str,
    # settings: PipelineSettings, # If API keys/endpoints are part of settings
    expected_response_type: str = "boolean" # "boolean", "json_list", "json_object"
) -> Optional[Union[bool, List[Dict[str, Any]], Dict[str, Any], str]]: # Extended return types
    """
    Helper function to interact with an LLM.
    This is a MOCK IMPLEMENTATION. Replace with actual LLM API calls.

    Args:
        prompt: The prompt to send to the LLM.
        model_name: The specific LLM model to use.
        expected_response_type: "boolean" for Yes/No, "json_list" for list of task dicts,
                                "json_object" for a generic JSON object (e.g. compliance judgment),
                                "text" for raw text.

    Returns:
        The parsed response from the LLM (bool, list of dicts, dict, or string) or None if an error occurs.
    """
    logger.info(f"Calling LLM API (mock) with model: {model_name}")
    logger.debug(f"LLM Prompt:\n{prompt}")

    # MOCK RESPONSE LOGIC
    # In a real scenario, this would involve:
    # 1. Setting up the LLM client with API keys (possibly from settings)
    # 2. Making the API call (e.g., client.chat.completions.create(...))
    # 3. Handling potential API errors (rate limits, auth issues, etc.)

    mock_response_content = None
    if model_name == "mock_need_check_model": # Corresponds to settings.llm_model_need_check
        if "Systems must have access control mechanisms" in prompt:
            mock_response_content = json.dumps({"requires_procedure": True})
        elif "Regular data backups must be performed" in prompt:
            mock_response_content = json.dumps({"requires_procedure": True})
        elif "Strong password policies must be enforced" in prompt:
            mock_response_content = json.dumps({"requires_procedure": True})
        elif "Passwords must be at least 12 characters" in prompt: # Sub-clause example
             mock_response_content = json.dumps({"requires_procedure": False}) # Example: sub-clauses might not directly need own procedures
        else:
            mock_response_content = json.dumps({"requires_procedure": False})

    elif model_name == "mock_audit_plan_model": # Corresponds to settings.llm_model_audit_plan
        if "Systems must have access control mechanisms" in prompt:
            mock_response_content = json.dumps({
                "audit_tasks": [
                    {"id": "AT001", "sentence": "Verify that a documented access control policy exists."},
                    {"id": "AT002", "sentence": "Check if systems enforce user authentication for access."}
                ]
            })
        elif "Regular data backups must be performed" in prompt:
            mock_response_content = json.dumps({
                "audit_tasks": [
                    {"id": "AT003", "sentence": "Confirm that data backup procedures are defined and up to date."},
                    {"id": "AT004", "sentence": "Inspect backup logs to ensure backups are performed regularly."}
                ]
            })
        elif "Strong password policies must be enforced" in prompt:
             mock_response_content = json.dumps({
                "audit_tasks": [
                    {"id": "AT005", "sentence": "Review the organization's password policy for strength requirements."},
                    {"id": "AT006", "sentence": "Test a sample of system configurations to ensure password complexity rules are enforced."}
                ]
            })
        else:
            mock_response_content = json.dumps({"audit_tasks": []}) # Default empty list

    elif model_name == "mock_judge_model": # Corresponds to settings.llm_model_judge
        # Mock responses for compliance judgment
        if "Verify that a documented access control policy exists" in prompt and "Evidence: Access control policy document found" in prompt:
            mock_response_content = json.dumps({"compliant": True, "reasoning": "Policy document directly supports the task."})
        elif "Check if systems enforce user authentication for access" in prompt and "Evidence: System logs show successful and failed logins" in prompt:
             mock_response_content = json.dumps({"compliant": True, "reasoning": "System logs confirm authentication attempts."})
        elif "Inspect backup logs to ensure backups are performed regularly" in prompt and "Evidence: Backup logs are missing for the last quarter" in prompt:
            mock_response_content = json.dumps({"compliant": False, "reasoning": "Missing backup logs indicate non-compliance."})
        else: # Default compliant response if no specific mock matches
            mock_response_content = json.dumps({"compliant": True, "reasoning": "Default mock compliant response."})
    else:
        logger.warning(f"No mock response defined for model: {model_name}")
        return None

    logger.debug(f"LLM Mock Response Content: {mock_response_content}")

    try:
        if not mock_response_content:
            raise ValueError("Mock response content is empty.")

        parsed_response = json.loads(mock_response_content)

        if expected_response_type == "boolean":
            if "requires_procedure" in parsed_response and isinstance(parsed_response["requires_procedure"], bool):
                return parsed_response["requires_procedure"]
            else:
                logger.error(f"LLM response for boolean check doesn't match expected format: {parsed_response}")
                return None
        elif expected_response_type == "json_list":
            if "audit_tasks" in parsed_response and isinstance(parsed_response["audit_tasks"], list):
                # Further validation of task structure could be added here
                return parsed_response["audit_tasks"]
            else:
                logger.error(f"LLM response for audit plan doesn't match expected format: {parsed_response}")
                return None # Or empty list: []
        elif expected_response_type == "json_object":
             # For responses that are a single JSON object, like compliance judgment
            if isinstance(parsed_response, dict):
                return parsed_response # Return the whole dict
            else:
                logger.error(f"LLM response for json_object doesn't match expected format: {parsed_response}")
                return None
        elif expected_response_type == "text":
            # If expecting raw text (not used in current steps but for future)
            return str(parsed_response.get("text_response", "") if isinstance(parsed_response, dict) else parsed_response)

        else:
            logger.error(f"Unknown expected_response_type: {expected_response_type}")
            return None

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding LLM JSON response: {e}. Response was: {mock_response_content}")
        return None
    except ValueError as e:
        logger.error(f"Error processing LLM response: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during LLM response processing: {e}")
        return None

if __name__ == '__main__':
    print("Testing LLM Utils...")

    # Test Need-Check
    prompt_need_check = "Control Clause: Systems must have access control mechanisms."
    need_check_result = call_llm_api(prompt_need_check, "mock_need_check_model", expected_response_type="boolean")
    print(f"Need-Check for '{prompt_need_check[:30]}...': {need_check_result} (Expected: True)")
    assert need_check_result is True

    prompt_need_check_false = "Control Clause: This is a test clause that does not need a procedure."
    need_check_result_false = call_llm_api(prompt_need_check_false, "mock_need_check_model", expected_response_type="boolean")
    print(f"Need-Check for '{prompt_need_check_false[:30]}...': {need_check_result_false} (Expected: False)")
    assert need_check_result_false is False

    # Test Audit-Plan
    prompt_audit_plan = "Control Clause: Systems must have access control mechanisms."
    audit_plan_result = call_llm_api(prompt_audit_plan, "mock_audit_plan_model", expected_response_type="json_list")
    print(f"Audit-Plan for '{prompt_audit_plan[:30]}...': {audit_plan_result} (Expected: List of 2 tasks)")
    assert isinstance(audit_plan_result, list) and len(audit_plan_result) == 2
    if audit_plan_result: # mypy check
        assert audit_plan_result[0]['id'] == "AT001"

    prompt_audit_plan_empty = "Control Clause: This clause results in no tasks."
    audit_plan_result_empty = call_llm_api(prompt_audit_plan_empty, "mock_audit_plan_model", expected_response_type="json_list")
    print(f"Audit-Plan for '{prompt_audit_plan_empty[:30]}...': {audit_plan_result_empty} (Expected: [])")
    assert isinstance(audit_plan_result_empty, list) and len(audit_plan_result_empty) == 0

    # Test Judge
    prompt_judge_compliant = "Control: Access Control. Task: Verify policy. Evidence: Access control policy document found."
    judge_result_compliant = call_llm_api(prompt_judge_compliant, "mock_judge_model", expected_response_type="json_object")
    print(f"Judge for '{prompt_judge_compliant[:30]}...': {judge_result_compliant} (Expected: compliant=True)")
    assert isinstance(judge_result_compliant, dict) and judge_result_compliant.get("compliant") is True

    prompt_judge_non_compliant = "Control: Backups. Task: Inspect logs. Evidence: Backup logs are missing for the last quarter."
    judge_result_non_compliant = call_llm_api(prompt_judge_non_compliant, "mock_judge_model", expected_response_type="json_object")
    print(f"Judge for '{prompt_judge_non_compliant[:30]}...': {judge_result_non_compliant} (Expected: compliant=False)")
    assert isinstance(judge_result_non_compliant, dict) and judge_result_non_compliant.get("compliant") is False

    print("LLM Utils tests completed.")

# print("app.pipeline.llm_utils.py created.") # Already exists, so this line is not accurate if re-running.
