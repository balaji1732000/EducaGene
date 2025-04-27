import os
from typing import Dict, Any
import azure.cognitiveservices.speech as speechsdk

from manim_video_generator.state import WorkflowState
from manim_video_generator.config import app


def generate_audio_node(state: WorkflowState) -> Dict[str, Any]:
    """TTS: Converts voiceover script into audio file."""
    app.logger.info("--- generate_audio_node ---")
    script = state.voiceover_script
    if not script:
        return {'error_message': 'No voiceover script provided', 'audio_path': None}
    audio_dir = os.path.join(state.temp_dir, 'audio')
    os.makedirs(audio_dir, exist_ok=True)
    out_path = os.path.join(audio_dir, f"{state.request_id}_audio.wav")
    cfg = speechsdk.SpeechConfig(subscription=os.getenv('AZURE_SPEECH_KEY'), region=os.getenv('AZURE_SPEECH_REGION'))
    cfg.speech_synthesis_voice_name = 'de-DE-Florian:DragonHDLatestNeural'
    audio_cfg = speechsdk.audio.AudioOutputConfig(filename=out_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_cfg)
    ssml = f"""<speak version='1.0' xml:lang='en-US'>
<voice name='en-US-AvaMultilingualNeural'>{script.replace('\n\n', '<break time="100ms"/>')}</voice>
</speak>"""
    result = synthesizer.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        app.logger.error("TTS failed to generate audio.")
        return {'error_message': 'TTS failed', 'audio_path': None}
    app.logger.info(f"Generated audio at {out_path}")
    return {'audio_path': out_path, 'error_message': None} 