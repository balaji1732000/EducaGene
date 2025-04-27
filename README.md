# Manim Video Generator

This web application allows users to generate educational animation videos using Manim by providing a text concept. It leverages LLMs (Azure OpenAI, Google Gemini) and LangGraph to automate the process from concept to final video with voiceover.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

### 1. Python

- **Requirement:** Python 3.10 or higher recommended.
- **Check Installation:** Open your terminal or command prompt and run `python --version` or `python3 --version`.
- **Installation:**
    - **Windows:** Download from [python.org](https://www.python.org/downloads/windows/). Ensure you check "Add Python to PATH" during installation.
    - **macOS:** Python usually comes pre-installed. If not, or if you need a specific version, download from [python.org](https://www.python.org/downloads/macos/) or use a package manager like Homebrew (`brew install python`).

### 2. FFmpeg

- **Requirement:** Manim uses FFmpeg for rendering videos.
- **Check Installation:** Run `ffmpeg -version` in your terminal.
- **Installation:**
    - **Windows:**
        1. Download the latest static build from [ffmpeg.org](https://ffmpeg.org/download.html#build-windows) (e.g., from gyan.dev).
        2. Extract the archive.
        3. Add the `bin` directory inside the extracted folder to your system's PATH environment variable.
    - **macOS:**
        - Using Homebrew (recommended): `brew install ffmpeg`

### 3. LaTeX Distribution

- **Requirement:** Manim requires a LaTeX distribution for rendering text and equations (MathTex).
- **Installation:**
    - **Windows:** Install [MiKTeX](https://miktex.org/download). During setup, choose the option to install missing packages on-the-fly.
    - **macOS:** Install [MacTeX](https://www.tug.org/mactex/download.html). The smaller BasicTeX distribution (`mactex-basictex.pkg` included in this repo, or downloadable) might suffice, but the full MacTeX is recommended for fewer issues. If using BasicTeX, you might need to manually install packages later using `tlmgr`.

## Setup Instructions

1.  **Clone the Repository (if applicable):**
    ```bash
    git clone <repository-url>
    cd manim-video-generator
    ```

2.  **Create and Activate Virtual Environment:**
    It's highly recommended to use a virtual environment.
    ```bash
    # Create the environment (use python3 if python maps to Python 2)
    python -m venv env

    # Activate the environment
    # Windows (Command Prompt/PowerShell)
    .\env\Scripts\activate
    # macOS/Linux (Bash/Zsh)
    source env/bin/activate
    ```
    You should see `(env)` prefixed to your terminal prompt.

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Create `.env` File:**
    Create a file named `.env` in the root of the `manim-video-generator` directory.

2.  **Add API Keys and Endpoints:**
    Copy the following structure into your `.env` file and replace the placeholder values with your actual credentials:

    ```env
    # Azure OpenAI
    AZURE_OPENAI_API_KEY="YOUR_AZURE_OPENAI_KEY"
    ENDPOINT_URL="YOUR_AZURE_OPENAI_ENDPOINT"
    AZURE_DEPLOYMENT="YOUR_AZURE_OPENAI_DEPLOYMENT_NAME" # e.g., gpt-4o

    # Azure Speech
    AZURE_SPEECH_KEY="YOUR_AZURE_SPEECH_KEY"
    AZURE_SPEECH_REGION="YOUR_AZURE_SPEECH_REGION" # e.g., eastus

    # Google Gemini (Optional - if vision features are used)
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
    ```

## Running the Application

1.  **Ensure Virtual Environment is Active:** If you closed your terminal, reactivate the environment (`.\env\Scripts\activate` or `source env/bin/activate`).

2.  **Run the Flask Server:**
    ```bash
    python main.py
    ```
    *(Note: If the main script name changes, update the command accordingly. Check `techContext.md` for the current script name if needed.)*

3.  **Access the Application:**
    Open your web browser and navigate to `http://127.0.0.1:5001` (or the address shown in the terminal output).

4.  **Generate a Video:**
    Enter a concept (e.g., "Pythagorean Theorem", "Photosynthesis") into the input field and click "Generate". The process may take several minutes depending on the concept complexity and LLM/rendering times.
