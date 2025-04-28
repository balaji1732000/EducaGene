from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.state import WorkflowState


def check_render_result(state: WorkflowState) -> str:
    """Checks render result and decides if retry is needed based on render errors."""
    render_error = state.rendering_error
    video_path = state.video_path
    # Use the specific render error iteration counter and limit
    iteration = state.render_error_iteration
    max_revisions = state.max_render_error_revisions

    app.logger.info(f"--- check_render_result (Error: {bool(render_error)}, Video: {bool(video_path)}, Render Iter: {iteration}/{max_revisions}) ---")

    if video_path and not render_error:
        return 'render_success'
    elif render_error:
        if iteration < max_revisions:
            app.logger.info("Render failed, retrying script generation.")
            return 'retry_script_generation_render_error'
        else:
            # Set error message in the state directly (LangGraph handles state updates)
            error_message = f"Render failed after {max_revisions} attempts. Last error: {render_error}"
            app.logger.error(error_message)
            # Even if render fails permanently, proceed to evaluation to potentially get feedback
            return 'render_failed_proceed'
    else:
        # This case should ideally not happen if render succeeded or failed clearly
        error_message = "Inconsistent state after render attempt (no video path and no render error)."
        app.logger.error(error_message)
        # Proceed to evaluation, but log the inconsistency
        return 'render_failed_proceed'
