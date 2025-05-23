import os
import re
import json # Import json for parsing structured errors
from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.utils import clean_code_string, fix_inline_latex
from manim_video_generator.llm_client import get_llm_client
from manim_video_generator.state import WorkflowState


def generate_full_script_node(state: WorkflowState) -> Dict[str, Any]:
    """Generates or revises a single Python script based on plan, evaluation feedback, or render error."""
    video_plan = state.video_plan
    raw_plan_text = state.error_message
    user_concept = state.user_concept
    language = state.language # Get target language
    render_error = state.rendering_error # This might be raw text OR a JSON string
    error_search_context = state.error_search_context # Read using the correct state attribute name
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
    app.logger.info(f"--- generate_full_script_node (Mode: {mode}, Iteration: {current_iter}) ---") # Corrected log message

    # --- Prepare History String ---
    history_prompt_addition = ""
    if mode == "Render Error Revision" and state.render_error_history:
        history_prompt_addition = "\n\n## Previous Render Error Attempts for this Request:\n"
        for i, attempt in enumerate(state.render_error_history):
            script_excerpt = attempt.get("script", "")[:150] # Show a snippet
            error_info = attempt.get("error", {})
            if isinstance(error_info, dict): # Structured error
                error_summary = f"Type: {error_info.get('error_details', [{}])[0].get('error_type', 'N/A')}, Message: {error_info.get('error_details', [{}])[0].get('error_message', 'N/A')[:100]}"
            else: # Raw error string
                error_summary = str(error_info)[:150]
            history_prompt_addition += f"- Attempt {i+1} (Script: '{script_excerpt}...'): Led to Error: {error_summary}...\n"
    elif mode == "Evaluation Revision" and state.eval_feedback_history:
        history_prompt_addition = "\n\n## Previous Evaluation Feedback Attempts for this Request:\n"
        for i, attempt in enumerate(state.eval_feedback_history):
            script_excerpt = attempt.get("script", "")[:150]
            feedback_info = attempt.get("feedback", {})
            issues_summary = [f"{issue.get('type', 'N/A')}: {issue.get('description', 'N/A')[:50]}..." for issue in feedback_info.get("issues", [])[:2]] # Summarize first 2 issues
            history_prompt_addition += f"- Attempt {i+1} (Script: '{script_excerpt}...'): Resulted in Feedback: {', '.join(issues_summary) if issues_summary else 'No specific issues listed.'}\n"
    
    if history_prompt_addition:
        app.logger.info(f"Adding history to prompt: {history_prompt_addition}")
    # --- End History String Preparation ---

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

    helper_block_instruction = """Start every script with the helper block shown below; do not change or remove it.
```python
### >>> BEGIN STANDARD HELPERS (inserted by generator) >>>
from manim import *
# Ensure DEGREES and other constants are available if not directly from manim.*
# For example, you might need: from manim.utils.constants import DEGREES, UP, DOWN, LEFT, RIGHT, ORIGIN

def fade_out_all(scene):
    \"\"\"Fade out everything currently on screen.\"\"\"
    if scene.mobjects: # Check if there are mobjects to fade
        scene.play(FadeOut(VGroup(*scene.mobjects)))

def safe_arrange(*mobjects, direction=DOWN, buff=0.4, **kwargs):
    \"\"\"Arrange objects evenly and keep them on‑frame.
    Passes additional kwargs (like 'aligned_edge') to VGroup.arrange().
    Default edge for to_edge is UP if direction is DOWN, and LEFT if direction is RIGHT.
    \"\"\"
    if not mobjects:
        return VGroup() # Return an empty VGroup if no mobjects are provided

    # Determine a sensible default edge for to_edge based on direction
    # This is a simple heuristic and might need adjustment based on common use cases
    default_edge = kwargs.pop('edge', None)
    if default_edge is None:
        if direction is DOWN or direction is UP:
            default_edge = UP
        elif direction is LEFT or direction is RIGHT:
            default_edge = LEFT
        else:
            default_edge = ORIGIN # Fallback for other directions

    arranged_group = VGroup(*mobjects).arrange(direction, buff=buff, **kwargs)
    
    # Check if the group has any mobjects before calling to_edge
    if arranged_group.submobjects:
        return arranged_group.to_edge(default_edge)
    return arranged_group # Return as is if empty after arrange (e.g. all mobjects were None)

### <<< END STANDARD HELPERS <<<
```

"""

    hard_rules = """## HARD RULES – NO EXCEPTIONS
A. START every logical scene (a block of animations fulfilling one part of the plan) by ensuring a clean slate. If a `cleanup` variable is true (assume `cleanup = True` at the start of `construct` unless the plan implies otherwise for a specific scene), fade out all existing mobjects:
       if locals().get("cleanup", True): # Default to True
           fade_out_all(self) # Use the provided helper
B. PLACE mobjects using an arrangement helper to avoid overlaps and ensure they are on-screen. Prefer `safe_arrange()` if suitable, or use `VGroup(obj1, obj2).arrange(DIRECTION, buff=0.3).to_edge(EDGE)`.
C.  NEVER add a new mobject that would significantly overlap with an existing mobject in the same visual space unless the previous one is explicitly part of a combined visual. If replacing, ensure the old one is removed or faded out first. (Visual check: `obj.get_center()` distance < 1 might indicate overlap).
D.  Use `self.wait(max(len(str(text_mobject.text))/12, 1))` after displaying any significant `Text` or `MathTex` object to allow for reading time (approx. 12 chars/sec). Ensure `text_mobject.text` is used to get the string length. For `MathTex`, you might need to estimate based on complexity if `.text` attribute is not directly suitable.

"""

    if mode == "Render Error Revision":
        # Enhanced prompt for Render Error Revision with specific guidance for ImportError/NameError
        prompt = f"""{helper_block_instruction}
{hard_rules}
{history_prompt_addition}

The previous attempt to render the Manim script for **'{user_concept}'** failed with a runtime error. Your task is to meticulously analyze the provided error information (which might be structured JSON or raw text) and **fix the specific error** in the code.

**Original Video Plan (for context only):**
{full_plan_description}

**Rendering Error Information (Analyze this carefully! Could be JSON or raw text):**
```
{render_error}
```

**Potentially Relevant Solution Hints from Web Search (Use these as clues):**
```
{error_search_context if error_search_context else 'No hints found.'}
```

**Previous Script Attempt (contains the error):**
```python
{current_code}
```

**VERY IMPORTANT DEBUGGING INSTRUCTIONS (TARGETING Manim Community v0.19.0):**
(Adhere to HARD RULES above first)
1. **Analyze Error & Hints:**
   - **Error Info:** If the 'Rendering Error Information' looks like JSON, parse it and focus on `error_details`. If it's raw text (traceback), identify the error type and line number.
   - **Hints:** Review the 'Solution Hints' from the web search for potential causes or fixes related to the error. The hints might contain code snippets or explanations.
2. **Targeted Fix:** Based on your analysis of the error and any relevant hints, modify **only the necessary lines** in the 'Previous Script Attempt' to resolve the identified root cause(s). **Prioritize fixes suggested by the hints if they seem relevant.**
   - For `NameError`/`ImportError`/`ModuleNotFoundError`: Check spelling, ensure imports are correct. **Assume Manim Community v0.19.0 import style.** Prefer direct imports (`from manim import Surface`) over submodule imports unless certain. Check hints for specific import issues.
   - Check for Manim v0.19 vs older version differences (e.g., `ShowCreation` is now `Create`). Use hints if available.
   - For `AttributeError`: Correct the attribute/method name or object type based on the error and hints.
   - For `TypeError`/`ValueError`: Adjust arguments passed to functions/methods.
   - For LaTeX Errors: Fix the LaTeX string syntax/escaping (use raw strings `r"..."`).
   - For other errors: Apply the specific fix indicated by the error message and context.
3. **Handling `MathTex` Indexing:** When applying operations like `SurroundingRectangle` to parts of a `MathTex` object created with multiple strings (e.g., `MathTex("a", "+", "b")`), ensure you are indexing correctly to get a valid sub-mobject. `eq[0]` usually works for the first part, `eq[1]` for the second, etc. If surrounding multiple parts, group them explicitly: `VGroup(eq[0], eq[1])`. Incorrect indexing can cause `TypeError`.
4. **Minimal Changes:** Do **not** rewrite large sections of code unless necessary to fix the specific error(s). Preserve the original structure.
5. **Maintain Single Class Structure:** Ensure the script still has exactly **ONE class** (`Scene` or `ThreeDScene`) with all logic in `construct`, and all necessary imports at the top.
6. **CODE ONLY OUTPUT:** Provide the full corrected Python script **with the error(s) fixed**, and nothing else. No explanations or extra text.

Apply the fix(es) and output the corrected code now."""
        next_render_iter = render_iter + 1 # Increment render error counter
        clear_error_field = 'rendering_error'

    elif mode == "Evaluation Revision":
        # Enhanced prompt for Evaluation Revision, focusing on visual fixes including 3D camera and transitions/pacing
        prompt = f"""{helper_block_instruction}
{hard_rules}
{history_prompt_addition}

The Manim script for **'{user_concept}'** rendered successfully, but the resulting video has some **visual issues** noted in the evaluation. **Revise the script** to address these issues without altering the intended content.

**Original Video Plan (for reference to maintain intent):**
{full_plan_description}

**Structured Evaluation Feedback (List of issues to fix in the video):**
```json
{json.dumps(feedback, indent=2)}
```
*(The JSON above provides a list of issues. Each issue has a 'scene_number', 'scene_title', 'type', 'severity', 'description', and a 'suggestion'. Focus on addressing each issue based on its details, particularly the 'description' and 'suggestion'.)*

**Previous Script Attempt (to be revised):**
```python
{current_code}
```

**IMPORTANT REVISION GUIDELINES:**
(Adhere to HARD RULES above first)
1. **Address Each Issue from Structured Feedback:** Iterate through each issue provided in the "Structured Evaluation Feedback" JSON. For each issue:
    - Refer to its `scene_number`, `scene_title`, `type`, `severity`, `description`, and `suggestion`.
    - Apply the `suggestion` if it's actionable. If not, use the `description` and `type` to guide your fix.
    - Examples of how to address common issue `type`s:
        - **"overlap", "off_frame", "layout":** Reposition objects using `.shift()`, `.next_to()`, `.to_edge()`, or an arrangement helper like `safe_arrange(...)` or `VGroup().arrange(...)`. Ensure elements are within the frame.
        - **"lingering_elements":** Ensure clean transitions by using `self.play(FadeOut(...))` or `fade_out_all(self)` to remove *all* necessary elements from the previous logical scene block.
        - **"readability", "contrast", "font_error":** Adjust text size, position, color, or add/correct `font="..."` parameter in `Text()` objects.
        - **"pacing":** Increase animation `run_time` (e.g., `run_time=1.5`) or add more `self.wait(max(len(str(text_obj.text))/12, 1))` calls, especially after `Text` or `MathTex`.
        - **"camera_angle", "camera_movement":** If using `ThreeDScene`, adjust `self.set_camera_orientation(...)`, `self.move_camera(...)`, or ambient rotation settings as per the issue's description and suggestion.
        - **"plan_deviation", "missing_scene_element":** Ensure the visuals align with the original video plan and that all key elements are present.
2. **Plan Consistency:** After addressing specific issues, ensure the visuals still match the original plan's intent and flow.
3. **Handling `MathTex` Indexing:** Index correctly (`eq[0]`, `eq[1]`, etc.) or use `VGroup(eq[0], eq[1])` when applying operations like `SurroundingRectangle` to parts of multi-string `MathTex`.
4. **Preserve Structure & Intent:** Do not remove any part of the content unless it’s causing the issue or is explicitly suggested for removal. Keep the one-class format and overall flow. We are only *improving* the existing script, not reinventing it.
5. **Standard Requirements:** The script must still meet all the requirements from the initial generation (imports, single class, correct use of `Scene` vs `ThreeDScene`, proper LaTeX, etc.). Only change things related to the feedback issues unless you spot an outright error.
6. **LaTeX Check:** Double-check any LaTeX in the code for errors since visual issues can sometimes come from unseen LaTeX problems.
7. **CODE ONLY OUTPUT:** Output the full revised Python script with the improvements. Do not include explanations or any text aside from the code itself.

Make the above adjustments and **provide the updated code** now, ensuring the video issues are resolved."""
        next_eval_iter = eval_iter + 1 # Increment evaluation counter
        # Also reset render error counter when revising based on evaluation
        next_render_iter = 0
        clear_error_field = 'evaluation_feedback'

    else: # Generation mode
        # Enhanced prompt for Generation mode, emphasizing transitions and pacing
        prompt = f"""{helper_block_instruction}
{hard_rules}
Generate **one single, complete, and runnable Manim Python script** containing **exactly ONE class** (e.g., `CombinedScene`) to explain '{user_concept}' in **{language}**.

The video plan consists of the following scenes (provided in {language}, with technical terms/formulas potentially in English), which should be implemented **sequentially within the single `construct` method** of the class:
{full_plan_description}

**VERY IMPORTANT REQUIREMENTS:**
(Adhere to HARD RULES above first)
1.  **Imports:** Start with necessary Manim imports (`from manim import *`). **Assume common classes like Circle, Square, Text, MathTex, ThreeDScene, ParametricSurface, Surface etc. are available directly under `manim` unless you know otherwise for the specific version.**
2.  **SINGLE Class Definition:** Define **exactly ONE Python class**.
    *   Inherit from `ThreeDScene` **only if** the plan explicitly requires 3D objects, 3D transformations, or camera angle changes.
    *   Otherwise, **strictly inherit from `Scene` (2D)**.
3.  **`construct` Method:** Implement all visual steps sequentially. Use comments `# --- Scene [Number]: [Scene Title] ---` for clarity.
    *   **3D Camera Setup (If using `ThreeDScene`):**
        *   **Initial View:** Start with a clear view using `self.set_camera_orientation(phi=..., theta=..., gamma=...)`. Good defaults are often `phi=60*DEGREES, theta=-45*DEGREES, gamma=0`. Adjust `phi` (up/down tilt) and `theta` (left/right rotation) to best show the initial objects.
        *   **Animated Changes:** If a scene description implies showing something from a different perspective (e.g., "rotate to view the back", "zoom in on the detail"), use `self.move_camera(phi=..., theta=..., frame_center=..., zoom=..., run_time=...)` to animate the transition smoothly (e.g., `run_time=2`). Center the camera (`frame_center=object.get_center()`) on the object of interest during the move.
        *   **Ambient Rotation:** For complex, evolving 3D scenes, consider adding subtle continuous rotation with `self.begin_ambient_camera_rotation(rate=0.1, about='theta')` during the main animation, and stop it with `self.stop_ambient_camera_rotation()` before the next static view or scene transition. Use sparingly to avoid distraction.
4.  **Language & Text:** All visible text in **{language}**.
    *   If {language} is not English, **MUST** provide a suitable `font="Font Name"` for each `Text("...")` (e.g., `"Noto Sans JP"` for Japanese). **Do not** set font for English.
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
6.  **Handling `MathTex` Indexing:** When applying operations like `SurroundingRectangle` to parts of a `MathTex` object created with multiple strings (e.g., `MathTex("a", "+", "b")`), ensure you are indexing correctly to get a valid sub-mobject. `eq[0]` usually works for the first part, `eq[1]` for the second, etc. If surrounding multiple parts, group them explicitly: `VGroup(eq[0], eq[1])`. Incorrect indexing can cause `TypeError`. Example:
    ```python
    # Example for prompt: How to correctly surround parts of MathTex
    my_equation = MathTex("a^2", "+", "b^2", "=", "c^2")
    self.play(Write(my_equation))
    # To surround 'a^2', access the first part:
    rect_a_squared = SurroundingRectangle(my_equation[0], buff=0.1)
    self.play(Create(rect_a_squared))
    # To surround multiple parts like 'a^2 + b^2':
    group_to_surround = VGroup(my_equation[0], my_equation[1], my_equation[2])
    rect_lhs = SurroundingRectangle(group_to_surround, buff=0.1)
    self.play(Create(rect_lhs))
    ```
7.  **Positioning & No Overlap:** Carefully position all mobjects so nothing important overlaps or goes off-screen. Use methods like `.to_edge()`, `.shift()`, `.next_to()`, or `.arrange()` as needed to keep elements tidy and within frame. If the plan calls for successive elements in the same place, remove or fade out the previous ones before adding new ones.
8.  **Animation Usage:** Use appropriate Manim animations and transformations for each step (e.g. `Write`, `Create`, `FadeIn`, `Transform`). **Important**: ensure any object you want to transform or fade out is already added to the scene (either by a previous `self.add(...)` or an animation like `Create`) before you call `self.play(Transform(...))` or `self.play(FadeOut(...))`. This prevents runtime errors and makes the animation visible.
9.  **Timing and Pacing:** Use `self.wait()` and `run_time` parameters to control the pace. Give the viewer enough time to read text and see transitions, especially after important animations.
10. **Self-Contained & Error-Free:** The script should run **without any errors**. Include all necessary imports and definitions. Avoid undefined variables or mismatched parentheses.
11. **CODE ONLY OUTPUT:** Your response **must be only** the Python code for the complete script. Do **NOT** include explanations, markdown, or anything outside the code. No comments in the output except those marking scene sections.

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
        # duration = estimate_scene_time(full_script_code)

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
