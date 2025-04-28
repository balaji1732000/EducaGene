import os
import sys
import logging
import subprocess
import shutil
import uuid
import json
import time
import traceback
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional, Literal
import shutil  # Added missing import for subprocess utilities
import re
from logging import FileHandler
import os
import sys
import logging
import subprocess
import shutil
import uuid
import json
import time
import traceback
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional, Literal
import shutil  # Added missing import for subprocess utilities
import re
from logging import FileHandler
import os
import sys
import logging
import subprocess
import shutil
import uuid
import json
import time
import traceback
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional, Literal
import shutil  # Added missing import for subprocess utilities
import re
from logging import FileHandler
import google.generativeai as genai

# Load environment variables as early as possible
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, url_for
from manim import *
# from dotenv import load_dotenv # Moved up
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI
import azure.cognitiveservices.speech as speechsdk

# Load environment variables as early as possible
load_dotenv()

try:
    import moviepy as mp
except ImportError:
    mp = None
    logging.warning("moviepy not installed. Video concatenation and merging will fail.")

try:
    import moviepy as mp
except ImportError:
    mp = None
    logging.warning("moviepy not installed. Video concatenation and merging will fail.")





# Helper functions (Keep these here or move to utils if they are truly utilities)
def sanitize_input(text: str) -> str:
    return ' '.join(text.strip().split())

