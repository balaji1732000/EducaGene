from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.state import WorkflowState


def should_retry_full_script(state: WorkflowState) -> str:
    """Decides whether to retry script generation or proceed to rendering the combined video."""
    verdict = state.code_eval_verdict
    iteration = state.script_revision_iteration
    max_revisions = state.max_script_revisions

    app.logger.info(f"--- should_retry_full_script (Verdict: {verdict}, Iter: {iteration}/{max_revisions}) ---")

    if verdict == 'REVISION_NEEDED':
        if iteration < max_revisions:
            app.logger.info("Evaluation requires revision, retrying script generation.")
            return 'retry_script_generation'
        else:
            app.logger.warning(f"Evaluation requires revision, but max revisions ({max_revisions}) reached. Proceeding to render potentially flawed script.")
            return 'proceed_to_render'
    elif verdict == 'SATISFIED':
        app.logger.info("Evaluation satisfied. Proceeding to render combined video.")
        return 'proceed_to_render'
    else:
        app.logger.error(f"Unexpected evaluation verdict '{verdict}'. Proceeding to render, but script may be flawed.")
        return 'proceed_to_render' 