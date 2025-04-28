import os
import subprocess
import shutil
from typing import Dict, Any

from manim import config as manim_config
from manim_video_generator.config import app, APP_ROOT
from manim_video_generator.state import WorkflowState


def render_combined_video_node(state: WorkflowState) -> Dict[str, Any]:
    """Renders the single combined scene class from the script."""
    script_path = state.full_script_path
    cls_name = state.scene_class_name
    td = state.temp_dir
    req_id = state.request_id

    app.logger.info(f"--- render_combined_video (Class: {cls_name}) ---")

    # Verify script path exists
    if not script_path or not os.path.exists(script_path):
        err = "Missing script path for rendering."
        app.logger.error(err)
        return {'rendering_error': err, 'video_path': None}

    media_dir = os.path.join(td, 'scene_media')
    output_filename = f'{req_id}_combined_video.mp4'
    os.makedirs(media_dir, exist_ok=True)

    cmd = [
        shutil.which('manim') or 'manim', 'render', '-qh',
        '--format', 'mp4',
        '--verbosity', 'DEBUG',
        '--media_dir', media_dir,
        '-o', output_filename,
        script_path,
    ]
    app.logger.info(f"Running Manim command: {' '.join(cmd)}")

    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=APP_ROOT,
            timeout=600, check=False, encoding='utf-8', errors='replace'
        )
        if res.stdout:
            app.logger.debug(f"Manim stdout:\n{res.stdout}")
        if res.stderr:
            app.logger.debug(f"Manim stderr:\n{res.stderr}")

        if res.returncode != 0:
            full_stderr = res.stderr or ''
            traceback_start_marker = "Traceback (most recent call last):"
            traceback_start_index = full_stderr.rfind(traceback_start_marker) # Find the last occurrence

            if traceback_start_index != -1:
                # Extract from the start of the traceback onwards
                extracted_error = full_stderr[traceback_start_index:]
                app.logger.info("Extracted traceback from Manim stderr.")
            else:
                # Fallback: Use the last ~1500 characters if traceback marker not found
                extracted_error = full_stderr[-1500:]
                app.logger.warning("Traceback marker not found in Manim stderr. Using tail end.")

            app.logger.error(f"Manim render failed (Code {res.returncode}). Extracted Error Info:\n{extracted_error}")
            return {'rendering_error': extracted_error, 'video_path': None}

        # Determine expected output path
        script_base = os.path.splitext(os.path.basename(script_path))[0]
        quality_folder = '1080p60' if 'high' in manim_config.quality else '720p30' if 'medium' in manim_config.quality else '480p15'
        expected_path = os.path.join(media_dir, 'videos', script_base, quality_folder, output_filename)
        fallback = os.path.join(media_dir, output_filename)
        video_path = expected_path if os.path.exists(expected_path) else fallback
        if not os.path.exists(video_path):
            err = f"Rendered video not found at {expected_path} or {fallback}"
            app.logger.error(err)
            return {'rendering_error': err, 'video_path': None}

        # Move to final_build
        final_dir = os.path.join(td, 'final_build')
        os.makedirs(final_dir, exist_ok=True)
        target = os.path.join(final_dir, output_filename)
        shutil.move(video_path, target)
        app.logger.info(f"Moved combined video to {target}")
        return {'rendering_error': None, 'video_path': target}

    except subprocess.TimeoutExpired:
        err = f"Manim render timed out after 600s ({cls_name})"
        app.logger.error(err)
        return {'rendering_error': err, 'video_path': None}
    except Exception as e:
        err = f"Unexpected error during render: {e}"
        app.logger.error(err, exc_info=True)
        return {'rendering_error': err, 'video_path': None}
