# Tech Context: Manim Video Generator

## 1. Technologies Used

- **Backend Language:** Python 3.x
- **Web Framework:** Flask (for serving UI and API)
- **Workflow Orchestration:** LangGraph
- **AI/LLM Interaction:**
    - Langchain (specifically `langchain-openai` for Azure)
    - Google Generative AI SDK (`google.generativeai` for Gemini Vision)
    - Azure OpenAI Service (GPT-4o, potentially others)
- **Animation Engine:** Manim Community Edition (installed via pip)
- **Text-to-Speech:** Azure Cognitive Services Speech SDK
- **Video/Audio Processing:** ffmpeg (expected to be available in the system PATH)
- **Frontend:** HTML, Tailwind CSS, vanilla JavaScript
- **Environment Management:** `python-dotenv` (for loading API keys etc. from `.env`)
- **Containerization:** (Not currently implemented, but a potential future step with Docker)

## 2. Development Setup

- **OS:** Developed on Windows, but should be cross-platform compatible assuming dependencies are met.
- **Python Environment:** Recommended to use a virtual environment (e.g., `venv`).
  ```bash
  python -m venv venv
  source venv/bin/activate # or venv\Scripts\activate on Windows
  pip install -r requirements.txt
  ```
- **Dependencies:** Key dependencies listed in `requirements.txt` (Flask, LangGraph, Langchain, Azure SDKs, Manim, google-generativeai, python-dotenv, etc.).
- **External Tools:** `ffmpeg` must be installed and accessible in the system's PATH.
- **Configuration:** API keys and endpoints for Azure OpenAI, Azure Speech, and potentially Gemini must be stored in a `.env` file in the project root. Example `.env` structure:
  ```env
  # Azure OpenAI
  AZURE_OPENAI_API_KEY="YOUR_AZURE_OPENAI_KEY"
  ENDPOINT_URL="YOUR_AZURE_OPENAI_ENDPOINT"
  AZURE_DEPLOYMENT="YOUR_DEPLOYMENT_NAME" # e.g., gpt-4o

  # Azure Speech
  AZURE_SPEECH_KEY="YOUR_AZURE_SPEECH_KEY"
  AZURE_SPEECH_REGION="YOUR_AZURE_SPEECH_REGION"

  # Google Gemini (if used, e.g., for vision)
  GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
  ```
- **Running the App:**
  ```bash
  python "new_complex_flow copy.py" # Or the current main script name
  ```
  Access via `http://localhost:5001` (or the configured host/port).

## 3. Technical Constraints

- **LLM Rate Limits/Costs:** Dependent on Azure/Google API limits and pricing tiers. Complex requests or many revisions can increase costs.
- **Manim Performance:** Rendering time depends heavily on scene complexity and video length. Long or complex animations can take significant time and CPU resources. Subprocess timeout is set (e.g., 600s) but might need adjustment.
- **ffmpeg Dependency:** Relies on an external `ffmpeg` installation.
- **Temporary Storage:** Workflow generates intermediate files (scripts, scene videos, audio). Sufficient disk space is required in the `tmp_requests` directory. Lack of cleanup means this directory will grow over time.
- **Error Handling Brittleness:** Relying on LLMs to generate and fix code can be unpredictable. Robust error parsing and retry logic are crucial but may not catch all edge cases. Parsing LLM output (like JSON plans or verdicts) can also be fragile.
- **Content Filtering:** Azure OpenAI includes content filters that might occasionally block prompts or responses, potentially halting the workflow. Error messages are truncated to mitigate this but might obscure the root cause.

## 4. Dependencies

- **Python Packages:** See `requirements.txt`. Key ones include `flask`, `langgraph`, `langchain-openai`, `azure-cognitiveservices-speech`, `manim`, `google-generativeai`, `python-dotenv`.
- **System Libraries:** `ffmpeg`.
- **External Services:** Azure OpenAI, Azure Cognitive Services, Google AI (Gemini). Internet connectivity is required to reach these APIs. 