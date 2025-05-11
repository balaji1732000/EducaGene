import os
from typing import Dict, Any, Optional, Literal as PyLiteral
from google import genai
from google.genai import types
import traceback
import json
# Removed Pydantic imports

from manim_video_generator.config import app
from manim_video_generator.state import WorkflowState
from manim_video_generator.utils import upload_to_gemini, wait_for_files_active, flag_overlap_frames # Updated import for CV utility

# Removed Pydantic model definition

# Configure Gemini API Key
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        app.logger.warning("GEMINI_API_KEY not found. Combined script/video evaluation node will be skipped.")
        # genai.configure(api_key="DUMMY_KEY")
    else:
        client = genai.Client(api_key=gemini_api_key)
except Exception as e:
    app.logger.error(f"Error configuring Gemini: {e}")

def evaluate_script_and_video_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Analyzes the rendered silent video alongside its source code using Gemini Vision.
    Identifies visual issues (overlaps, clarity, timing) AND potential code errors (LaTeX).
    Provides consolidated feedback and a verdict for potential code revision via JSON.
    """
    app.logger.info("--- evaluate_script_and_video ---")
    video_path = state.video_path
    script_code = state.current_code
    feedback = None
    verdict = 'SATISFIED' # Default to satisfied

    # Basic checks
    if not gemini_api_key:
        app.logger.warning("Skipping combined evaluation as GEMINI_API_KEY is not configured.")
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED"}

    if not video_path or not os.path.exists(video_path):
        app.logger.error(f"Video path '{video_path}' not found. Skipping combined evaluation.")
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED", "error_message": "Silent video path missing for evaluation."}

    if not script_code:
        app.logger.error("Script code missing. Skipping combined evaluation.")
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED", "error_message": "Script code missing for evaluation."}

    video_file = None
    try:
        app.logger.info(f"Uploading video '{video_path}' to Gemini for combined evaluation...")
        video_file = upload_to_gemini(video_path)
        app.logger.info(f"Waiting for video file '{video_file.name}' to become active...")
        wait_for_files_active(video_file)
        app.logger.info("Video file active.")

        # --- CV Overlap Pre-pass ---
        overlap_data_str = "CV overlap pre-pass not run or no overlaps found."
        try:
            app.logger.info(f"Running CV overlap pre-pass on {video_path}...")
            # Use the tuned parameters
            cv_overlaps = flag_overlap_frames(
                video_path, 
                iou_thr=0.25, 
                sample_rate=25, 
                contour_threshold=180,
                min_contour_area=100
            )
            if cv_overlaps and not cv_overlaps.get("error") and not cv_overlaps.get("warning"):
                overlap_data_str = json.dumps(cv_overlaps, indent=2)
                app.logger.info(f"CV overlap pre-pass found {len(cv_overlaps)} frames with potential overlaps.")
            elif cv_overlaps.get("error"):
                overlap_data_str = f"CV overlap pre-pass failed: {cv_overlaps.get('error')}"
                app.logger.error(overlap_data_str)
            elif cv_overlaps.get("warning"):
                 overlap_data_str = f"CV overlap pre-pass warning: {cv_overlaps.get('warning')}"
                 app.logger.warning(overlap_data_str)
            else:
                app.logger.info("CV overlap pre-pass found no significant overlaps with current settings.")
        except Exception as cv_e:
            overlap_data_str = f"Exception during CV overlap pre-pass: {cv_e}"
            app.logger.error(overlap_data_str, exc_info=True)
        # --- End CV Overlap Pre-pass ---

        app.logger.info("Proceeding with Gemini Vision analysis.")
        # Define the detailed system instruction requesting structured JSON output with scene-based feedback
        # Added stricter checks for transitions and pacing
        system_instruction = """You are a meticulous Manim Quality Assurance expert. Evaluate the provided script and video based on the user prompt's context.

