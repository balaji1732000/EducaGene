import os
import sys
import logging
from logging import FileHandler
from dotenv import load_dotenv
from flask import Flask
from manim import config as manim_config
import google.generativeai as genai

# Load environment variables (Moved to main.py)
# load_dotenv()

# Project root (parent of this config.py)
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Directories
TMP_BASE = os.path.join(APP_ROOT, 'tmp_requests')
STATIC_VIDEOS = os.path.join(APP_ROOT, 'static', 'videos')
MEDIA_DIR = os.path.join(APP_ROOT, 'media_manim')

# Ensure directories exist
for directory in [TMP_BASE, STATIC_VIDEOS]:
    os.makedirs(directory, exist_ok=True)
for sub in ['log', 'videos', 'tex', 'texts', 'images']:
    os.makedirs(os.path.join(MEDIA_DIR, sub), exist_ok=True)

# Configure Manim
manim_config.media_dir = MEDIA_DIR
manim_config.video_dir = os.path.join(MEDIA_DIR, 'videos')
manim_config.quality = 'high_quality'
manim_config.format = 'mp4'
manim_config.renderer = 'cairo'
manim_config.verbosity = 'DEBUG'

# Configure logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Console handler
tream_handler = logging.StreamHandler(sys.stdout)
tream_handler.setFormatter(formatter)
root_logger.addHandler(tream_handler)

# File handler
log_file = os.path.join(APP_ROOT, 'app.log')
file_handler = FileHandler(log_file, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)


# go up one level from this file:
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir)
)

TEMPLATE_FOLDER = os.path.join(PROJECT_ROOT, 'templates')
STATIC_FOLDER   = os.path.join(PROJECT_ROOT, 'static')


# Flask app
app = Flask(
    __name__,
    template_folder=TEMPLATE_FOLDER,
    static_folder=STATIC_FOLDER,
)
app.logger.handlers = root_logger.handlers
app.logger.setLevel(logging.DEBUG)

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Public API
__all__ = [
    'APP_ROOT',
    'TMP_BASE',
    'STATIC_VIDEOS',
    'MEDIA_DIR',
    'root_logger',
    'formatter',
    'tream_handler',
    'file_handler',
    'app'
]
