import pygetwindow as gw
import pywinctl
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

def list_windows(title_filter: Optional[str] = None) -> List[str]:
    """
    Lists the titles of all currently open and visible windows.
    Optionally filters by title (case-insensitive contains).

    Args:
        title_filter: Optional string to filter window titles.
                      Only windows whose titles contain this string will be returned.

    Returns:
        A list of window titles.
    """
    titles = []
    try:
        all_windows = gw.getAllWindows()
        for window in all_windows:
            # Filter out windows with no title or that might be background processes
            if window.title and window.visible and not window.isMinimized:
                if title_filter:
                    if title_filter.lower() in window.title.lower():
                        titles.append(window.title)
                else:
                    titles.append(window.title)
        logger.info(f"Found {len(titles)} windows matching filter '{title_filter if title_filter else 'None'}'.")
    except Exception as e:
        logger.error(f"Error listing windows: {e}", exc_info=True)
    return titles

def get_active_window_title() -> Optional[str]:
    """
    Gets the title of the currently active (focused) window.

    Returns:
        The title of the active window, or None if it cannot be determined or has no title.
    """
    try:
        active_window = gw.getActiveWindow()
        if active_window and active_window.title:
            logger.info(f"Active window title: '{active_window.title}'")
            return active_window.title
        elif active_window:
            logger.info("Active window found but has no title.")
            return "" # Return empty string if active but no title
        else:
            logger.info("No active window found by pygetwindow.")
            return None
    except Exception as e:
        logger.error(f"Error getting active window title: {e}", exc_info=True)
        return None

def focus_window(title: str) -> bool:
    """
    Attempts to focus (activate) a window with the given title.
    Uses an exact title match first, then a case-insensitive substring match if exact fails.

    Args:
        title: The title of the window to focus.

    Returns:
        True if the window was successfully focused, False otherwise.
    """
    try:
        # PyWinCtl provides more reliable activation
        windows = pywinctl.getAllWindows()
        target_window_ctl = None

        # Try exact match first
        for win_ctl in windows:
            if win_ctl.title == title:
                target_window_ctl = win_ctl
                break

        # If no exact match, try case-insensitive substring
        if not target_window_ctl:
            for win_ctl in windows:
                if title.lower() in win_ctl.title.lower():
                    target_window_ctl = win_ctl
                    logger.info(f"Focusing window via substring match: '{target_window_ctl.title}' for query '{title}'")
                    break

        if target_window_ctl:
            try:
                target_window_ctl.activate()
                # Verify activation (sometimes activate() might not raise error but fail)
                # A short delay might be needed for the OS to process activation
                import time; time.sleep(0.2)
                if gw.getActiveWindow() and gw.getActiveWindow().title == target_window_ctl.title:
                    logger.info(f"Successfully focused window: '{target_window_ctl.title}'")
                    return True
                else:
                    logger.warning(f"Called activate on '{target_window_ctl.title}', but it did not become the active window.")
                    # Fallback attempt with pygetwindow for activation if pywinctl didn't make it active
                    gw_windows = gw.getWindowsWithTitle(target_window_ctl.title)
                    if gw_windows:
                        gw_windows[0].activate()
                        time.sleep(0.2)
                        if gw.getActiveWindow() and gw.getActiveWindow().title == target_window_ctl.title:
                            logger.info(f"Successfully focused window with pygetwindow fallback: '{target_window_ctl.title}'")
                            return True
                    logger.warning(f"Still failed to focus window '{target_window_ctl.title}' after pygetwindow fallback.")
                    return False

            except Exception as e_activate:
                logger.error(f"Error activating window '{target_window_ctl.title}': {e_activate}", exc_info=True)
                return False
        else:
            logger.warning(f"Window with title containing '{title}' not found for focusing.")
            return False
    except Exception as e:
        logger.error(f"General error focusing window: {e}", exc_info=True)
        return False

def get_window_geometry(title: str) -> Optional[Dict[str, int]]:
    """
    Gets the geometry (x, y, width, height) of a window with the given title.
    Uses an exact title match first, then a case-insensitive substring match.

    Args:
        title: The title of the window.

    Returns:
        A dictionary {"x": x, "y": y, "width": width, "height": height} or None if not found.
    """
    try:
        # Using pygetwindow as it's generally good for geometry and finding windows
        target_windows = gw.getWindowsWithTitle(title)
        found_window = None

        if target_windows: # Exact match
            found_window = target_windows[0]
        else: # Try substring match
            all_windows = gw.getAllWindows()
            for window in all_windows:
                if window.title and title.lower() in window.title.lower():
                    found_window = window
                    logger.info(f"Found window for geometry via substring: '{found_window.title}' for query '{title}'")
                    break

        if found_window:
            if not found_window.visible or found_window.isMinimized:
                 logger.warning(f"Window '{found_window.title}' found but is not visible or is minimized. Geometry might be inaccurate or (0,0).")

            # PyGetWindow returns box(left, top, right, bottom)
            # We want x, y, width, height
            # x = left, y = top, width = right - left, height = bottom - top
            # However, PyGetWindow also directly provides .left, .top, .width, .height
            geometry = {
                "x": found_window.left,
                "y": found_window.top,
                "width": found_window.width,
                "height": found_window.height,
                "title": found_window.title # Include actual matched title
            }
            logger.info(f"Geometry for window '{found_window.title}': {geometry}")
            return geometry
        else:
            logger.warning(f"Window with title containing '{title}' not found for geometry.")
            return None
    except Exception as e:
        logger.error(f"Error getting window geometry: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    logger.info("Window Manager Module Example")

    print("\n--- Listing all visible windows ---")
    all_titles = list_windows()
    if all_titles:
        for i, title in enumerate(all_titles):
            print(f"{i+1}. {title}")
    else:
        print("No visible windows found or error occurred.")

    print("\n--- Listing windows containing 'Visual Studio Code' (example) ---")
    vscode_titles = list_windows(title_filter="Visual Studio Code") # Adjust filter as needed
    if vscode_titles:
        for i, title in enumerate(vscode_titles):
            print(f"{i+1}. {title}")
    else:
        print("No 'Visual Studio Code' windows found.")

    print("\n--- Getting active window title ---")
    active_title = get_active_window_title()
    if active_title is not None: # Could be empty string if active window has no title
        print(f"Active window: '{active_title}'")
    else:
        print("Could not determine active window or no active window.")

    # --- Focus and Geometry Test (Interactive - be careful) ---
    # Find a safe window title to test with, e.g., "Calculator" or "Notepad" if open.
    # test_window_title_exact = "Calculator" # Change this to a window you have open
    # test_window_title_substring = "Calc"   # Or a substring

    # print(f"\n--- Attempting to get geometry for window titled '{test_window_title_exact}' ---")
    # geom = get_window_geometry(test_window_title_exact)
    # if geom:
    #     print(f"Geometry: {geom}")
    # else:
    #     print(f"Window '{test_window_title_exact}' not found for geometry.")

    # print(f"\n--- Attempting to focus window '{test_window_title_exact}' in 3 seconds ---")
    # print("Ensure it's open and visible. This might steal focus.")
    # import time
    # time.sleep(3)
    # if focus_window(test_window_title_exact):
    #     print(f"Successfully focused '{test_window_title_exact}'. Check if it's now active.")
    #     focused_active_title = get_active_window_title()
    #     print(f"Window active after focus attempt: '{focused_active_title}'")
    # else:
    #     print(f"Failed to focus '{test_window_title_exact}'.")

    logger.info("Window manager example finished.")
