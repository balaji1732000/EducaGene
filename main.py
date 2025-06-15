import os
import logging
import json
from datetime import datetime
from typing import Any
import json
import os
import sys
import logging
import shutil
import json
from IPython.display import Image, display
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
from langgraph.graph import StateGraph, END
import azure.cognitiveservices.speech as speechsdk

# Load environment variables as early as possible
load_dotenv()

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
from manim_video_generator.config import * # Assuming this sets up logging, paths etc.
from manim_video_generator.utils import * # Keep specific utils if needed elsewhere
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
    search_for_solution_node, # Import the new node
)




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
    ('search_for_solution', search_for_solution_node), # Add the new node
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
        # If render fails but retries allowed, go to the NEW search node first
        'retry_script_generation_render_error': 'search_for_solution',
        # If render fails and max retries hit, still try evaluation (node handles missing video)
        'render_failed_proceed': 'evaluate_script_and_video'
    }
)

# After searching for a solution, always go back to generate script
workflow.add_edge('search_for_solution', 'generate_full_script')

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

# Attempt to generate workflow diagram
try:
    output_path = "workflow.png"
    # Try calling draw_mermaid_png() and writing the returned bytes
    graph_viz = manim_graph.get_graph()
    if hasattr(graph_viz, 'draw_mermaid_png'):
        png_data = graph_viz.draw_mermaid_png() # Call without arguments
        with open(output_path, "wb") as f:
            f.write(png_data)
        app.logger.info(f"LangGraph workflow diagram saved to {output_path} using draw_mermaid_png()")
    elif hasattr(graph_viz, 'draw_png'): # Fallback to draw_png if draw_mermaid_png doesn't exist
        graph_viz.draw_png(output_path) # Assumes draw_png takes path
        app.logger.info(f"LangGraph workflow diagram saved to {output_path} using draw_png()")
    else: # Fallback to the standard pygraphviz draw method
        graph_viz.draw(output_path, format='png', prog='dot')
        app.logger.info(f"LangGraph workflow diagram saved to {output_path} using graph_viz.draw()")
except ImportError:
    app.logger.warning("pygraphviz not found. Skipping workflow diagram generation. Install with: pip install pygraphviz")
except AttributeError as ae:
    app.logger.warning(f"Failed to generate workflow diagram due to AttributeError (e.g. method not found): {ae}. Ensure LangGraph and pygraphviz versions are compatible.")
except Exception as e:
    app.logger.warning(f"Failed to generate workflow diagram: {e}. Ensure Graphviz is installed and in PATH, and LangGraph/pygraphviz are correctly installed.")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_langraph():
    data = request.get_json(force=True)
    concept = sanitize_input(data.get('concept', ''))
    language = data.get('language', 'en-US') # Default to English if not provided
    if not concept:
        return jsonify({'error': 'Missing "concept"'}), 400
    # Initialize dataclass state, including language
    state = WorkflowState(user_concept=concept, language=language)
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
