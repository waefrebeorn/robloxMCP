import sounddevice as sd
import numpy as np
import whisper
import tempfile
import os
import logging
import time
from scipy.io.wavfile import write as write_wav # For saving WAV file

logger = logging.getLogger(__name__)

# Configuration for Whisper model (can be made configurable via config_manager later)
DEFAULT_WHISPER_MODEL = "base" # Options: "tiny", "base", "small", "medium", "large"
DEFAULT_SAMPLE_RATE = 16000 # Whisper is trained on 16kHz audio
DEFAULT_CHANNELS = 1 # Mono audio

# Global variable to cache the loaded Whisper model
_whisper_model_cache = {}

def load_whisper_model(model_name: str = DEFAULT_WHISPER_MODEL):
    """Loads a Whisper model, caching it for subsequent uses."""
    if model_name not in _whisper_model_cache:
        logger.info(f"Loading Whisper model: {model_name}...")
        try:
            _whisper_model_cache[model_name] = whisper.load_model(model_name)
            logger.info(f"Whisper model '{model_name}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model '{model_name}': {e}", exc_info=True)
            # You might want to raise the exception or handle it by returning None
            # For now, if a model fails to load, it won't be cached, and subsequent calls will retry.
            # This could be problematic if the model name is invalid or files are missing.
            # Consider raising an error to make the failure more explicit.
            raise
    return _whisper_model_cache[model_name]


def record_audio(duration_seconds: int = 5,
                 sample_rate: int = DEFAULT_SAMPLE_RATE,
                 channels: int = DEFAULT_CHANNELS) -> Optional[str]:
    """
    Records audio from the default microphone for a specified duration and saves it as a temporary WAV file.

    Args:
        duration_seconds: The duration of the recording in seconds.
        sample_rate: The sample rate for the recording.
        channels: The number of audio channels.

    Returns:
        The file path to the temporary WAV file, or None if recording failed.
    """
    logger.info(f"Starting audio recording for {duration_seconds} seconds...")
    try:
        recording = sd.rec(int(duration_seconds * sample_rate), samplerate=sample_rate, channels=channels, dtype='int16')
        sd.wait()  # Wait until recording is finished
        logger.info("Audio recording finished.")

        # Save as a temporary WAV file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", prefix="user_audio_")
        write_wav(temp_file.name, sample_rate, recording) # Use scipy.io.wavfile.write
        logger.info(f"Audio saved to temporary file: {temp_file.name}")
        return temp_file.name
    except sd.PortAudioError as pae:
        logger.error(f"PortAudio error during recording: {pae}")
        logger.error("This might indicate an issue with your microphone setup or sounddevice/PortAudio installation.")
        logger.error("Common issues: No default microphone, microphone muted, or driver problems.")
    except Exception as e:
        logger.error(f"Failed to record audio: {e}", exc_info=True)
    return None

def transcribe_audio_with_whisper(audio_file_path: str, model_name: str = DEFAULT_WHISPER_MODEL) -> Optional[str]:
    """
    Transcribes the given audio file using the specified Whisper model.

    Args:
        audio_file_path: Path to the audio file to transcribe.
        model_name: Name of the Whisper model to use (e.g., "tiny", "base", "small").

    Returns:
        The transcribed text, or None if transcription failed.
    """
    if not os.path.exists(audio_file_path):
        logger.error(f"Audio file not found: {audio_file_path}")
        return None

    logger.info(f"Transcribing audio file: {audio_file_path} using Whisper model: {model_name}")
    try:
        model = load_whisper_model(model_name)
        if model is None: # Should not happen if load_whisper_model raises on failure
            logger.error(f"Whisper model '{model_name}' could not be loaded for transcription.")
            return None

        result = model.transcribe(audio_file_path)
        transcribed_text = result["text"]
        logger.info(f"Transcription successful. Text: \"{transcribed_text[:100]}...\"")
        return transcribed_text
    except Exception as e:
        logger.error(f"Failed to transcribe audio: {e}", exc_info=True)
    finally:
        # Clean up the temporary audio file
        if audio_file_path and "user_audio_" in audio_file_path and audio_file_path.endswith(".wav"):
            try:
                os.remove(audio_file_path)
                logger.info(f"Cleaned up temporary audio file: {audio_file_path}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary audio file {audio_file_path}: {e}")
    return None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    # Pre-load model for testing (optional, but good for seeing load time separately)
    try:
        load_whisper_model(DEFAULT_WHISPER_MODEL) # Load the default model
    except Exception as e:
        logger.error(f"Failed to pre-load Whisper model for example: {e}")
        logger.error("Please ensure Whisper is installed correctly and model files are accessible.")
        logger.error("Try: pip install openai-whisper")
        logger.error("You might also need ffmpeg: sudo apt-get install ffmpeg (Linux) or choco install ffmpeg (Windows)")
        exit() # Exit if model can't load, as example won't work.

    logger.info("Starting voice input example...")
    duration = 5 # seconds

    # Check for available microphones
    try:
        print("\nAvailable audio devices:")
        print(sd.query_devices())
        # You can set a specific device using sd.default.device = <device_id_or_name>
        # For example, to set input device: sd.default.device[0] = <input_device_id>
        # sd.default.device = 1 # Example: set default device to device ID 1
    except Exception as e:
        logger.error(f"Could not query audio devices: {e}")


    print(f"\nSpeak into your default microphone for {duration} seconds in 3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("Recording!")

    temp_audio_file = record_audio(duration_seconds=duration)

    if temp_audio_file:
        print(f"\nAudio recorded to: {temp_audio_file}")
        print("Transcribing audio, please wait...")
        transcribed_text = transcribe_audio_with_whisper(temp_audio_file, model_name=DEFAULT_WHISPER_MODEL)

        if transcribed_text:
            print(f"\nTranscription:\n---\n{transcribed_text}\n---")
        else:
            print("\nTranscription failed or returned empty.")
    else:
        print("\nAudio recording failed. Cannot transcribe.")

    logger.info("Voice input example finished.")
