import os
import subprocess
import json # Added for JSON parsing
from typing import Dict, Any, Optional, Tuple

from google import genai
from google.genai import types
from manim_video_generator.config import app
from manim_video_generator.utils import upload_to_gemini, wait_for_files_active
from manim_video_generator.state import WorkflowState
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))  # Initialize Gemini client with API key

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
            model="gemini-2.5-flash-preview-04-17",
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

def _convert_timestamped_to_plain_script(segments: list[Dict[str, str]]) -> str:
    """Converts a list of timestamped script segments to a single plain text script."""
    if not segments:
        return ""
    plain_script_parts = [segment.get("text", "").strip() for segment in segments if segment.get("text")]
    return " ".join(plain_script_parts)


def generate_final_script_node(video_path, language) -> Dict[str, Any]:
    """Generates a voiceover script via Gemini for the combined video in the target language."""
    app.logger.info("--- generate_final_script_node (Gemini voiceover) ---")
    video_path = video_path
    language = language

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
            max_output_tokens=65000,
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



import os
from typing import Dict, Any, Optional, List
import azure.cognitiveservices.speech as speechsdk
import traceback
import json # Import json
import html # Import html for escaping

# Pydantic is not needed here as we are parsing the JSON manually
# from pydantic import BaseModel, Field

from manim_video_generator.state import WorkflowState
from manim_video_generator.config import app, APP_ROOT # Import APP_ROOT

# --- Helper Function to Get Voice Name ---
# def _get_voice_name_for_locale(locale: str, voice_data_path: str = "text_to_speech.json") -> Optional[str]:
#     """
#     Loads voice data from a JSON file and finds the first matching voice ShortName for the given locale.
#     """
#     default_voice = "en-US-AvaMultilingualNeural" # Default fallback voice
#     # Construct full path relative to project root (assuming text_to_speech.json is in manim-video-generator folder)
#     full_path = os.path.join(APP_ROOT, voice_data_path)

#     if not os.path.exists(full_path):
#         app.logger.error(f"Voice data file not found at: {full_path}. Using default voice '{default_voice}'.")
#         return default_voice

#     try:
#         with open(full_path, 'r', encoding='utf-8') as f:
#             voice_data = json.load(f)

#         if not isinstance(voice_data, list):
#             app.logger.error(f"Invalid format in {full_path}: Expected a JSON list. Using default voice '{default_voice}'.")
#             return default_voice

#         # Find the first voice matching the locale
#         for voice_info in voice_data:
#             if isinstance(voice_info, dict) and voice_info.get("Locale") == locale:
#                 voice_name = voice_info.get("ShortName")
#                 if voice_name:
#                     app.logger.info(f"Found voice '{voice_name}' for locale '{locale}'.")
#                     return voice_name
#                 else:
#                      app.logger.warning(f"Found matching locale '{locale}' but 'ShortName' is missing. Skipping.")

#         # If no specific voice is found for the locale, try finding a multilingual voice as a better fallback
#         app.logger.warning(f"No specific voice found for locale '{locale}' in {full_path}. Searching for a suitable multilingual voice...")
#         for voice_info in voice_data:
#              # Heuristic: Check if 'Multilingual' is in the name and if the locale might be generally supported
#              # This is imperfect; Azure documentation is the best source for multilingual support.
#              if isinstance(voice_info, dict) and "MultilingualNeural" in voice_info.get("ShortName", ""):
#                   # Prioritize Ava if available
#                   if "en-US-AvaMultilingualNeural" in voice_info.get("ShortName", ""):
#                        voice_name = "en-US-AvaMultilingualNeural"
#                        app.logger.info(f"Using default multilingual voice '{voice_name}' for locale '{locale}'.")
#                        return voice_name
#                   # Otherwise take the first multilingual found (could be improved)
#                   voice_name = voice_info.get("ShortName")
#                   if voice_name:
#                        app.logger.info(f"Using first available multilingual voice '{voice_name}' for locale '{locale}'.")
#                        return voice_name

#         # Final fallback if no specific or multilingual voice found
#         app.logger.warning(f"No specific or suitable multilingual voice found for locale '{locale}'. Using absolute default '{default_voice}'.")
#         return default_voice

#     except json.JSONDecodeError:
#         app.logger.error(f"Error decoding JSON from {full_path}. Using default voice '{default_voice}'.")
#         return default_voice
#     except Exception as e:
#         app.logger.error(f"Error reading or processing {full_path}: {e}. Using default voice '{default_voice}'.")
#         return default_voice

