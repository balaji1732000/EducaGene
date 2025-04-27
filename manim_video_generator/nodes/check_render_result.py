from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.state import WorkflowState


def check_render_result(state: WorkflowState) -> str:
    """Checks render result and decides if retry is needed."""
    render_error = state.rendering_error
    video_path = state.video_path
    iteration = state.script_revision_iteration
    max_revisions = state.max_script_revisions

    app.logger.info(f"--- check_render_result (Error: {bool(render_error)}, Video: {bool(video_path)}, Iter: {iteration}/{max_revisions}) ---")

    if video_path and not render_error:
        return 'render_success'
    elif render_error:
        if iteration < max_revisions:
            return 'retry_script_generation_render_error'
        else:
            state.error_message = f"Render failed after {max_revisions} attempts. Last error: {render_error}"
            return 'render_failed_proceed'
    else:
        state.error_message = "Inconsistent state after render attempt."
        return 'render_failed_proceed' 