import os
import shutil
import subprocess
from typing import Dict, Any
from flask import url_for

from manim_video_generator.config import app, STATIC_VIDEOS
from manim_video_generator.state import WorkflowState


def combine_final_video_audio_node(state: WorkflowState) -> Dict[str, Any]:
    """Combines the silent video and TTS audio into the final MP4."""
    vid = state.video_path
    aud = state.audio_path
    req = state.request_id

    app.logger.info("--- combine_final_video_audio ---")

    # Ensure video exists
    if not vid or not os.path.exists(vid):
        err = "Cannot combine: Missing silent video path."
        app.logger.error(err)
        return {'error_message': err}

    final_name = f"{req}_final.mp4"
    output_path = os.path.join(STATIC_VIDEOS, final_name)
    os.makedirs(STATIC_VIDEOS, exist_ok=True)

    # If no audio, just copy silent video
    if not aud or not os.path.exists(aud):
        app.logger.warning("Missing audio; copying silent video to final output.")
        try:
            shutil.copy(vid, output_path)
            url = url_for('static', filename=f'videos/{final_name}')
            return {'final_video_path': output_path, 'final_video_url': url}
        except Exception as e:
            err = f"Copy fallback failed: {e}"
            app.logger.error(err)
            return {'error_message': err}

    # Combine video & audio with ffmpeg
    cmd = [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y", "-i", vid, "-i", aud,
        "-c:v", "copy", "-c:a", "aac", "-shortest", output_path,
    ]
    app.logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=180)
        app.logger.info("FFmpeg combination successful.")
        url = url_for('static', filename=f'videos/{final_name}')
        return {'final_video_path': output_path, 'final_video_url': url, 'error_message': None}
    except subprocess.CalledProcessError as e:
        err = f"FFmpeg failed (code {e.returncode}): {e.stderr[:500]}"
        app.logger.error(err)
        # Fallback to silent only
        try:
            shutil.copy(vid, output_path)
            url = url_for('static', filename=f'videos/{final_name}')
            app.logger.warning("FFmpeg failed; provided silent video instead.")
            return {'final_video_path': output_path, 'final_video_url': url, 'error_message': err}
        except Exception as copy_e:
            err2 = f"Fallback copy also failed: {copy_e}"
            app.logger.error(err2)
            return {'error_message': err2}
    except subprocess.TimeoutExpired:
        err = "FFmpeg command timed out during combination."
        app.logger.error(err)
        return {'error_message': err} 