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
    language = state.language # Get the target language

    prompt = f"""Create a structured plan in **{language}** for an educational Manim animation video explaining the concept: '{concept}'. The style should be similar to visual explanations found on channels like 3Blue1Brown, focusing on clear, step-by-step visual intuition.

**Planning Considerations:**
1.  **Language:** Generate all scene 'titles' and 'descriptions' in **{language}**. However, keep mathematical formulas (e.g., `a^2+b^2=c^2`), specific Manim object names (e.g., `MathTex`, `Square`), code snippets, and universally understood technical terms in **English**.
2.  **Duration/Scene Count:** Analyze the user's concept '{concept}'.
    *   If the concept implies a specific duration (e.g., "short video", "2-minute explanation"), create a plan with a number of scenes appropriate for that length (estimate ~5-10 seconds per scene).
    *   If no duration is implied, create a detailed plan with enough scenes to cover the topic thoroughly. For complex topics, aim for significant depth (e.g., ~30 scenes as a guideline, but adjust based on the actual content).
2.  **Dimensionality (Strict):** Carefully determine if the concept **inherently requires 3D visualization** (`ThreeDScene`). Examples include plotting 3D surfaces, vector fields, complex spatial relationships. **If 2D (`Scene`) is sufficient, strongly prefer 2D.** If recommending 3D, **explicitly state why** it's necessary for that specific scene (e.g., "Requires 3D to show the surface plot"). Mention relevant 3D objects (`Sphere`, `Cube`, `ThreeDAxes`, `ParametricSurface`) only if 3D is truly needed.

**Scene Breakdown:**
Break the concept down into a logical sequence of distinct scenes based on the duration/complexity analysis above.
For each scene:
- Provide a concise, descriptive 'title'.
- Provide a detailed 'description' outlining:
    - The key idea or sub-topic this scene addresses.
    - A step-by-step guide of the visual elements to show and animate (mention 2D or 3D objects as appropriate).
    - Mention specific Manim objects/methods (in English) that might be useful (e.g., `Text`, `MathTex`, `Square`, `Circle`, `Create`, `Transform`, `FadeIn`, `Rotate`). Only mention 3D objects (`ThreeDAxes`, `Surface`, `Sphere`) if 3D is deemed necessary for this scene.
    - If 3D is recommended, state: "Requires `ThreeDScene`. Reason: [briefly explain why 3D is needed]".
    - The main takeaway point or connection to the next scene (in {language}).

**Output Format:**
- Output the plan **ONLY** as a valid JSON list of objects.
- Each object must have keys 'title' and 'description' (with values in {language}, respecting the English exceptions mentioned above).
- **DO NOT** include any explanations, comments, greetings, or markdown fences.
- The very first character must be `[` and the last must be `]`.

Generate the plan JSON in **{language}** for: '{concept}'"""

    messages = [
        {'role': 'system', 'content': f'You are an expert educational content planner. Output ONLY the raw JSON plan as a list of objects, with text content in {language} unless it is a technical term, formula, or Manim object name (keep those in English). No other text allowed.'},
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
