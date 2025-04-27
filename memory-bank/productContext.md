# Product Context: Manim Video Generator

## 1. Problem Solved

Creating engaging educational animation videos, especially complex mathematical or scientific visualizations, is currently difficult, time-consuming, and requires specialized skills.

- **High Barrier to Entry:** Tools like Manim are powerful but demand significant Python programming knowledge and understanding of the Manim library itself.
- **Slow Production Cycle:** Manually scripting scenes, debugging code, rendering video, generating voiceover, and combining media takes hours or days per minute of video.
- **Lack of Interactivity/Accessibility:** Standard video formats lack interactivity, and creating multi-language versions requires separate, manual efforts for translation, voiceover, and captioning.
- **Content Bottleneck:** Many educators and creators have great ideas for visual explanations but lack the time or technical ability to produce them, limiting the availability of high-quality visual learning resources.

## 2. How It Should Work (User Flow)

1.  **Input:** The user accesses a simple web interface. They type or paste a description of the educational concept they want to visualize (e.g., "Explain the Pythagorean theorem using an animated triangle and squares").
2.  **Generation:** The user clicks a "Generate" button.
3.  **Processing (Backend):**
    - The system receives the concept.
    - An AI breaks the concept down into logical visual scenes (storyboard).
    - For each scene (or the combined video), AI generates the necessary Manim Python code.
    - The system attempts to render the video using the generated code.
    - If errors occur (code issues, rendering failures), AI attempts to evaluate the error and revise the code, then re-renders (within limits).
    - Once a silent video is successfully rendered, AI analyzes the video content to generate a voiceover script.
    - A Text-to-Speech service converts the script into an audio file, potentially synchronizing pauses with video timing.
    - The silent video and audio voiceover are combined into a final MP4 file.
4.  **Output:** The web interface displays the final generated video preview. A download link is provided. Error messages or warnings are displayed if the process fails or encounters issues.

*(Note: The current implementation focuses on generating a single combined script and video rather than individual scenes, followed by voiceover generation)*

## 3. User Experience Goals

- **Simplicity:** The user interface should be minimal and intuitive, requiring only text input and a button click.
- **Speed:** Generation should be reasonably fast, ideally providing results within minutes for typical concepts.
- **Reliability:** The workflow should handle common errors gracefully and provide informative feedback to the user.
- **Quality:** The generated videos should be visually clear, reasonably accurate to the concept, and have acceptable rendering quality.
- **"Wow" Factor:** Users should feel empowered to create animations they previously couldn't, achieving a sense of "magic" from the AI automation. 