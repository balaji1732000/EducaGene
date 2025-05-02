import os
from typing import Dict, Any, Optional, List
import azure.cognitiveservices.speech as speechsdk
import traceback
import json # Import json

# Pydantic is not needed here as we are parsing the JSON manually
# from pydantic import BaseModel, Field

from manim_video_generator.state import WorkflowState
from manim_video_generator.config import app, APP_ROOT # Import APP_ROOT

# --- Helper Function to Get Voice Name ---
def _get_voice_name_for_locale(locale: str, voice_data_path: str = "text_to_speech.json") -> Optional[str]:
    """
    Loads voice data from a JSON file and finds the first matching voice ShortName for the given locale.
    """
    default_voice = "en-US-AvaMultilingualNeural" # Default fallback voice
    # Construct full path relative to project root (assuming text_to_speech.json is in manim-video-generator folder)
    full_path = os.path.join(APP_ROOT, voice_data_path)

    if not os.path.exists(full_path):
        app.logger.error(f"Voice data file not found at: {full_path}. Using default voice '{default_voice}'.")
        return default_voice

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            voice_data = json.load(f)

        if not isinstance(voice_data, list):
            app.logger.error(f"Invalid format in {full_path}: Expected a JSON list. Using default voice '{default_voice}'.")
            return default_voice

        # Find the first voice matching the locale
        for voice_info in voice_data:
            if isinstance(voice_info, dict) and voice_info.get("Locale") == locale:
                voice_name = voice_info.get("ShortName")
                if voice_name:
                    app.logger.info(f"Found voice '{voice_name}' for locale '{locale}'.")
                    return voice_name
                else:
                     app.logger.warning(f"Found matching locale '{locale}' but 'ShortName' is missing. Skipping.")

        # If no specific voice is found for the locale, try finding a multilingual voice as a better fallback
        app.logger.warning(f"No specific voice found for locale '{locale}' in {full_path}. Searching for a suitable multilingual voice...")
        for voice_info in voice_data:
             # Heuristic: Check if 'Multilingual' is in the name and if the locale might be generally supported
             # This is imperfect; Azure documentation is the best source for multilingual support.
             if isinstance(voice_info, dict) and "MultilingualNeural" in voice_info.get("ShortName", ""):
                  # Prioritize Ava if available
                  if "en-US-AvaMultilingualNeural" in voice_info.get("ShortName", ""):
                       voice_name = "en-US-AvaMultilingualNeural"
                       app.logger.info(f"Using default multilingual voice '{voice_name}' for locale '{locale}'.")
                       return voice_name
                  # Otherwise take the first multilingual found (could be improved)
                  voice_name = voice_info.get("ShortName")
                  if voice_name:
                       app.logger.info(f"Using first available multilingual voice '{voice_name}' for locale '{locale}'.")
                       return voice_name

        # Final fallback if no specific or multilingual voice found
        app.logger.warning(f"No specific or suitable multilingual voice found for locale '{locale}'. Using absolute default '{default_voice}'.")
        return default_voice

    except json.JSONDecodeError:
        app.logger.error(f"Error decoding JSON from {full_path}. Using default voice '{default_voice}'.")
        return default_voice
    except Exception as e:
        app.logger.error(f"Error reading or processing {full_path}: {e}. Using default voice '{default_voice}'.")
        return default_voice

# --- Original Node Function (Modified) ---
def generate_audio_node(state: WorkflowState) -> Dict[str, Any]:
    """TTS: Converts voiceover script into audio file using a dynamically selected voice."""
    app.logger.info("--- generate_audio_node ---")
    script = state.voiceover_script
    language = state.language # Get target language (locale)
    if not script:
        return {'error_message': 'No voiceover script provided', 'audio_path': None}

    # Dynamically get the voice name using the helper function
    voice_name = _get_voice_name_for_locale(language)
    if not voice_name:
         # This case should ideally be handled by the default in _get_voice_name_for_locale,
         # but as a safeguard:
         app.logger.error("Failed to determine a voice name. Cannot proceed with TTS.")
         return {'error_message': 'Failed to determine voice name for TTS.', 'audio_path': None}

    audio_dir = os.path.join(state.temp_dir, 'audio')
    os.makedirs(audio_dir, exist_ok=True)
    out_path = os.path.join(audio_dir, f"{state.request_id}_audio.wav")

    try:
        cfg = speechsdk.SpeechConfig(subscription=os.getenv('AZURE_SPEECH_KEY'), region=os.getenv('AZURE_SPEECH_REGION'))
        cfg.speech_synthesis_voice_name = voice_name # Use dynamically selected voice
    except Exception as e:
         app.logger.error(f"Failed to configure Azure Speech SDK: {e}")
         return {'error_message': f"Azure Speech SDK config error: {e}", 'audio_path': None}

    audio_cfg = speechsdk.audio.AudioOutputConfig(filename=out_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_cfg)

    # SSML with target language and the selected voice
    formatted_text = script.replace('\n\n', '<break time="100ms"/>')
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
