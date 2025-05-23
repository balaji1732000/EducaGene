import os
import re
import json
import logging
import time
from google import genai
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, ContentSettings # Added Blob imports
from typing import Optional
import traceback
from manim_video_generator.config import app
import cv2 # Added for CV functions
import numpy as np # Added for CV functions
from dotenv import load_dotenv

load_dotenv()
# --- Existing Functions ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def clean_code_string(code_string: str) -> str:
    """Removes markdown fences and leading/trailing whitespace."""
    if code_string.startswith("```python"):
        code_string = code_string[9:]
    elif code_string.startswith("```"):
        code_string = code_string[3:]
    if code_string.endswith("```"):
        code_string = code_string[:-3]
    return code_string.strip()

def fix_inline_latex(code: str) -> str:
    """Finds single $...$ and replaces with $$...$$ for Manim compatibility."""
    # This regex finds $...$ that are not $$...$$
    # It uses negative lookarounds to ensure the $ isn't preceded or followed by another $
    pattern = r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)"
    # Replacement function adds the extra $
    repl = r"$$\1$$"
    fixed_code, count = re.subn(pattern, repl, code)
    if count > 0:
        app.logger.info(f"Replaced {count} single $...$ with $$...$$")
    return fixed_code

# def estimate_scene_time(script_code: str) -> float:
#     """Estimates duration by summing wait times and default play times."""
#     wait_time = sum(float(t) for t in re.findall(r"self\.wait\((.*?)\)", script_code))
#     play_count = len(re.findall(r"self\.play\(", script_code))
#     # Assume default 1s run_time for self.play if not specified
#     # This is a rough estimate
#     estimated_duration = wait_time + play_count * 1.0
#     app.logger.info(f"Estimated script duration: {estimated_duration:.2f}s (Wait: {wait_time}s, Plays: {play_count})")
#     return estimated_duration


def upload_to_gemini(path):
    """Uploads the given file to Gemini using client.files.upload."""
    
    file = client.files.upload(file=path)  # Use client.files.upload
    app.logger.info(f"Uploaded file '{file.name}' to Gemini as: {file.uri}")
    return file

def wait_for_files_active(file, max_wait_seconds=600):  
    """Waits for the given Gemini file to be active using client.files.get."""
    start_time = time.time()
    
    while True:  # Keep checking until file is active or timeout
        elapsed_time = time.time() - start_time
        if elapsed_time > max_wait_seconds:
            raise TimeoutError(f"File {file.name} did not become active within {max_wait_seconds} seconds.")

        file_info = client.files.get(name=file.name)  # Use client.files.get to get file info
        
        if file_info.state.name == "ACTIVE":
            print("\nFile is active.")
            break  # File is active, exit the loop
        elif file_info.state.name == "PROCESSING":
            print(".", end="")
            time.sleep(10)
        else:
            raise ValueError(f"File {file.name} failed processing: {file_info.state.name}")
# --- New Azure Blob Storage Upload Function ---

def upload_to_blob_storage(local_file_path: str, request_id: str) -> Optional[str]:
    """
    Uploads a local file to Azure Blob Storage and returns its URL.

    Args:
        local_file_path: The path to the local file to upload.
        request_id: The unique request ID, used for naming the blob.

    Returns:
        The URL of the uploaded blob, or None if upload fails.
    """
    app.logger.info(f"Attempting to upload '{local_file_path}' to Azure Blob Storage...")

    connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING").strip('"')
    app.logger.debug(f"Using connection string: {os.getenv("AZURE_STORAGE_CONNECTION_STRING")}")
    app.logger.debug(f"Using container name: {os.getenv("AZURE_STORAGE_CONTAINER_NAME")}")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME").strip('"')

    if not connect_str or connect_str == "YOUR_CONNECTION_STRING_HERE":
        app.logger.error("Azure Storage connection string not configured in .env file.")
        return None
    if not container_name or container_name == "YOUR_CONTAINER_NAME_HERE":
        app.logger.error("Azure Storage container name not configured in .env file.")
        return None
    if not os.path.exists(local_file_path):
        app.logger.error(f"Local file not found for upload: {local_file_path}")
        return None

    # Create a unique blob name using the request ID and original filename
    blob_name = f"{request_id}_{os.path.basename(local_file_path)}"
    # Sanitize blob name if necessary (e.g., replace spaces), although request_id should be safe
    blob_name = blob_name.replace(" ", "_")

    try:
        # Create the BlobServiceClient object
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)

        # Get a client to interact with the specified blob
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        # Define content settings (especially important for video)
        file_extension = os.path.splitext(local_file_path)[1].lower()
        content_type = None
        if file_extension == ".mp4":
            content_type = "video/mp4"
        elif file_extension == ".wav":
            content_type = "audio/wav"
        # Add other types as needed

        content_settings = ContentSettings(content_type=content_type) if content_type else None

        app.logger.info(f"Uploading to container '{container_name}' as blob '{blob_name}'...")

        # Upload the file
        with open(local_file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)

        blob_url = blob_client.url
        app.logger.info(f"Upload successful. Blob URL: {blob_url}")
        return blob_url

    except Exception as ex:
        app.logger.error(f"Error uploading file to Azure Blob Storage: {ex}")
        app.logger.debug(traceback.format_exc())
        return None

