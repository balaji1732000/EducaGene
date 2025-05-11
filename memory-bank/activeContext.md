# Active Context: Manim Video Generator

## 1. Current Work Focus

- **Structured Evaluation Integration:** Implementing and refining the structured JSON output from the `evaluate_script_and_video_node` and ensuring the `generate_full_script_node` correctly consumes this structured feedback for revisions.
- **CV Overlap Detection:** Integrating a Computer Vision pre-pass (`flag_overlap_frames` in `utils.py`) into the evaluation node to provide concrete overlap evidence to the Gemini Vision model. Tuning CV parameters (`iou_thr`, `sample_rate`, `min_contour_area`) and summarizing results (top 3 overlaps per frame) to manage data volume.
- **Workflow Robustness:** Continuing to improve error handling and reliability across the workflow nodes (e.g., TTS SSML escaping, Gemini API call fixes, Gemini file processing timeout).
- **Testing & Verification:** Testing the end-to-end flow with the new structured evaluation and CV pre-pass to ensure improvements in revision quality and robustness.
- **Prompt Engineering:** Continuing refinement of prompts for `generate_full_script` (including HARD RULES) and `evaluate_script_and_video` (JSON schema adherence).
- **Docker Deployment:** Ongoing setup and configuration.

## 2. Recent Changes

- **Error Handling:**
    - Updated the "Render Error Revision" prompt in `generate_full_script.py` with stricter guidance on analyzing tracebacks and fixing specific errors, including hints for common `ImportError` issues (e.g., `ParametricSurface` vs `Surface`, trying direct `manim` imports).
    - Attempted to integrate structured error extraction (using LLM/Pydantic) into `render_combined_video.py` but reverted due to complexity/user preference.
- **Evaluation:**
    - Updated the "Render Error Revision" prompt in `generate_full_script.py` with stricter guidance on analyzing tracebacks and fixing specific errors.
    - Fixed Azure TTS SSML error in `generate_audio_node` by adding `html.escape()` for the script text.
    - Fixed `AttributeError` and `TypeError` in `evaluate_script_and_video_node` related to Gemini API calls (`generation_config` access and `content` vs `contents` parameter).
    - Increased Gemini file processing timeout in `utils.py` (`wait_for_files_active`) from 300s to 600s.
- **Evaluation & Structured Data:**
    - Implemented CV overlap pre-pass (`flag_overlap_frames` in `utils.py`) with parameter tuning and result summarization (top 3 per frame). Moved function from `cv_flags.py` to `utils.py`.
    - Updated `evaluate_script_and_video_node` to run CV pre-pass, include results in the prompt, and require structured JSON output (Schema 2: verdict, metrics, issues list) from Gemini.
    - Updated `state.py` (`evaluation_feedback` type hint) to store the structured list of issues.
    - Updated `generate_full_script_node` ("Evaluation Revision" mode) to consume the structured list of issues from the state.
    - Created `test_gemini_structured_output.py` to verify JSON generation.
- **TTS:**
    - Updated `generate_audio.py` to dynamically load voice mappings from `text_to_speech.json` and select the appropriate voice based on the target locale, with fallbacks.
    - Added more detailed error logging to `generate_audio.py`.
- **Prompt Engineering:**
    - Added standard helper functions (`fade_out_all`, `safe_arrange`) to the `generate_full_script_node` prompt via `helper_block_instruction`.
    - Added "HARD RULES" section to `generate_full_script_node` prompts (scene cleanup, arrangement helpers, overlap prevention, text pacing).
    - Updated prompts in `generate_full_script.py` for `MathTex` indexing.
    - Updated prompts in `evaluate_script_and_video.py` for stricter 3D camera checks.
- **Docker:** Created/updated `Dockerfile` and `.dockerignore`.
- **Rendering:** Modified `render_combined_video.py` to use Manim's OpenGL renderer.

## 3. Next Steps

- **Test End-to-End Structured Evaluation:** Run the full workflow to ensure the structured JSON evaluation works correctly:
    - Verify `evaluate_script_and_video_node` produces valid JSON according to the schema.
    - Verify `generate_full_script_node` correctly interprets and acts upon the structured `issues` list during revisions.
- **Test CV Integration Impact:** Assess if providing the CV overlap data improves Gemini's overlap detection and the resulting script revisions.
- **Refine CV Parameters:** If the CV output is still too noisy or misses important overlaps, further tune `iou_thr`, `sample_rate`, `contour_threshold`, and `min_contour_area` in `evaluate_script_and_video_node`.
- **Verify TTS Fix:** Confirm that the `html.escape()` change prevents the SSML error for scripts containing special characters like '&'.
- **Verify Gemini Timeout Fix:** Confirm that increasing the timeout in `wait_for_files_active` resolves the file processing timeout error.
- **Review Overall Quality:** Assess the quality of generated videos considering all recent changes (structured eval, CV flags, prompt rules, TTS fix, etc.).
- **Test Docker Deployment:** Build the Docker image and run the container.

## 4. Active Decisions & Considerations

- **Evaluation Output:** Committed to using the structured JSON output (Schema 2) from `evaluate_script_and_video_node`.
- **CV Pre-pass:** Integrated the CV pre-pass as an input to the evaluation LLM, using parameter tuning and summarization (top 3) to manage data volume. Further tuning might be needed based on testing.
- **Error Handling:** Preferring programmatic fixes (like `html.escape`) over relying solely on prompt tuning for strict formatting requirements (like SSML). Relying on LLM prompting for code error correction, enhanced by structured error info and web search context. Increased Gemini file processing timeout.
- **Voice Selection:** Using a JSON file (`text_to_speech.json`) for dynamic voice mapping.
- **Deployment Strategy:** Actively pursuing Docker containerization.
- **Rendering Strategy:** Using Manim's OpenGL renderer.