def clean_code_string(code: str) -> str:
    if code.startswith('```'):
        lines = code.splitlines()[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        return '\n'.join(lines).strip()
    return code

# --- Structured imports ---
from manim_video_generator.config import * 
from manim_video_generator.utils import sanitize_input, clean_code_string, fix_inline_latex, estimate_scene_time, upload_to_gemini, wait_for_files_active
from manim_video_generator.llm_client import get_llm_client
from manim_video_generator.state import WorkflowState
# --- Structured imports ---
from manim_video_generator.config import * # Assuming this sets up logging, paths etc.
from manim_video_generator.utils import sanitize_input # Keep specific utils if needed elsewhere
from manim_video_generator.state import WorkflowState
from manim_video_generator.nodes import (
    setup_request_node,
    plan_video_node,
    generate_full_script_node,
    # evaluate_code_node, # Removed old node
    evaluate_script_and_video_node, # Added new node
    render_combined_video_node,
    generate_final_script_node,
    generate_audio_node,
    combine_final_video_audio_node,
    should_retry_full_script,
    check_render_result,
)

# def upload_to_gemini(path: str, mime_type: Optional[str] = None) -> Any:
#     """Uploads the given file to Gemini and returns the file object."""
#     return genai.upload_file(path, mime_type=mime_type)

# def wait_for_files_active(files: List[Any]) -> None:
#     """Blocks until all uploaded files are processed and active in Gemini."""
#     print("Waiting for file processing...")
#     for file in files:
#         f = genai.get_file(file.name)
#         while f.state.name == "PROCESSING":
#             time.sleep(10)
#             f = genai.get_file(file.name)
#         if f.state.name != "ACTIVE":
#             raise Exception(f"File {f.name} failed to process")
#     print("...all files ready")
#     print()

# # LLM client
# def get_llm_client() -> AzureChatOpenAI:
#     return AzureChatOpenAI(
#         azure_endpoint=os.getenv('ENDPOINT_URL'),
#         api_key=os.getenv('AZURE_OPENAI_API_KEY'),
#         api_version='2024-12-01-preview',
#         azure_deployment="o3-mini-2",
#         max_completion_tokens=100000,
        
#     )

# # --- timing heuristic -------------------------------------------------
# WAIT_RE = re.compile(r"\.wait\(\s*([0-9.]+)\s*\)")
# PLAY_RE = re.compile(r"\.play\(")

# def estimate_scene_time(code: str) -> float:
#     """
#     Very quick heuristic:
#       • explicit .wait(x) => add x seconds
#       • each .play(...)   => assume ~2 s of animation
#     Good enough to keep narration in sync.
#     """
#     waits = [float(x) for x in WAIT_RE.findall(code)]
#     plays = len(PLAY_RE.findall(code))
#     return sum(waits) + plays * 2.0


# # -----------------------------------------------------------------------
# # helper – fix inline LaTeX that the LLM often produces
# # -----------------------------------------------------------------------
# _INLINE_DOLLARS = re.compile(r"(?<!\\)\\$([^$]+?)\\$")       # $...$  → \( ... \)
# _DOUBLE_LBRACE  = re.compile(r"\\{\\{")                     # {{     → \\{
# _DOUBLE_RBRACE  = re.compile(r"\\}\\}")                     # }}     → \\}

# def fix_inline_latex(code: str) -> str:
#     """
#     Convert inline $...$ to \\( ... \\) so MathTex doesn't choke,
#     and escape stray '{{' / '}}' that break LaTeX parsing.
#     Call this once on the full script before saving.
#     """
#     code = _INLINE_DOLLARS.sub(lambda m: f"\\({m.group(1).strip()}\\)", code)
#     code = _DOUBLE_LBRACE.sub(r"\\{", code)
#     code = _DOUBLE_RBRACE.sub(r"\\}", code)
#     return code



# Workflow state definition
class ManimWorkflowState(TypedDict):
    user_concept: str
    request_id: str
    estimated_duration: float
    temp_dir: str
    video_plan: Optional[List[Dict[str, Any]]]
    current_render_index: int
    scene_class_name: Optional[str]
    rendering_error: Optional[str]
    video_path: Optional[str]
    collected_final_scene_paths: List[str]
    concatenated_silent_video_path: Optional[str]
    voiceover_script: Optional[str]
    audio_path: Optional[str]
    final_video_path: Optional[str]
    final_video_url: Optional[str]
    error_message: Optional[str]
    code_eval_verdict: Optional[Literal['SATISFIED', 'REVISION_NEEDED']]
    script_revision_iteration: int
    max_script_revisions: int
    current_code: Optional[str]
    full_script_path: Optional[str]
    all_scene_class_names: List[str]
    evaluation_feedback: Optional[str]

# Build graph
workflow = StateGraph(WorkflowState)

# Add nodes and wiring
nodes_to_add = [
    ('setup_request', setup_request_node),
    ('plan_video', plan_video_node),
    ('generate_full_script', generate_full_script_node),
    # ('evaluate_code', evaluate_code_node), # Removed old node
    ('evaluate_script_and_video', evaluate_script_and_video_node), # Added new node
    ('render_combined_video', render_combined_video_node),
    ('generate_final_script', generate_final_script_node),
    ('generate_audio', generate_audio_node),
    ('combine_final_video_audio', combine_final_video_audio_node),
]
for name, fn in nodes_to_add:
    workflow.add_node(name, fn)
workflow.set_entry_point('setup_request')
workflow.add_edge('setup_request', 'plan_video')
workflow.add_edge('plan_video', 'generate_full_script')

# After generating script, go directly to rendering
workflow.add_edge('generate_full_script', 'render_combined_video')

# After rendering, check result and decide next step
workflow.add_conditional_edges(
    'render_combined_video',
    check_render_result,
    {
        # If render succeeds, go to the new combined evaluation node
        'render_success': 'evaluate_script_and_video',
        # If render fails but retries allowed, go back to generate script
        'retry_script_generation_render_error': 'generate_full_script',
        # If render fails and max retries hit, still try evaluation (node handles missing video)
        'render_failed_proceed': 'evaluate_script_and_video'
    }
)

# After combined evaluation, check if revision is needed
workflow.add_conditional_edges(
    'evaluate_script_and_video', # New source node for this decision
    should_retry_full_script, # Re-use the same logic (checks code_eval_verdict)
    {
        # If revision needed, go back to generate script
        'retry_script_generation': 'generate_full_script',
        # If satisfied, proceed to generate voiceover script
        'proceed_to_voiceover': 'generate_final_script' # Match the target name from should_retry_full_script
    }
)

# Final steps remain the same
workflow.add_edge('generate_final_script', 'generate_audio')
workflow.add_edge('generate_audio', 'combine_final_video_audio')
workflow.add_edge('combine_final_video_audio', END)

# Compile graph
manim_graph = workflow.compile()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_langraph():
    data = request.get_json(force=True)
    concept = sanitize_input(data.get('concept', ''))
    if not concept:
        return jsonify({'error': 'Missing "concept"'}), 400
    # Initialize dataclass state
    state = WorkflowState(user_concept=concept)
    app.logger.info(f"Invoking graph with initial state: {state}")
    try:
        final_state = None
        for step in manim_graph.stream(state, {'recursion_limit': 150}):
            step_name = list(step.keys())[0]
            step_output = step[step_name]
            app.logger.info(f"--- Completed Step: {step_name} ---")
            final_state = step_output

        if final_state is None:
            return jsonify({'error': 'Graph execution finished without a final state.'}), 500

        loggable_state = {k: (f"<{type(v).__name__} len={len(v)}>" if isinstance(v, (str, list, dict)) and len(v) > 200 else v) for k, v in final_state.items()}
        app.logger.debug(f"Final state contents: {json.dumps(loggable_state, indent=2, default=str)}")

        if final_state.get('error_message') and "Max script revisions reached" not in final_state['error_message']:
            return jsonify({'error': final_state['error_message']}), 500

        error_msg = final_state.get('error_message')
        warning_msg = error_msg if isinstance(error_msg, str) and "Max script revisions reached" in error_msg else None

        # --- Read Final Script Code ---
        final_script_code = None
        script_path = final_state.get('full_script_path')
        if script_path and os.path.exists(script_path):
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    final_script_code = f.read()
                app.logger.info(f"Successfully read final script from {script_path}")
            except Exception as e:
                app.logger.error(f"Failed to read final script {script_path}: {e}")
                # Decide if this should be a warning or prevent success response
                # For now, log it and continue
        else:
            app.logger.warning(f"Final script path not found or doesn't exist: {script_path}")
        # --- End Read Final Script Code ---

        return jsonify({
            'message': 'Workflow completed.',
            'warning': warning_msg,
            'final_video_url': final_state.get('final_video_url'),
            'final_script_code': final_script_code, # <-- Added script content
            'final_state_summary': loggable_state
        })

    except Exception as e:
        app.logger.error(f"Exception during graph invocation: {e}", exc_info=True)
        if "RecursionError" in str(e) or "recursion limit" in str(e).lower():
            return jsonify({'error': f'Workflow exceeded recursion limit. Check for infinite loops. Error: {e}'}), 500
        return jsonify({'error': f'Internal server error during workflow execution: {e}'}), 500
    
if __name__ == '__main__':
    os.makedirs(STATIC_VIDEOS, exist_ok=True)
    app.logger.info('Starting server at 0.0.0.0:5001')
    app.run(host='0.0.0.0', port=5001, debug=False)
