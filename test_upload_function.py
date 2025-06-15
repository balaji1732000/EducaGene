import os
import logging
from dotenv import load_dotenv

# Configure basic logging for the test
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Attempt to import the upload function
try:
    from manim_video_generator.utils import upload_to_blob_storage
except ImportError:
    logger.error("Failed to import 'upload_to_blob_storage' from 'manim_video_generator.utils'.")
    logger.error("Ensure the script is run from the project root or PYTHONPATH is set correctly.")
    upload_to_blob_storage = None # Define it as None so the script doesn't break immediately

def create_dummy_file(filepath="dummy_upload_test.txt", content="Hello Azure Blob Storage!"):
    """Creates a dummy file for testing uploads."""
    try:
        with open(filepath, "w") as f:
            f.write(content)
        logger.info(f"Created dummy file: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to create dummy file {filepath}: {e}")
        return None

def test_upload_main():
    """
    Main function to test the Azure Blob Storage upload.
    """
    if not upload_to_blob_storage:
        logger.error("upload_to_blob_storage function not available. Exiting test.")
        return

    logger.info("--- Starting Azure Blob Upload Test ---")
    
    # Load environment variables from .env file
    # This is crucial for Azure credentials
    load_dotenv() 
    
    # 1. Define a sample local file to upload
    # For a robust test, we create a dummy file.
    dummy_file_name = "test_upload_sample.txt"
    local_file_to_upload = create_dummy_file(dummy_file_name, "This is a test file for Azure Blob Storage upload.")
    
    if not local_file_to_upload:
        logger.error("Could not create dummy file for upload. Aborting test.")
        return

    # 2. Define a request_id (used for blob naming in the function)
    test_request_id = "test_upload_req_001"
    
    # 3. Call the upload function
    logger.info(f"Attempting to upload '{local_file_to_upload}' with request_id '{test_request_id}'...")
    uploaded_blob_url = upload_to_blob_storage(local_file_to_upload, test_request_id)
    
    # 4. Print the result
    if uploaded_blob_url:
        logger.info(f"SUCCESS: File uploaded to Azure Blob Storage.")
        logger.info(f"Blob URL: {uploaded_blob_url}")
    else:
        logger.error("FAILURE: File upload to Azure Blob Storage failed.")
        logger.error("Please check .env for AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER_NAME.")
        logger.error("Also ensure the Azure Storage account and container exist and have correct permissions.")

    # 5. Clean up the dummy file
    if os.path.exists(local_file_to_upload):
        try:
            os.remove(local_file_to_upload)
            logger.info(f"Cleaned up dummy file: {local_file_to_upload}")
        except Exception as e:
            logger.error(f"Failed to clean up dummy file {local_file_to_upload}: {e}")
            
    logger.info("--- Azure Blob Upload Test Finished ---")

if __name__ == "__main__":
    # Note: The `upload_to_blob_storage` function uses `app.logger`.
    # For this standalone test, `app.logger` might not be configured as in the Flask app.
    # The `logging` configured at the top of this file will catch messages from this script's logger.
    # Messages from `app.logger` inside `upload_to_blob_storage` might go to a default handler
    # or not appear if `app` isn't fully initialized here. This is a common challenge with
    # testing utility functions that rely on app-contextual loggers.
    # For a simple test, direct print statements or this script's logger are sufficient.
    
    # To make app.logger work here if needed, one might need to do:
    # from manim_video_generator.config import app
    # app.testing = True # Or some other way to initialize parts of the app context
    # However, for a utility function, it's often better if it takes a logger instance or uses standard logging.
    
    test_upload_main()
