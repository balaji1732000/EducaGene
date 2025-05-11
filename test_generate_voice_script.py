import os
from typing import Dict, Any, Optional

from google import genai
from google.genai import types
from manim_video_generator.config import app
from manim_video_generator.utils import upload_to_gemini, wait_for_files_active
from manim_video_generator.state import WorkflowState
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file


client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))  # Initialize Gemini client with API key
def generate_final_script_node(language, video) -> Dict[str, Any]:
    """Generates a voiceover script via Gemini for the combined video in the target language."""
    app.logger.info("--- generate_final_script_node (Gemini voiceover) ---")
    video_path = video
    language = language # Get target language
    if not video_path or not os.path.exists(video_path):
        err = f"Cannot generate voiceover: Missing video at {video_path}"
        app.logger.error(err)
        return {'error_message': err, 'voiceover_script': None}

    video_file = upload_to_gemini(video_path)
    wait_for_files_active(video_file)

    generation_config =types.GenerateContentConfig(
        temperature=0.7,
        top_p=0.95,
        top_k=40,
        max_output_tokens=10000,
        response_mime_type="application/json",
        safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        # Add any other necessary parameters here
    )
    
    
    # Construct the prompt for generate_content
    prompt = f"""
You are given a silent educational animation video (provided as input).
Analyze the visual content and generate a concise, engaging voiceover script in **{language}** that:
- Exactly matches the video's timeline; narration must start and end aligned to the video duration.
- Contains only the spoken lines in **{language}**; do NOT include any timestamps, explanations, stage directions, or extraneous commentary.
- Keep mathematical formulas, code snippets, or universally recognized technical terms in **English** if they appear visually and direct translation is awkward or incorrect.
- Ensure the script length corresponds approximately to the length of the video.
Output ONLY the raw narration text in **{language}** without any additional text or formatting.
"""
    
    # Call generate_content with the prompt and the video file object
    app.logger.info("Sending video analysis request to Gemini for voiceover script generation...")
    response = client.models.generate_content(
            model="gemini-2.5-flash-preview-04-17", # Using flash
            config=generation_config,
            contents=[prompt,video_file]
            
        )
    
    script = response.text.strip()
    if not script:
        err = 'Gemini returned empty script for voiceover.'
        app.logger.error(err)
        return {'error_message': err, 'voiceover_script': None}
    app.logger.info("Voiceover script generated successfully.")
    return {'voiceover_script': script, 'error_message': None}

if __name__ == "__main__":
    # Test the function with a dummy state
    
    video_path="C:/Users/ASUS/Documents/Video generation/manim-video-generator/tmp_requests/req_20250508_001825_20649c/final_build/req_20250508_001825_20649c_combined_video.mp4"
    language="en-US"
    
    result = generate_final_script_node(language, video_path)
    print(result)  # Print the result for testing purposes