Strict Evaluation Checklist (Apply per scene where relevant):
1.  **Plan Adherence:** Does the video visually execute the steps described in the Video Plan? Note deviations/omissions.
2.  **Visual Clarity & Readability:** Is text readable (size, contrast, position)? Are diagrams clear? Check for Font/Unicode Errors (□□□) indicating missing `font` parameters in `Text()`.
3.  **Layout, Overlaps & Framing:** Are elements within 16:9 frame? Is there clutter or confusing overlap? **Consult the 'Pre-computed CV Overlap Flags' section in the user prompt for specific frames and bounding boxes identified by a CV pre-pass.** Cross-reference this data with your visual assessment. **[Critical]** Overlaps or elements outside frame are critical issues.
4.  **Scene Transitions [STRICT]:** Are elements from the previous logical scene block properly removed (e.g., via `FadeOut`) before the next scene begins? Flag lingering elements as **[Critical]**.
5.  **Animation Quality & Pacing [STRICT]:** Are animations smooth? Does the overall pacing feel too rushed? Are `run_time` values appropriate (generally >= 1s)? Are there sufficient `wait()` calls (e.g., `wait(1)`) between distinct steps/scenes? Flag rushed pacing as **[Major]**.
6.  **Code-Visual Consistency:** Does the visual output match the script's intent?
7.  **3D Usage Appropriateness:** Was `ThreeDScene` used only when necessary according to the plan?
8.  **3D Camera Angles & Movement [STRICT]:** If `ThreeDScene` is used:
    *   **Clarity:** Is the initial camera angle (`set_camera_orientation`) effective? Does it clearly show the relevant objects without awkward perspectives? Flag unclear initial angles as **[Major]**.
    *   **Purposeful Movement:** Are camera movements (`move_camera`) smooth, directly related to the content (e.g., focusing on details, revealing hidden parts), and genuinely enhance understanding? Flag confusing, jerky, or pointless movements as **[Critical]** if they obscure information or **[Major]** otherwise.
    *   **Appropriate Rotation:** Is ambient rotation (`begin_ambient_camera_rotation`) used subtly and only when it adds value (e.g., showing a complex object during explanation)? Flag distracting or excessive rotation as **[Major]**.
    *   **Overall Effectiveness:** Does the camera work make the 3D scene *easier* to understand? Flag ineffective camera work that hinders comprehension as **[Critical]**.

You MUST respond with JSON that matches this Schema:
```json
{
  "verdict": "SATISFIED" | "REVISION_NEEDED",
  "metrics": {
    "coverage": "<int 0-100>",      // Overall plan coverage
    "visual": "<int 0-100>",        // Overall visual quality and clarity
    "pedagogy": "<int 0-100>"       // Overall pedagogical effectiveness (flow, pacing)
  },
  "issues": [
    {
      "scene_number": "<int>",      // 1-based index from the plan, or 0 if not tied to a specific scene
      "scene_title": "<string>",    // Title of the scene from the plan, or empty string
      "frame": "<int|null>",        // Frame number where issue is most visible, if applicable
      "type": "overlap" | "off_frame" | "readability" | "contrast" | "pacing" | "lingering_elements" | "plan_deviation" | "missing_scene_element" | "camera_angle" | "camera_movement" | "font_error" | "other",
      "severity": "Critical" | "Major" | "Minor",
      "description": "<string>",    // Human-readable description of the issue in {language}
      "suggestion": "<string>"     // Concrete suggestion for fixing the issue
    }
  ]
}
```
If verdict == "SATISFIED", "issues" MUST be an empty list `[]`.
The `metrics` should be your best estimate based on the overall quality.
Do NOT wrap the JSON in markdown fences.
Focus *only* on visual quality, clarity, pacing, 3D usage, and plan adherence. Do not evaluate educational content or runtime errors.
Ensure the output is valid JSON and all string values within the JSON (like description, suggestion) are in the target language specified in the user prompt.
"""

        generation_config =types.GenerateContentConfig(
        temperature=0.5,
        top_p=0.95,
        top_k=40,
        max_output_tokens=10000,
        response_mime_type="application/json",
        system_instruction=system_instruction,
        safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        # Add any other necessary parameters here
    )

       

        # Simplified User Prompt providing context
        video_plan_str = json.dumps(state.video_plan, indent=2) if state.video_plan else "Video plan not available."
        user_concept = state.user_concept
        language = state.language # Language needed for feedback text
        
        prompt = f"""TASK:
