# System Patterns: Manim Video Generator

## 1. System Architecture

- **Frontend:** Single-page web application built with Flask and HTML/CSS (Tailwind CSS)/JavaScript. Serves the UI and interacts with the backend API.
- **Backend:** Flask web server providing an API endpoint (`/generate`).
- **Workflow Orchestration:** LangGraph state machine manages the multi-step process of video generation.
- **AI Core:** Leverages Large Language Models (LLMs, primarily Azure OpenAI/Gemini) for planning, code generation, evaluation, revision, and script generation.
- **Rendering Engine:** Uses the Manim library (executed as a subprocess) with the **OpenGL renderer** (`--renderer=opengl`) to render Python code into video frames/files, aiming for potential GPU acceleration.
- **Voice Synthesis:** Utilizes a Text-to-Speech (TTS) service (Azure Cognitive Speech Services) to generate audio voiceovers.
- **Media Processing:** Uses `ffmpeg` (via subprocess) for combining video and audio, and potentially for audio manipulation (stretching).

```mermaid
graph TD
    UserInterface[User Interface (Flask/HTML/JS)] -->|POST /generate (concept)| APIEndpoint(Flask API Endpoint)
    APIEndpoint -->|Invoke Workflow| LangGraphWorkflow(LangGraph State Machine)

    subgraph LangGraphWorkflow
        direction LR
        Start(Setup Request) --> Plan(Plan Video Node - LLM)
        Plan --> GenerateScript(Generate Full Script Node - LLM)
        
        GenerateScript --> Render(Render Combined Video Node - Manim Subprocess)
        
        Render -- RENDER_SUCCESS --> Evaluate(Evaluate Script & Video Node - CV Pre-pass + Gemini Vision)
        Render -- RENDER_ERROR --> SearchError(Search Error Solution Node - Web Search)
        
        SearchError --> GenerateScript # Always retry script gen after searching
        
        Evaluate -- REVISION_NEEDED --> GenerateScript # Loop back to fix script based on structured feedback
        Evaluate -- SATISFIED --> GenerateVoiceover(Generate Final Script Node - Gemini Vision)
        
        GenerateVoiceover --> GenerateAudio(Generate Audio Node - Azure TTS)
        GenerateAudio --> Combine(Combine Video/Audio Node - ffmpeg)
        Combine --> FinalEnd(END)
    end

    LangGraphWorkflow -->|Final State (Video URL/Error/Feedback)| APIEndpoint
    APIEndpoint -->|JSON Response| UserInterface
```

## 2. Key Technical Decisions

- **LangGraph for Orchestration:** Chosen for its ability to define complex, stateful, potentially cyclic workflows involving LLMs and other tools, managing retries and conditional logic effectively.
- **LLM for Code Generation/Revision:** Central to the concept, automating the Manim coding process. Requires careful prompt engineering and potentially multiple LLM calls for evaluation and fixing errors.
- **Subprocess Execution:** Manim and ffmpeg are run as external processes. This decouples them from the main Flask application but requires careful handling of paths, arguments, stdout/stderr, and error codes.
- **Single Combined Script:** The workflow was adapted to generate one single Manim script containing one class that sequentially implements all planned scenes, rather than rendering many separate scenes. This simplifies rendering coordination but may make scripts longer and potentially harder for the LLM to manage correctly.
- **Stateless API:** The `/generate` endpoint is largely stateless from the user's perspective; each request initiates a new, independent workflow run. State is managed internally by LangGraph for the duration of that run.
- **Temporary File Management:** Each request gets a unique temporary directory. Initially, cleanup was automatic, but it was removed to allow inspection of intermediate files upon completion/failure.

## 3. Design Patterns in Use

- **State Machine:** LangGraph implements a state machine pattern to manage the flow of the generation process.
- **Retry Loop:** Implicit retry loops are implemented via conditional edges in LangGraph for code revision (based on evaluation or render errors).
- **Prompt Engineering:** Significant effort is placed on crafting detailed prompts for the LLMs to guide their output for planning, code generation, evaluation, and voiceover scripting.
- **Error Handling & Fallback:** Nodes attempt to catch errors (e.g., subprocess failures, API errors, parsing errors) and update the workflow state with error messages, allowing downstream nodes or conditional edges to react. In some cases (like ffmpeg failure), a fallback (copying the silent video) is implemented.
- **Facade (Implicit):** The Flask API acts as a simple facade over the complex underlying LangGraph workflow.

## 4. Component Relationships

- **Flask App:** Serves the frontend (`index.html`, `base.html`, static assets) and provides the `/generate` API. It initiates the LangGraph process.
- **LangGraph Workflow:** Defined within the Flask app's context but runs as a separate logical unit. It contains nodes (Python functions) that perform specific tasks.
- **Nodes:** Functions within the workflow definition. They interact with:
    - **LLMs:** Via client libraries (e.g., `langchain_openai`, `google.generativeai`).
    - **Manim:** Via `subprocess.run`.
    - **TTS:** Via `speechsdk`.
    - **ffmpeg:** Via `subprocess.run`.
    - **Filesystem:** Reading/writing scripts, videos, audio files in temporary directories.
- **State Object:** A dataclass (`WorkflowState`) passed between nodes, carrying all necessary data (user input, intermediate results, file paths, errors, structured feedback, etc.).
