import os
import google.generativeai as genai
import json
from dotenv import load_dotenv
import traceback

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API Key
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("ERROR: GEMINI_API_KEY not found in environment variables.")
        exit()
    else:
        genai.configure(api_key=gemini_api_key)
        print("Gemini API Key configured.")
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    exit()

def test_gemini_json_output():
    """Tests Gemini's ability to return JSON and parses it."""
    print("\n--- Starting Gemini JSON Mode Test ---")

    try:
        # Define the system instruction requesting JSON output
        system_instruction = """You are a helpful assistant. Your task is to provide a response strictly in JSON format. The JSON object must have exactly two keys: "verdict" (string, either "GOOD" or "BAD") and "reason" (string, explaining the verdict). Do not include any text outside the JSON structure."""

        generation_config = {
            "temperature": 0.7,
            "top_p": 1.0,
            "top_k": 32,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json", # Request JSON output
            # Not using response_schema here to test basic JSON text parsing
        }

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest", # Or another suitable model
            generation_config=generation_config,
            system_instruction=system_instruction,
             safety_settings=[ # Basic safety settings
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        )

        # Simple user prompt
        prompt = "Evaluate this statement: 'Manim is a useful library.' Provide your verdict and reason in the required JSON format."

        print(f"\nSending prompt to Gemini:\n{prompt}")
        print(f"Using System Instruction:\n{system_instruction}")
        print(f"Using Generation Config:\n{json.dumps(generation_config, indent=2)}")

        response = model.generate_content(prompt)

        print("\n--- Gemini Raw Response ---")
        raw_response_text = response.text.strip()
        print(raw_response_text)
        print("--------------------------")

        print("\n--- Attempting JSON Parsing ---")
        try:
            parsed_json = json.loads(raw_response_text)
            print("JSON Parsing Successful!")
            print("Parsed Dictionary:")
            print(json.dumps(parsed_json, indent=4))

            # Accessing elements
            verdict = parsed_json.get("verdict")
            reason = parsed_json.get("reason")
            print(f"\nAccessed Verdict: {verdict}")
            print(f"Accessed Reason: {reason}")

            if verdict and reason:
                 print("\nSuccessfully accessed required keys.")
            else:
                 print("\nWarning: Could not access 'verdict' or 'reason' key.")

        except json.JSONDecodeError as json_e:
            print(f"ERROR: Failed to parse response as JSON: {json_e}")
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during parsing: {e}")

    except Exception as e:
        print(f"\nERROR: An error occurred during the Gemini API call:")
        print(traceback.format_exc())

    print("\n--- Test Complete ---")

if __name__ == "__main__":
    test_gemini_json_output()