Execute the STRICT CHECKLIST you received in the system message.
Map your findings to the JSON Schema provided in the system message, including the 'metrics' object.
Use the overlap_json (provided as 'Pre-computed CV Overlap Flags' in the context below) as ground truth: if a frame is listed there with overlaps, you MUST create an issue of type "overlap", severity "Critical", and include that frame index in your feedback for the 'frame' field in the 'issues' list.
Respond in the exact JSON schema given in the system message. All descriptive text in the JSON (like 'description' and 'suggestion') MUST be in **{language}**.

**Context:**
*   **User Concept:** {user_concept}
*   **Target Language:** {language}
*   **Video Plan:**
```json
{video_plan_str}
```
*   **Generated Manim Script:**
```python
{script_code}
```
*   **Pre-computed CV Overlap Flags:**
```json
{overlap_data_str}
```
*   **Rendered Video:** (Provided as input)"""

        app.logger.info("Sending combined script/video analysis request to Gemini...")
        # The response_mime_type is set in generation_config when the model is initialized.
        # No need to check or set it again here.
            
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-04-17", # Using flash
            config=generation_config,
            contents=[prompt,video_file]
            
        )

        try:
            # Parse the raw text response as JSON
            response_text = response.text.strip()
            # Clean potential markdown fences just in case
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            app.logger.info(f"Raw Gemini evaluation response: {response_text}")
            eval_data = json.loads(response_text) 

            verdict = eval_data.get("verdict")
            issues = eval_data.get("issues", []) # Default to empty list
            # metrics = eval_data.get("metrics", {}) # Store metrics if needed later

            if verdict not in ["SATISFIED", "REVISION_NEEDED"]:
                raise ValueError(f"Invalid 'verdict' value received: {verdict}")
            if not isinstance(issues, list):
                raise ValueError(f"Invalid 'issues' format received: expected a list, got {type(issues)}")

            if verdict == "SATISFIED" and issues:
                app.logger.warning("Verdict is SATISFIED, but issues list is not empty. Clearing issues.")
                issues = []
            
            # The 'feedback' variable will now store the list of issue dictionaries
            feedback = issues if verdict == "REVISION_NEEDED" else []

            app.logger.info(f"Parsed evaluation verdict: {verdict}")
            app.logger.info(f"Parsed evaluation issues: {json.dumps(feedback, indent=2)}")
            # app.logger.info(f"Parsed evaluation metrics: {metrics}")

        except (json.JSONDecodeError, ValueError) as parse_e:
            err_msg = f"Failed to parse evaluation JSON response or invalid structure: {parse_e}. Raw response: {response.text if hasattr(response, 'text') else 'N/A'}"
            app.logger.error(err_msg)
            # Fallback: create a generic issue to indicate parsing failure
            verdict = "REVISION_NEEDED"
            feedback = [{
                "scene_number": 0,
                "scene_title": "JSON Parsing Error",
                "frame": None,
                "type": "other",
                "severity": "Critical",
                "description": f"Failed to parse LLM evaluation response. Error: {parse_e}",
                "suggestion": "Check LLM response format and system prompt for schema adherence."
            }]

        return {"evaluation_feedback": feedback, "code_eval_verdict": verdict, "error_message": None}

    except Exception as e:
        err_msg = f"General error during combined script/video evaluation: {e}\n{traceback.format_exc()}"
        app.logger.error(err_msg)
        # Default to SATISFIED on other errors to avoid loops
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED", "error_message": err_msg}
    finally:
        if video_file:
            try:
                client.files.delete(video_file.name)
                app.logger.info(f"Deleted temporary video file '{video_file.name}' from Gemini.")
            except Exception as del_e:
                app.logger.warning(f"Could not delete temporary Gemini file '{video_file.name}': {del_e}")
