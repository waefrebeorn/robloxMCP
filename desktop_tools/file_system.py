import os
import logging
from pathlib import Path
from typing import List, Dict, Union, Optional

logger = logging.getLogger(__name__)

# Define a maximum file size for reading to prevent memory issues with large files
MAX_READ_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

def list_directory(path_str: str) -> Dict[str, Union[str, List[Dict[str, str]]]]:
    """
    Lists the contents (files and subdirectories) of a given directory path.

    Args:
        path_str: The absolute or relative path to the directory.

    Returns:
        A dictionary containing:
        - "path": The absolute path of the listed directory.
        - "contents": A list of dictionaries, each representing an item in the directory
                      with "name" and "type" ('file' or 'directory').
        - "error": An error message if the path is invalid or inaccessible.
    """
    try:
        path = Path(path_str).resolve() # Resolve to absolute path and handle symlinks potentially

        if not path.exists():
            return {"error": f"Path does not exist: {path_str}"}
        if not path.is_dir():
            return {"error": f"Path is not a directory: {path_str}"}

        items = []
        for item in path.iterdir():
            item_type = "directory" if item.is_dir() else "file"
            items.append({"name": item.name, "type": item_type})

        logger.info(f"Listed directory '{path}'. Found {len(items)} items.")
        return {"path": str(path), "contents": items}

    except PermissionError:
        logger.error(f"Permission denied for path: {path_str}")
        return {"error": f"Permission denied for path: {path_str}"}
    except Exception as e:
        logger.error(f"Error listing directory '{path_str}': {e}", exc_info=True)
        return {"error": f"An unexpected error occurred while listing directory: {e}"}

def read_text_file(path_str: str, max_chars: Optional[int] = None) -> Dict[str, str]:
    """
    Reads the content of a text file.

    Args:
        path_str: The absolute or relative path to the text file.
        max_chars: Optional. Maximum number of characters to read from the beginning of the file.
                   If None, attempts to read up to MAX_READ_FILE_SIZE_BYTES.

    Returns:
        A dictionary containing:
        - "path": The absolute path of the read file.
        - "content": The content of the file (potentially truncated).
        - "error": An error message if the path is invalid, not a file, too large, or unreadable.
        - "warning": A warning message if the content was truncated.
    """
    try:
        path = Path(path_str).resolve()

        if not path.exists():
            return {"error": f"File does not exist: {path_str}"}
        if not path.is_file():
            return {"error": f"Path is not a file: {path_str}"}

        file_size = path.stat().st_size
        if file_size > MAX_READ_FILE_SIZE_BYTES and max_chars is None:
            warning_msg = (f"File is large ({file_size} bytes). "
                           f"Reading only the first {MAX_READ_FILE_SIZE_BYTES // 1024}KB.")
            logger.warning(warning_msg)
            # Read only up to the defined max size for very large files if no specific max_chars
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(MAX_READ_FILE_SIZE_BYTES)
            return {"path": str(path), "content": content, "warning": warning_msg}

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            if max_chars is not None and max_chars > 0:
                content = f.read(max_chars)
                warning = "Content truncated to max_chars." if len(content) == max_chars and file_size > max_chars else None
                logger.info(f"Read {len(content)} characters from file '{path}'. Max_chars was {max_chars}.")
                return {"path": str(path), "content": content, "warning": warning}
            else: # No max_chars or invalid max_chars, read full file (up to internal limit already checked)
                content = f.read()
                logger.info(f"Read file '{path}'. Length: {len(content)} chars.")
                return {"path": str(path), "content": content}

    except PermissionError:
        logger.error(f"Permission denied for file: {path_str}")
        return {"error": f"Permission denied for file: {path_str}"}
    except UnicodeDecodeError:
        logger.error(f"Cannot decode file as UTF-8 text: {path_str}. It might be a binary file.")
        return {"error": f"File is likely not a text file or has an unsupported encoding: {path_str}"}
    except Exception as e:
        logger.error(f"Error reading file '{path_str}': {e}", exc_info=True)
        return {"error": f"An unexpected error occurred while reading file: {e}"}

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    logger.info("File System Module Example")

    # Create some dummy files and directories for testing
    test_dir = Path("./test_fs_dir")
    test_dir.mkdir(exist_ok=True)
    (test_dir / "file1.txt").write_text("This is file1.\nHello world.")
    (test_dir / "file2.log").write_text("Log entry 1\nLog entry 2")
    (test_dir / "subdir").mkdir(exist_ok=True)
    (test_dir / "subdir" / "nested_file.txt").write_text("Nested content.")

    # Test list_directory
    print("\n--- Listing current directory ---")
    # current_dir_contents = list_directory(".") # Use a known directory for more consistent testing
    test_dir_contents = list_directory(str(test_dir))
    if "error" in test_dir_contents:
        print(f"Error: {test_dir_contents['error']}")
    else:
        print(f"Contents of {test_dir_contents['path']}:")
        for item in test_dir_contents.get("contents", []):
            print(f"  - {item['name']} ({item['type']})")

    print("\n--- Listing non-existent directory ---")
    non_existent_contents = list_directory("./non_existent_dir_test_fs")
    if "error" in non_existent_contents:
        print(f"Correctly handled error: {non_existent_contents['error']}")
    else:
        print("Error: Expected an error for non-existent directory.")

    # Test read_text_file
    file1_path = str(test_dir / "file1.txt")
    print(f"\n--- Reading file: {file1_path} ---")
    file1_data = read_text_file(file1_path)
    if "error" in file1_data:
        print(f"Error: {file1_data['error']}")
    else:
        print(f"Content of {file1_data['path']}:\n---\n{file1_data['content']}\n---")
        if "warning" in file1_data and file1_data["warning"]:
            print(f"Warning: {file1_data['warning']}")

    print(f"\n--- Reading file with max_chars: {file1_path} (10 chars) ---")
    file1_partial_data = read_text_file(file1_path, max_chars=10)
    if "error" in file1_partial_data:
        print(f"Error: {file1_partial_data['error']}")
    else:
        print(f"Content (partial): {file1_partial_data['content']}")
        if "warning" in file1_partial_data and file1_partial_data["warning"]:
            print(f"Warning: {file1_partial_data['warning']}")

    # Test reading a non-text file (e.g., a directory treated as a file)
    print(f"\n--- Attempting to read directory as text file: {test_dir} ---")
    dir_as_file_data = read_text_file(str(test_dir))
    if "error" in dir_as_file_data:
        print(f"Correctly handled error: {dir_as_file_data['error']}")
    else:
        print("Error: Expected an error when trying to read a directory as a text file.")

    # Clean up dummy files and directory
    try:
        (test_dir / "subdir" / "nested_file.txt").unlink()
        (test_dir / "subdir").rmdir()
        (test_dir / "file1.txt").unlink()
        (test_dir / "file2.log").unlink()
        test_dir.rmdir()
        logger.info("Cleaned up test directory and files.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    logger.info("File system example finished.")
