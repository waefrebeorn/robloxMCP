import requests
import base64
import io
from PIL import Image
import json
import os

# Attempt to import configuration, fallback if not found (e.g. during testing)
try:
    from config_manager import config as global_config
except ImportError:
    global_config = {} # Fallback to empty dict if config_manager is not available

# --- Moondream Configuration ---
# Prefer environment variable, then config file, then a default
MOONDREAM_DEFAULT_API_URL = "http://localhost:8080/moondream" # A common local moondream URL

def get_moondream_api_url():
    """Gets the Moondream API URL from env, config, or default."""
    url = os.environ.get("MOONDREAM_API_URL")
    if url:
        return url
    url = global_config.get("MOONDREAM_API_URL")
    if url:
        return url
    return MOONDREAM_DEFAULT_API_URL

def analyze_image_with_moondream(image_input: str | Image.Image, prompt_text: str) -> dict:
    """
    Sends an image and a text prompt to the Moondream v2 API and returns the response.

    Args:
        image_input: Path to the image file (str) or a PIL Image object.
        prompt_text: The text prompt to send with the image.

    Returns:
        A dictionary containing the parsed JSON response from the Moondream API.
        Returns a dictionary with an 'error' key in case of failure.
    """
    api_url = get_moondream_api_url()
    if not api_url:
        return {"error": "MOONDREAM_API_URL is not configured."}

    files = None
    image_bytes = None

    try:
        if isinstance(image_input, str): # Path to image file
            with open(image_input, "rb") as f:
                image_bytes = f.read()
            # files = {'image': (os.path.basename(image_input), image_bytes)}
        elif isinstance(image_input, Image.Image): # PIL Image object
            buffer = io.BytesIO()
            # Ensure image is in a common format like PNG or JPEG for sending
            format_to_save = image_input.format if image_input.format in ['JPEG', 'PNG'] else 'PNG'
            image_input.save(buffer, format=format_to_save)
            image_bytes = buffer.getvalue()
            # files = {'image': ('image.png', image_bytes, 'image/png')}
        else:
            return {"error": "Invalid image_input type. Must be a file path (str) or PIL.Image.Image object."}

        if not image_bytes:
             return {"error": "Failed to read or convert image to bytes."}

        # Moondream (ollama version) expects base64 encoded image in the 'images' list
        # and the prompt as 'prompt'.
        # The official moondream repo might have a different API structure if run standalone.
        # This implementation targets an Ollama-like/common local server structure.
        payload = {
            "model": global_config.get("OLLAMA_MOONDREAM_MODEL", "moondream"), # Or however your specific moondream model is named in Ollama
            "prompt": prompt_text,
            "images": [base64.b64encode(image_bytes).decode('utf-8')]
            # "stream": False # Optional, depending on API
        }

        # Adjust headers if needed, e.g., for specific content types or auth
        headers = {"Content-Type": "application/json"}

        # Check if the target URL is an Ollama endpoint for /api/generate or /api/chat
        # This is a common way to run moondream locally.
        is_ollama_endpoint = "ollama" in api_url and ("/api/generate" in api_url or "/api/chat" in api_url)

        if not is_ollama_endpoint and ("ollama" in api_url.lower() or "11434" in api_url):
            # If it looks like an ollama base URL but not a specific endpoint, try /api/generate
            print(f"Warning: MOONDREAM_API_URL '{api_url}' looks like an Ollama base URL. Appending '/api/generate'.")
            api_url = api_url.rstrip('/') + "/api/generate"


        response = requests.post(api_url, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        # Assuming the response is JSON. For Ollama, the actual text is in response.json()['response']
        response_json = response.json()

        if is_ollama_endpoint: # Or check response structure
             # Example for Ollama /api/generate:
             # { "model": "moondream:latest", "created_at": "...", "response": "The OCR text or description", "done": true, ... }
             # For /api/chat (if moondream supports it):
             # { "message": { "role": "assistant", "content": "The OCR text..." }, ... }
            if "response" in response_json: # /api/generate style
                return {"status": "success", "data": {"text": response_json["response"].strip(), "raw_response": response_json}}
            elif "message" in response_json and "content" in response_json["message"]: # /api/chat style
                return {"status": "success", "data": {"text": response_json["message"]["content"].strip(), "raw_response": response_json}}
            else:
                # Fallback if structure is unexpected but request succeeded
                return {"status": "success_unknown_format", "data": response_json}
        else:
            # For a non-Ollama specific Moondream endpoint, the response structure might be different.
            # This is a placeholder.
            return {"status": "success", "data": response_json}

    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {e}"}
    except FileNotFoundError:
        return {"error": f"Image file not found at path: {image_input}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

if __name__ == '__main__':
    print("Moondream Interaction Module Example")
    # This example assumes you have a Moondream server running at the configured URL.
    # And an image file named 'test_image.png' in the same directory as this script.

    # Create a dummy config for testing if config_manager is not available
    if not global_config:
        print("Using dummy config for MOONDREAM_API_URL as config_manager was not imported.")
        # You might need to set MOONDREAM_API_URL environment variable or update MOONDREAM_DEFAULT_API_URL
        # For Ollama, it's typically http://localhost:11434/api/generate or /api/chat
        # global_config["MOONDREAM_API_URL"] = "http://localhost:11434/api/generate"
        # global_config["OLLAMA_MOONDREAM_MODEL"] = "moondream" # ensure this model is pulled in Ollama

    api_url_to_test = get_moondream_api_url()
    print(f"Attempting to use Moondream API URL: {api_url_to_test}")

    # 1. Create a dummy image file for testing
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (400, 100), color = (255, 255, 255))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except IOError:
            font = ImageFont.load_default()
        d.text((10,10), "Hello Moondream", fill=(0,0,0), font=font)
        img.save("test_image_moondream.png")
        print("Created a dummy image 'test_image_moondream.png' for testing.")
        image_path_for_test = "test_image_moondream.png"

        # Test with image path
        prompt1 = "What does this image say?"
        print(f"\nTesting with image path: '{image_path_for_test}' and prompt: '{prompt1}'")
        result1 = analyze_image_with_moondream(image_path_for_test, prompt1)
        print("Response from Moondream (path input):")
        print(json.dumps(result1, indent=2))

        # Test with PIL Image object
        pil_image = Image.open(image_path_for_test)
        prompt2 = "Describe this image."
        print(f"\nTesting with PIL Image object and prompt: '{prompt2}'")
        result2 = analyze_image_with_moondream(pil_image, prompt2)
        print("Response from Moondream (PIL input):")
        print(json.dumps(result2, indent=2))

    except ImportError:
        print("Pillow (PIL) is not installed. Cannot create dummy image or test with PIL object.")
        print("Please install it: pip install Pillow")
    except Exception as e:
        print(f"An error occurred during the example run: {e}")
        print("Ensure your Moondream (e.g., Ollama with Moondream model) server is running and accessible.")
        print(f"Also check if the MOONDREAM_API_URL is correctly set (currently: {api_url_to_test}).")
        print(f"If using Ollama, make sure you have pulled the moondream model (e.g., 'ollama pull moondream').")

    # Clean up dummy image
    if os.path.exists("test_image_moondream.png"):
        try:
            os.remove("test_image_moondream.png")
            print("\nCleaned up dummy image 'test_image_moondream.png'.")
        except Exception as e:
            print(f"Error cleaning up dummy image: {e}")
