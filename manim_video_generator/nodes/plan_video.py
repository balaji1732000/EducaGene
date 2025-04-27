import json
from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.utils import clean_code_string
from manim_video_generator.llm_client import get_llm_client
from manim_video_generator.state import WorkflowState


def plan_video_node(state: WorkflowState) -> Dict[str, Any]:
    """Generates a structured JSON plan for the video concept."""
    app.logger.info("--- plan_video ---")
    if state.error_message:
        return {}
    llm = get_llm_client()
    concept = state.user_concept

    prompt = f"""Create a structured plan for an educational Manim animation video explaining the concept: '{concept}'. The style should be similar to visual explanations found on channels like 3Blue1Brown, focusing on clear, step-by-step visual intuition.

Break the concept down into a logical sequence of distinct scenes.
For each scene:
- Provide a concise, descriptive 'title'.
- Provide a detailed 'description' outlining:
    - The key idea or sub-topic this scene addresses.
    - A step-by-step guide of the visual elements to show and animate.
    - Mention specific Manim objects that might be useful.
    - The main takeaway point or connection to the next scene.

**Output the plan *ONLY* as a valid JSON list of objects.**
- Each object must have keys 'title', and 'description'.
- **DO NOT** include any explanations, comments, greetings, or markdown fences.
- The very first character must be `[` and the last must be `]`.

Generate the plan JSON for: '{concept}'"""

    messages = [
        {'role': 'system', 'content': 'You are an educational planner. Output ONLY the raw JSON list.'},
        {'role': 'user', 'content': prompt}
    ]

    raw = ""
    try:
        resp = llm.invoke(messages)
        raw = resp.content
        plan_str = clean_code_string(raw).strip()
        plan = json.loads(plan_str)
        if not isinstance(plan, list):
            raise ValueError("Plan JSON not a list")
        processed = []
        for i, scene in enumerate(plan):
            if not isinstance(scene, dict) or 'title' not in scene or 'description' not in scene:
                raise ValueError(f"Invalid scene at {i}: {scene}")
            scene['scene_num'] = i + 1
            processed.append(scene)
        return {'video_plan': processed, 'error_message': None}
    except Exception as e:
        app.logger.error(f"Plan generation failed: {e}", exc_info=True)
        # Store raw if parse fail
        return {'video_plan': None, 'error_message': raw[:1000]} 