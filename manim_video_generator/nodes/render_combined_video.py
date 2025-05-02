import os
import subprocess
import shutil
from typing import Dict, Any, Optional, List, Literal as PyLiteral
import json
import traceback

from pydantic import BaseModel, Field
from langchain_openai import AzureChatOpenAI # Use the same client as web_scrap.py for consistency
from manim_video_generator.llm_client import get_llm_client, get_non_reasoning_llm_client # Importing the LLM client from the existing module
from manim import config as manim_config
from manim_video_generator.config import app, APP_ROOT
from manim_video_generator.state import WorkflowState

# --- Pydantic Models for Structured Error ---
class StructuredErrorDetail(BaseModel):
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    line_number: Optional[int] = None
    context: Optional[str] = None

class StructuredErrorResponse(BaseModel):
    errors_found: bool
    error_details: List[StructuredErrorDetail] = Field(default_factory=list)

# --- Helper Function for Error Extraction ---
def _extract_structured_error(stderr_text: str) -> Optional[str]:
    """
    Uses an LLM to attempt to parse stderr text into a structured JSON error report.
    Returns the JSON string if successful and errors are found, otherwise returns None.
    """
    app.logger.info("Attempting to extract structured error from stderr...")
    if not stderr_text:
        return None

    try:
        # Initialize LLM client (consider moving to a shared client module later)
        llm = get_non_reasoning_llm_client()
    except Exception as e:
        app.logger.error(f"Failed to initialize LLM for error extraction: {e}")
        return None # Cannot proceed without LLM

    system_instruction = """You are an error analysis assistant. Analyze the user-provided text (likely stderr output or a traceback) focusing on identifying distinct error reports. Don't put the same error again and again if same error comes 
Your response MUST be a single, valid JSON object matching this schema:
{
  "errors_found": boolean,
  "error_details": [
    {
      "error_type": "string (e.g., ZeroDivisionError, ModuleNotFoundError, NameError)",
      "error_message": "string (The specific error message)",
      "line_number": "integer or null (Line number from traceback if available)",
      "context": "string or null (Relevant line of code from traceback if available) code snippet where the error occurred"
    }
    // ... more error objects if multiple distinct errors are found
  ]
}
- If errors are found, set "errors_found" to true and create an object for each distinct error in "error_details". Extract the type, message, line number, and context line from the traceback.
- If no clear programming errors/tracebacks are found, set "errors_found" to false and provide an empty list for "error_details".
- Be precise. For tracebacks, the 'error_type' and 'error_message' are usually on the last line(s). The line number and context come from the `File "..."` lines pointing to the user's script.
Do not include any text outside the main JSON structure."""

    prompt = f"""Analyze the following text and extract structured details for any specific error messages or tracebacks. Provide the result in the required JSON format.

Input Text:
\"\"\"
{stderr_text}
\"\"\"

JSON Output:"""

    try:
        messages = [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': prompt}
        ]
        response = llm.invoke(messages)
        response_text = response.content.strip()
        # Clean potential markdown fences
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        app.logger.debug(f"LLM raw response for error extraction: {response_text}")

        # Validate response using Pydantic
        validated_response = StructuredErrorResponse.model_validate_json(response_text)

        if validated_response.errors_found:
            # Return the validated data as a pretty-printed JSON string
            json_output = validated_response.model_dump_json(indent=2)
            app.logger.info("Successfully extracted structured error details.")
            return json_output
        else:
            app.logger.info("LLM reported no structured errors found in stderr.")
            return None # No structured errors found

    except Exception as e:
        app.logger.error(f"Failed during structured error extraction (LLM call or parsing): {e}")
        app.logger.debug(traceback.format_exc())
        return None # Fallback if LLM call or parsing fails