# --- Original Node Function (Modified) ---
def generate_audio_node(voice_over_script) -> Dict[str, Any]:
    """TTS: Converts voiceover script into audio file using a dynamically selected voice."""
    app.logger.info("--- generate_audio_node ---")
    script = voice_over_script
    language = "en-US" # Get target language (locale)
    if not script:
        return {'error_message': 'No voiceover script provided', 'audio_path': None}

    # Using static voice and language as per user's local test file structure
    voice_name = "en-US-AvaMultilingualNeural" # Static voice for testing
    # language parameter is already "en-US" from the __main__ block for this local function

    # Ensure audio_dir is the current working directory for the test output
    audio_dir = "." # Output audio to the current directory
    # No need for os.makedirs(audio_dir, exist_ok=True) if audio_dir is "."
    
    # Use a fixed name for the test output file, or make it unique if running multiple tests
    request_id_for_test = "test_audio_001" # Example request_id for filename
    out_path = os.path.join(audio_dir, f"{request_id_for_test}_audio.wav")
    app.logger.info(f"Test audio output path: {os.path.abspath(out_path)}")

    try:
        cfg = speechsdk.SpeechConfig(subscription=os.getenv('AZURE_SPEECH_KEY'), region=os.getenv('AZURE_SPEECH_REGION'))
        cfg.speech_synthesis_voice_name = voice_name
    except Exception as e:
         app.logger.error(f"Failed to configure Azure Speech SDK: {e}")
         return {'error_message': f"Azure Speech SDK config error: {e}", 'audio_path': None}

    audio_cfg = speechsdk.audio.AudioOutputConfig(filename=out_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_cfg)

    # SSML with target language and the selected voice
    # Escape special XML characters in the script before inserting into SSML
    escaped_script = html.escape(script) 
    formatted_text = escaped_script.replace('\n\n', '<break time="100ms"/>')
    ssml = f"""<speak version='1.0' xml:lang='{language}'>
<voice name='{voice_name}'>{formatted_text}</voice>
</speak>"""
    app.logger.info(f"Generating audio with language '{language}' and voice '{voice_name}'")
    app.logger.debug(f"Sending SSML to Azure TTS:\n{ssml}")

    try:
        result = synthesizer.speak_ssml_async(ssml).get()

        # Check result and log cancellation details on failure
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            app.logger.info(f"Generated audio at {out_path}")
            return {'audio_path': out_path, 'error_message': None}
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            err_msg = f"TTS failed: Cancelled. Reason: {cancellation_details.reason}"
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                if cancellation_details.error_details:
                    err_msg += f" | Error Details: {cancellation_details.error_details}"
            app.logger.error(err_msg)
            return {'error_message': err_msg, 'audio_path': None}
        else:
            err_msg = f"TTS failed with unexpected reason: {result.reason}"
            app.logger.error(err_msg)
            return {'error_message': err_msg, 'audio_path': None}

    except Exception as e:
        err_msg = f"Exception during Azure TTS call: {e}"
        app.logger.error(err_msg)
        app.logger.debug(traceback.format_exc())
        return {'error_message': err_msg, 'audio_path': None}



if __name__ == "__main__":
    # Test the function with a dummy state
    
    video_path="C:/Users/ASUS/Documents/Video generation/manim-video-generator/tmp_requests/req_20250513_185159_4218fc/final_build/req_20250513_185159_4218fc_combined_video.mp4"
    language_for_test = "en-US" # Static language for this test
    
    script_result = generate_final_script_node(video_path, language_for_test)
    
    print("\n--- Script Generation Result (Test) ---")
    print(json.dumps(script_result, indent=2))

    voice_script_text = script_result.get('voiceover_script')
    
    if voice_script_text and not script_result.get('error_message'):
        app.logger.info("Test script generated successfully. Proceeding to audio generation.")
        
        # Call the local generate_audio_node
        audio_result = generate_audio_node(voice_script_text) # Pass only the script text
        
        print("\n--- Audio Generation Result (Test) ---")
        print(json.dumps(audio_result, indent=2))
        
        if audio_result.get('audio_path') and not audio_result.get('error_message'):
            app.logger.info(f"Test audio generated successfully at: {audio_result.get('audio_path')}")
        else:
            app.logger.error(f"Test audio generation failed: {audio_result.get('error_message')}")
            
    elif script_result.get('error_message'):
        app.logger.error(f"Test script generation failed: {script_result.get('error_message')}")
    else:
        app.logger.error("Test script generation resulted in no script and no error message.")

    app.logger.info("--- Test Run Finished (Local Functions) ---")
