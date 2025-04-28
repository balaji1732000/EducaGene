import os
import re
from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.utils import clean_code_string, fix_inline_latex, estimate_scene_time
from manim_video_generator.llm_client import get_llm_client
from manim_video_generator.state import WorkflowState


def generate_full_script_node(state: WorkflowState) -> Dict[str, Any]:
    """Generates or revises a single Python script based on plan, evaluation feedback, or render error."""
    video_plan = state.video_plan
    raw_plan_text = state.error_message
    user_concept = state.user_concept # 'user_concept' is required, default in get() was likely unnecessary
    render_error = state.rendering_error
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
    if mode == "Render Error Revision":
        prompt = f"""The previous attempt to render the Manim script for '{user_concept}' failed with a runtime error. Please revise the script to fix the specific error reported below.\n\nOriginal Plan:\n{full_plan_description}\n\nError:\n{render_error or 'No error provided.'}\n\nPrevious Code:\n```python\n{current_code or 'No code.'}\n```\nOutput ONLY the corrected raw Python code (single Scene class within construct)."""
    # Compose prompt based on mode (Original Prompts from main_final.py logic)
    clear_error_field = None
    # Initialize next iteration counts
    next_render_iter = render_iter
    next_eval_iter = eval_iter

    if mode == "Render Error Revision":
        prompt = f"""The previous attempt to render the Manim script for '{user_concept}' failed with a runtime error. Please revise the script to fix the **specific error** reported below.

**Original Video Plan (for context):**
{full_plan_description}

**Rendering Error Message (Focus on this):**
```
{render_error if render_error else "No specific error message provided."}
```

**Previous Script Attempt (Single Class, to fix):**
```python
{current_code or "No previous code available."}
```

**VERY IMPORTANT INSTRUCTIONS:**
1.  **Analyze & Fix Specific Error:** Focus on fixing the root cause identified in the 'Rendering Error Message'. Common issues include:
    *   **LaTeX Errors:** Check all `MathTex` and `Tex` objects. Ensure correct syntax, proper escaping of special characters (\\, {{, }}, %, &, #, _), or use Python raw strings (r"..."). Mismatched braces are common.
    *   **NameError/AttributeError:** Ensure all variables and Manim objects are defined before use and spelled correctly.
    *   **TypeError:** Check that arguments passed to methods have the correct type.
    *   **Object Not Added:** Ensure `self.add(...)` is called for an object *before* it's used in `self.play()` animations like `Transform` or `FadeOut`.
2.  **Maintain Goals & SINGLE Class Structure:** The corrected script must still implement the 'Original Video Plan' sequentially within the single class's `construct` method.
3.  **Requirements:** Script must have necessary imports, **ONE single class**, one `construct(self)` method.
4.  **Positioning:** Ensure elements are placed within the 16:9 frame and avoid overlaps. Use `.to_edge()`, `.shift()`, `.next_to()`, `.arrange()` etc.
5.  **CODE ONLY OUTPUT:** Your *entire response* must be **ONLY** the raw Python code for the complete, corrected script. No explanations, comments outside code, greetings, or markdown fences.

Fix the script based **specifically on the render error message** provided."""
        next_render_iter = render_iter + 1 # Increment render error counter
        clear_error_field = 'rendering_error'

    elif mode == "Evaluation Revision":
        # This prompt now handles combined code/video feedback
        prompt = f"""The previous attempt to generate a **single-class** Manim script for '{user_concept}' received evaluation feedback based on both the code and the rendered video. Please revise the entire script according to the feedback.

**Original Video Plan (Multiple Scenes):**
{full_plan_description}

**Evaluation Feedback (Includes Code & Visual Issues):**
```
{feedback}
```

**Previous Script Attempt (Single Class, to revise):**
```python
{current_code or "No previous code available."}
```

**VERY IMPORTANT INSTRUCTIONS:**
1.  **Address Feedback:** Modify the 'Previous Script Attempt' to specifically address all points raised in the 'Evaluation Feedback'. This feedback might include issues found by analyzing the rendered video (like overlaps, timing) or potential code errors.
2.  **Maintain Goals & SINGLE Class Structure:** Ensure the revised script *still* accurately implements the 'Original Video Plan' sequentially within the **single class's `construct` method**. Use comments like `# --- Scene [Number] Start: [Title] ---` to mark sections.
3.  **Requirements:** Script must have imports, **ONE single class**, one `construct(self)` method.
4.  **Positioning:** Ensure elements are placed within the 16:9 frame and avoid overlaps. Use `.to_edge()`, `.shift()`, `.next_to()`, `.arrange()` etc.
5.  **LaTeX Safety:** Double-check any LaTeX for potential errors (escaping, syntax).
6.  **CODE ONLY OUTPUT:** Your *entire response* must be **ONLY** the raw Python code for the complete, revised script. No explanations, comments outside code, greetings, or markdown fences.

Revise the single-class script now based on the combined evaluation feedback."""
        next_eval_iter = eval_iter + 1 # Increment evaluation counter
        # Also reset render error counter when revising based on evaluation
        next_render_iter = 0
        clear_error_field = 'evaluation_feedback'

    else: # Generation mode
        prompt = f"""Generate **one single, complete, and runnable Manim Python script** containing **exactly ONE class** (e.g., `CombinedScene`) to explain '{user_concept}'.

The video plan consists of the following scenes, which should be implemented **sequentially within the single `construct` method** of the class:
{full_plan_description}

**VERY IMPORTANT REQUIREMENTS:**
1.  **Imports:** Start with necessary Manim imports (`from manim import *`).
2.  **SINGLE Class Definition:** Define **exactly ONE Python class**.
    *   Inherit from `ThreeDScene` if the plan descriptions mention 3D elements or explicitly state the need for 3D.
    *   Otherwise, inherit from `Scene`.
3.  **`construct` Method:** Implement all visual steps from the plan sequentially within the single `construct(self)` method. Use comments like `# --- Scene [Number] Start: [Scene Title] ---` to delineate logical scene blocks.
4.  **LaTeX Handling:** Be very careful with LaTeX in `MathTex` and `Tex`. Use raw strings (r"...") or double backslashes (\\) for escaping where needed. Ensure correct math syntax (e.g., use `\text{{...}}` for plain text within math).
5.  **Positioning & Clarity:** Position elements thoughtfully within the 16:9 frame using `.to_edge()`, `.shift()`, `.next_to()`, `.arrange()` etc. Avoid overlaps. Ensure text is readable.
6.  **Animation Logic:** Use Manim objects (`MathTex`, `Text`, Shapes, etc.) and animations (`self.play`, `Create`, `Write`, `Transform`, etc.). **Crucially, ensure `self.add(object)` is called before animating it with `self.play(Transform(object, ...))` or `self.play(FadeOut(object))` if it wasn't already added via `Create` or `Write`.**
7.  **Wait Times:** Use `self.wait(...)` appropriately between logical steps and scenes to control pacing.
8.  **Self-Contained & Runnable:** The script must run without errors.
9.  **CODE ONLY OUTPUT:** Your *entire response* must be **ONLY** the raw Python code for the complete script. **DO NOT** include *any* explanations, comments outside the code, greetings, summaries, or markdown fences.

Generate the single-class script now, paying close attention to LaTeX, positioning, and animation logic."""
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