# --- Original Node Function ---
def render_combined_video_node(state: WorkflowState) -> Dict[str, Any]:
    """Renders the single combined scene class from the script."""
    script_path = state.full_script_path
    cls_name = state.scene_class_name
    td = state.temp_dir
    req_id = state.request_id

    app.logger.info(f"--- render_combined_video (Class: {cls_name}) ---")

    # Verify script path exists
    if not script_path or not os.path.exists(script_path):
        err = "Missing script path for rendering."
        app.logger.error(err)
        # Cannot extract error if script is missing, return raw message
        return {'rendering_error': err, 'video_path': None}

    media_dir = os.path.join(td, 'scene_media')
    output_filename = f'{req_id}_combined_video.mp4'
    os.makedirs(media_dir, exist_ok=True)

    cmd = [
        shutil.which('manim') or 'manim', 'render', '-qm',
        '--format', 'mp4',
        '--verbosity', 'DEBUG', # Keep DEBUG to get full tracebacks in stderr
        '--media_dir', media_dir,
        '-o', output_filename,
        script_path,
    ]
    # Removed class name argument if present, as we render the whole file
    # if cls_name:
    #     cmd.append(cls_name)

    app.logger.info(f"Running Manim command: {' '.join(cmd)}")

    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=APP_ROOT,
            timeout=6000, check=False, encoding='utf-8', errors='replace'
        )
        if res.stdout:
            app.logger.debug(f"Manim stdout:\n{res.stdout}")
        if res.stderr:
            app.logger.debug(f"Manim stderr:\n{res.stderr}")

        processed_error_info = None # Initialize
        if res.returncode != 0:
            raw_stderr = res.stderr or 'Manim failed with non-zero exit code but no stderr.'
            # Attempt to extract structured error info
            processed_error_info = _extract_structured_error(raw_stderr)
            # Log appropriately
            # if processed_error_info:
            #     app.logger.error(f"Manim render failed (Code {res.returncode}). Extracted Structured Error:\n{processed_error_info}")
            # else:
            #     # Fallback: Use the last ~1500 characters if extraction fails
            #     fallback_error = raw_stderr
            #     app.logger.error(f"Manim render failed (Code {res.returncode}). Could not extract structured error. Using raw stderr tail:\n{fallback_error}")
            #     processed_error_info = fallback_error # Pass raw tail as error

            # Return the processed info (JSON string or raw string)
            return {'rendering_error': processed_error_info, 'video_path': None}

        # --- Robust File Finding Logic ---
        # (Keep the existing robust finding logic for successful renders)
        found_video_path = None
        app.logger.info(f"Manim execution successful (Code 0). Searching for output file '{output_filename}' in '{media_dir}'...")
        # Prioritize checking direct output path first
        direct_path = os.path.join(media_dir, output_filename)
        if os.path.exists(direct_path):
             found_video_path = direct_path
             app.logger.info(f"Found rendered video directly at: {found_video_path}")
        else:
            app.logger.info(f"Video not at direct path '{direct_path}'. Searching recursively...")
            # Search recursively within the media_dir if not found directly
            for root, dirs, files in os.walk(media_dir):
                if output_filename in files:
                    found_video_path = os.path.join(root, output_filename)
                    app.logger.info(f"Found rendered video recursively at: {found_video_path}")
                    break # Stop searching once found

        if not found_video_path:
            # If still not found after searching, log error and return None
            err = f"Rendered video '{output_filename}' not found within '{media_dir}' after successful Manim execution."
            app.logger.error(err)
            # Return rendering_error as None because Manim itself succeeded, but file is missing
            return {'rendering_error': None, 'video_path': None, 'error_message': err}
        # --- End Robust File Finding Logic ---

        # Move the found video to final_build
        final_dir = os.path.join(td, 'final_build')
        os.makedirs(final_dir, exist_ok=True)
        target_path = os.path.join(final_dir, output_filename)
        try:
            shutil.move(found_video_path, target_path)
            app.logger.info(f"Moved combined video to {target_path}")
            return {'rendering_error': None, 'video_path': target_path} # Return the final path
        except Exception as move_e:
            err = f"Failed to move rendered video from {found_video_path} to {target_path}: {move_e}"
            app.logger.error(err, exc_info=True)
            # Return error message, video_path is None as it wasn't moved successfully
            return {'rendering_error': None, 'video_path': None, 'error_message': err}

    except subprocess.TimeoutExpired:
        err = f"Manim render timed out after 600s"
        app.logger.error(err)
        # Attempt to extract structured error (though stderr might be empty on timeout)
        processed_error_info = _extract_structured_error(err) or err
        return {'rendering_error': processed_error_info, 'video_path': None}
    except Exception as e:
        err = f"Unexpected error during render: {e}"
        app.logger.error(err, exc_info=True)
        # Attempt to extract structured error from the exception string
        processed_error_info = _extract_structured_error(str(e)) or err
        return {'rendering_error': processed_error_info, 'video_path': None}
