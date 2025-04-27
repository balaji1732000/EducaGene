import os
from typing import Dict, Any, Optional

import google.generativeai as genai
from manim_video_generator.config import app
from manim_video_generator.utils import upload_to_gemini, wait_for_files_active
from manim_video_generator.state import WorkflowState


def generate_final_script_node(state: WorkflowState) -> Dict[str, Any]:
    """Generates a voiceover script via Gemini for the combined video."""
    app.logger.info("--- generate_final_script_node (Gemini voiceover) ---")
    video_path = state.video_path
    if not video_path or not os.path.exists(video_path):
        err = f"Cannot generate voiceover: Missing video at {video_path}"
        app.logger.error(err)
        return {'error_message': err, 'voiceover_script': None}

    video_file = upload_to_gemini(video_path, mime_type='video/mp4')
    wait_for_files_active([video_file])

    generation_config = {
        'temperature': 1,
        'top_p': 0.95,
        'top_k': 64,
        'max_output_tokens': 65536,
        'response_mime_type': 'text/plain',
    }
    model = genai.GenerativeModel(
        model_name='gemini-2.5-pro-preview-03-25',
        generation_config=generation_config,
    )
    chat_session = model.start_chat(history=[{'role': 'user', 'parts': [video_file]}])
    prompt = ("""
You are given a silent educational animation video.
Analyze the visual content and generate a concise, engaging voiceover script that:
- Exactly matches the video's timeline; narration must start and end aligned to the video duration.
- Contains only the spoken lines; do NOT include any timestamps, explanations, stage directions, or extraneous commentary.
- Ensure the script length corresponds to approximately length of the video.
Output ONLY the raw narration text without any additional text or formatting.
""")
    response = chat_session.send_message(prompt)
    script = response.text.strip()
    if not script:
        err = 'Gemini returned empty script.'
        app.logger.error(err)
        return {'error_message': err, 'voiceover_script': None}
    app.logger.info("Voiceover script generated successfully.")
    return {'voiceover_script': script, 'error_message': None} 