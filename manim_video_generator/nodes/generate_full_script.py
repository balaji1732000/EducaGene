import os
import re
import json # Import json for parsing structured errors
from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.utils import clean_code_string, fix_inline_latex, estimate_scene_time
from manim_video_generator.llm_client import get_llm_client
from manim_video_generator.state import WorkflowState


def generate_full_script_node(state: WorkflowState) -> Dict[str, Any]:
    """Generates or revises a single Python script based on plan, evaluation feedback, or render error."""
    video_plan = state.video_plan
    raw_plan_text = state.error_message
    user_concept = state.user_concept
    language = state.language # Get target language
    render_error = state.rendering_error # This might be raw text OR a JSON string
    feedback = state.evaluation_feedback # Consolidated feedback
    # Read separate iteration counters
    render_iter = state.render_error_iteration
    eval_iter = state.evaluation_revision_iteration
    current_code = state.current_code

    # Determine mode: Render Error > Evaluation Feedback > Generation
    if render_error:
        mode = "Render Error Revision"
    elif feedback: # Feedback from combined evaluation node
        mode = "Evaluation Revision"
    else: # Generation mode
        mode = "Generation"

    # Log using appropriate iteration counter for the current mode
    current_iter = render_iter if mode == "Render Error Revision" else eval_iter if mode == "Evaluation Revision" else 0
    app.logger.info(f"--- generate_single_class_script (Mode: {mode}, Iteration: {current_iter}) ---")

    # Build full_plan_description
    full_plan_description = ""
    if video_plan:
        scenes_prompt_parts = []
        for i, scene in enumerate(video_plan):
            scenes_prompt_parts.append(f"""
---
Scene {i+1}: {scene.get('title', 'N/A')}
Description: {scene.get('description', 'N/A')}
---""")
        full_plan_description = "\n".join(scenes_prompt_parts)
    elif raw_plan_text and isinstance(raw_plan_text, str) and not raw_plan_text.startswith("Failed to parse") and not raw_plan_text.startswith("An unexpected error"):
        app.logger.warning("Video plan parsing failed. Using raw text as plan description.")
        full_plan_description = raw_plan_text
    else:
        err = "generate_full_script_node: video_plan is missing, and no usable raw plan text found in error_message."
        app.logger.error(err)
        return {"error_message": err}

    # Compose prompt based on mode
    clear_error_field = None
    # Initialize next iteration counts
    next_render_iter = render_iter
    next_eval_iter = eval_iter

    if mode == "Render Error Revision":
        # Enhanced prompt for Render Error Revision with specific guidance for ImportError/NameError
        prompt = f"""The previous attempt to render the Manim script for **'{user_concept}'** failed with a runtime error. Your task is to meticulously analyze the provided error information (which might be structured JSON or raw text) and **fix the specific error** in the code.

**Original Video Plan (for context only):**
{full_plan_description}

**Rendering Error Information (Analyze this carefully! Could be JSON or raw text):**
```
{render_error}
```

**Previous Script Attempt (contains the error):**
```python
{current_code}
```

**VERY IMPORTANT DEBUGGING INSTRUCTIONS:**
1. **Analyze Error:**
   - **If the 'Rendering Error Information' looks like JSON:** Parse it. Focus on the `error_details` list. For each error object, use the `error_type`, `error_message`, `line_number`, and `context` to understand the root cause.
   - **If it's raw text (traceback):** Read the traceback carefully. Identify the exact error type and the specific line number where it occurred in the 'Previous Script Attempt'.
2. **Targeted Fix:** Based on your analysis (JSON or raw text), modify **only the necessary lines** in the 'Previous Script Attempt' to resolve the identified root cause(s).
   - For `NameError`/`ImportError`/`ModuleNotFoundError`: Check spelling, ensure imports are correct. **Crucially, for common Manim classes (like `Circle`, `Square`, `Text`, `MathTex`, `ThreeDScene`, `Surface`, etc.), the import path often changes between Manim versions. STRONGLY PREFER importing directly from the main `manim` package first (e.g., `from manim import Surface`). Note that `ParametricSurface` might now be called `Surface` in recent versions.** Only try specific submodules (like `manim.mobject.three_d`) if the direct import fails or if you are certain it's correct for the specific Manim version (assume v0.18+).
   - Check for Manim v0.18/v0.19 vs older version differences (e.g., `ShowCreation` is now `Create`).
   - For `AttributeError`: Correct the attribute/method name or object type. Check the Manim documentation if unsure about available methods.
   - For `TypeError`/`ValueError`: Adjust arguments passed to functions/methods.
   - For LaTeX Errors: Fix the LaTeX string syntax/escaping (use raw strings `r"..."`).
   - For other errors: Apply the specific fix indicated by the error message and context.
3. **Minimal Changes:** Do **not** rewrite large sections of code unless necessary to fix the specific error(s). Preserve the original structure.
4. **Maintain Single Class Structure:** Ensure the script still has exactly **ONE class** (`Scene` or `ThreeDScene`) with all logic in `construct`, and all necessary imports at the top.
5. **CODE ONLY OUTPUT:** Provide the full corrected Python script **with the error(s) fixed**, and nothing else. No explanations or extra text.

Apply the fix(es) and output the corrected code now."""
        next_render_iter = render_iter + 1 # Increment render error counter
        clear_error_field = 'rendering_error'

    elif mode == "Evaluation Revision":
        # Enhanced prompt for Evaluation Revision, focusing on visual fixes including 3D camera and transitions/pacing
        prompt = f"""The Manim script for **'{user_concept}'** rendered successfully, but the resulting video has some **visual issues** noted in the evaluation. **Revise the script** to address these issues without altering the intended content.

**Original Video Plan (for reference to maintain intent):**
{full_plan_description}

**Evaluation Feedback (problems to fix in the video):**
```
{feedback}
```
*(The feedback above describes what looked wrong in the video — e.g. overlapping text, elements off-screen, pacing too fast, lingering elements from previous scenes, or 3D view issues — possibly with pointers to segments of code.)*

**Previous Script Attempt (to be revised):**
```python
{current_code}
```

**IMPORTANT REVISION GUIDELINES:**
1. **Fix Noted Visual Issues:** For each issue mentioned in the feedback, modify the code to resolve it:
   - **Overlaps/Clutter/Framing:** If objects overlap, clutter the scene, or go off-frame, reposition them using `.shift()`, `.next_to()`, `.to_edge()`, or `VGroup().arrange(...)`.
   - **Scene Transitions [STRICT]:** If the feedback mentions lingering elements from a previous scene causing overlap, **ensure all relevant Mobjects from the previous logical scene block are removed** using `self.play(FadeOut(obj1, obj2, ...))` **before** starting the next scene's animations. Be thorough in identifying all elements that should be removed for a clean transition.
   - **Text Readability:** Ensure text is large enough, well-positioned, and contrasts with the background. If feedback mentions □□□ boxes, add the correct `font="..."` parameter to the `Text` object.
   - **Pacing/Timing [STRICT]:** If feedback indicates rushed pacing, **increase animation `run_time`** (e.g., `run_time=1.5` or `run_time=2`) and **add more `self.wait(1)` or `self.wait(1.5)` calls** between distinct steps and especially between scene transitions to allow viewers to process the information.
   - **3D Camera Angles:** If using `ThreeDScene` and feedback mentions poor angles, adjust `self.set_camera_orientation(phi=..., theta=...)` for better readability (e.g., `phi=60*DEGREES, theta=-45*DEGREES`).
   - **Plan Consistency:** Ensure the visuals still follow the sequence and intent of the original plan after your changes.
2. **Use Feedback Hints:** If the feedback included specific code pointers or suggested changes, incorporate those precisely (e.g. “Text at line 45 overlaps” -> move or size the text at that line).
3. **Preserve Structure & Intent:** Do not remove any part of the content unless it’s causing the issue. Keep the one-class format and overall flow. We are only *improving* the existing script, not reinventing it.
4. **Standard Requirements:** The script must still meet all the requirements from the initial generation (imports, single class, correct use of `Scene` vs `ThreeDScene`, proper LaTeX, etc.). Only change things related to the feedback issues unless you spot an outright error.
5. **LaTeX Check:** Double-check any LaTeX in the code for errors since visual issues can sometimes come from unseen LaTeX problems.
6. **CODE ONLY OUTPUT:** Output the full revised Python script with the improvements. Do not include explanations or any text aside from the code itself.

Make the above adjustments and **provide the updated code** now, ensuring the video issues are resolved."""
        next_eval_iter = eval_iter + 1 # Increment evaluation counter
        # Also reset render error counter when revising based on evaluation
        next_render_iter = 0
        clear_error_field = 'evaluation_feedback'

    else: # Generation mode
        # Enhanced prompt for Generation mode, emphasizing transitions and pacing
        prompt = f"""Generate **one single, complete, and runnable Manim Python script** containing **exactly ONE class** (e.g., `CombinedScene`) to explain '{user_concept}' in **{language}**.

The video plan consists of the following scenes (provided in {language}, with technical terms/formulas potentially in English), which should be implemented **sequentially within the single `construct` method** of the class:
{full_plan_description}

**VERY IMPORTANT REQUIREMENTS:**
1.  **Imports:** Start with necessary Manim imports (`from manim import *`). **Assume common classes like Circle, Square, Text, MathTex, ThreeDScene, ParametricSurface, Surface etc. are available directly under `manim` unless you know otherwise for the specific version.**
2.  **SINGLE Class Definition:** Define **exactly ONE Python class**.
    *   Inherit from `ThreeDScene` **only if** the plan explicitly requires 3D animations or camera movement.
    *   Otherwise, **strictly inherit from `Scene` (2D)**.
3.  **`construct` Method:** Implement all visual steps from the plan sequentially within the single `construct(self)` method. Use comments like `# --- Scene [Number]: [Scene Title] ---` to separate sections for each scene from the plan (for clarity).
    *   **If using `ThreeDScene`:** set a good camera angle at the start of construct (e.g. `self.set_camera_orientation(phi=75*DEGREES, theta=-30*DEGREES)` or similar) so 3D objects are clearly visible.
4.  **Language & Text:** All visible text should be in **{language}** (the target audience’s language).
    *   If {language} is not English, you **MUST** provide a suitable `font="Font Name"` for each `Text("...")` to ensure the characters render (e.g. Noto Sans fonts for non-Latin scripts). **Do not** set a font for English text.
    **IMPORTANT:** If `{language}` is NOT English ('en-US', 'en-GB', etc.), you **MUST** specify an appropriate `font` parameter within the `Text(...)` object to ensure correct rendering. Examples:
        *   For Hindi ('hi-IN'): `Text("...", font="Noto Sans Devanagari")`
        *   For Tamil ('ta-IN'): `Text("...", font="Noto Sans Tamil")`
        *   For Japanese ('ja-JP'): `Text("...", font="Noto Sans JP")`
        *   For Chinese ('zh-CN'): `Text("...", font="Noto Sans SC")`
        *   For Arabic ('ar-SA'): `Text("...", font="Noto Sans Arabic")`
        *   For Korean ('ko-KR'): `Text("...", font="Noto Sans KR")`
        *   For Thai ('th-TH'): `Text("...", font="Noto Sans Thai")`
        *   For Vietnamese ('vi-VN'): `Text("...", font="Noto Sans Vietnamese")`
        for other languages, use the appropriate Noto Sans font for that language.
    *   Keep technical terms, code, or math formulae in English if we can’t translate them well (e.g., `MathTex`, `a^2+b^2=c^2`).
5.  **LaTeX and Math:** Use raw strings (prefix `r` or double backslashes) for any LaTeX in `Tex`/`MathTex` to avoid errors. Check that any LaTeX is valid and properly formatted (e.g., use `\text{{}}` for non-math text in equations).
6.  **Positioning & No Overlap:** Carefully position all mobjects so nothing important overlaps or goes off-screen (the 16:9 frame). Use methods like `.to_edge()`, `.shift()`, `.next_to()`, or `.arrange()` as needed to keep elements tidy and within frame. If the plan calls for successive elements in the same place, remove or fade out the previous ones before adding new ones.
7.  **Animation Usage:** Use appropriate Manim animations and transformations for each step (e.g. `Write`, `Create`, `FadeIn`, `Transform`). **Important**: ensure any object you want to transform or fade out is already added to the scene (either by a previous `self.add(...)` or an animation like `Create`) before you call `self.play(Transform(...))` or `self.play(FadeOut(...))`. This prevents runtime errors and makes the animation visible.
8.  **Timing and Pacing:** Use `self.wait()` and `run_time` parameters to control the pace. Give the viewer enough time to read text and see transitions, especially after important animations.
9.  **Self-Contained & Error-Free:** The script should run **without any errors**. Include all necessary imports and definitions. Avoid undefined variables or mismatched parentheses.
10. **CODE ONLY OUTPUT:** Your response **must be only** the Python code for the complete script. Do **NOT** include explanations, markdown, or anything outside the code. No comments in the output except those marking scene sections.

Now, **generate the Python code** for the single-class Manim scene based on the plan above, following all requirements.
Generate the single-class script now in **{language}** (except for code/math terms), paying close attention to LaTeX, positioning, 3D usage, camera angles, and animation logic."""
        # Reset both counters for initial generation
        next_render_iter = 0
        next_eval_iter = 0
        clear_error_field = None

    try:
        messages = [
            {'role': 'system', 'content': 'You are a senior Manim developer. Output ONLY raw Python code.'},
            {'role': 'user', 'content': prompt}
        ]
        llm = get_llm_client()
        response = llm.invoke(messages)
        full_script_code = clean_code_string(response.content)

        # Save script to file
        script_fp = os.path.join(state.temp_dir, 'scripts', f"combined_script_{state.request_id}.py")
        os.makedirs(os.path.dirname(script_fp), exist_ok=True)
        with open(script_fp, 'w', encoding='utf-8') as f:
            f.write(full_script_code)
        app.logger.info(f"Saved script to {script_fp}")

        # Postprocess: inline LaTeX & estimate duration
        full_script_code = fix_inline_latex(full_script_code)
        duration = estimate_scene_time(full_script_code)

        # Extract class name
        matches = re.findall(r"class\s+(\w+)\s*\(\s*(?:manim\.)?(?:Scene|ThreeDScene)\s*\)", full_script_code)
        scene_class = matches[0] if len(matches) == 1 else None

        # Prepare the return dictionary
        return_dict = {
            'current_code': full_script_code,
            'full_script_path': script_fp,
            'scene_class_name': scene_class,
            'render_error_iteration': next_render_iter, # Use the correctly calculated next render iteration
            'evaluation_revision_iteration': next_eval_iter, # Use the correctly calculated next eval iteration
            'code_eval_verdict': None, # Clear verdict before next eval/render
            'error_message': None # Clear general error
        }

        # Clear the specific error/feedback field that triggered this revision
        if clear_error_field:
            return_dict[clear_error_field] = None
        else: # Ensure fields are None if not cleared specifically (handles Generation mode)
             return_dict['rendering_error'] = None
             return_dict['evaluation_feedback'] = None

        return return_dict
    except Exception as e:
        err = f"Error in generate_full_script_node: {e}"
        app.logger.error(err, exc_info=True)
        return {'error_message': err}
