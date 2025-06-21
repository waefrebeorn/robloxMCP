# Desktop AI Assistant (Windows MCP Agent)

This project is a Python-based agent designed to control a Windows desktop environment. It leverages Large Language Models (LLMs like Google's Gemini or local models via Ollama) for understanding user commands. It uses dedicated libraries for screen interaction, OCR (via Tesseract and potentially Moondream v2 for general vision), Speech-to-Text (via Whisper), and Text-to-Speech (via pyttsx3). Users can interact with the assistant via a command-line interface (text or voice) to automate desktop tasks.

## Features

*   **Desktop Control**: Programmatic control over mouse and keyboard actions.
*   **Screen Interaction**:
    *   Capture the full screen or specific regions.
    *   OCR (Optical Character Recognition) using Tesseract to find text and its coordinates on screen.
    *   Click on text found via OCR.
*   **Vision Analysis**: Utilizes Moondream v2 (or a similar vision model if configured) for general image description tasks.
*   **Window Management**: List open windows, get active window title, focus windows, get window geometry.
*   **File System (Read-Only)**: List directory contents and read text files.
*   **Voice Interaction**:
    *   Speech-to-Text (STT) using local Whisper models.
    *   Text-to-Speech (TTS) using pyttsx3 for spoken responses.
*   **LLM Integration**: Supports Google Gemini (via API) and local LLMs (e.g., Llama, Phi, Qwen) through Ollama for natural language understanding and tool orchestration.
*   **Command-Line Interface**: Allows users to type commands or use voice to interact with their desktop.
*   **Configurable**: Settings for API keys, model names, and behavior can be managed through `config.json` and `.env` files.

## Prerequisites

*   **Python**: Version 3.9 or higher is recommended. Ensure Python is added to your system's PATH.
*   **Git**: For cloning the repository.
*   **Tesseract OCR**: Required for the `find_text_on_screen_and_click` tool and other precise text-location tasks.
    *   Installation instructions: [Tesseract OCR Documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
    *   Ensure Tesseract is added to your system's PATH, or you may need to configure `pytesseract.tesseract_cmd` within the `ocr_service.py` if issues arise (not currently implemented as a config option).
*   **Ollama**: (Optional, if using local LLMs/Moondream) Install from [ollama.com](https://ollama.com).
*   **ffmpeg**: (Required by `openai-whisper`) A cross-platform solution to record, convert and stream audio and video.
    *   Linux: `sudo apt update && sudo apt install ffmpeg`
    *   macOS: `brew install ffmpeg`
    *   Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH, or via Chocolatey: `choco install ffmpeg`

## Setup Instructions

1.  **Clone the Repository**:
    ```bash
    git clone <repository_url> # Replace <repository_url> with the actual URL
    cd <repository_directory>   # Replace <repository_directory>
    ```

2.  **Create and Activate Python Virtual Environment**:
    ```bash
    python -m venv venv
    ```
    Activate:
    *   Windows: `.\venv\Scripts\activate`
    *   macOS/Linux: `source venv/bin/activate`

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    This installs all necessary Python packages including `pyautogui`, `Pillow`, `requests`, `pytesseract`, `pandas`, `openai-whisper`, `sounddevice`, `scipy`, `pyttsx3`, `PyGetWindow`, and `PyWinCtl`.

4.  **Configuration**:
    *   **Copy Example Configuration**:
        ```bash
        cp config.example.json config.json
        ```
    *   **Edit `config.json`**: Review and update the settings:
        *   `LLM_PROVIDER`: `"gemini"` or `"ollama"`.
        *   `OLLAMA_API_URL`: (If Ollama) Defaults to `"http://localhost:11434"`.
        *   `OLLAMA_DEFAULT_MODEL`: (If Ollama) Default text LLM (e.g., `"phi3:mini"`).
        *   `MOONDREAM_API_URL`: Endpoint for Moondream v2 (if used, e.g., via Ollama: `"http://localhost:11434/api/generate"`).
        *   `OLLAMA_MOONDREAM_MODEL`: Name of Moondream model in Ollama (e.g., `"moondream"`).
        *   `SCREENSHOT_SAVE_PATH`: Optional path to save screenshots (e.g., `"./screenshots"`).
        *   `GEMINI_MODEL_NAME`: (If Gemini) e.g., `"gemini-1.5-flash-latest"`.
        *   `PYAUTOGUI_FAILSAFE_ENABLED`: `true` or `false`.
        *   `PYAUTOGUI_PAUSE_PER_ACTION`: e.g., `0.1`.
        *   `VOICE_RECORDING_DURATION`: Default recording time in seconds for voice input (e.g., `5`).
        *   `WHISPER_MODEL_NAME`: Whisper model for STT (e.g., `"base"`, `"tiny"`).
        *   `ENABLE_TTS`: `true` or `false` to enable/disable spoken responses.
    *   **Gemini API Key (if using Gemini)**:
        Create a `.env` file in the project root:
        ```env
        GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
        ```
    *   **Ollama Setup (if using Ollama)**:
        *   Ensure Ollama is installed and running.
        *   Pull your chosen LLM: `ollama pull <your_llm_name>` (e.g., `ollama pull phi3:mini`).
        *   Pull Moondream (if using for vision): `ollama pull moondream`.
    *   **Microphone Access**: Ensure the application has permission to access your microphone for voice input.

## Running the Assistant

1.  **Activate your virtual environment**.
2.  **Run `main.py`**:
    ```bash
    python main.py
    ```
    **Command-Line Arguments**:
    *   `--voice`: Enable voice input mode (uses Whisper).
    *   `--llm_provider {gemini,ollama}`: Override `LLM_PROVIDER` from `config.json`.
    *   `--ollama_model <model_name>`: (If Ollama) Override `OLLAMA_DEFAULT_MODEL`.
    *   `--test_command "<command>"`: Execute a single command.
    *   `--test_file <filepath>`: Execute commands from a file.

### Interactive Mode
Type commands or use voice (if `--voice` flag is used). For voice, the system will prompt you to speak.

Examples:
*   "List all open windows."
*   "What is the title of the active window?"
*   "Focus the window titled 'Notepad'." (Ensure Notepad is open)
*   "Read the first 100 characters of requirements.txt."
*   "Capture the screen and tell me what text you see near the top." (Uses screenshot + Moondream)
*   "Find the text 'File' on screen and click it." (Uses screenshot + Tesseract OCR)

## Available Tools (Examples)

*   **Screen & Vision**: `capture_screen_region`, `capture_full_screen`, `get_screen_resolution`, `analyze_image_with_vision_model` (Moondream), `find_text_on_screen_and_click` (Tesseract).
*   **Mouse & Keyboard**: `mouse_move`, `mouse_click`, `mouse_drag`, `mouse_scroll`, `keyboard_type`, `keyboard_press_key`, `keyboard_hotkey`.
*   **Window Management**: `list_windows`, `get_active_window_title`, `focus_window`, `get_window_geometry`.
*   **File System (Read-Only)**: `list_directory`, `read_text_file`.

## Example Workflow

1.  **User (Voice/Text)**: "List all windows that have 'Editor' in their title."
2.  **Agent (LLM Decision)**: Calls `list_windows` tool with `title_filter="Editor"`.
3.  **Agent (Response to User - Text/TTS)**: "Found windows: [List of titles]."
4.  **User**: "Focus the window '[Specific Editor Title]'."
5.  **Agent**: Calls `focus_window` tool.
6.  **Agent**: "Okay, I've attempted to focus '[Specific Editor Title]'."
7.  **User**: "Type 'This is a test.' into the active window."
8.  **Agent**: Calls `keyboard_type` tool.
9.  **Agent**: "Done."

---
*The batch scripts (`.bat` files) previously in the repository are legacy and not relevant for this desktop assistant. Rely on `python main.py`.*
