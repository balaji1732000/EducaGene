# Active Context: Manim Video Generator

## 1. Current Work Focus

- **Workflow Robustness:** Improving the backend LangGraph workflow's ability to handle errors and produce higher-quality output.
- **Error Handling:** Enhancing the error handling mechanisms, particularly for Manim rendering errors (`ImportError`, `NameError`, etc.) and Azure TTS failures.
- **Prompt Engineering:** Refining prompts for LLM nodes (`generate_full_script`, `evaluate_script_and_video`) to improve code quality, visual output (e.g., scene transitions, pacing, 3D camera angles), and error correction effectiveness.
- **TTS Voice Selection:** Implementing dynamic voice selection for Azure TTS based on the target language using a configuration file (`text_to_speech.json`).

## 2. Recent Changes

- **Error Handling:**
    - Updated the "Render Error Revision" prompt in `generate_full_script.py` with stricter guidance on analyzing tracebacks and fixing specific errors, including hints for common `ImportError` issues (e.g., `ParametricSurface` vs `Surface`, trying direct `manim` imports).
    - Attempted to integrate structured error extraction (using LLM/Pydantic) into `render_combined_video.py` but reverted due to complexity/user preference.
- **Evaluation:**
    - Updated the `evaluate_script_and_video.py` prompt to require more structured feedback (by scene, with severity) within the feedback string.
    - Added stricter evaluation checks for scene transitions (requiring `FadeOut`) and pacing (`run_time`, `wait()`).
- **TTS:**
    - Updated `generate_audio.py` to dynamically load voice mappings from `text_to_speech.json` and select the appropriate voice based on the target locale, with fallbacks.
    - Added more detailed error logging to `generate_audio.py` to capture Azure cancellation details.
    - Created `test_voice_lookup.py` to isolate and debug the voice selection logic. Fixed path issues in the test script.
- **Dependencies:** Added and then removed `pydantic` from `requirements.txt` based on changes in error handling approach. Re-added `pydantic` when implementing structured error extraction in `render_combined_video.py`. *(Self-correction: Pydantic was added back for the structured error extraction within the render node)*.

## 3. Next Steps

- **Verify Dynamic Voice Selection:** Confirm that the `generate_audio_node` now correctly selects and uses the appropriate voice based on the target language and the `text_to_speech.json` file. Run the test script `test_voice_lookup.py` to ensure the lookup logic is correct.
- **Test Enhanced Error Handling:** Run workflows that are likely to produce render errors (e.g., using concepts requiring specific imports like `Surface`) to see if the enhanced "Render Error Revision" prompt leads to successful fixes.
- **Test Enhanced Evaluation:** Run workflows and check if the evaluation feedback is now more structured (by scene, with severity) and if it correctly flags issues related to scene transitions and pacing.
- **Review Overall Quality:** Assess the quality of generated videos considering the recent prompt changes for transitions, pacing, and 3D angles.

## 4. Active Decisions & Considerations

- **Error Handling Strategy:** Currently relying on enhanced LLM prompting for error correction within `generate_full_script.py`. Decided against adding external search tools (Tavily) or separate error processing nodes for now due to complexity.
- **Structured Error Info:** Implemented structured error extraction using an LLM call within `render_combined_video.py` to provide better context to the revision LLM.
- **Voice Selection:** Using a JSON file (`text_to_speech.json`) for dynamic voice mapping is preferred over hardcoding. Need to ensure the file path logic is correct in both the test script and the main node.
