from typing import Dict, Any

from manim_video_generator.config import app
from manim_video_generator.state import WorkflowState


def should_retry_full_script(state: WorkflowState) -> str:
    """Decides whether to retry script generation based on evaluation feedback or proceed."""
    verdict = state.code_eval_verdict
    # Use the specific evaluation iteration counter and limit
    iteration = state.evaluation_revision_iteration
    max_revisions = state.max_evaluation_revisions

    app.logger.info(f"--- should_retry_full_script (Verdict: {verdict}, Eval Iter: {iteration}/{max_revisions}) ---")

    if verdict == 'REVISION_NEEDED':
        if iteration < max_revisions:
            app.logger.info("Evaluation requires revision, retrying script generation.")
            # Reset render error counter before retrying based on evaluation
            state.render_error_iteration = 0
            app.logger.info("Resetting render error iteration count.")
            return 'retry_script_generation'
        else:
            app.logger.warning(f"Evaluation requires revision, but max evaluation revisions ({max_revisions}) reached. Proceeding to voiceover generation with potentially flawed script.")
            # Set error message? Or just proceed? Let's proceed for now.
            return 'proceed_to_voiceover' # Changed target name for clarity
    elif verdict == 'SATISFIED':
        app.logger.info("Evaluation satisfied. Proceeding to voiceover generation.")
        return 'proceed_to_voiceover' # Changed target name for clarity
    else:
        # Includes the case where evaluation failed and returned SATISFIED by default
        app.logger.error(f"Unexpected evaluation verdict '{verdict}' or evaluation failed. Proceeding to voiceover generation, but script/video may be flawed.")
        return 'proceed_to_voiceover' # Changed target name for clarity
