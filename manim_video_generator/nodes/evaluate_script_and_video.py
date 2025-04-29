import os
from typing import Dict, Any, Optional
import google.generativeai as genai
import traceback

from manim_video_generator.config import app
from manim_video_generator.state import WorkflowState
from manim_video_generator.utils import upload_to_gemini, wait_for_files_active
# Removed incorrect import: from manim_video_generator.llm_client import get_gemini_client

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
    Provides consolidated feedback and a verdict for potential code revision.
    """
    app.logger.info("--- evaluate_script_and_video ---")
    # Corrected to use the state field set by the rendering node
    video_path = state.video_path
    script_code = state.current_code
    feedback = None
    verdict = 'SATISFIED' # Default to satisfied

    # Basic checks
    if not gemini_api_key:
        app.logger.warning("Skipping combined evaluation as GEMINI_API_KEY is not configured.")
        # Return satisfied to proceed without evaluation
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED"}

    if not video_path or not os.path.exists(video_path):
        app.logger.error(f"Video path '{video_path}' not found. Skipping combined evaluation.")
        # Return satisfied as we cannot evaluate
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED", "error_message": "Silent video path missing for evaluation."}

    if not script_code:
        app.logger.error("Script code missing. Skipping combined evaluation.")
         # Return satisfied as we cannot evaluate
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED", "error_message": "Script code missing for evaluation."}

    video_file = None # Initialize video_file to ensure it exists for finally block
    try:
        app.logger.info(f"Uploading video '{video_path}' to Gemini for combined evaluation...")
        video_file = upload_to_gemini(video_path, mime_type="video/mp4")
        app.logger.info(f"Waiting for video file '{video_file.name}' to become active...")
        wait_for_files_active([video_file])
        app.logger.info("Video file active. Proceeding with Gemini Vision analysis.")

        # Initialize Gemini model directly, similar to generate_final_script_node
        # Assuming a vision-capable model is needed. Adjust model_name if necessary.
        # Using gemini-1.5-flash as a potentially faster/cheaper vision option
        generation_config = {
            "temperature": 0.7, # Slightly lower temp for more deterministic evaluation
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 65000, # Allow for detailed feedback if needed
            "response_mime_type": "text/plain",
        }
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-04-17", # Or gemini-pro-vision if flash is unavailable/unsuitable
            generation_config=generation_config,
            # safety_settings adjusted to allow potentially discussing "errors" if needed
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        )

        # Define the main part of the prompt using an f-string
        prompt_main = f"""Analyze the provided Manim Python script AND the corresponding rendered video.

**Manim Script:**
```python
{script_code}
```

**Video Analysis Task:**
Examine the video frame by frame alongside the script. Identify significant issues that require code revision, focusing on:
1.  **Visual Clarity & Overlaps:** Are elements (text, shapes) overlapping badly? Is text readable? Are diagrams clear? Describe specific instances.
2.  **Timing/Pacing:** Does anything appear too quickly/slowly compared to reasonable expectations for the code's animations (`self.play`, `self.wait`)?
3.  **Code-Visual Mismatch:** Does the visual output seem inconsistent with what the code *intended* to do? (e.g., an object animated before being added, wrong transformations).
4.  **Potential Code Errors (Visual Clues):** Does the video show signs of common Manim errors?
    *   *LaTeX Errors:* Look for garbled text/equations (often appears as "[Tex Error]"). If seen, suggest checking LaTeX syntax in the script.
    *   *Positioning Errors:* Elements appearing off-screen or crammed together. Suggest using `.shift`, `.next_to`, `.arrange`.
    *   **Font/Unicode Errors:** Pay close attention to any text generated using `Text(...)`. If the video shows empty boxes ('tofu', □□□) instead of characters (especially for non-English languages like Hindi, Tamil, etc.), this indicates a missing or incorrect `font` parameter in the corresponding `Text(...)` object in the script. Flag this and suggest adding an appropriate `font="..."` parameter (e.g., `font="Noto Sans Devanagari"` for Hindi).

**Output Format:**
- Provide concise, actionable feedback ONLY if significant issues requiring code changes are found. Focus on what needs fixing in the code based on the visual evidence.
- **Crucially, if providing feedback for revision, include the relevant code snippet from the Manim script where the issue occurs.**
- If NO significant issues are found in the video or suggested by the code, respond with the single word: SATISFIED
- If issues ARE found, provide the feedback (including the code snippet) and conclude with the single word: REVISION_NEEDED
"""

        # Define the example part as a regular string to avoid f-string issues with braces
        prompt_examples = """
Example Feedback (if issues found):
"Text overlaps the diagram in Scene 2 around the 15s mark. Adjust positioning using .next_to().
Relevant Code Snippet:
```python
text = Text(...)
diagram = ...
self.play(Write(text), Create(diagram)) # Potential overlap here
```
Potential LaTeX error in Scene 1's title.
Relevant Code Snippet:
```python
title = MathTex(r"Title with {{invalid syntax}}")
self.play(Write(title))
```
REVISION_NEEDED"

Example Response (if no issues):
"SATISFIED"
"""
        # Combine the parts
        prompt = prompt_main + prompt_examples

        app.logger.info("Sending combined script/video analysis request to Gemini...")
        response = model.generate_content([prompt, video_file])
        response_text = response.text.strip()
        app.logger.info(f"Gemini combined evaluation response: {response_text}")

        # Parse verdict and feedback
        if response_text.endswith("REVISION_NEEDED"):
            verdict = "REVISION_NEEDED"
            # Extract feedback part (everything before the last line)
            feedback_lines = response_text.splitlines()
            if len(feedback_lines) > 1:
                 feedback = "\n".join(feedback_lines[:-1]).strip()
            else: # Only verdict line was returned
                 feedback = "Revision needed, but specific feedback was not provided by the model."
            app.logger.info(f"Combined evaluation requires revision. Feedback: {feedback}")
        elif response_text == "SATISFIED":
            verdict = "SATISFIED"
            feedback = None
            app.logger.info("Combined evaluation satisfied.")
        else:
            # Unexpected response format, assume revision needed and use full response as feedback
            verdict = "REVISION_NEEDED"
            feedback = f"Unexpected response format from evaluation model: {response_text}"
            app.logger.warning(feedback)


        return {"evaluation_feedback": feedback, "code_eval_verdict": verdict, "error_message": None}

    except Exception as e:
        err_msg = f"Error during combined script/video evaluation: {e}\n{traceback.format_exc()}"
        app.logger.error(err_msg)
        # Default to SATISFIED on error to avoid infinite loops if Gemini fails repeatedly
        return {"evaluation_feedback": None, "code_eval_verdict": "SATISFIED", "error_message": err_msg}
    finally:
        # Ensure the uploaded file is deleted from Gemini
        if video_file:
            try:
                genai.delete_file(video_file.name)
                app.logger.info(f"Deleted temporary video file '{video_file.name}' from Gemini.")
            except Exception as del_e:
                app.logger.warning(f"Could not delete temporary Gemini file '{video_file.name}': {del_e}")
