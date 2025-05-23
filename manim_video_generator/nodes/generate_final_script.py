import os
import subprocess # Keep for _get_video_duration if re-added, but not used now
import json
from typing import Dict, Any, Optional, Tuple, List

from google import genai
from google.genai import types
from manim_video_generator.config import app
from manim_video_generator.utils import upload_to_gemini, wait_for_files_active
from manim_video_generator.state import WorkflowState # Still needed for type hinting in actual node
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Removed _get_video_duration_and_word_target function as per feedback

def _generate_timestamped_script(
    video_file: types.File, 
    language: str,
    # duration: Optional[float], # Removed duration
    # target_words: Optional[int], # Removed target_words
    llm_client: genai.Client
) -> Optional[Dict[str, Any]]:
    """Generates a timestamped voiceover script using Gemini."""
    app.logger.info("Attempting to generate timestamped script...")
    
    # duration_info = f"The video is approximately {duration:.2f} seconds long." if duration else "Video duration could not be determined."
    # word_target_info = f"Aim for a natural, conversational pace, targeting around {target_words} words for the narration, distributed across segments." if target_words else "Aim for a natural, conversational pace that matches the video's length."

    prompt = f"""
You are an expert scriptwriter for educational animations. You will be given a silent video.
Your task is to generate a voiceover script in **{language}** with precise timestamps for each narration segment. The script should naturally align with the video's pacing and content.

**Script Requirements:**
1.  **Language:** The narration MUST be in **{language}**.
2.  **Pacing & Tone:** Maintain a natural, conversational, and engaging tone. Pacing should align with visual cues and the overall video duration.
3.  **Timestamps:** Provide `start_time` and `end_time` for each text segment in "HH:MM:SS.mmm" or "SS.mmm" format. Timestamps must be accurate to the video.
4.  **Content Focus:** Explain or complement the visuals.
5.  **Technical Terms:** Keep mathematical formulas, code snippets, or universally recognized technical terms in **English** if direct translation into **{language}** is awkward or loses precision.
6.  **No Extraneous Text in Segments:** The `text` field for each segment should contain ONLY the spoken narration.

**Output Format:**
You MUST respond with a single, valid JSON object matching this exact schema:
```json
{{
  "segments": [
    {{ 
      "start_time": "<string: e.g., 00:00:00.000 or 0.000>", 
      "end_time": "<string: e.g., 00:00:05.300 or 5.300>", 
      "text": "<string: Narration for this segment in {language}.>"
    }}
    // ... more segment objects
  ],
  "total_word_count": "<integer: The total word count of all 'text' fields combined.>"
}}
```
Ensure `segments` is a list of objects, each with `start_time`, `end_time`, and `text`.
Do NOT include any text outside this JSON structure.
"""

    generation_config_ts = types.GenerateContentConfig(
        temperature=0.6,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        response_mime_type="application/json",
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
    )

    try:
        response = llm_client.models.generate_content(
            model="gemini-1.5-flash-latest",
            config=generation_config_ts,
            contents=[prompt, video_file]
        )
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        app.logger.debug(f"Raw Gemini JSON response for timestamped script: {response_text}")
        parsed_json = json.loads(response_text)

        if "segments" in parsed_json and isinstance(parsed_json["segments"], list):
            app.logger.info(f"Successfully parsed timestamped script JSON with {len(parsed_json['segments'])} segments.")
            return parsed_json
        else:
            app.logger.warning("Timestamped script JSON parsed but 'segments' key is missing or not a list.")
            return {"error": "Missing 'segments' in LLM response", "raw_response": response_text}

    except (json.JSONDecodeError, ValueError) as e:
        app.logger.error(f"Failed to parse JSON for timestamped script: {e}. Raw response: {response.text if hasattr(response, 'text') else 'N/A'}")
        return {"error": f"JSON parsing error: {e}", "raw_response": response.text if hasattr(response, 'text') else 'N/A'}
    except Exception as e:
        app.logger.error(f"Unexpected error generating timestamped script: {e}")
        return {"error": f"Unexpected error: {e}"}

def _convert_timestamped_to_plain_script(segments: List[Dict[str, str]]) -> str:
    """Converts a list of timestamped script segments to a single plain text script."""
    if not segments:
        return ""
    plain_script_parts = [segment.get("text", "").strip() for segment in segments if segment.get("text")]
    return " ".join(plain_script_parts)


