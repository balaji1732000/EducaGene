import os
import json
from google import genai
from dotenv import load_dotenv
import logging
from google.genai import types
# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gemini_json_output():
    """
    Tests Gemini's ability to generate structured JSON output based on a schema
    provided in the system prompt.
    """
    load_dotenv()
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not gemini_api_key:
        logger.error("GEMINI_API_KEY not found in .env file. Please set it.")
        return

    try:
        client = genai.Client(api_key=gemini_api_key)
    except Exception as e:
        logger.error(f"Error configuring Gemini: {e}")
        return

    # Define the target JSON schema (Schema 2)
    # For the prompt, it's often easier to represent this as a string.
    # For the 'response_schema' parameter in generation_config, you'd use Pydantic models or type hints.
    # Here, we are testing the schema-in-prompt method.
    json_schema_definition = """
```json
{
  "verdict": "SATISFIED" | "REVISION_NEEDED",
  "metrics": {
    "coverage": "<int 0-100>",
    "visual": "<int 0-100>",
    "pedagogy": "<int 0-100>"
  },
  "issues": [
    {
      "scene_number": "<int>",
      "scene_title": "<string>",
      "frame": "<int|null>",
      "type": "overlap" | "off_frame" | "readability" | "contrast" | "pacing" | "lingering_elements" | "plan_deviation" | "missing_scene_element" | "camera_angle" | "camera_movement" | "font_error" | "other",
      "severity": "Critical" | "Major" | "Minor",
      "description": "<string>",
      "suggestion": "<string>"
    }
  ]
}
```
If verdict == "SATISFIED", "issues" MUST be an empty list `[]`.
Do NOT wrap the JSON in markdown fences.
All string values within the JSON (like description, suggestion) MUST be in the specified target language.
"""

    system_instruction = f"""You are a meticulous Quality Assurance expert for educational videos.
Your task is to evaluate a hypothetical video scenario and respond ONLY with a single, valid JSON object that strictly adheres to the schema provided below.

You MUST respond with JSON that matches this Schema:
{json_schema_definition}
"""

    user_prompt_text = """Please evaluate a hypothetical 2-scene video about 'The Solar System' in English.
Scene 1: "Introduction to Planets", shows Earth and Mars. Earth is well-centered, but Mars (frame 120) slightly overlaps with some on-screen text.
Scene 2: "The Sun", shows a large, bright sun. The pacing is a bit too fast for the narration.
Provide your evaluation in the specified JSON format.
"""

    generation_config=types.GenerateContentConfig(
        temperature=0.5,
        top_p=0.95,
        top_k=40,
        max_output_tokens=10000,
        response_mime_type="application/json",
        system_instruction=system_instruction,
        # Add any other necessary parameters here
    )
    


    logger.info("Sending request to Gemini for structured JSON output...")
    try:
        response = client.models.generate_content(
        model="gemini-2.5-pro-exp-03-25", # Using a common model
        config=generation_config,
        contents=[user_prompt_text] 
    )

        logger.info("--- Raw Gemini Response Text ---")
        print(response.text)
        logger.info("---------------------------------")

        parsed_data = None
        try:
            # Clean potential markdown fences just in case (though system prompt says not to use them)
            response_text_cleaned = response.text.strip()
            if response_text_cleaned.startswith("```json"):
                response_text_cleaned = response_text_cleaned[7:]
            if response_text_cleaned.endswith("```"):
                response_text_cleaned = response_text_cleaned[:-3]
            response_text_cleaned = response_text_cleaned.strip()
            
            parsed_data = json.loads(response_text_cleaned)
            logger.info("--- Parsed JSON Data ---")
            print(json.dumps(parsed_data, indent=2))
            logger.info("------------------------")

            # Basic validation
            if "verdict" in parsed_data and "metrics" in parsed_data and "issues" in parsed_data:
                logger.info("SUCCESS: Parsed JSON contains the main expected keys (verdict, metrics, issues).")
                if parsed_data["verdict"] == "REVISION_NEEDED" and len(parsed_data["issues"]) > 0:
                    logger.info("Found issues as expected for the test scenario.")
                    first_issue = parsed_data["issues"][0]
                    if "scene_number" in first_issue and "type" in first_issue and "description" in first_issue:
                        logger.info("First issue seems well-structured.")
                    else:
                        logger.warning("First issue might be missing some fields.")
                elif parsed_data["verdict"] == "SATISFIED" and not parsed_data["issues"]:
                     logger.info("Verdict is SATISFIED with no issues, as per schema rule.")
                else:
                    logger.warning(f"Verdict is {parsed_data['verdict']} but issues list state is unexpected (length: {len(parsed_data['issues'])}).")

            else:
                logger.error("FAILURE: Parsed JSON is missing one or more main keys (verdict, metrics, issues).")

        except json.JSONDecodeError as e:
            logger.error(f"FAILURE: Failed to decode Gemini response as JSON: {e}")
        except Exception as e:
            logger.error(f"An error occurred during parsing or validation: {e}")

    except Exception as e:
        logger.error(f"Error during Gemini API call: {e}")

if __name__ == "__main__":
    test_gemini_json_output()