# --- CV Overlap Detection Functions ---
# (Moved from utils/cv_flags.py)

# Configure logger for this module (or use app.logger if preferred and accessible globally)
# Using __name__ will make log messages come from 'manim_video_generator.utils'
cv_logger = logging.getLogger(__name__) 

def _iou(boxA, boxB):
    """
    Compute the Intersection over Union (IoU) of two bounding boxes.
    Each box is (x, y, w, h).
    """
    # Determine the (x, y)-coordinates of the intersection rectangle
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

    # Compute the area of intersection rectangle
    interArea = max(0, xB - xA) * max(0, yB - yA)

    # Compute the area of both the prediction and ground-truth
    # rectangles
    boxAArea = boxA[2] * boxA[3]
    boxBArea = boxB[2] * boxB[3]

    # Compute the intersection over union by taking the intersection
    # area and dividing it by the sum of prediction + ground-truth
    # areas - the intersection area
    iou_val = interArea / float(boxAArea + boxBArea - interArea) if (boxAArea + boxBArea - interArea) > 0 else 0

    # Return the intersection over union value
    return iou_val

def flag_overlap_frames(
    video_path: str, 
    iou_thr: float = 0.05, 
    sample_rate: int = 8, 
    contour_threshold: int = 180,
    min_contour_area: int = 50
):
    """
    Returns a dict {frame_idx: [{"bboxA": (x,y,w,h), "bboxB": (x,y,w,h), "iou": float}, ...], ...}
    for frames where any two contours overlap > iou_thr. Filters contours smaller than min_contour_area.
    Samples 1 / sample_rate frames for speed.
    contour_threshold: Grayscale value (0-255) for binary thresholding.
    """
    overlaps = {}
    cap = None
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            cv_logger.error(f"Error: Could not open video file {video_path}")
            return {"error": f"Could not open video file {video_path}"}

        f_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if f_idx % sample_rate == 0:
                try:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    # Apply binary threshold
                    _, th = cv2.threshold(gray, contour_threshold, 255, cv2.THRESH_BINARY)
                    # Find contours using RETR_LIST to get all contours
                    cs, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                    
                    # Get bounding boxes for contours, filtering by the provided min_contour_area
                    bbs = [cv2.boundingRect(c) for c in cs if cv2.contourArea(c) > min_contour_area]

                    # Naive O(n^2) comparison; fine for typical number of mobjects in Manim
                    frame_overlaps = []
                    for i in range(len(bbs)):
                        for j in range(i + 1, len(bbs)):
                            iou = _iou(bbs[i], bbs[j])
                            if iou > iou_thr:
                                frame_overlaps.append(
                                    {"bboxA": tuple(bbs[i]), "bboxB": tuple(bbs[j]), "iou": round(iou, 3)} # Ensure tuples for JSON
                                )
                    
                    # If overlaps were found in this frame, sort by IoU and keep top N
                    if frame_overlaps:
                        # Sort by 'iou' in descending order
                        frame_overlaps.sort(key=lambda x: x['iou'], reverse=True)
                        # Keep only top N (e.g., 3)
                        overlaps[f_idx] = frame_overlaps[:3] 
                                
                except Exception as e:
                    cv_logger.warning(f"Could not process frame {f_idx} in {video_path}: {e}")
            f_idx += 1
        
        if not overlaps and f_idx == 0: # Video was read but no frames processed (e.g. bad video)
             cv_logger.warning(f"No frames processed for video {video_path}. It might be empty or corrupted.")
             return {"warning": f"No frames processed for video {video_path}. It might be empty or corrupted.", "frames_processed": 0}


    except Exception as e:
        cv_logger.error(f"Error processing video {video_path} for overlap detection: {e}", exc_info=True)
        return {"error": f"General error processing video {video_path}: {e}"}
    finally:
        if cap:
            cap.release()
    
    cv_logger.info(f"Overlap detection complete for {video_path}. Found overlaps in {len(overlaps)} sampled frames.")
    return overlaps

# Note: The if __name__ == '__main__': block from cv_flags.py is not moved here,
# as it was for direct testing of that module. Testing for utils.py would be separate.
# if __name__ == '__main__':
#     # Example usage of the functions in this module
#     video_path = "C:/Users/ASUS/Documents/Video generation/manim-video-generator/tmp_requests/req_20250507_215729_1fe5d1/final_build/req_20250507_215729_1fe5d1_combined_video.mp4"
#     file = upload_to_gemini(video_path)
#     wait_for_files_active(file.name)
#     print(f"Uploaded file: {file.name}")