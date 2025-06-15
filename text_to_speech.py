# text_to_speech.py
import os
import requests # Added for making HTTP requests
import json     # Added for JSON handling
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

def text_to_speech(text: str, language: str, output_path: str):
    """
    Converts the given text to speech using Azure Cognitive Services
    and saves it to the specified output path.

    Args:
        text (str): The text to convert to speech.
        language (str): The language code (e.g., 'en-US', 'zh-CN').
        output_path (str): The path to save the generated audio file (e.g., 'output.wav').
    """
    # Load environment variables from .env file
    load_dotenv()

    # Get Azure credentials
    speech_key = os.getenv('AZURE_SPEECH_KEY')
    speech_region = os.getenv('AZURE_SPEECH_REGION')

    if not speech_key or not speech_region:
        print("Error: AZURE_SPEECH_KEY or AZURE_SPEECH_REGION environment variables not set.")
        print("Please create a .env file in the same directory with these variables.")
        return

    try:
        # Configure Speech SDK
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)

        # Use the specified multilingual voice (as in the reference code)
        # You can change this to other voices available in your region if needed.
        # Find voices here: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts
        voice_name = "zh-CN-XiaoxiaoMultilingualNeural"
        speech_config.speech_synthesis_voice_name = voice_name

        # Configure audio output
        # Ensure the directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")

        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)

        # Initialize Speech Synthesizer
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        # Prepare SSML
        # Replacing double newlines with a short break for better pacing
        formatted_text = text.replace('\n\n', '<break time="100ms"/>')
        ssml = f"""<speak version='1.0' xml:lang='{language}'>
    <voice name='{voice_name}'>{formatted_text}</voice>
</speak>"""

        print(f"Synthesizing speech for language '{language}' with voice '{voice_name}'...")
        print(f"Output will be saved to: {output_path}")

        # Synthesize speech
        result = synthesizer.speak_ssml_async(ssml).get()

        # Check result
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"Speech synthesized successfully and saved to {output_path}")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {cancellation_details.error_details}")
            print("Did you update the subscription info?")

    except Exception as e:
        print(f"An error occurred: {e}")

def get_available_voices():
    """
    Fetches the list of available TTS voices from the Azure REST API.

    Returns:
        list: A list of voice dictionaries, or None if an error occurs.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Get Azure credentials
    speech_key = os.getenv('AZURE_SPEECH_KEY')
    speech_region = os.getenv('AZURE_SPEECH_REGION')

    if not speech_key or not speech_region:
        print("Error: AZURE_SPEECH_KEY or AZURE_SPEECH_REGION environment variables not set.")
        print("Please ensure they are present in the .env file.")
        return None

    url = f"https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    headers = {
        'Ocp-Apim-Subscription-Key': speech_key
    }

    try:
        print(f"Fetching voice list from: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        voices = response.json()
        print(f"Successfully fetched {len(voices)} voices.")
        return voices

    except requests.exceptions.RequestException as e:
        print(f"Error fetching voice list: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


if __name__ == "__main__":
    print("Azure TTS Voice List Fetcher")
    print("-----------------------------")
    print("Ensure you have a .env file with AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.")
    print("You might need to install the requests library: pip install requests")
    print("-----------------------------")

    # Check if requests is installed
    try:
        import requests
    except ImportError:
        print("Error: The 'requests' library is not installed.")
        print("Please install it using: pip install requests")
        exit() # Exit if requests is not found

    # Fetch and print the voices
    available_voices = get_available_voices()

    if available_voices:
        output_filename = "text_to_speech.json"
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(available_voices, f, ensure_ascii=False, indent=4)
            print(f"\nSuccessfully saved voice list to {output_filename}")
        except IOError as e:
            print(f"\nError saving voice list to {output_filename}: {e}")
        except Exception as e:
             print(f"\nAn unexpected error occurred while saving the JSON file: {e}")

    else:
        print("\nFailed to retrieve voice list. JSON file not created.")

    # --- Original TTS test code (remains commented out) ---
    # input_text = input("Enter the text you want to convert to speech:\n")
    # input_language = input("Enter the language code (e.g., en-US, es-ES, zh-CN): ")
    # output_file = input("Enter the desired output file path (e.g., output/speech.wav): ")
    #
    # if input_text and input_language and output_file:
    #     text_to_speech(input_text, input_language, output_file)
    # else:
    #     print("Error: Please provide text, language, and output file path.")
