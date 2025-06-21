import pyautogui
from PIL import Image

def capture_screen_region(x: int, y: int, width: int, height: int, filename: str = None) -> Image.Image:
    """
    Captures a specified region of the primary screen.

    Args:
        x: The x-coordinate of the top-left corner of the region.
        y: The y-coordinate of the top-left corner of the region.
        width: The width of the region.
        height: The height of the region.
        filename: Optional. If provided, the screenshot will be saved to this path.

    Returns:
        A PIL/Pillow Image object of the captured region.
    """
    try:
        screenshot = pyautogui.screenshot(region=(x, y, width, height))
        if filename:
            screenshot.save(filename)
        return screenshot
    except Exception as e:
        # Consider more specific error handling or logging
        print(f"Error capturing screen region: {e}")
        raise

def capture_full_screen(filename: str = None) -> Image.Image:
    """
    Captures the entire primary screen.

    Args:
        filename: Optional. If provided, the screenshot will be saved to this path.

    Returns:
        A PIL/Pillow Image object of the captured screen.
    """
    try:
        screenshot = pyautogui.screenshot()
        if filename:
            screenshot.save(filename)
        return screenshot
    except Exception as e:
        print(f"Error capturing full screen: {e}")
        raise

def get_screen_resolution() -> tuple[int, int]:
    """
    Gets the resolution of the primary screen.

    Returns:
        A tuple (width, height) in pixels.
    """
    try:
        width, height = pyautogui.size()
        return width, height
    except Exception as e:
        print(f"Error getting screen resolution: {e}")
        raise

if __name__ == '__main__':
    # Example usage (be careful, this will actually take screenshots if run)
    try:
        res_width, res_height = get_screen_resolution()
        print(f"Screen Resolution: {res_width}x{res_height}")

        # Capture a small region (e.g., top-left 100x100 pixels)
        # Ensure the coordinates and size are valid for your screen
        if res_width >= 100 and res_height >= 100:
            print("Capturing 100x100 region at (0,0)...")
            region_image = capture_screen_region(0, 0, 100, 100, "test_region_capture.png")
            print(f"Captured region image: {region_image.size}, format: {region_image.format}")
            print("Saved to test_region_capture.png")
        else:
            print("Screen resolution too small for 100x100 region test.")

        # Capture full screen
        # print("Capturing full screen...")
        # full_screen_image = capture_full_screen("test_full_screen_capture.png")
        # print(f"Captured full screen image: {full_screen_image.size}, format: {full_screen_image.format}")
        # print("Saved to test_full_screen_capture.png")

    except Exception as e:
        print(f"An error occurred during example usage: {e}")
