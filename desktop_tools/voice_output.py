import pyttsx3
import logging
import asyncio # For running blocking TTS in a separate thread

logger = logging.getLogger(__name__)

# Initialize the TTS engine globally but carefully
_tts_engine = None
_tts_engine_initialized_successfully = False

def _initialize_tts_engine():
    """Initializes the TTS engine if not already done."""
    global _tts_engine, _tts_engine_initialized_successfully
    if _tts_engine_initialized_successfully:
        return _tts_engine

    if _tts_engine is None: # Attempt initialization only once if it failed before or not tried
        try:
            logger.info("Initializing TTS engine (pyttsx3)...")
            _tts_engine = pyttsx3.init()

            # Optional: Configure voice, rate, volume
            # voices = _tts_engine.getProperty('voices')
            # For example, to set a specific voice (if available on the system):
            # _tts_engine.setProperty('voice', voices[1].id) # Index 1 for a different voice

            # _tts_engine.setProperty('rate', 150)  # Speed percent (can go over 100)
            # _tts_engine.setProperty('volume', 0.9) # Volume 0-1

            _tts_engine_initialized_successfully = True
            logger.info("TTS engine initialized successfully.")
            return _tts_engine
        except Exception as e:
            logger.error(f"Failed to initialize pyttsx3 engine: {e}", exc_info=True)
            logger.error("TTS functionality will be disabled. Ensure you have a TTS engine installed on your system (e.g., SAPI5 on Windows, NSSpeechSynthesizer on macOS, espeak on Linux).")
            _tts_engine = None # Ensure it's None if init failed
            _tts_engine_initialized_successfully = False # Explicitly mark as failed
            return None
    return _tts_engine # Return None if initialization previously failed

def _speak_text_sync(text: str):
    """Synchronous part of speaking text."""
    engine = _initialize_tts_engine()
    if engine:
        try:
            engine.say(text)
            engine.runAndWait() # Blocks until speaking is complete
            logger.info(f"Spoke text: \"{text[:50]}...\"")
        except Exception as e:
            logger.error(f"Error during TTS speech: {e}", exc_info=True)
    else:
        logger.warning("TTS engine not available. Cannot speak text.")

async def speak_text_async(text: str):
    """
    Speaks the given text using pyttsx3, running the blocking call in a separate thread.
    This is important for not blocking the main asyncio event loop.
    """
    if not text or not text.strip():
        logger.info("speak_text_async called with empty or whitespace-only text. Nothing to speak.")
        return

    # Ensure engine is initialized (or initialization is attempted) before trying to speak
    # _initialize_tts_engine() # This will be called by _speak_text_sync

    # pyttsx3's runAndWait is blocking, so it needs to be run in a thread
    # when used with asyncio.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _speak_text_sync, text)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.info("Voice Output (TTS) Example")

    # Attempt to initialize engine first to see if it works
    engine_test = _initialize_tts_engine()
    if not engine_test:
        logger.error("TTS engine could not be initialized for the example. Exiting.")
        exit()

    async def main_example():
        test_phrase_1 = "Hello from your friendly Desktop AI Assistant!"
        print(f"Attempting to speak: \"{test_phrase_1}\"")
        await speak_text_async(test_phrase_1)
        print("Speaking finished for phrase 1.")

        await asyncio.sleep(0.5) # Small pause

        test_phrase_2 = "This is a test of the text to speech system."
        print(f"Attempting to speak: \"{test_phrase_2}\"")
        await speak_text_async(test_phrase_2)
        print("Speaking finished for phrase 2.")

        test_phrase_3 = "" # Test empty
        print(f"Attempting to speak empty phrase: \"{test_phrase_3}\"")
        await speak_text_async(test_phrase_3)
        print("Speaking finished for empty phrase.")


    asyncio.run(main_example())
    logger.info("Voice output example finished.")
