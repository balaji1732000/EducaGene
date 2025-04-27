# Project Brief: Manim Video Generator

## 1. Core Requirements & Goals

- **Goal:** Create an easy-to-use web application that allows users (content creators, teachers, students) to generate educational animation videos using Manim without needing to write Manim code themselves.
- **Input:** User provides a text concept or script idea.
- **Output:** A final rendered MP4 video with synchronized voiceover, hosted or downloadable.
- **Key Feature:** Automate the process from concept -> storyboard -> Manim code -> rendering -> voiceover -> final video.
- **Target Style:** Visually engaging animations, similar to educational channels like 3Blue1Brown.

## 2. Scope

**In Scope:**
- Web UI for inputting concepts.
- Backend workflow (using LangGraph) to orchestrate LLM calls and Manim rendering.
- LLM integration for:
    - Planning video scenes (storyboarding).
    - Generating Manim Python code for scenes.
    - Evaluating generated code for correctness and relevance.
    - Revising code based on evaluation or rendering errors.
    - Generating voiceover script from video content.
- Manim execution for rendering video scenes.
- Text-to-Speech (TTS) integration for generating audio voiceover.
- Video/audio combination into a final MP4.
- Basic error handling and reporting to the UI.
- Support for a range of educational topics (initially math/science focused, but adaptable).

**Out of Scope (Initially):**
- Complex UI features beyond basic input/output display.
- User accounts or persistent storage of generated videos.
- Advanced video editing capabilities within the app.
- Direct Manim code editing interface for users.
- Highly interactive elements *within* the generated videos (e.g., clickable buttons, embedded quizzes - focus is on generation *of* the video).
- Fine-grained control over Manim parameters (quality, specific objects, themes) via UI.
- Formal multi-language support beyond the TTS capability (UI localization, etc.).

## 3. Success Metrics

- Users can successfully generate a coherent video from a reasonable concept input.
- The workflow completes reliably without frequent crashes or unhandled errors.
- The generated video roughly matches the intent of the user's concept.
- Generation time is acceptable (e.g., within a few minutes for short concepts).

## 4. Target Audience

- Content Creators (YouTube, blogs, social media) needing quick animations.
- Educators (Teachers, Professors) wanting visual aids for lessons.
- Students exploring concepts visually.
- Users with minimal to no programming/Manim experience. 