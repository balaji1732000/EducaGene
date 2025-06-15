# Progress: Manim Video Generator

## 1. What Works

- **Core Workflow Execution:** The LangGraph state machine successfully orchestrates the main steps: setup -> plan -> generate script -> evaluate -> render -> generate voiceover -> combine.
- **Concept to Plan:** The `plan_video_node` uses an LLM to generate a structured JSON plan from a user concept. Prompt refined to prefer 2D scenes unless 3D is justified.
- **Plan to Script:** The `generate_full_script_node` takes the plan and generates a single Manim Python script containing one class. Prompt refined to enforce 2D/3D based on plan, add default 3D camera orientation, ensure clean scene transitions (FadeOut), use slightly slower pacing, and **provide specific guidance on handling `MathTex` indexing**.
- **Code Evaluation (Structured JSON):** The `evaluate_script_and_video_node` uses Gemini Vision, **integrates a CV overlap pre-pass (`flag_overlap_frames`)**, and outputs a structured JSON (verdict, metrics, issues list) according to a defined schema. Prompting guides Gemini to use CV data for overlap assessment.
- **Code Revision Loop (Structured Feedback):**
    - **Evaluation-Based:** If evaluation verdict is 'REVISION_NEEDED', the workflow loops back to `generate_full_script_node` with the **structured list of issues** to attempt correction (up to `max_evaluation_revisions`). Prompt updated to consume this structured feedback.
    - **Render-Error-Based:** If `render_combined_video_node` fails, the workflow loops back to `generate_full_script_node` with structured error details or raw error message to attempt correction (up to `max_render_error_revisions`). Prompt updated to handle potentially structured error input.
- **Manim Rendering:** The `render_combined_video_node` executes Manim using the **OpenGL renderer** (`--renderer=opengl`), captures stderr, and attempts to extract structured error details using an LLM helper function upon failure.
- **Voiceover Script Generation:** The `generate_final_script_node` uses Gemini Vision to analyze the rendered silent video and generate a corresponding narration script.
- **TTS Audio Generation:** The `generate_audio_node` uses Azure TTS. **Dynamically selects the appropriate voice** based on the target language using `text_to_speech.json`. **Includes `html.escape()` to prevent SSML errors** from special characters.
- **Final Video Combination:** The `combine_final_video_audio_node` uses ffmpeg to combine the silent video and the generated audio into a final MP4.
- **Basic UI Interaction:** The frontend allows users to input a concept, click "Generate", see a loading state, and view the final video with a download link if successful.
- **Logging:** Comprehensive logging captures workflow steps, LLM calls, Manim output, and errors.
- **Configuration:** API keys and endpoints are loaded from a `.env` file. Voice mappings loaded from `text_to_speech.json`.
- **Docker Setup:** `Dockerfile` and `.dockerignore` created for containerization.

## 2. What's Left to Build / Refine

- **Verify Structured Evaluation:** Test the end-to-end flow with the new structured JSON evaluation and feedback consumption.
- **Verify CV Integration:** Assess if the CV pre-pass data improves overlap detection and revision quality.
- **Verify TTS Fix:** Confirm `html.escape()` prevents SSML errors.
- **Verify Gemini Timeout Fix:** Confirm the increased timeout prevents file processing errors.
- **Test OpenGL Renderer:** Evaluate performance and visual output.
- **Test Docker Deployment:** Build and run the Docker container.
- **"Inspire Me" / "Enhance Script":** Implement UI button functionality.
- **UI Stability/Polish:** Improve error/warning display, refine styling.
- **Error Handling Robustness:** Further improve parsing of LLM JSON outputs (plan, evaluation). Handle edge cases in voice selection. Refine CV parameters if needed.
- **Prompt Optimization:** Continue refining prompts (HARD RULES, helpers, etc.) based on test results.
- **Workflow Edge Cases:** Test with more complex concepts, different languages.
- **Performance Optimization:** Profile workflow.
- **Testing:** Implement unit/integration tests.

## 3. Current Status

- Core end-to-end flow is functional.
- Significant recent work focused on improving backend robustness:
    - Enhanced LLM prompts for code generation (error handling, transitions, pacing).
    - Implemented structured error extraction in the render node.
    - Implemented structured feedback generation in the evaluation node.
    - Implemented dynamic TTS voice selection based on a JSON config file.
    - Switched Manim rendering to use the OpenGL renderer.
    - Updated code generation prompts to improve `MathTex` handling.
    - Set up Docker configuration (`Dockerfile`, `.dockerignore`) for deployment.
- UI remains largely unchanged from the previous overhaul.
- **Deployment:** Actively working on deploying the application using Docker.

## 4. Known Issues

- **LLM Reliability:** Quality/correctness of LLM outputs can vary. JSON parsing might fail if LLM deviates from the requested schema (though less likely now). Content filtering can occur.
- **CV Pre-pass Tuning:** The current CV parameters might still be too sensitive or not sensitive enough for certain videos, potentially generating large JSON files or missing overlaps. Requires ongoing tuning based on results.
- **TTS Voice Availability:** Dynamic voice selection relies on `text_to_speech.json` being present, correctly formatted, and containing a suitable voice for the target locale. Fallback logic exists.
- **Gemini File Processing:** Uploaded videos might still occasionally time out during Gemini processing, even with the increased timeout.
- **Performance:** Generation can still be slow. Effectiveness of OpenGL renderer needs testing.
- **OpenGL Renderer:** May introduce new compatibility issues or visual differences. Requires OpenGL support in the execution environment.
- **UI:** Basic error display, "Inspire Me"/"Enhance Script" not implemented.
