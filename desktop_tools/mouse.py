import pyautogui
try:
    from config_manager import config
except ImportError:
    # Fallback if config_manager is not in the Python path directly
    # This might happen if desktop_tools is used as a standalone library
    # In the main application, config_manager should be accessible
    print("Warning: config_manager not found. Using PyAutoGUI default settings for mouse.py.")
    config = {}

# Apply global PyAutoGUI settings from config
pyautogui.FAILSAFE = config.get("PYAUTOGUI_FAILSAFE_ENABLED", True)
pyautogui.PAUSE = config.get("PYAUTOGUI_PAUSE_PER_ACTION", 0.1)


def mouse_move(x: int, y: int, duration: float = 0.25) -> None:
    """
    Moves the mouse cursor to the specified X, Y coordinates.

    Args:
        x: The target x-coordinate.
        y: The target y-coordinate.
        duration: The time in seconds to spend moving the mouse. Defaults to 0.25.
    """
    try:
        pyautogui.moveTo(x, y, duration=duration)
    except Exception as e:
        print(f"Error moving mouse: {e}")
        raise

def mouse_click(x: int = None, y: int = None, button: str = 'left', clicks: int = 1, interval: float = 0.1) -> None:
    """
    Performs a mouse click. Can click at current position or specified X, Y coordinates.

    Args:
        x: Optional. The target x-coordinate. If None, clicks at current mouse position.
        y: Optional. The target y-coordinate. If None, clicks at current mouse position.
        button: The mouse button to click ('left', 'middle', 'right'). Defaults to 'left'.
        clicks: The number of times to click. Defaults to 1.
        interval: The time in seconds between clicks. Defaults to 0.1.
    """
    try:
        pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
    except Exception as e:
        print(f"Error clicking mouse: {e}")
        raise

def mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5, button: str = 'left') -> None:
    """
    Drags the mouse from a starting position to an ending position.

    Args:
        start_x: The x-coordinate of the drag start.
        start_y: The y-coordinate of the drag start.
        end_x: The x-coordinate of the drag end.
        end_y: The y-coordinate of the drag end.
        duration: The time in seconds to spend dragging. Defaults to 0.5.
        button: The mouse button to hold down during the drag ('left', 'middle', 'right'). Defaults to 'left'.
    """
    try:
        pyautogui.moveTo(start_x, start_y, duration=0.1) # Move to start position quickly
        pyautogui.dragTo(end_x, end_y, duration=duration, button=button)
    except Exception as e:
        print(f"Error dragging mouse: {e}")
        raise

def mouse_scroll(amount: int, x: int = None, y: int = None) -> None:
    """
    Scrolls the mouse wheel. Positive amount scrolls up, negative scrolls down.

    Args:
        amount: The number of units to scroll. Positive for up, negative for down.
        x: Optional. The x-coordinate where the scroll should occur. Defaults to current mouse position.
        y: Optional. The y-coordinate where the scroll should occur. Defaults to current mouse position.
    """
    try:
        pyautogui.scroll(amount, x=x, y=y)
    except Exception as e:
        print(f"Error scrolling mouse: {e}")
        raise

if __name__ == '__main__':
    # Example usage (BE VERY CAREFUL - this will move and click your mouse)
    # It's recommended to have a way to quickly stop scripts (e.g., move mouse to a corner for pyautogui.FAILSAFE)
    pyautogui.FAILSAFE = True # Move mouse to top-left corner to stop

    try:
        current_x, current_y = pyautogui.position()
        print(f"Current mouse position: {current_x}, {current_y}")

        # Test move (move to 100,100 relative to current for safety, then back)
        # target_x, target_y = current_x + 100, current_y + 100
        # print(f"Moving mouse to {target_x},{target_y} and back...")
        # mouse_move(target_x, target_y, duration=0.5)
        # mouse_move(current_x, current_y, duration=0.5)
        # print("Move test complete.")

        # Test click (at current position - ensure a safe spot is selected before running)
        # print("Clicking left mouse button at current position in 3 seconds...")
        # pyautogui.sleep(3)
        # mouse_click()
        # print("Click test complete.")

        # Test scroll (scroll down by 10 units)
        # print("Scrolling down by 10 units in 3 seconds...")
        # pyautogui.sleep(3)
        # mouse_scroll(-10) # Negative for down
        # print("Scroll test complete.")

        # Test drag (draw a small square - ensure a safe spot for dragging)
        # print("Preparing to drag in 3 seconds... (drawing a small square)")
        # pyautogui.sleep(3)
        # drag_start_x, drag_start_y = pyautogui.position()
        # print(f"Drag start: {drag_start_x}, {drag_start_y}")
        # mouse_drag(drag_start_x, drag_start_y, drag_start_x + 50, drag_start_y, duration=0.5)
        # mouse_drag(drag_start_x + 50, drag_start_y, drag_start_x + 50, drag_start_y + 50, duration=0.5)
        # mouse_drag(drag_start_x + 50, drag_start_y + 50, drag_start_x, drag_start_y + 50, duration=0.5)
        # mouse_drag(drag_start_x, drag_start_y + 50, drag_start_x, drag_start_y, duration=0.5)
        # print("Drag test complete.")

        print("Example usage section complete. Most actions are commented out for safety.")
        print("To test, uncomment specific actions and ensure pyautogui.FAILSAFE is True.")

    except pyautogui.FailSafeException:
        print("PyAutoGUI FAILSAFE triggered (mouse moved to a corner). Script terminated.")
    except Exception as e:
        print(f"An error occurred during example usage: {e}")
