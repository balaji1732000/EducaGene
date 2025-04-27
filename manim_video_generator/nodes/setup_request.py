import os
import uuid
from datetime import datetime
from typing import Dict, Any

from manim_video_generator.config import TMP_BASE as tmp_base, app
from manim_video_generator.state import WorkflowState


def setup_request_node(state: WorkflowState) -> Dict[str, Any]:
    """Creates unique temporary directory and initializes workflow state."""
    app.logger.info("--- setup_request ---")
    rid = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    base_dir = os.path.join(tmp_base, rid)
    subdirs = ['scripts', 'scene_media', 'final_scenes', 'audio', 'final_build']
    for sub in subdirs:
        os.makedirs(os.path.join(base_dir, sub), exist_ok=True)
    return {
        'request_id': rid,
        'temp_dir': base_dir,
        'video_plan': None,
        'current_code': None,
        'scene_class_name': None,
        'full_script_path': None,
        'evaluation_feedback': None,
        'code_eval_verdict': None,
        'script_revision_iteration': 0,
        'max_script_revisions': 3,
        'rendering_error': None,
        'video_path': None,
        'voiceover_script': None,
        'audio_path': None,
        'final_video_path': None,
        'final_video_url': None,
        'error_message': None,
        'estimated_duration': 0.0,
    } 