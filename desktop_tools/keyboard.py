import pyautogui
try:
    from config_manager import config
except ImportError:
    print("Warning: config_manager not found. Using PyAutoGUI default settings for keyboard.py.")
    config = {}

# Apply global PyAutoGUI settings from config
# FAILSAFE is more mouse-related but PAUSE applies to keyboard actions too if set globally.
pyautogui.FAILSAFE = config.get("PYAUTOGUI_FAILSAFE_ENABLED", True)
pyautogui.PAUSE = config.get("PYAUTOGUI_PAUSE_PER_ACTION", 0.1)


def keyboard_type(text: str, interval: float = 0.01) -> None:
    """
    Types the given text using the keyboard.

    Args:
        text: The string to type.
        interval: The time in seconds between pressing each key. Defaults to 0.01.
    """
    try:
        pyautogui.write(text, interval=interval)
    except Exception as e:
        print(f"Error typing text: {e}")
        raise

def keyboard_press_key(key_name: str | list[str]) -> None:
    """
    Presses a single key or a sequence of keys.
    For special keys, use names like 'enter', 'esc', 'ctrl', 'shift', 'alt', 'tab',
    'left', 'right', 'up', 'down', 'f1', 'volumemute', etc.
    See pyautogui.KEYBOARD_KEYS for all available special key names.

    Args:
        key_name: The name of the key to press (e.g., 'enter') or a list of key names to press in sequence.
    """
    try:
        if isinstance(key_name, list):
            pyautogui.press(key_name)
        else:
            pyautogui.press(key_name)
    except Exception as e:
        print(f"Error pressing key(s): {e}")
        raise

def keyboard_hotkey(keys: list[str]) -> None:
    """
    Presses a combination of keys simultaneously (e.g., Ctrl+C).

    Args:
        keys: A list of key names to press together.
              Example: ['ctrl', 'c'] for Ctrl+C
                       ['ctrl', 'shift', 'esc'] for Ctrl+Shift+Esc
    """
    if not keys:
        print("Warning: keyboard_hotkey called with an empty list of keys.")
        return
    try:
        pyautogui.hotkey(*keys)
    except Exception as e:
        print(f"Error pressing hotkey: {e}")
        raise

if __name__ == '__main__':
    # Example usage (BE VERY CAREFUL - this will type and press keys)
    # It's recommended to have a text editor or safe window focused before running.
    pyautogui.FAILSAFE = True # Move mouse to top-left corner to stop

    try:
        print("Focus a text editor or a safe input field within 5 seconds to test typing...")
        pyautogui.sleep(5)

        # Test typing
        # print("Typing 'Hello, World!'...")
        # keyboard_type("Hello, World!")
        # print("Typing test complete.")
        # pyautogui.sleep(1)

        # Test pressing Enter key
        # print("Pressing 'Enter' key...")
        # keyboard_press_key('enter')
        # print("Enter key press test complete.")
        # pyautogui.sleep(1)

        # Test pressing a sequence of keys
        # print("Typing 'abc' by pressing keys 'a', 'b', 'c' in sequence...")
        # keyboard_press_key(['a', 'b', 'c'])
        # print("Sequence key press test complete.")
        # pyautogui.sleep(1)

        # Test hotkey (e.g., Ctrl+A to select all - be careful where this is active)
        # print("Simulating Ctrl+A (select all) in 3 seconds... Ensure a safe context!")
        # pyautogui.sleep(3)
        # keyboard_hotkey(['ctrl', 'a'])
        # print("Hotkey test complete.")

        print("\nExample usage section complete. Most actions are commented out for safety.")
        print("To test, uncomment specific actions and ensure a safe window is focused and pyautogui.FAILSAFE is True.")

    except pyautogui.FailSafeException:
        print("PyAutoGUI FAILSAFE triggered (mouse moved to a corner). Script terminated.")
    except Exception as e:
        print(f"An error occurred during example usage: {e}")
