import os
import shutil
import subprocess
from typing import Dict, Any
from flask import url_for

from manim_video_generator.config import app, STATIC_VIDEOS
from manim_video_generator.state import WorkflowState
from manim_video_generator.utils import upload_to_blob_storage # Import the upload function


def combine_final_video_audio_node(state: WorkflowState) -> Dict[str, Any]:
    """Combines the silent video and TTS audio, uploads to blob storage, and returns the URL."""
    vid = state.video_path
    aud = state.audio_path
    req = state.request_id
    td = state.temp_dir # Get temp dir for local path construction

    app.logger.info("--- combine_final_video_audio ---")

    # Ensure video exists
    if not vid or not os.path.exists(vid):
        err = "Cannot combine: Missing silent video path."
        app.logger.error(err)
        return {'error_message': err}

    # Define local output path (still needed temporarily)
    # Using temp dir instead of static for intermediate file
    local_final_dir = os.path.join(td, 'final_build')
    os.makedirs(local_final_dir, exist_ok=True)
    final_name = f"{req}_final.mp4"
    local_output_path = os.path.join(local_final_dir, final_name)

    # If no audio, just copy silent video to the temporary final path
    if not aud or not os.path.exists(aud):
        app.logger.warning("Missing audio; copying silent video to temporary final path.")
        try:
            shutil.copy(vid, local_output_path)
            app.logger.info(f"Copied silent video to {local_output_path}")
        except Exception as e:
            err = f"Copy fallback failed: {e}"
            app.logger.error(err)
            return {'error_message': err}
    else:
        # Combine video & audio with ffmpeg to the temporary final path
        cmd = [
            shutil.which("ffmpeg") or "ffmpeg",
            "-y", "-i", vid, "-i", aud,
            "-c:v", "copy", "-c:a", "aac", "-shortest", local_output_path,
        ]
        app.logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=180)
            app.logger.info("FFmpeg combination successful.")
        except subprocess.CalledProcessError as e:
            err = f"FFmpeg failed (code {e.returncode}): {e.stderr[:500]}"
            app.logger.error(err)
            # Fallback to silent only
            try:
                shutil.copy(vid, local_output_path)
                app.logger.warning(f"FFmpeg failed; copied silent video to {local_output_path} instead.")
            except Exception as copy_e:
                err2 = f"Fallback copy also failed: {copy_e}"
                app.logger.error(err2)
                return {'error_message': err2}
        except subprocess.TimeoutExpired:
            err = "FFmpeg command timed out during combination."
            app.logger.error(err)
            return {'error_message': err}
        except Exception as e:
             err = f"Unexpected error during ffmpeg combination: {e}"
             app.logger.error(err, exc_info=True)
             return {'error_message': err}

    # --- Upload to Azure Blob Storage ---
    blob_url = None
    if os.path.exists(local_output_path):
        blob_url = upload_to_blob_storage(local_output_path, req)
        if blob_url:
            app.logger.info(f"Successfully uploaded final video to Azure Blob Storage: {blob_url}")
            # Optionally delete local file after successful upload
            try:
                os.remove(local_output_path)
                app.logger.info(f"Removed local temporary file: {local_output_path}")
            except OSError as e:
                app.logger.warning(f"Could not remove local file {local_output_path}: {e}")
        else:
            # Upload failed, log error but maybe still return local path/URL if needed?
            # For now, we'll return an error if upload fails.
            app.logger.error("Azure Blob Storage upload failed.")
            return {'error_message': 'Failed to upload final video to Azure Blob Storage.'}
    else:
         app.logger.error(f"Combined video file not found at expected location: {local_output_path}")
         return {'error_message': 'Combined video file missing before upload.'}

    # Return the Blob URL
    return {'final_video_path': None, # No longer storing local final path in state
            'final_video_url': blob_url,
            'error_message': None}
