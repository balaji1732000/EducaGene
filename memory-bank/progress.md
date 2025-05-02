# Progress: Manim Video Generator

## 1. What Works

- **Core Workflow Execution:** The LangGraph state machine successfully orchestrates the main steps: setup -> plan -> generate script -> evaluate -> render -> generate voiceover -> combine.
- **Concept to Plan:** The `plan_video_node` uses an LLM to generate a structured JSON plan from a user concept. Prompt refined to prefer 2D scenes unless 3D is justified.
- **Plan to Script:** The `generate_full_script_node` takes the plan and generates a single Manim Python script containing one class. Prompt refined to enforce 2D/3D based on plan, add default 3D camera orientation, ensure clean scene transitions (FadeOut), and use slightly slower pacing.
- **Code Evaluation:** The `evaluate_script_and_video_node` uses Gemini Vision to review the rendered script/video against the plan and quality criteria (including 3D usage, camera angles, transitions, pacing). Outputs a 'SATISFIED' or 'REVISION_NEEDED' verdict and structured feedback (by scene, with severity) as a JSON string.
- **Code Revision Loop:**
    - **Evaluation-Based:** If evaluation verdict is 'REVISION_NEEDED', the workflow loops back to `generate_full_script_node` with the structured feedback to attempt correction (up to `max_evaluation_revisions`). Prompt updated to handle structured feedback.
    - **Render-Error-Based:** If `render_combined_video_node` fails, the workflow loops back to `generate_full_script_node` with structured error details (extracted by LLM) or raw error message to attempt correction (up to `max_render_error_revisions`). Prompt updated to handle potentially structured error input and includes specific guidance for `ImportError`/`NameError` (e.g., `Surface` vs `ParametricSurface`).
- **Manim Rendering:** The `render_combined_video_node` executes Manim, captures stderr, and attempts to extract structured error details using an LLM helper function (`_extract_structured_error`) upon failure. Includes robust logic for finding the output video file on success.
- **Voiceover Script Generation:** The `generate_final_script_node` uses Gemini Vision to analyze the rendered silent video and generate a corresponding narration script.
- **TTS Audio Generation:** The `generate_audio_node` uses Azure TTS to convert the voiceover script into a WAV audio file. **Dynamically selects the appropriate voice** based on the target language using `text_to_speech.json`. Includes improved error logging.
- **Final Video Combination:** The `combine_final_video_audio_node` uses ffmpeg to combine the silent video and the generated audio into a final MP4.
- **Basic UI Interaction:** The frontend allows users to input a concept, click "Generate", see a loading state, and view the final video with a download link if successful.
- **Logging:** Comprehensive logging captures workflow steps, LLM calls, Manim output, and errors.
- **Configuration:** API keys and endpoints are loaded from a `.env` file. Voice mappings loaded from `text_to_speech.json`.

## 2. What's Left to Build / Refine

- **Verify Recent Changes:** Thoroughly test the dynamic voice selection, structured error extraction, enhanced evaluation feedback, and improved script generation prompts (transitions, pacing, error handling).
- **"Inspire Me" / "Enhance Script":** Implement UI button functionality.
- **UI Stability/Polish:** Improve error/warning display, refine styling.
- **Error Handling Robustness:** Improve parsing of LLM JSON outputs (plan, evaluation, structured error). Handle edge cases in voice selection (missing locales/files).
- **Prompt Optimization:** Continue refining prompts based on test results.
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
- UI remains largely unchanged from the previous overhaul.

## 4. Known Issues

- **LLM Reliability:** Quality/correctness of LLM outputs can vary. JSON parsing might fail if LLM deviates from requested format. Content filtering can occur.
- **TTS Voice Availability:** Dynamic voice selection relies on `text_to_speech.json` being present, correctly formatted, and containing a suitable voice for the target locale. Fallback logic exists but might not always be ideal.
- **Structured Error Extraction:** The LLM call within `render_combined_video` to extract structured errors might fail or return poor results, causing the revision node to receive raw stderr instead.
- **Performance:** Generation can still be slow.
- **UI:** Basic error display, "Inspire Me"/"Enhance Script" not implemented.
