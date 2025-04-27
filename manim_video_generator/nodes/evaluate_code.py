import re
from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.llm_client import get_llm_client
from manim_video_generator.state import WorkflowState


def evaluate_code_node(state: WorkflowState) -> Dict[str, Any]:
    """Evaluates the single-class script against the video plan."""
    video_plan = state.video_plan
    script_code = state.current_code or ''
    iteration = state.script_revision_iteration

    app.logger.info(f"--- evaluate_single_class_script (Revision Iteration: {iteration}) ---")

    if not video_plan:
        return {"error_message": "evaluate_code_node: video_plan is missing."}
    if not script_code:
        return {"error_message": "evaluate_code_node: script_code is missing."}

    # Construct plan description
    scenes = [f"- Scene {sc.get('scene_num','N/A')} ({sc.get('title','N/A')}): {sc.get('description','N/A')}" for sc in video_plan]
    full_plan_description = "\n".join(scenes)

    prompt = f"""Please evaluate the following Manim Python script, which should contain **one single class** whose `construct` method implements multiple logical scenes sequentially, based on the provided video plan.\n\n**Video Plan (Logical Scenes):**\n{full_plan_description}\n\n**Generated Script:**\n```python\n{script_code}\n```\n\n**Evaluation Checklist & Focus Areas:**\n1. Single Class?\n2. Necessary imports?\n3. Plan adherence?\n4. Potential runtime errors (LaTeX, positioning, animation logic)?\n5. Visual quality?\n6. Timing/Pacing?\n7. Content accuracy?\n\n**Provide brief feedback and end with only a verdict line:**\n'Verdict: SATISFIED' or 'Verdict: REVISION_NEEDED'"""

    messages = [
        {'role': 'system', 'content': 'You are a Manim code reviewer. End with only the verdict line.'},
        {'role': 'user', 'content': prompt}
    ]

    try:
        llm = get_llm_client()
        resp = llm.invoke(messages).content.strip()
        lines = resp.splitlines()
        verdict = 'REVISION_NEEDED'
        feedback = '\n'.join(lines[:-1]) if lines and lines[-1].startswith('Verdict:') else resp
        if lines and lines[-1].startswith('Verdict:') and lines[-1].split(':',1)[1].strip() in ('SATISFIED','REVISION_NEEDED'):
            verdict = lines[-1].split(':',1)[1].strip()
        # Scene cleanup guard
        if verdict == 'SATISFIED':
            blocks = re.split(r"(?=# --- Scene \d+ Start)", script_code)
            for b in blocks[1:]:
                if all(x not in b for x in ('FadeOut','Clear','self.clear(')):
                    verdict = 'REVISION_NEEDED'
                    feedback = f"Scene cleanup missing in block {b[:30]}..."
                    break
        return {'code_eval_verdict': verdict, 'evaluation_feedback': feedback if verdict=='REVISION_NEEDED' else None}
    except Exception as e:
        err = f"Error in evaluate_code_node: {e}"
        app.logger.error(err, exc_info=True)
        return {'error_message': err} 