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
    feedback = state.evaluation_feedback
    iteration = state.script_revision_iteration # Default is 0 in dataclass
    current_code = state.current_code

    if render_error:
        mode = "Render Error Revision"
    elif feedback:
        mode = "Evaluation Revision"
    else:
        mode = "Generation"

    app.logger.info(f"--- generate_single_class_script (Mode: {mode}, Iteration: {iteration}) ---")

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
    elif mode == "Evaluation Revision":
        prompt = f"""The previous attempt to generate a single-class Manim script for '{user_concept}' received evaluation feedback. Please revise the entire script according to the feedback.\n\nOriginal Plan:\n{full_plan_description}\n\nFeedback:\n{feedback}\n\nPrevious Code:\n```python\n{current_code or 'No code.'}\n```\nOutput ONLY the revised raw Python code (single Scene class)."""
    else:
        prompt = f"""Generate one single, complete, and runnable Manim Python script containing exactly one class explaining '{user_concept}'. Implement scenes sequentially: {full_plan_description}\nOutput ONLY the raw Python code (single Scene class)."""

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

        return {
            'current_code': full_script_code,
            'full_script_path': script_fp,
            'scene_class_name': scene_class,
            'script_revision_iteration': iteration + (1 if mode != 'Generation' else 0),
            'rendering_error': None,
            'code_eval_verdict': None,
            'error_message': None
        }
    except Exception as e:
        err = f"Error in generate_full_script_node: {e}"
        app.logger.error(err, exc_info=True)
        return {'error_message': err}
