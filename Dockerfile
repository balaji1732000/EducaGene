# Use an official Python runtime as a parent image
FROM python:3.13.1-slim

# Set environment variables to ensure apt-get runs non-interactively
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
# - build-essential: For C compiler (gcc) needed by pycairo etc.
# - pkg-config: Helps find library paths during builds.
# - libcairo2-dev: Development headers for Cairo, needed by pycairo.
# - libpango1.0-dev: Development headers for Pango/PangoCairo, needed by manimpango.
# - ffmpeg for video/audio processing
# - texlive-* for Manim's LaTeX rendering
# - git as Manim sometimes uses it
# - dvipng and dvisvgm for specific LaTeX output formats Manim might need
# - fontconfig: Utility to manage fonts
# - fonts-noto-*: Common fonts for various languages needed by Manim Text()
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    ffmpeg \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-science \
    dvipng \
    dvisvgm \
    git \
    fontconfig \
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-unhinted \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


# Rebuild the font cache to include newly installed fonts
RUN fc-cache -fv

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir reduces image size
# --default-timeout=100 increases timeout for potentially slow installs
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# Copy the rest of the application code into the container at /app
# This includes main.py, the manim_video_generator package, text_to_speech.json etc.
# .dockerignore prevents copying unnecessary files like .env, venv, .git etc.
COPY . .

# Make port 5001 available to the world outside this container
# (Assuming Flask runs on 5001 as configured in main.py)
EXPOSE 5001

# Define the command to run the app using Gunicorn
# - Bind to 0.0.0.0 to accept connections from outside the container
# - Use 1 worker initially (can be scaled later)
# - Set a long timeout (6000s) for potentially long video generation requests
# - Point to the Flask app instance (app) within the main module (main.py)
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--timeout", "6000", "main:app"]
