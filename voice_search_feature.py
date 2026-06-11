import os
import soundfile as sf
import numpy as np
import warnings

# Suppress a specific warning from the transformers library if needed
warnings.filterwarnings("ignore", message="Using `force_download` will force the redownload of the model")

def initialize_transcriber():
    """
    Initializes and returns the speech-to-text pipeline.
    This function will download the model if it's not already cached.
    """
    from transformers import pipeline
    try:
        # Using "openai/whisper-base" as it's a good general-purpose model.
        print("Initializing speech-to-text model...")
        transcriber = pipeline("automatic-speech-recognition", model="openai/whisper-base")
        print("Model initialized successfully.")
        return transcriber
    except Exception as e:
        print(f"Error initializing speech-to-text pipeline: {e}")
        print("Please ensure you have an internet connection to download the model and its components.")
        print("You may also need to install dependencies: pip install transformers torch soundfile librosa")
        return None

def transcribe_audio_file(transcriber, audio_file_path: str) -> str:
    """
    Transcribes an audio file to text using the initialized ASR model.

    Args:
        transcriber: The initialized speech-to-text pipeline.
        audio_file_path: Path to the audio file (e.g., .wav).

    Returns:
        The transcribed text as a string, or an empty string if transcription fails.
    """
    if not transcriber:
        print("Transcriber not initialized. Cannot process audio.")
        return ""

    if not os.path.exists(audio_file_path):
        print(f"Error: Audio file not found at {audio_file_path}")
        return ""

    print(f"Transcribing audio from {audio_file_path}...")
    try:
        result = transcriber(audio_file_path)
        transcribed_text = result["text"]
        print(f"Transcription successful: '{transcribed_text}'")
        return transcribed_text.strip()
    except Exception as e:
        print(f"An error occurred during transcription: {e}")
        return ""

def perform_search(query: str):
    """
    This is a placeholder for your application's search logic.
    It simulates searching for a doctor based on the transcribed text.
    """
    print(f"\n--- Performing search for: '{query}' ---")
    # In your actual application, you would replace this with a call
    # to your database or API to find doctors.
    print("... searching database for doctors ...")
    print("--- Search complete. ---")


if __name__ == "__main__":
    # 1. Initialize the speech-to-text model
    asr_pipeline = initialize_transcriber()

    if asr_pipeline:
        # 2. Create a dummy audio file for demonstration.
        # In your real application, you would get this from a microphone input.
        audio_file = 'my_voice_query.wav'
        if not os.path.exists(audio_file):
            print(f"Creating a dummy silent audio file: '{audio_file}'.")
            print("For a real test, please replace this with a recording of your voice.")
            sf.write(audio_file, np.zeros(16000 * 2), 16000)

        # 3. Transcribe the audio to get a search query
        search_query = transcribe_audio_file(asr_pipeline, audio_file)

        # 4. If transcription was successful, perform the search
        if search_query:
            perform_search(search_query)
        else:
            print("Could not generate a search query from the audio.")
