import os
import json
from typing import Optional, List, Dict, Any

# Define APP_ROOT relative to this test script's location
# Assuming this script is in the root directory alongside 'manim-video-generator'
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
# MANIM_PROJECT_ROOT = os.path.join(APP_ROOT, 'manim-video-generator')

# --- Copied Helper Function ---
def _get_voice_name_for_locale(locale: str, voice_data_path: str = "text_to_speech.json") -> Optional[str]:
    """
    Loads voice data from a JSON file and finds the first matching voice ShortName for the given locale.
    """
    default_voice = "en-US-AvaMultilingualNeural" # Default fallback voice
    # Construct full path relative to the manim-video-generator project root
    full_path = os.path.join(APP_ROOT, voice_data_path)
    print(f"Attempting to load voice data from: {full_path}") # Debug print

    if not os.path.exists(full_path):
        print(f"Error: Voice data file not found at: {full_path}. Using default voice '{default_voice}'.")
        return default_voice

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            voice_data = json.load(f)

        if not isinstance(voice_data, list):
            print(f"Error: Invalid format in {full_path}: Expected a JSON list. Using default voice '{default_voice}'.")
            return default_voice

        # Find the first voice matching the locale
        for voice_info in voice_data:
            if isinstance(voice_info, dict) and voice_info.get("Locale") == locale:
                voice_name = voice_info.get("ShortName")
                if voice_name:
                    print(f"Success: Found voice '{voice_name}' for locale '{locale}'.")
                    return voice_name
                else:
                     print(f"Warning: Found matching locale '{locale}' but 'ShortName' is missing. Skipping.")

        # If no specific voice is found for the locale, try finding a multilingual voice
        print(f"Warning: No specific voice found for locale '{locale}'. Searching for a suitable multilingual voice...")
        for voice_info in voice_data:
             if isinstance(voice_info, dict) and "MultilingualNeural" in voice_info.get("ShortName", ""):
                  if "en-US-AvaMultilingualNeural" in voice_info.get("ShortName", ""):
                       voice_name = "en-US-AvaMultilingualNeural"
                       print(f"Info: Using default multilingual voice '{voice_name}' for locale '{locale}'.")
                       return voice_name
                  voice_name = voice_info.get("ShortName")
                  if voice_name:
                       print(f"Info: Using first available multilingual voice '{voice_name}' for locale '{locale}'.")
                       return voice_name

        # Final fallback
        print(f"Warning: No specific or suitable multilingual voice found for locale '{locale}'. Using absolute default '{default_voice}'.")
        return default_voice

    except json.JSONDecodeError:
        print(f"Error: Error decoding JSON from {full_path}. Using default voice '{default_voice}'.")
        return default_voice
    except Exception as e:
        print(f"Error: Error reading or processing {full_path}: {e}. Using default voice '{default_voice}'.")
        return default_voice

# --- Test Execution ---
if __name__ == "__main__":
    print("--- Testing Voice Lookup Function ---")

    test_locales = ["ta-IN", "en-US", "es-ES", "fr-FR", "non-existent-XX"]

    for locale_to_test in test_locales:
        print(f"\n--- Testing Locale: {locale_to_test} ---")
        found_voice = _get_voice_name_for_locale(locale_to_test)
        print(f"Result for {locale_to_test}: {found_voice}")

    print("\n--- Test Complete ---")
