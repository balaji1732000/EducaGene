import os
from typing import Dict, Any, Optional, Literal as PyLiteral
import google.generativeai as genai
import traceback
import json
# Removed Pydantic imports

from manim_video_generator.config import app
from manim_video_generator.state import WorkflowState
from manim_video_generator.utils import upload_to_gemini, wait_for_files_active

# Removed Pydantic model definition

# Configure Gemini API Key
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        app.logger.warning("GEMINI_API_KEY not found. Combined script/video evaluation node will be skipped.")
        genai.configure(api_key="DUMMY_KEY")
    else:
        genai.configure(api_key=gemini_api_key)
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
        video_file = upload_to_gemini(video_path, mime_type="video/mp4")
        app.logger.info(f"Waiting for video file '{video_file.name}' to become active...")
        wait_for_files_active([video_file])
        app.logger.info("Video file active. Proceeding with Gemini Vision analysis.")

        # Define the detailed system instruction requesting structured JSON output with scene-based feedback
        # Added stricter checks for transitions and pacing
        system_instruction = """You are a meticulous Manim Quality Assurance expert. Evaluate the provided script and video based on the user prompt's context.

Strict Evaluation Checklist (Apply per scene where relevant):
1.  **Plan Adherence:** Does the video visually execute the steps described in the Video Plan? Note deviations/omissions.
2.  **Visual Clarity & Readability:** Is text readable (size, contrast, position)? Are diagrams clear? Check for Font/Unicode Errors (□□□) indicating missing `font` parameters in `Text()`.
3.  **Layout, Overlaps & Framing:** Are elements within 16:9 frame? Is there clutter or confusing overlap? **[Critical]** Overlaps or elements outside frame are critical issues.
4.  **Scene Transitions [STRICT]:** Are elements from the previous logical scene block properly removed (e.g., via `FadeOut`) before the next scene begins? Flag lingering elements as **[Critical]**.
5.  **Animation Quality & Pacing [STRICT]:** Are animations smooth? Does the overall pacing feel too rushed? Are `run_time` values appropriate (generally >= 1s)? Are there sufficient `wait()` calls (e.g., `wait(1)`) between distinct steps/scenes? Flag rushed pacing as **[Major]**.
6.  **Code-Visual Consistency:** Does the visual output match the script's intent?
7.  **3D Usage Appropriateness:** Was `ThreeDScene` used only when necessary according to the plan?
8.  **3D Camera Angle:** If `ThreeDScene` is used, is the camera angle effective and readable?

Output Requirements:
*   Your entire response **MUST** be a single, valid JSON object: `{ "verdict": "...", "feedback": "..." }`
*   "verdict" **MUST** be either "SATISFIED" or "REVISION_NEEDED".
*   "feedback" **MUST** be a string.
    *   If issues are found (verdict is "REVISION_NEEDED"), format the feedback string as follows:
        - For each scene number where issues occur:
          - Start with "Scene [Number]: [Scene Title from Plan]"
          - Optionally, include the relevant code snippet: "Relevant Code:\n```python\n...\n```"
          - List numbered issues found in that scene:
            - Start each issue with severity: `[Critical]` (for overlaps, out-of-frame, lingering elements), `[Major]` (for readability, pacing, significant plan deviation), or `[Minor]` (for small aesthetic issues).
            - Describe the issue clearly in the target language provided in the user prompt context.
            - Suggest a specific fix (e.g., "Adjust position using .shift()", "Add font='...'","Add self.play(FadeOut(...)) before this scene", "Increase run_time/add wait()").
        - Separate scenes with a double newline (`\\n\\n`).
    *   If no issues are found (verdict is "SATISFIED"), the "feedback" string **MUST** be empty (`""`).

Example Feedback String (Issues Found):
"Scene 2: Scatter Plot\\nRelevant Code:\\n```python\\nself.play(Write(title))\\nself.play(Create(dots))\\n```\\n1. [Critical] Title text overlaps with dots. Suggest using `FadeOut(title)` before creating dots.\\n\\nScene 5: Cost Function\\n1. [Major] Animation of formula writing is too fast (run_time=0.5). Suggest increasing run_time to 1.5.\\n2. [Critical] Elements from Scene 4 are still visible. Add `self.play(FadeOut(scene4_elements))` before Scene 5 starts."

Focus *only* on visual quality, clarity, pacing, 3D usage, and plan adherence. Do not evaluate educational content or runtime errors. Ensure the output is valid JSON and feedback text is in the target language."""

        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 65000,
            "response_mime_type": "application/json", # Request JSON MIME type
            # Removed response_schema
        }

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-04-17", # Using flash
            generation_config=generation_config,
            system_instruction=system_instruction,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        )

        # Simplified User Prompt providing context
        video_plan_str = json.dumps(state.video_plan, indent=2) if state.video_plan else "Plan not available."
        user_concept = state.user_concept
        language = state.language # Language needed for feedback text
        prompt = f"""Evaluate the script and video based on the following context. Follow the instructions provided in the system prompt precisely, providing feedback text in **{language}**.

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
*   **Rendered Video:** (Provided as input)"""

        app.logger.info("Sending combined script/video analysis request to Gemini...")
        response = model.generate_content([prompt, video_file])

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
            eval_result = json.loads(response_text) # Use standard json.loads

            verdict = eval_result.get("verdict")
            feedback_str = eval_result.get("feedback") # Get feedback string

            # Validate verdict
            if verdict not in ["SATISFIED", "REVISION_NEEDED"]:
                raise ValueError(f"Invalid verdict value received: {verdict}")

            # Process feedback based on verdict
            if verdict == "REVISION_NEEDED":
                if not feedback_str: # Check if feedback string is empty or None
                    feedback = "Revision needed, but specific feedback was not provided in JSON."
                    app.logger.warning(feedback)
                else:
                    feedback = feedback_str # Assign the non-empty string
            elif verdict == "SATISFIED":
                feedback = None # Explicitly set to None if satisfied

            app.logger.info(f"Parsed evaluation verdict: {verdict}")
            if feedback:
                app.logger.info(f"Parsed evaluation feedback (structured string): {feedback}")

        except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as parse_e:
            # Handle errors during JSON parsing or validation
            err_msg = f"Failed to parse evaluation JSON response or invalid structure: {parse_e}. Raw response: {response.text if hasattr(response, 'text') else 'N/A'}"
            app.logger.error(err_msg)
            verdict = "REVISION_NEEDED" # Default to revision needed on parse error
            feedback = f"Failed to parse evaluation response. Raw response: {response.text if hasattr(response, 'text') else 'N/A'}"

        # Ensure feedback is None if verdict is SATISFIED, even if LLM provided some text
        if verdict == "SATISFIED":
            feedback = None

        return {"evaluation_feedback": feedback, "code_eval_verdict": verdict, "error_message": None}

    except Exception as e:
        err_msg = f"Error during combined script/video evaluation: {e}\n{traceback.format_exc()}"
        app.logger.error(err_msg)
        # Default to SATISFIED on other errors to avoid loops
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED", "error_message": err_msg}
    finally:
        if video_file:
            try:
                genai.delete_file(video_file.name)
                app.logger.info(f"Deleted temporary video file '{video_file.name}' from Gemini.")
            except Exception as del_e:
                app.logger.warning(f"Could not delete temporary Gemini file '{video_file.name}': {del_e}")