def generate_final_script_node(state: WorkflowState) -> Dict[str, Any]:
    """Generates a voiceover script via Gemini for the combined video in the target language."""
    app.logger.info("--- generate_final_script_node (Gemini voiceover) ---")
    video_path = state.video_path
    language = state.language

    if not video_path or not os.path.exists(video_path):
        err = f"Cannot generate voiceover: Missing video at {video_path}"
        app.logger.error(err)
        return {'error_message': err, 'voiceover_script': None}
    
    video_file = upload_to_gemini(video_path)
    wait_for_files_active(video_file)

    script = None
    actual_word_count = None

    # Attempt 1: Generate timestamped script and convert
    app.logger.info("Attempting to generate timestamped script first...")
    # Pass client directly, remove duration and target_words from call
    timestamped_script_data = _generate_timestamped_script(video_file, language, client) 

    if timestamped_script_data and isinstance(timestamped_script_data, dict) and timestamped_script_data.get("segments"):
        app.logger.info(f"Successfully generated timestamped script with {len(timestamped_script_data['segments'])} segments.")
        script = _convert_timestamped_to_plain_script(timestamped_script_data["segments"])
        if script:
            actual_word_count = timestamped_script_data.get("total_word_count") or len(script.split())
            app.logger.info(f"Converted timestamped script to plain script. Word count: {actual_word_count}")
        else:
            app.logger.warning("Conversion from timestamped to plain script resulted in empty script. Will attempt direct generation.")
            
    else:
        error_detail = timestamped_script_data.get("error", "Unknown reason") if isinstance(timestamped_script_data, dict) else "Malformed response"
        app.logger.warning(f"Failed to generate valid timestamped script (Reason: {error_detail}). Will attempt direct plain script generation.")

    # Attempt 2 (Fallback): Direct plain script generation if timestamped approach failed or yielded empty script
    if not script:
        app.logger.info("Falling back to direct plain script generation (requesting JSON with 'script' and 'word_count')...")
        
        # duration_info_plain = f"The video is approximately {duration:.2f} seconds long." if duration else "Video duration could not be determined."
        # word_target_info_plain = f"Aim for a natural, conversational pace, targeting around {target_words} words for the narration." if target_words else "Aim for a natural, conversational pace that matches the video's length."
        # Removed duration and word target info from this prompt as well for consistency

        prompt_plain = f"""
You are an expert scriptwriter for educational animations. You will be given a silent video.
Your task is to generate a concise, engaging voiceover script in **{language}**.
The script should naturally align with the video's pacing and content.

**Script Requirements:**
1.  **Language:** The narration MUST be in **{language}**.
2.  **Pacing & Tone:** Maintain a natural, conversational, and engaging tone suitable for educational content. The pacing should feel smooth and unhurried, aligning with the visual cues in the video.
3.  **Timeline Adherence:** The narration must start and end aligned with the video's duration.
4.  **Content Focus:** The script should explain or complement the visuals.
5.  **Technical Terms:** Keep mathematical formulas, code snippets, or universally recognized technical terms in **English** if they appear visually and direct translation into **{language}** is awkward, incorrect, or would lose precision.
6.  **No Extraneous Text:** Do NOT include timestamps, scene numbers, speaker names, stage directions, or any commentary outside the actual spoken narration.

**Output Format:**
You MUST respond with a single, valid JSON object matching this exact schema:
```json
{{
  "script": "<string: The full narration text in {language}.>",
  "word_count": "<integer: The actual word count of the generated script.>"
}}
```
Ensure the `script` field contains only the raw narration text.
Ensure the `word_count` field accurately reflects the number of words in the `script` field.
Do NOT include any text outside this JSON structure.
"""
        generation_config_plain = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_mime_type="application/json",
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        )
        
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-04-17", # Using latest flash model
                config=generation_config_plain,
                contents=[prompt_plain, video_file]
            )
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            app.logger.debug(f"Raw Gemini JSON response for (fallback) voiceover: {response_text}")
            parsed_json = json.loads(response_text)
            script = parsed_json.get("script", "").strip()
            actual_word_count = parsed_json.get("word_count")
            if not isinstance(script, str) or (actual_word_count is not None and not isinstance(actual_word_count, int)):
                raise ValueError("Parsed JSON (fallback) does not match expected schema.")
            app.logger.info(f"Successfully parsed JSON response (fallback). Word count: {actual_word_count}")

        except (json.JSONDecodeError, ValueError) as e_fallback:
            app.logger.warning(f"Failed to parse JSON response (fallback) from Gemini or schema mismatch: {e_fallback}. Using raw text as final fallback.")
            script = response.text.strip() 
            if script: 
                actual_word_count = len(script.split())
                app.logger.info(f"Using raw text as script (final fallback). Estimated word count: {actual_word_count}")
            else: 
                app.logger.error("Gemini returned empty response (final fallback).")
                actual_word_count = 0
        except Exception as e_gen_fallback: 
            app.logger.error(f"Error during fallback direct script generation: {e_gen_fallback}")
            script = None 
            actual_word_count = 0
    
    if not script:
        err = 'Gemini returned empty script for voiceover (after all attempts).'
        app.logger.error(err)
        return {'error_message': err, 'voiceover_script': None}
    
    app.logger.info(f"Final voiceover script generated. Word count: {actual_word_count if actual_word_count is not None else 'N/A'}.")
    return {'voiceover_script': script, 'error_message': None}

# if __name__ == "__main__":
# # Test the function with a dummy state
# # This part will be updated in test_generate_voice_script.py instead
# pass
