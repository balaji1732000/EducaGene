from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal

@dataclass
class WorkflowState:
    user_concept: str
    language: str = "en-US" # Target language code (e.g., "en-US", "es-ES")
    request_id: Optional[str] = None
    estimated_duration: float = 0.0 # Estimated duration based on generated script
    temp_dir: Optional[str] = None
    video_plan: Optional[List[Dict[str, Any]]] = None
    current_render_index: int = 0
    scene_class_name: Optional[str] = None
    rendering_error: Optional[str] = None
    video_path: Optional[str] = None
    collected_final_scene_paths: List[str] = field(default_factory=list)
    concatenated_silent_video_path: Optional[str] = None
    voiceover_script: Optional[str] = None
    audio_path: Optional[str] = None
    final_video_path: Optional[str] = None
    final_video_url: Optional[str] = None
    error_message: Optional[str] = None
    code_eval_verdict: Optional[Literal['SATISFIED', 'REVISION_NEEDED']] = None # Set by evaluation node
    # Separate iteration counters and limits
    render_error_iteration: int = 0
    max_render_error_revisions: int = 6 # Max retries for render errors
    evaluation_revision_iteration: int = 0
    max_evaluation_revisions: int = 3 # Max retries for evaluation feedback (Increased to 3)
    current_code: Optional[str] = None
    full_script_path: Optional[str] = None
    all_scene_class_names: List[str] = field(default_factory=list)
    evaluation_feedback: Optional[str] = None # Consolidated feedback (from code OR combined code/video eval)
    error_search_context: Optional[str] = None # Context from web search for render errors
