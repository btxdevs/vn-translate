Okay, let's rework the caching system according to your requirements.

**Changes Summary:**

1.  **Game Identification:** Added `get_executable_details(hwnd)` in `utils/capture.py` to get the executable path and size.
2.  **Cache Directory:** Changed `CACHE_DIR` in `utils/translation.py` to be a `cache` subdirectory within the application's root folder.
3.  **Game-Specific Cache Files:** Cache files are now named `<game_hash>.json` inside the `cache` directory.
4.  **Cache Key:** Simplified `get_cache_key` in `utils/translation.py` to only use `text` and `target_language`.
5.  **Cache Functions:** Modified cache loading/saving functions in `utils/translation.py` to work with game-specific files.
6.  **Cache Clearing:** Added `clear_current_game_cache(hwnd)` and `clear_all_cache()` in `utils/translation.py`.
7.  **UI Updates:** Added "Clear Current Game Cache" button in `ui/translation_tab.py` and updated the existing clear button.
8.  **Integration:** Modified `TranslationTab.perform_translation` to pass the `hwnd` to `translate_text`. Modified `App.__init__` to ensure the cache directory exists.
9.  **Code Style:** Ensured proper indentation and removed semicolons.

---

Here are the full scripts for the modified files:

**`utils/capture.py`**
```python
# --- START OF FILE utils/capture.py ---

import win32gui
import win32ui
import win32con
import mss
import numpy as np
import cv2
from ctypes import windll, byref, wintypes
import time # For performance timing
import win32process # For getting process ID and executable path
import win32api # For opening process
import os # For getting file size

# Flag to reduce repetitive logging
LOG_CAPTURE_DETAILS = False # Set to True for debugging capture methods/rects

def enum_window_callback(hwnd, windows):
    """Callback for win32gui.EnumWindows adds visible, non-minimized windows with titles."""
    try:
        # Filter more aggressively: check style, title, visibility, parent, not minimized
        if not win32gui.IsWindowVisible(hwnd): return True
        if not win32gui.GetWindowText(hwnd): return True
        # if win32gui.GetParent(hwnd) != 0: return True # Exclude child windows? Might exclude some games.
        if win32gui.IsIconic(hwnd): return True # Exclude minimized

        # Optional: Filter based on class name? (e.g., exclude Taskbar, specific tool windows)
        # class_name = win32gui.GetClassName(hwnd)
        # if class_name in ["Shell_TrayWnd", "Progman", "ApplicationFrameWindow"]: return True # AppFrame for UWP borders

        windows.append(hwnd)
    except Exception as e:
        # Ignore errors for windows we can't access
        # print(f"Enum callback error for HWND {hwnd}: {e}")
        pass
    return True

def get_windows():
    """Return a list of handles for potentially relevant windows."""
    if LOG_CAPTURE_DETAILS: print("Getting list of windows...")
    windows = []
    try:
        win32gui.EnumWindows(enum_window_callback, windows)
    except Exception as e:
        print(f"Error during EnumWindows: {e}")
    if LOG_CAPTURE_DETAILS: print(f"Found {len(windows)} candidate windows")
    return windows

def get_window_title(hwnd):
    """Return the title of a window given its handle."""
    try:
        title = win32gui.GetWindowText(hwnd)
        # if LOG_CAPTURE_DETAILS: print(f"Window title for HWND {hwnd}: {title}")
        return title
    except Exception as e:
        # print(f"Error getting title for HWND {hwnd}: {e}") # Can be noisy
        return ""

def get_executable_details(hwnd):
    """
    Gets the full path and size of the executable associated with the window handle.

    Args:
        hwnd: The window handle.

    Returns:
        A tuple (executable_path, file_size) or (None, None) if failed.
    """
    try:
        if not hwnd or not win32gui.IsWindow(hwnd):
            return None, None

        # Get the process ID (PID) associated with the window thread
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            print(f"Could not get PID for HWND {hwnd}")
            return None, None

        # Open the process with necessary access rights
        # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ might be needed
        # Using PROCESS_QUERY_LIMITED_INFORMATION for potentially better compatibility/security
        process_handle = None
        try:
            process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        except Exception as open_err:
            # Fallback if limited info fails (e.g., older systems or specific permissions)
            try:
                process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
            except Exception as open_err_fallback:
                print(f"Could not open process PID {pid} for HWND {hwnd}: {open_err_fallback}")
                return None, None

        if not process_handle:
             print(f"Failed to get handle for process PID {pid}")
             return None, None

        try:
            # Get the executable file path
            exe_path = win32process.GetModuleFileNameEx(process_handle, 0)
            if not exe_path or not os.path.exists(exe_path):
                print(f"Could not get valid executable path for PID {pid}")
                return None, None

            # Get the file size
            file_size = os.path.getsize(exe_path)
            return exe_path, file_size

        except Exception as e:
            print(f"Error getting module filename or size for PID {pid}: {e}")
            return None, None
        finally:
            if process_handle:
                win32api.CloseHandle(process_handle)

    except Exception as e:
        print(f"General error getting executable details for HWND {hwnd}: {e}")
        return None, None


def get_window_rect(hwnd):
    """Return (left, top, right, bottom) of the window including borders."""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        if LOG_CAPTURE_DETAILS: print(f"Window rect for HWND {hwnd}: {rect}")
        return rect
    except Exception as e:
        print(f"Error getting window rect for HWND {hwnd}: {e}")
        return None

def get_client_rect(hwnd):
    """Get the client area rectangle relative to the screen."""
    try:
        if not win32gui.IsWindow(hwnd): return None

        # Get client rectangle relative to window's top-left
        client_rect_rel = win32gui.GetClientRect(hwnd)
        # if LOG_CAPTURE_DETAILS: print(f"Relative client rect for HWND {hwnd}: {client_rect_rel}")

        # Convert client rect's top-left (0,0) and bottom-right points to screen coordinates
        pt_tl = wintypes.POINT(client_rect_rel[0], client_rect_rel[1])
        pt_br = wintypes.POINT(client_rect_rel[2], client_rect_rel[3])

        # Check if ClientToScreen succeeds
        if not windll.user32.ClientToScreen(hwnd, byref(pt_tl)):
            print(f"ClientToScreen failed for top-left point, HWND {hwnd}")
            return None
        if not windll.user32.ClientToScreen(hwnd, byref(pt_br)):
            print(f"ClientToScreen failed for bottom-right point, HWND {hwnd}")
            return None

        # Screen coordinates rectangle
        rect_screen = (pt_tl.x, pt_tl.y, pt_br.x, pt_br.y)
        # if LOG_CAPTURE_DETAILS: print(f"Screen client rect for HWND {hwnd}: {rect_screen}")
        return rect_screen
    except Exception as e:
        print(f"Error getting client rect for HWND {hwnd}: {e}")
        return None

def capture_window_direct(hwnd):
    """
    Capture window's client area using Windows API (PrintWindow/BitBlt).
    Returns numpy array (BGR) or None.
    """
    start_time = time.perf_counter()
    save_bitmap = None # Define outside try for cleanup
    save_dc = None
    mfc_dc = None
    hwnd_dc = None
    try:
        # --- Get Target Area ---
        # Prioritize client rect
        target_rect = get_client_rect(hwnd)
        rect_type = "Client"
        if target_rect is None:
            # Fallback to full window rect if client rect fails
            target_rect = get_window_rect(hwnd)
            rect_type = "Window"
            if target_rect is None:
                print(f"Failed to get any rect for HWND {hwnd}. Cannot capture.")
                return None

        left, top, right, bottom = target_rect
        width = right - left
        height = bottom - top

        if LOG_CAPTURE_DETAILS:
            print(f"Direct Capture using {rect_type} Rect: ({left},{top}) {width}x{height}")

        if width <= 0 or height <= 0:
            # print(f"Invalid dimensions for HWND {hwnd}: {width}x{height}")
            # If it's the window rect, maybe the window is minimized?
            if rect_type == "Window" and win32gui.IsIconic(hwnd):
                print("Window is minimized.")
            return None

        # --- Prepare Device Contexts ---
        # Get DC for the entire window (needed for PrintWindow and BitBlt source)
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        if not hwnd_dc:
            print(f"Failed to get Window DC for HWND {hwnd}")
            return None
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        # Create compatible DC for destination bitmap
        save_dc = mfc_dc.CreateCompatibleDC()

        # --- Create Bitmap ---
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        # Select bitmap into destination DC
        save_dc.SelectObject(save_bitmap)

        # --- Perform Capture ---
        # Try PrintWindow first (better for layered windows, DWM)
        # Flags: 0 = Full window, 1 = Client area only (use if rect_type == "Client"),
        # 2 (PW_RENDERFULLCONTENT) or 3? Docs vary. Let's stick to 0 or 1.
        # PW_CLIENTONLY = 0x00000001
        # PW_RENDERFULLCONTENT = 0x00000002 # Needed for some modern apps
        print_window_flag = 0x1 | 0x2 if rect_type == "Client" else 0x2 # Try client + full render or just full render

        result = 0
        try:
            # Important: For PrintWindow, the target DC (save_dc) gets the content.
            # The source is the window itself (hwnd).
            result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), print_window_flag)
            # if LOG_CAPTURE_DETAILS: print(f"PrintWindow result: {result} (Flag: {print_window_flag})")
        except Exception as pw_error:
            print(f"PrintWindow call failed: {pw_error}")
            result = 0

        # Fallback to BitBlt if PrintWindow failed (result is 0)
        if not result:
            if LOG_CAPTURE_DETAILS: print("PrintWindow failed or skipped, falling back to BitBlt")
            try:
                # For BitBlt: Copy from source DC (mfc_dc) to destination DC (save_dc)
                # Source origin depends on the DC obtained by GetWindowDC.
                # For client rect, we want to copy from the client origin within that DC.
                # For window rect, we copy from (0,0).
                src_x = 0
                src_y = 0
                if rect_type == "Client":
                    # Client rect was screen coords, need coords relative to window origin
                    window_rect = win32gui.GetWindowRect(hwnd)
                    src_x = left - window_rect[0] # client left screen - window left screen
                    src_y = top - window_rect[1]  # client top screen - window top screen
                    if LOG_CAPTURE_DETAILS: print(f"BitBlt source offset: ({src_x}, {src_y})")


                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (src_x, src_y), win32con.SRCCOPY)
                # if LOG_CAPTURE_DETAILS: print("BitBlt executed.")
            except Exception as blt_error:
                print(f"BitBlt failed: {blt_error}")
                # Clean up handled in finally block
                return None


        # --- Convert Bitmap to Numpy Array ---
        bmp_info = save_bitmap.GetInfo()
        bmp_str = save_bitmap.GetBitmapBits(True)
        # Check if bitmap data is valid
        if not bmp_str or len(bmp_str) != bmp_info['bmWidthBytes'] * bmp_info['bmHeight']:
            print("Error: Invalid bitmap data received.")
            return None

        img = np.frombuffer(bmp_str, dtype='uint8')
        img.shape = (bmp_info['bmHeight'], bmp_info['bmWidth'], 4) # BGRA format

        # Remove alpha channel, convert to BGR
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        end_time = time.perf_counter()
        if LOG_CAPTURE_DETAILS:
            print(f"Direct capture success ({rect_type}). Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")

        return img_bgr

    except Exception as e:
        print(f"!!! Direct capture error for HWND {hwnd}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # --- Ensure Cleanup ---
        try:
            if save_bitmap: win32gui.DeleteObject(save_bitmap.GetHandle())
        except: pass
        try:
            if save_dc: save_dc.DeleteDC()
        except: pass
        try:
            if mfc_dc: mfc_dc.DeleteDC()
        except: pass
        try:
            if hwnd_dc: win32gui.ReleaseDC(hwnd, hwnd_dc)
        except: pass


def capture_window_mss(hwnd):
    """
    Capture window using MSS (fallback, uses screen coordinates).
    Returns numpy array (BGR) or None.
    """
    start_time = time.perf_counter()
    try:
        # --- Get Target Area (Screen Coordinates) ---
        # Must use screen coordinates for MSS
        target_rect = get_client_rect(hwnd)
        rect_type = "Client"
        if target_rect is None:
            target_rect = get_window_rect(hwnd)
            rect_type = "Window"
            if target_rect is None:
                print(f"MSS: Failed to get any rect for HWND {hwnd}.")
                return None

        left, top, right, bottom = target_rect
        width = right - left
        height = bottom - top

        # if LOG_CAPTURE_DETAILS:
        #      print(f"MSS Capture using Screen {rect_type} Rect: ({left},{top}) {width}x{height}")

        if width <= 0 or height <= 0:
            # print(f"MSS: Invalid dimensions for HWND {hwnd}: {width}x{height}")
            return None

        # --- Capture using MSS ---
        monitor = {"left": left, "top": top, "width": width, "height": height}
        with mss.mss() as sct:
            img_mss = sct.grab(monitor)

        # Convert to numpy array (BGRA) -> (BGR)
        img_bgra = np.array(img_mss, dtype=np.uint8)
        img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)

        end_time = time.perf_counter()
        # if LOG_CAPTURE_DETAILS:
        #      print(f"MSS capture success ({rect_type}). Shape: {img_bgr.shape}. Time: {end_time - start_time:.4f}s")

        return img_bgr

    except Exception as e:
        print(f"!!! MSS capture error for HWND {hwnd}: {e}")
        return None


def capture_window(hwnd):
    """
    Capture a window using the best available method.
    Tries direct capture first, then falls back to MSS.

    Args:
        hwnd: Window handle

    Returns:
        numpy array (BGR) of the captured frame or None if failed
    """
    # Check if window handle is valid and window is visible/not minimized
    if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
        # print(f"Capture attempt skipped: Invalid/hidden/minimized HWND {hwnd}") # Can be noisy
        return None

    # Try direct method
    frame = capture_window_direct(hwnd)

    # If direct failed, try MSS
    if frame is None:
        if LOG_CAPTURE_DETAILS: print("Direct capture failed, trying MSS fallback...")
        frame = capture_window_mss(hwnd)
        if frame is None and LOG_CAPTURE_DETAILS:
            print("MSS capture also failed.")

    # Optional: Check frame dimensions/content?
    if frame is not None and (frame.shape[0] < 10 or frame.shape[1] < 10):
        # print(f"Warning: Captured frame seems too small ({frame.shape}).")
        return None # Reject tiny frames?

    return frame

# --- END OF FILE utils/capture.py ---
```

**`utils/translation.py`**
```python
# --- START OF FILE utils/translation.py ---

import json
import re
import os
from openai import OpenAI
from pathlib import Path
import hashlib # For cache key generation
import time # For potential corrupted cache backup naming
from utils.capture import get_executable_details # Import the new function

# File-based cache settings
APP_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Get app root directory
CACHE_DIR = APP_DIR / "cache"

# Context management (global list)
context_messages = []

def _ensure_cache_dir():
    """Make sure the cache directory exists"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating cache directory {CACHE_DIR}: {e}")

def _get_game_hash(hwnd):
    """Generates a hash based on the game's executable path and size."""
    exe_path, file_size = get_executable_details(hwnd)
    if exe_path and file_size is not None:
        try:
            # Normalize path, use lower case, combine with size
            identity_string = f"{os.path.normpath(exe_path).lower()}|{file_size}"
            hasher = hashlib.sha256()
            hasher.update(identity_string.encode('utf-8'))
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error generating game hash: {e}")
    return None

def _get_cache_file_path(hwnd):
    """Gets the specific cache file path for the given game window."""
    game_hash = _get_game_hash(hwnd)
    if game_hash:
        return CACHE_DIR / f"{game_hash}.json"
    else:
        print("Warning: Could not determine game hash. Using default cache file.")
        # Fallback to a generic name if hashing fails
        return CACHE_DIR / "default_cache.json"


def _load_cache(cache_file_path):
    """Load the translation cache from the specified game file"""
    _ensure_cache_dir()
    try:
        if cache_file_path.exists():
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                # Check if file is empty
                content = f.read()
                if not content:
                    return {}
                return json.loads(content)
    except json.JSONDecodeError:
        print(f"Warning: Cache file {cache_file_path} is corrupted or empty. Starting fresh cache.")
        try:
            # Optionally backup corrupted file
            corrupted_path = cache_file_path.parent / f"{cache_file_path.name}.corrupted_{int(time.time())}"
            os.rename(cache_file_path, corrupted_path)
            print(f"Corrupted cache backed up to {corrupted_path}")
        except Exception as backup_err:
            print(f"Error backing up corrupted cache file: {backup_err}")
        return {}
    except Exception as e:
        print(f"Error loading cache from {cache_file_path}: {e}")
    return {}


def _save_cache(cache, cache_file_path):
    """Save the translation cache to the specified game file"""
    _ensure_cache_dir()
    try:
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving cache to {cache_file_path}: {e}")

def reset_context():
    """Reset the translation context history."""
    global context_messages
    context_messages = []
    print("Translation context history reset.")
    return "Translation context has been reset."

def add_context_message(message, context_limit):
    """Add a message to the translation context history, enforcing the limit."""
    global context_messages
    # Ensure context_limit is a positive integer
    try:
        limit = int(context_limit)
        if limit <= 0:
            limit = 1 # Keep at least one exchange if limit is invalid
    except (ValueError, TypeError):
        limit = 10 # Default if conversion fails

    context_messages.append(message)
    # Maintain pairs (user + assistant). Trim oldest pairs if limit exceeded.
    # Example: limit=2 means keep last 2 user and 2 assistant messages (4 total)
    max_messages = limit * 2
    if len(context_messages) > max_messages:
        context_messages = context_messages[-max_messages:]
        print(f"Context trimmed to last {len(context_messages)} messages (limit: {limit} exchanges).")


def clear_current_game_cache(hwnd):
    """Clear the translation cache for the currently selected game."""
    cache_file_path = _get_cache_file_path(hwnd)
    if not cache_file_path:
        return "Could not identify game to clear cache."

    if cache_file_path.exists():
        try:
            os.remove(cache_file_path)
            print(f"Cache file deleted: {cache_file_path}")
            return f"Cache cleared for the current game ({cache_file_path.stem})."
        except Exception as e:
            print(f"Error deleting cache file {cache_file_path}: {e}")
            return f"Error clearing current game cache: {e}"
    else:
        print(f"Cache file not found for current game: {cache_file_path}")
        return "Cache for the current game was already empty."

def clear_all_cache():
    """Clear all translation cache files in the cache directory."""
    _ensure_cache_dir()
    cleared_count = 0
    errors = []
    try:
        for item in CACHE_DIR.iterdir():
            if item.is_file() and item.suffix == '.json':
                try:
                    os.remove(item)
                    cleared_count += 1
                    print(f"Deleted cache file: {item.name}")
                except Exception as e:
                    errors.append(item.name)
                    print(f"Error deleting cache file {item.name}: {e}")

        if errors:
            return f"Cleared {cleared_count} cache files. Errors deleting: {', '.join(errors)}."
        elif cleared_count > 0:
            return f"Successfully cleared all {cleared_count} translation cache files."
        else:
            return "Cache directory was empty or contained no cache files."
    except Exception as e:
        print(f"Error iterating cache directory {CACHE_DIR}: {e}")
        return f"Error accessing cache directory: {e}"


def get_cache_key(text, target_language):
    """
    Generate a unique cache key based ONLY on the input text and target language.
    """
    # Use a hash to keep keys manageable
    hasher = hashlib.sha256()
    hasher.update(text.encode('utf-8'))
    hasher.update(target_language.encode('utf-8'))
    return hasher.hexdigest()

def get_cached_translation(cache_key, cache_file_path):
    """Get a cached translation if it exists from the specific game cache file."""
    if not cache_file_path: return None
    cache = _load_cache(cache_file_path)
    return cache.get(cache_key)

def set_cache_translation(cache_key, translation, cache_file_path):
    """Cache a translation result to the specific game cache file."""
    if not cache_file_path: return
    cache = _load_cache(cache_file_path)
    cache[cache_key] = translation
    _save_cache(cache, cache_file_path)


def parse_translation_output(response_text, original_tag_mapping):
    """
    Parse the translation output from a tagged format (<|n|>)
    and map it back to the original ROI names using the tag_mapping.

    Args:
        response_text: The raw text from the LLM.
        original_tag_mapping: Dictionary mapping segment numbers ('1', '2',...) to original ROI names.

    Returns:
        Dictionary mapping original ROI names to translated text.
        Returns {'error': msg} if parsing fails badly.
    """
    parsed_segments = {}
    # Regex to find <|number|> content pairs, trying to capture content until the next tag or end of string
    # Updated regex to handle potential variations and ensure non-greedy matching of content
    pattern = r"<\|(\d+)\|>(.*?)(?=<\|\d+\|>|$)"

    matches = re.findall(pattern, response_text, re.DOTALL | re.MULTILINE) # DOTALL matches newline, MULTILINE anchors ^$

    if matches:
        for segment_number, content in matches:
            original_roi_name = original_tag_mapping.get(segment_number)
            if original_roi_name:
                # Clean up content: strip leading/trailing whitespace
                cleaned_content = content.strip()
                # Optional: Normalize multiple spaces/newlines within the content?
                # cleaned_content = ' '.join(cleaned_content.split())
                parsed_segments[original_roi_name] = cleaned_content
            else:
                print(f"Warning: Received segment number '{segment_number}' which was not in the original mapping.")
    else:
        # Fallback: Try strict line-by-line matching if the first pattern failed
        line_pattern = r"^\s*<\|(\d+)\|>\s*(.*)$" # Match only if tag is at the start of a line
        lines = response_text.strip().split('\n')
        found_line_match = False
        for line in lines:
            match = re.match(line_pattern, line)
            if match:
                found_line_match = True
                segment_number, content = match.groups()
                original_roi_name = original_tag_mapping.get(segment_number)
                if original_roi_name:
                    parsed_segments[original_roi_name] = content.strip()
                else:
                    print(f"Warning: Received segment number '{segment_number}' (line match) which was not in original mapping.")
        if not found_line_match:
            # If still no matches, the format is likely wrong
            print("[LOG] Failed to parse any <|n|> segments from response:")
            print(f"Raw Response: '{response_text}'")
            # Attempt a very basic extraction if response is just plain text (single segment case?)
            if not response_text.startswith("<|") and len(original_tag_mapping) == 1:
                first_tag = next(iter(original_tag_mapping))
                first_roi = original_tag_mapping[first_tag]
                print(f"Warning: Response had no tags, assuming plain text response for single ROI '{first_roi}'.")
                parsed_segments[first_roi] = response_text.strip()
            else:
                # Only return error if it's not a single segment plain text response
                return {"error": f"Error: Unable to extract formatted translation.\nRaw response:\n{response_text}"}


    # Check if all original tags were translated
    missing_tags = set(original_tag_mapping.values()) - set(parsed_segments.keys())
    if missing_tags:
        print(f"Warning: Translation response missing segments for ROIs: {', '.join(missing_tags)}")
        # Add placeholders for missing ones
        for roi_name in missing_tags:
            parsed_segments[roi_name] = "[Translation Missing]"


    return parsed_segments


def preprocess_text_for_translation(aggregated_text):
    """
    Convert input text with tags like [tag]: content to the numbered format <|1|> content.
    Ensures that only lines matching the pattern are converted.

    Args:
        aggregated_text: Multi-line string with "[ROI_Name]: Content" format.

    Returns:
        tuple: (preprocessed_text_for_llm, tag_mapping)
               preprocessed_text_for_llm: Text like "<|1|> Content1\n<|2|> Content2"
               tag_mapping: Dictionary mapping '1' -> 'ROI_Name1', '2' -> 'ROI_Name2'
    """
    lines = aggregated_text.strip().split('\n')
    preprocessed_lines = []
    tag_mapping = {}
    segment_count = 1

    for line in lines:
        # More robust regex: allows spaces around colon, captures ROI name and content
        match = re.match(r'^\s*\[\s*([^\]]+)\s*\]\s*:\s*(.*)$', line)
        if match:
            roi_name, content = match.groups()
            roi_name = roi_name.strip()
            content = content.strip()
            if content: # Only include segments with actual content
                tag_mapping[str(segment_count)] = roi_name
                preprocessed_lines.append(f"<|{segment_count}|> {content}")
                segment_count += 1
            else:
                print(f"Skipping empty content for ROI: {roi_name}")
        else:
            # Ignore lines that don't match the expected format
            print(f"Ignoring line, does not match '[ROI]: content' format: {line}")

    if not tag_mapping:
        print("Warning: No lines matched the '[ROI]: content' format during preprocessing.")

    return '\n'.join(preprocessed_lines), tag_mapping


def translate_text(aggregated_input_text, hwnd, preset, target_language="en", additional_context="", context_limit=10):
    """
    Translate the given text using an OpenAI-compatible API client, using game-specific caching.

    Args:
        aggregated_input_text: Text in "[ROI_Name]: Content" format.
        hwnd: The window handle of the game (used for cache identification).
        preset: The translation preset configuration (LLM specific parts).
        target_language: The target language code (e.g., "en", "Spanish").
        additional_context: General instructions or context from the UI.
        context_limit: Max number of conversational exchanges (user+assistant pairs) to keep.

    Returns:
        A dictionary mapping original ROI names to translated text,
        or {'error': message} on failure.
    """
    # 0. Determine Cache File
    cache_file_path = _get_cache_file_path(hwnd)
    if not cache_file_path:
        print("Error: Cannot proceed with translation without a valid cache file path.")
        return {"error": "Could not determine cache file path for the game."}

    # 1. Preprocess input text to <|n|> format and get mapping
    preprocessed_text_for_llm, tag_mapping = preprocess_text_for_translation(aggregated_input_text)

    if not preprocessed_text_for_llm or not tag_mapping:
        print("No valid text segments found after preprocessing. Nothing to translate.")
        return {} # Return empty dict if nothing to translate

    # 2. Check Cache (Using simplified key)
    cache_key = get_cache_key(preprocessed_text_for_llm, target_language)
    cached_result = get_cached_translation(cache_key, cache_file_path)
    if cached_result:
        print(f"[LOG] Using cached translation for key: {cache_key[:10]}... from {cache_file_path.name}")
        # Ensure cache returns the expected format (roi_name -> translation)
        if isinstance(cached_result, dict) and not 'error' in cached_result:
            # Quick check: does cached result contain keys for current request?
            if all(roi_name in cached_result for roi_name in tag_mapping.values()):
                return cached_result
            else:
                print("[LOG] Cached result seems incomplete for current request, fetching fresh translation.")
        else:
            print("[LOG] Cached result format mismatch or error, fetching fresh translation.")


    # 3. Prepare messages for API
    # System Prompt
    system_prompt = preset.get('system_prompt', "You are a translator.")
    # Refined System Prompt for clarity
    system_content = (
        f"{system_prompt}\n\n"
        f"Translate the following text segments into {target_language}. "
        "Input segments are tagged like <|1|>, <|2|>, etc. "
        "Your response MUST replicate this format exactly, using the same tags for the corresponding translated segments. "
        "For example, input '<|1|> Hello\n<|2|> World' requires output '<|1|> [Translation of Hello]\n<|2|> [Translation of World]'. "
        "Output ONLY the tagged translated lines. Do NOT add introductions, explanations, apologies, or any text outside the <|n|> tags."
    )
    messages = [{"role": "system", "content": system_content}]

    # Add context history (if any)
    global context_messages
    if context_messages:
        messages.extend(context_messages)
        print(f"[LOG] Including {len(context_messages)} messages from context history.")


    # Current User Request
    user_message_parts = []
    # Add additional context from UI if provided
    if additional_context.strip():
        user_message_parts.append(f"Additional context: {additional_context.strip()}")

    # The core request
    user_message_parts.append(f"Translate these segments to {target_language}, maintaining the exact <|n|> tags:")
    user_message_parts.append(preprocessed_text_for_llm)

    user_content = "\n\n".join(user_message_parts)
    current_user_message = {"role": "user", "content": user_content}
    messages.append(current_user_message)

    # 4. Prepare API Payload
    # Validate required preset fields
    if not preset.get("model") or not preset.get("api_url"):
        missing = [f for f in ["model", "api_url"] if not preset.get(f)]
        errmsg = f"Missing required preset fields: {', '.join(missing)}"
        print(f"[LOG] {errmsg}")
        return {"error": errmsg}

    payload = {
        "model": preset["model"],
        "messages": messages,
        "temperature": preset.get("temperature", 0.3),
        "max_tokens": preset.get("max_tokens", 1000)
    }
    # Add optional parameters safely
    for param in ["top_p", "frequency_penalty", "presence_penalty"]:
        if param in preset and preset[param] is not None:
            try:
                payload[param] = float(preset[param])
            except (ValueError, TypeError):
                print(f"Warning: Invalid value for parameter '{param}': {preset[param]}. Skipping.")


    print("[LOG] Sending translation request...")
    # print(json.dumps(payload, indent=2, ensure_ascii=False)) # Might reveal API keys if preset has them

    # 5. Initialize API Client
    try:
        # Ensure API key is handled correctly (might be None or empty string)
        api_key = preset.get("api_key") or None # Treat empty string as None for client
        client = OpenAI(
            base_url=preset.get("api_url"),
            api_key=api_key
        )
    except Exception as e:
        print(f"[LOG] Error creating API client: {e}")
        return {"error": f"Error creating API client: {e}"}

    # 6. Make API Request
    try:
        completion = client.chat.completions.create(**payload)
        # Check for valid response structure
        if not completion.choices or not completion.choices[0].message or completion.choices[0].message.content is None:
            print("[LOG] Invalid response structure received from API.")
            print(f"API Response: {completion}")
            return {"error": "Invalid response structure received from API."}

        response_text = completion.choices[0].message.content.strip()
        print(f"[LOG] Raw LLM response received ({len(response_text)} chars).")
        # print(f"[LOG] Raw response snippet: '{response_text[:100]}...'")
    except Exception as e:
        # Try to get more info from the exception if it's an APIError
        error_message = str(e)
        status_code = getattr(e, 'status_code', 'N/A')
        try:
            # Attempt to parse error body if it's JSON
            error_body = json.loads(getattr(e, 'body', '{}') or '{}')
            detail = error_body.get('error', {}).get('message', '')
            if detail: error_message = detail
        except:
            pass # Ignore parsing errors
        log_msg = f"[LOG] API error during translation request: Status {status_code}, Error: {error_message}"
        print(log_msg)
        return {"error": f"API Error ({status_code}): {error_message}"}


    # 7. Parse LLM Response
    # Use the tag_mapping from preprocessing to convert back to ROI names
    final_translations = parse_translation_output(response_text, tag_mapping)

    # Check if parsing resulted in an error
    if 'error' in final_translations:
        print("[LOG] Parsing failed after receiving response.")
        return final_translations # Return the error dictionary

    # 8. Update Context and Cache
    # Add the successful exchange to context
    current_assistant_message = {"role": "assistant", "content": response_text}
    # Add user message first, then assistant response
    add_context_message(current_user_message, context_limit)
    add_context_message(current_assistant_message, context_limit)

    # Add to cache using the key generated earlier and the game-specific file
    set_cache_translation(cache_key, final_translations, cache_file_path)
    print(f"[LOG] Translation cached successfully to {cache_file_path.name}")

    return final_translations

# --- END OF FILE utils/translation.py ---
```

**`ui/translation_tab.py`**
```python
# --- START OF FILE ui/translation_tab.py ---

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import copy
from ui.base import BaseTab
from utils.translation import translate_text, clear_all_cache, clear_current_game_cache, reset_context # Updated imports
from utils.config import save_translation_presets, load_translation_presets
from utils.settings import get_setting, set_setting, update_settings # Import settings functions

# Default presets configuration
DEFAULT_PRESETS = {
    "OpenAI (GPT-3.5)": {
        "api_url": "https://api.openai.com/v1/chat/completions", # Corrected endpoint
        "api_key": "",
        "model": "gpt-3.5-turbo",
        "system_prompt": (
            "You are a professional translator. Translate the following text from its source language to the target language. "
            "Return your answer in the following format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "and so on. Provide only the tagged translated text lines, each preceded by its tag."
        ),
        "temperature": 0.3,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1000,
        "context_limit": 10
    },
    "OpenAI (GPT-4)": {
        "api_url": "https://api.openai.com/v1/chat/completions", # Corrected endpoint
        "api_key": "",
        "model": "gpt-4", # Or specific variants like gpt-4-turbo-preview
        "system_prompt": (
            "You are a professional translator. Translate the following text from its source language to the target language. "
            "Return your answer in the following format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "and so on. Provide only the tagged translated text lines, each preceded by its tag."
        ),
        "temperature": 0.3,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1000,
        "context_limit": 10
    },
    "Claude": {
        "api_url": "https://api.anthropic.com/v1/messages", # Corrected endpoint
        "api_key": "", # Requires header x-api-key
        "model": "claude-3-haiku-20240307", # Or other Claude models
        "system_prompt": ( # Claude uses 'system' parameter, not message role
            "You are a translation assistant. Translate the following text and format your answer as follows:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "Only output the tagged lines."
        ),
        "temperature": 0.3,
        "top_p": 1.0, # Check if Claude supports top_p, might use top_k
        "max_tokens": 1000, # Claude uses max_tokens
        "context_limit": 10
        # Note: Claude API structure differs significantly from OpenAI.
        # utils.translation.py would need adaptation for non-OpenAI compatible APIs.
        # This preset might not work without modifications to the API call logic.
    },
    "Mistral": {
        "api_url": "https://api.mistral.ai/v1/chat/completions", # OpenAI compatible endpoint
        "api_key": "",
        "model": "mistral-medium-latest", # Or other Mistral models
        "system_prompt": (
            "You are a professional translator. Translate the following text accurately and return the output in this format:\n"
            "<|1|> translated text for segment 1\n"
            "<|2|> translated text for segment 2\n"
            "Only include the tagged lines."
        ),
        "temperature": 0.3,
        "top_p": 0.95, # Mistral supports top_p
        "max_tokens": 1000,
        "context_limit": 10
    }
    # Add Local LLM Example (using LM Studio / Ollama OpenAI compatible endpoint)
    ,"Local Model (LM Studio/Ollama)": {
        "api_url": "http://localhost:1234/v1/chat/completions", # Example LM Studio endpoint
        "api_key": "not-needed", # Usually not needed for local
        "model": "loaded-model-name", # Specify the model loaded in your local server
        "system_prompt": (
            "You are a helpful translation assistant. Translate the provided text segments into the target language. "
            "The input format uses tags like <|1|>, <|2|>, etc. Your response MUST strictly adhere to this format, "
            "reproducing the exact same tags for each corresponding translated segment. "
            "Output ONLY the tagged translated lines."
        ),
        "temperature": 0.5,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "max_tokens": 1500,
        "context_limit": 5
    }
}

class TranslationTab(BaseTab):
    """Tab for translation settings and results with improved preset management."""

    def setup_ui(self):
        # --- Load relevant settings ---
        self.target_language = get_setting("target_language", "en")
        self.additional_context = get_setting("additional_context", "")
        self.auto_translate_enabled = get_setting("auto_translate", False)
        last_preset_name = get_setting("last_preset_name")

        # --- Translation settings frame ---
        self.settings_frame = ttk.LabelFrame(self.frame, text="Translation Settings", padding="10")
        self.settings_frame.pack(fill=tk.X, pady=10)

        # --- Preset Management ---
        preset_frame = ttk.Frame(self.settings_frame)
        preset_frame.pack(fill=tk.X, pady=5)

        ttk.Label(preset_frame, text="Preset:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        # Load presets
        self.translation_presets = load_translation_presets()
        if not self.translation_presets:
            self.translation_presets = copy.deepcopy(DEFAULT_PRESETS)
            # Optionally save the defaults if they were missing
            # save_translation_presets(self.translation_presets)

        self.preset_names = sorted(list(self.translation_presets.keys())) # Sort names
        self.preset_combo = ttk.Combobox(preset_frame, values=self.preset_names, width=30, state="readonly") # Wider
        preset_index = -1
        if last_preset_name and last_preset_name in self.preset_names:
            try:
                preset_index = self.preset_names.index(last_preset_name)
            except ValueError:
                pass # Name not found
        if preset_index != -1:
            self.preset_combo.current(preset_index)
        elif self.preset_names:
            self.preset_combo.current(0) # Default to first if last not found

        self.preset_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_selected)

        # Preset management buttons
        btn_frame = ttk.Frame(preset_frame)
        btn_frame.grid(row=0, column=2, padx=5, pady=5)

        self.save_preset_btn = ttk.Button(btn_frame, text="Save", command=self.save_preset)
        self.save_preset_btn.pack(side=tk.LEFT, padx=2)

        self.save_as_preset_btn = ttk.Button(btn_frame, text="Save As...", command=self.save_preset_as)
        self.save_as_preset_btn.pack(side=tk.LEFT, padx=2)

        self.delete_preset_btn = ttk.Button(btn_frame, text="Delete", command=self.delete_preset)
        self.delete_preset_btn.pack(side=tk.LEFT, padx=2)

        # Make preset combo column expandable
        preset_frame.columnconfigure(1, weight=1)

        # --- Notebook for settings ---
        self.settings_notebook = ttk.Notebook(self.settings_frame)
        self.settings_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # === Basic Settings Tab ===
        self.basic_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.basic_frame, text="General Settings") # Renamed tab

        # Target language (Loads from general settings)
        ttk.Label(self.basic_frame, text="Target Language:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_lang_entry = ttk.Entry(self.basic_frame, width=15) # Wider
        self.target_lang_entry.insert(0, self.target_language)
        self.target_lang_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.target_lang_entry.bind("<FocusOut>", self.save_basic_settings) # Save on leaving field
        self.target_lang_entry.bind("<Return>", self.save_basic_settings)   # Save on pressing Enter

        # Additional context (Loads from general settings)
        ttk.Label(self.basic_frame, text="Additional Context:", anchor=tk.NW).grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.additional_context_text = tk.Text(self.basic_frame, width=40, height=5, wrap=tk.WORD)
        self.additional_context_text.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=5) # Expand fully
        scroll_ctx = ttk.Scrollbar(self.basic_frame, command=self.additional_context_text.yview)
        scroll_ctx.grid(row=1, column=2, sticky=tk.NS, pady=5)
        self.additional_context_text.config(yscrollcommand=scroll_ctx.set)
        self.additional_context_text.insert("1.0", self.additional_context)
        self.additional_context_text.bind("<FocusOut>", self.save_basic_settings) # Save on leaving field

        # Make context column expandable
        self.basic_frame.columnconfigure(1, weight=1)
        self.basic_frame.rowconfigure(1, weight=1) # Allow context text to expand vertically


        # === Preset Settings Tab ===
        self.preset_settings_frame = ttk.Frame(self.settings_notebook, padding=10)
        self.settings_notebook.add(self.preset_settings_frame, text="Preset Details") # Renamed tab

        # API Key (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_key_entry = ttk.Entry(self.preset_settings_frame, width=40, show="*")
        self.api_key_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        # API URL (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="API URL:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_url_entry = ttk.Entry(self.preset_settings_frame, width=40)
        self.api_url_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        # Model (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="Model:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_entry = ttk.Entry(self.preset_settings_frame, width=40)
        self.model_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)

        # System prompt (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="System Prompt:", anchor=tk.NW).grid(row=3, column=0, sticky=tk.NW, padx=5, pady=5)
        self.system_prompt_text = tk.Text(self.preset_settings_frame, width=50, height=6, wrap=tk.WORD)
        self.system_prompt_text.grid(row=3, column=1, sticky=tk.NSEW, padx=5, pady=5) # Expand
        scroll_sys = ttk.Scrollbar(self.preset_settings_frame, command=self.system_prompt_text.yview)
        scroll_sys.grid(row=3, column=2, sticky=tk.NS, pady=5)
        self.system_prompt_text.config(yscrollcommand=scroll_sys.set)

        # Context Limit (Part of Preset)
        ttk.Label(self.preset_settings_frame, text="Context Limit (History):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.context_limit_entry = ttk.Entry(self.preset_settings_frame, width=10)
        self.context_limit_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        # --- Advanced Parameters Frame ---
        adv_param_frame = ttk.Frame(self.preset_settings_frame)
        adv_param_frame.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(10,0))

        # Temperature (Part of Preset)
        ttk.Label(adv_param_frame, text="Temp:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.temperature_entry = ttk.Entry(adv_param_frame, width=8)
        self.temperature_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Top P (Part of Preset)
        ttk.Label(adv_param_frame, text="Top P:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        self.top_p_entry = ttk.Entry(adv_param_frame, width=8)
        self.top_p_entry.grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)

        # Frequency Penalty (Part of Preset)
        ttk.Label(adv_param_frame, text="Freq Pen:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.frequency_penalty_entry = ttk.Entry(adv_param_frame, width=8)
        self.frequency_penalty_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # Presence Penalty (Part of Preset)
        ttk.Label(adv_param_frame, text="Pres Pen:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        self.presence_penalty_entry = ttk.Entry(adv_param_frame, width=8)
        self.presence_penalty_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)

        # Max Tokens (Part of Preset)
        ttk.Label(adv_param_frame, text="Max Tokens:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.max_tokens_entry = ttk.Entry(adv_param_frame, width=8)
        self.max_tokens_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Make columns expandable in preset settings frame
        self.preset_settings_frame.columnconfigure(1, weight=1)
        self.preset_settings_frame.rowconfigure(3, weight=1) # Allow system prompt to expand

        # Load initial preset data
        self.on_preset_selected() # Load data for the initially selected preset

        # === Action Buttons ===
        action_frame = ttk.Frame(self.settings_frame)
        action_frame.pack(fill=tk.X, pady=10)

        # --- Cache and Context Buttons ---
        cache_context_frame = ttk.Frame(action_frame)
        cache_context_frame.pack(side=tk.LEFT, padx=0)

        self.clear_current_cache_btn = ttk.Button(cache_context_frame, text="Clear Current Game Cache", command=self.clear_current_translation_cache)
        self.clear_current_cache_btn.pack(side=tk.TOP, padx=5, pady=2, anchor=tk.W)

        self.clear_all_cache_btn = ttk.Button(cache_context_frame, text="Clear All Cache", command=self.clear_all_translation_cache)
        self.clear_all_cache_btn.pack(side=tk.TOP, padx=5, pady=2, anchor=tk.W)

        self.reset_context_btn = ttk.Button(cache_context_frame, text="Reset Translation Context", command=self.reset_translation_context)
        self.reset_context_btn.pack(side=tk.TOP, padx=5, pady=(5,2), anchor=tk.W) # Add some top padding

        # --- Translate Button ---
        self.translate_btn = ttk.Button(action_frame, text="Translate Stable Text Now", command=self.perform_translation)
        self.translate_btn.pack(side=tk.RIGHT, padx=5, pady=5) # Add padding

        # === Auto Translation Option (Loads from general settings) ===
        auto_frame = ttk.Frame(self.settings_frame)
        auto_frame.pack(fill=tk.X, pady=5)

        self.auto_translate_var = tk.BooleanVar(value=self.auto_translate_enabled)
        self.auto_translate_check = ttk.Checkbutton(
            auto_frame,
            text="Auto-translate when stable text changes",
            variable=self.auto_translate_var,
            command=self.toggle_auto_translate # Save setting on change
        )
        self.auto_translate_check.pack(side=tk.LEFT, padx=5)

        # === Translation Output ===
        output_frame = ttk.LabelFrame(self.frame, text="Translated Text (Preview)", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.translation_display = tk.Text(output_frame, wrap=tk.WORD, height=10, width=40) # Reduced height
        self.translation_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(output_frame, command=self.translation_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.translation_display.config(yscrollcommand=scrollbar.set)
        self.translation_display.config(state=tk.DISABLED)

    def save_basic_settings(self, event=None):
        """Save non-preset settings like target language and additional context."""
        new_target_lang = self.target_lang_entry.get().strip()
        new_additional_context = self.additional_context_text.get("1.0", tk.END).strip()

        # Use update_settings for efficiency
        settings_to_update = {}
        changed = False
        if new_target_lang != self.target_language:
            settings_to_update["target_language"] = new_target_lang
            self.target_language = new_target_lang
            changed = True
        if new_additional_context != self.additional_context:
            settings_to_update["additional_context"] = new_additional_context
            self.additional_context = new_additional_context
            changed = True

        if changed and settings_to_update:
            if update_settings(settings_to_update):
                print("General translation settings (lang/context) updated.")
                self.app.update_status("Target language/context saved.")
            else:
                messagebox.showerror("Error", "Failed to save general translation settings.")
        elif changed: # Should not happen if settings_to_update is empty but check anyway
            print("Logic error: Changed flag set but no settings to update.")


    def toggle_auto_translate(self):
        """Save the auto-translate setting."""
        self.auto_translate_enabled = self.auto_translate_var.get()
        if set_setting("auto_translate", self.auto_translate_enabled):
            status_msg = f"Auto-translate {'enabled' if self.auto_translate_enabled else 'disabled'}."
            print(status_msg)
            self.app.update_status(status_msg)
            # Sync with floating controls if they exist
            if self.app.floating_controls and self.app.floating_controls.winfo_exists():
                self.app.floating_controls.auto_var.set(self.auto_translate_enabled)
        else:
            messagebox.showerror("Error", "Failed to save auto-translate setting.")


    def is_auto_translate_enabled(self):
        """Check if auto-translation is enabled."""
        return self.auto_translate_var.get() # Use the variable directly

    def get_translation_config(self):
        """Get the current translation preset AND general settings."""
        preset_name = self.preset_combo.get()
        if not preset_name or preset_name not in self.translation_presets:
            messagebox.showerror("Error", "No valid translation preset selected.", parent=self.app.master)
            return None

        # Get preset values directly from the stored dictionary
        preset_config_base = self.translation_presets.get(preset_name)
        if not preset_config_base:
            messagebox.showerror("Error", f"Could not load preset data for '{preset_name}'.", parent=self.app.master)
            return None

        # --- Crucially, get API key from the UI entry, not the saved preset ---
        # This allows users to enter keys without saving them permanently in the preset file
        api_key_from_ui = self.api_key_entry.get().strip()

        # --- Get other preset values from UI (allowing unsaved changes for translation) ---
        try:
            preset_config_from_ui = {
                "api_key": api_key_from_ui, # Use UI key
                "api_url": self.api_url_entry.get().strip(),
                "model": self.model_entry.get().strip(),
                "system_prompt": self.system_prompt_text.get("1.0", tk.END).strip(),
                "temperature": float(self.temperature_entry.get().strip() or 0.3),
                "top_p": float(self.top_p_entry.get().strip() or 1.0),
                "frequency_penalty": float(self.frequency_penalty_entry.get().strip() or 0.0),
                "presence_penalty": float(self.presence_penalty_entry.get().strip() or 0.0),
                "max_tokens": int(self.max_tokens_entry.get().strip() or 1000),
                "context_limit": int(self.context_limit_entry.get().strip() or 10)
            }
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid number format in Preset Details: {e}", parent=self.app.master)
            return None


        # --- Get general settings from UI / saved state ---
        target_lang = self.target_lang_entry.get().strip()
        additional_ctx = self.additional_context_text.get("1.0", tk.END).strip()

        # --- Combine into a working configuration ---
        # Use the preset settings currently displayed in the UI
        working_config = preset_config_from_ui
        # Add the non-preset settings
        working_config["target_language"] = target_lang
        working_config["additional_context"] = additional_ctx

        # Validate required fields (URL and Model primarily)
        # API Key validity checked by API call itself
        if not working_config.get("api_url"):
            messagebox.showwarning("Warning", "API URL is missing in preset details.", parent=self.app.master)
            # return None # Allow proceeding maybe?
        if not working_config.get("model"):
            messagebox.showwarning("Warning", "Model name is missing in preset details.", parent=self.app.master)
            # return None

        return working_config


    def on_preset_selected(self, event=None):
        """Load the selected preset into the UI fields, BUT keep UI API key if already entered."""
        preset_name = self.preset_combo.get()
        if not preset_name or preset_name not in self.translation_presets:
            # Keep current UI values if selection is invalid
            print(f"Invalid preset selected: {preset_name}")
            return

        preset = self.translation_presets[preset_name]
        print(f"Loading preset '{preset_name}' into UI.")

        # --- Load preset values into UI ---
        # Preserve API Key if user has entered one, otherwise load from preset
        current_api_key = self.api_key_entry.get().strip()
        preset_api_key = preset.get("api_key", "")
        self.api_key_entry.delete(0, tk.END)
        self.api_key_entry.insert(0, current_api_key if current_api_key else preset_api_key)


        self.api_url_entry.delete(0, tk.END)
        self.api_url_entry.insert(0, preset.get("api_url", ""))

        self.model_entry.delete(0, tk.END)
        self.model_entry.insert(0, preset.get("model", ""))

        self.system_prompt_text.delete("1.0", tk.END)
        self.system_prompt_text.insert("1.0", preset.get("system_prompt", ""))

        self.context_limit_entry.delete(0, tk.END)
        self.context_limit_entry.insert(0, str(preset.get("context_limit", 10)))

        self.temperature_entry.delete(0, tk.END)
        self.temperature_entry.insert(0, str(preset.get("temperature", 0.3)))

        self.top_p_entry.delete(0, tk.END)
        self.top_p_entry.insert(0, str(preset.get("top_p", 1.0)))

        self.frequency_penalty_entry.delete(0, tk.END)
        self.frequency_penalty_entry.insert(0, str(preset.get("frequency_penalty", 0.0)))

        self.presence_penalty_entry.delete(0, tk.END)
        self.presence_penalty_entry.insert(0, str(preset.get("presence_penalty", 0.0)))

        self.max_tokens_entry.delete(0, tk.END)
        self.max_tokens_entry.insert(0, str(preset.get("max_tokens", 1000)))

        # --- Save the name of the selected preset ---
        set_setting("last_preset_name", preset_name)


    def get_current_preset_values_for_saving(self):
        """Get ONLY the preset-specific values from the UI fields for saving."""
        try:
            # Only include fields that belong IN the preset file
            preset_data = {
                "api_key": self.api_key_entry.get().strip(), # Save the key from UI to preset
                "api_url": self.api_url_entry.get().strip(),
                "model": self.model_entry.get().strip(),
                "system_prompt": self.system_prompt_text.get("1.0", tk.END).strip(),
                "temperature": float(self.temperature_entry.get().strip() or 0.3),
                "top_p": float(self.top_p_entry.get().strip() or 1.0),
                "frequency_penalty": float(self.frequency_penalty_entry.get().strip() or 0.0),
                "presence_penalty": float(self.presence_penalty_entry.get().strip() or 0.0),
                "max_tokens": int(self.max_tokens_entry.get().strip() or 1000),
                "context_limit": int(self.context_limit_entry.get().strip() or 10)
            }
            # Basic validation
            if not preset_data["api_url"] or not preset_data["model"]:
                # Don't prevent saving, but maybe warn?
                print("Warning: Saving preset with potentially empty API URL or Model.")
            return preset_data
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid number format in Preset Details: {e}", parent=self.app.master)
            return None
        except Exception as e:
            messagebox.showerror("Error", f"Could not read preset settings: {e}", parent=self.app.master)
            return None

    def save_preset(self):
        """Save the current UI settings (preset part) to the selected preset."""
        preset_name = self.preset_combo.get()
        if not preset_name:
            messagebox.showwarning("Warning", "No preset selected to save over.", parent=self.app.master)
            return

        preset_data = self.get_current_preset_values_for_saving()
        if preset_data is None:
            return # Error message already shown

        confirm = messagebox.askyesno("Confirm Save", f"Overwrite preset '{preset_name}' with current settings?", parent=self.app.master)
        if not confirm:
            return

        self.translation_presets[preset_name] = preset_data
        if save_translation_presets(self.translation_presets):
            messagebox.showinfo("Saved", f"Preset '{preset_name}' has been updated.", parent=self.app.master)
        else:
            # Error message shown by save_translation_presets
            pass


    def save_preset_as(self):
        """Save the current UI settings (preset part) as a new preset."""
        new_name = simpledialog.askstring("Save Preset As", "Enter a name for the new preset:", parent=self.app.master)
        if not new_name:
            return # User cancelled

        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("Warning", "Preset name cannot be empty.", parent=self.app.master)
            return

        preset_data = self.get_current_preset_values_for_saving()
        if preset_data is None:
            return # Error message already shown

        if new_name in self.translation_presets:
            overwrite = messagebox.askyesno("Overwrite", f"Preset '{new_name}' already exists. Overwrite?", parent=self.app.master)
            if not overwrite:
                return

        self.translation_presets[new_name] = preset_data
        if save_translation_presets(self.translation_presets):
            # Update the combobox
            self.preset_names = sorted(list(self.translation_presets.keys()))
            self.preset_combo['values'] = self.preset_names
            self.preset_combo.set(new_name)
            # Save the new name as the last used
            set_setting("last_preset_name", new_name)
            messagebox.showinfo("Saved", f"Preset '{new_name}' has been saved.", parent=self.app.master)
        else:
            # Error message shown by save_translation_presets
            # Rollback the addition? Maybe not necessary if saving failed.
            if new_name in self.translation_presets:
                del self.translation_presets[new_name] # Clean up if it was added locally


    def delete_preset(self):
        """Delete the selected preset."""
        preset_name = self.preset_combo.get()
        if not preset_name:
            messagebox.showwarning("Warning", "No preset selected to delete.", parent=self.app.master)
            return

        # Prevent deleting the last preset? Optional.
        # if len(self.translation_presets) <= 1:
        #     messagebox.showwarning("Warning", "Cannot delete the last preset.")
        #     return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{preset_name}'?", parent=self.app.master)
        if not confirm:
            return

        if preset_name in self.translation_presets:
            original_data = self.translation_presets[preset_name] # Keep for potential rollback
            del self.translation_presets[preset_name]
            if save_translation_presets(self.translation_presets):
                # Update the combobox
                self.preset_names = sorted(list(self.translation_presets.keys()))
                self.preset_combo['values'] = self.preset_names
                new_selection = ""
                if self.preset_names:
                    new_selection = self.preset_names[0]
                    self.preset_combo.current(0)
                else:
                    self.preset_combo.set("") # Clear if no presets left
                # Update last used preset if the deleted one was selected
                if get_setting("last_preset_name") == preset_name:
                    set_setting("last_preset_name", new_selection)

                self.on_preset_selected() # Load the new selection's data (or clear UI if none)
                messagebox.showinfo("Deleted", f"Preset '{preset_name}' has been deleted.", parent=self.app.master)
            else:
                # Error message shown by save_translation_presets
                # Re-add the preset locally on failed save
                self.translation_presets[preset_name] = original_data
                messagebox.showerror("Error", "Failed to save presets after deletion. The preset was not deleted.", parent=self.app.master)


    def perform_translation(self):
        """Translate the stable text using the current settings."""
        # Get combined config (preset + general settings like lang, context)
        config = self.get_translation_config()
        if config is None:
            print("Translation cancelled due to configuration error.")
            self.app.update_status("Translation cancelled: Configuration error.")
            return # Error message already shown

        # --- Get the HWND for game-specific caching ---
        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            messagebox.showwarning("Warning", "No game window selected. Cannot determine game for caching.", parent=self.app.master)
            self.app.update_status("Translation cancelled: No window selected.")
            return

        # Get text to translate (only non-empty stable texts)
        texts_to_translate = {name: text for name, text in self.app.stable_texts.items() if text and text.strip()}

        if not texts_to_translate:
            print("No stable text available to translate.")
            self.app.update_status("No stable text to translate.")
            # Clear previous translation display
            self.translation_display.config(state=tk.NORMAL)
            self.translation_display.delete(1.0, tk.END)
            self.translation_display.insert(tk.END, "[No stable text detected]")
            self.translation_display.config(state=tk.DISABLED)
            # Clear overlays
            if hasattr(self.app, 'overlay_manager'):
                self.app.overlay_manager.clear_all_overlays()
            return

        # Format text for the API (using original ROI names as keys for now)
        # utils.translation.preprocess_text_for_translation handles the <|n|> conversion
        aggregated_input_text = "\n".join([f"[{name}]: {text}" for name, text in texts_to_translate.items()])

        self.app.update_status("Translating...")
        # Show translating message in preview
        self.translation_display.config(state=tk.NORMAL)
        self.translation_display.delete(1.0, tk.END)
        self.translation_display.insert(tk.END, "Translating...\n")
        self.translation_display.config(state=tk.DISABLED)

        # Show translating message in overlays
        if hasattr(self.app, 'overlay_manager'):
            for roi_name in texts_to_translate:
                self.app.overlay_manager.update_overlay(roi_name, "...") # Indicate loading


        # --- Perform translation in a separate thread ---
        def translation_thread():
            try:
                # Call the translation utility function
                # It handles caching, context, API call, and parsing <|n|> output
                # It now returns a dictionary mapping the original ROI name to the translation
                translated_segments = translate_text(
                    aggregated_input_text=aggregated_input_text, # Text with "[ROI_Name]: content" format
                    hwnd=current_hwnd, # Pass HWND for caching
                    preset=config, # Pass the combined config from get_translation_config
                    target_language=config["target_language"],
                    additional_context=config["additional_context"],
                    context_limit=config.get("context_limit", 10) # Pass context limit
                )

                # --- Process results ---
                if "error" in translated_segments:
                    error_msg = translated_segments["error"]
                    print(f"Translation API Error: {error_msg}")
                    # Display error in preview (via main thread)
                    self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                    # Display error in one overlay? Or clear them?
                    if hasattr(self.app, 'overlay_manager'):
                        first_roi = next(iter(texts_to_translate), None)
                        if first_roi:
                            self.app.master.after_idle(lambda name=first_roi: self.app.overlay_manager.update_overlay(name, f"Error!"))
                            # Clear others maybe?
                            for r_name in texts_to_translate:
                                if r_name != first_roi:
                                    self.app.master.after_idle(lambda n=r_name: self.app.overlay_manager.update_overlay(n, ""))


                else:
                    print("Translation successful.")
                    # Prepare display text for the preview box
                    preview_lines = []
                    # Use app's ROI order for display consistency
                    for roi in self.app.rois:
                        roi_name = roi.name
                        original_text = self.app.stable_texts.get(roi_name, "") # Check original stable text
                        translated_text = translated_segments.get(roi_name) # Use ROI name as key

                        # Only show lines for ROIs that had text AND received a translation
                        if original_text.strip(): # Was there input for this ROI?
                            preview_lines.append(f"[{roi_name}]:")
                            preview_lines.append(translated_text if translated_text else "[Translation N/A]")
                            preview_lines.append("") # Add blank line

                    preview_text = "\n".join(preview_lines).strip() # Remove trailing newline

                    # Update UI (Preview and Overlays) from the main thread
                    self.app.master.after_idle(lambda seg=translated_segments, prev=preview_text: self.update_translation_results(seg, prev))

            except Exception as e:
                error_msg = f"Unexpected error during translation thread: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                # Clear overlays on unexpected error
                if hasattr(self.app, 'overlay_manager'):
                    self.app.master.after_idle(self.app.overlay_manager.clear_all_overlays)


        threading.Thread(target=translation_thread, daemon=True).start()

    def update_translation_results(self, translated_segments, preview_text):
        """Update the preview display and overlays with translation results. Runs in main thread."""
        self.app.update_status("Translation complete.")
        # Update preview text box
        self.translation_display.config(state=tk.NORMAL)
        self.translation_display.delete(1.0, tk.END)
        self.translation_display.insert(tk.END, preview_text if preview_text else "[No translation received]")
        self.translation_display.config(state=tk.DISABLED)

        # Update overlays
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.update_overlays(translated_segments)

        # Store last successful translation for potential re-translation/copy
        self.last_translation_result = translated_segments
        self.last_translation_input = self.app.stable_texts.copy() # Store the input that led to this


    def update_translation_display_error(self, error_message):
        """Update the preview display with an error message. Runs in main thread."""
        self.app.update_status(f"Translation Error: {error_message[:50]}...") # Show snippet in status
        self.translation_display.config(state=tk.NORMAL)
        self.translation_display.delete(1.0, tk.END)
        self.translation_display.insert(tk.END, f"Translation Error:\n\n{error_message}")
        self.translation_display.config(state=tk.DISABLED)
        self.last_translation_result = None # Clear last result on error
        self.last_translation_input = None

    def clear_all_translation_cache(self):
        """Clear ALL translation cache files and show confirmation."""
        if messagebox.askyesno("Confirm Clear All Cache", "Are you sure you want to delete ALL translation cache files?", parent=self.app.master):
            result = clear_all_cache()
            messagebox.showinfo("Cache Cleared", result, parent=self.app.master)
            self.app.update_status("All translation cache cleared.")

    def clear_current_translation_cache(self):
        """Clear the translation cache for the current game and show confirmation."""
        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            messagebox.showwarning("Warning", "No game window selected. Cannot clear current game cache.", parent=self.app.master)
            return

        if messagebox.askyesno("Confirm Clear Current Cache", "Are you sure you want to delete the translation cache for the currently selected game?", parent=self.app.master):
            result = clear_current_game_cache(current_hwnd)
            messagebox.showinfo("Cache Cleared", result, parent=self.app.master)
            self.app.update_status("Current game translation cache cleared.")


    def reset_translation_context(self):
        """Reset the translation context history and show confirmation."""
        result = reset_context()
        messagebox.showinfo("Context Reset", result, parent=self.app.master)
        self.app.update_status("Translation context reset.")

# --- END OF FILE ui/translation_tab.py ---
```

**`app.py`**
```python
# --- START OF FILE app.py ---

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
# No longer need win32gui here unless used elsewhere
from paddleocr import PaddleOCR, paddleocr
import platform
from pathlib import Path # Import Path

# Import utilities
from utils.capture import get_window_title, capture_window
from utils.config import load_rois
# Import settings functions, including the new overlay config helpers
from utils.settings import (
    load_settings,
    set_setting,
    get_setting,
    update_settings,
    get_overlay_config_for_roi,
    save_overlay_config_for_roi,
)
from utils.roi import ROI
from utils.translation import CACHE_DIR # Import CACHE_DIR for ensuring it exists

# Import UI components
from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab
from ui.overlay_tab import OverlayTab
from ui.overlay_manager import OverlayManager  # Still used to manage window lifecycle
# FloatingOverlayWindow is imported by OverlayManager
from ui.floating_controls import FloatingControls

# Constants
FPS = 10
FRAME_DELAY = 1.0 / FPS
OCR_ENGINE_LOCK = threading.Lock()


class VisualNovelTranslatorApp:
    """Main application class for the Visual Novel Translator."""

    def __init__(self, master):
        self.master = master
        self.settings = load_settings()
        self.config_file = get_setting("last_roi_config", "vn_translator_config.json")  # Use get_setting

        window_title = "Visual Novel Translator"
        if self.config_file and os.path.exists(self.config_file):
            window_title += f" - {os.path.basename(self.config_file)}"
        master.title(window_title)
        master.geometry("1200x800")
        master.minsize(1000, 700)
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Ensure Cache Directory Exists ---
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Cache directory ensured at: {CACHE_DIR}")
        except Exception as e:
            print(f"Warning: Could not create cache directory {CACHE_DIR}: {e}")

        # --- Initialize variables ---
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = []
        self.current_frame = None
        self.display_frame_tk = None
        self.snapshot_frame = None
        self.using_snapshot = False
        self.roi_start_coords = None
        self.roi_draw_rect_id = None
        self.scale_x, self.scale_y = 1.0, 1.0
        self.frame_display_coords = {'x': 0, 'y': 0, 'w': 0, 'h': 0}

        self.text_history = {}
        self.stable_texts = {}
        self.stable_threshold = get_setting("stable_threshold", 3)
        self.max_display_width = get_setting("max_display_width", 800)
        self.max_display_height = get_setting("max_display_height", 600)
        self.last_status_message = ""

        self.ocr = None
        self.ocr_lang = get_setting("ocr_language", "jpn")
        self._resize_job = None

        # --- Setup UI ---
        self._setup_ui() # Calls the modified method

        # --- Initialize Managers ---
        self.overlay_manager = OverlayManager(self.master, self)  # Still needed
        self.floating_controls = None

        # --- Load initial config (ROIs) ---
        self._load_initial_rois()  # This now also triggers overlay_manager.rebuild_overlays

        # --- Initialize OCR Engine ---
        initial_ocr_lang = self.ocr_lang or "jpn"
        self.update_ocr_engine(initial_ocr_lang, initial_load=True)

        # --- Show Floating Controls (Initial show) ---
        self.show_floating_controls()

    def _setup_ui(self):
        """Set up the main UI layout and tabs."""

        # --- ADD MENU BAR ---
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)

        # Create "File" menu (optional, example)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        # Check if roi_tab exists before adding menu commands that use it
        # This can be deferred or checked lazily, but adding now with a placeholder is okay
        file_menu.add_command(label="Load ROI Config...", command=lambda: self.roi_tab.load_rois() if hasattr(self, 'roi_tab') else None)
        file_menu.add_command(label="Save ROI Config As...", command=lambda: self.roi_tab.save_rois() if hasattr(self, 'roi_tab') else None)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        # Create "Window" menu
        window_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Window", menu=window_menu)
        window_menu.add_command(label="Show Floating Controls", command=self.show_floating_controls)
        # --- END OF MENU BAR ADDITION ---

        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left frame for preview
        self.left_frame = ttk.Frame(self.paned_window, padding=0)
        self.paned_window.add(self.left_frame, weight=3)
        self.canvas = tk.Canvas(self.left_frame, bg="gray15", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Right frame for controls
        self.right_frame = ttk.Frame(self.paned_window, padding=(5, 0, 0, 0))
        self.paned_window.add(self.right_frame, weight=1)
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.capture_tab = CaptureTab(self.notebook, self)
        self.notebook.add(self.capture_tab.frame, text="Capture")
        self.roi_tab = ROITab(self.notebook, self)
        self.notebook.add(self.roi_tab.frame, text="ROIs")
        self.overlay_tab = OverlayTab(self.notebook, self)  # Overlay config tab
        self.notebook.add(self.overlay_tab.frame, text="Overlays")
        self.text_tab = TextTab(self.notebook, self)
        self.notebook.add(self.text_tab.frame, text="Live Text")
        self.stable_text_tab = StableTextTab(self.notebook, self)
        self.notebook.add(self.stable_text_tab.frame, text="Stable Text")
        self.translation_tab = TranslationTab(self.notebook, self)
        self.notebook.add(self.translation_tab.frame, text="Translation")

        # Status bar
        self.status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = ttk.Label(
            self.status_bar_frame,
            text="Status: Initializing...",
            anchor=tk.W,
            padding=(5, 2)
        )
        self.status_bar.pack(fill=tk.X)
        self.update_status("Ready.")

    def update_status(self, message):
        """Update the status bar message."""
        def _do_update():
            if hasattr(self, "status_bar") and self.status_bar.winfo_exists():
                try:
                    current_text = self.status_bar.cget("text")
                    new_text = f"Status: {message}"
                    if new_text != current_text:
                        self.status_bar.config(text=new_text)
                        self.last_status_message = message
                        # Update CaptureTab's label too
                        if (
                                hasattr(self, "capture_tab")
                                and hasattr(self.capture_tab, "status_label")
                                and self.capture_tab.status_label.winfo_exists()
                        ):
                            self.capture_tab.status_label.config(text=new_text)
                except tk.TclError:
                    pass  # Ignore if dying
            else:
                self.last_status_message = message

        try:
            if self.master.winfo_exists():
                self.master.after_idle(_do_update)
            else:
                self.last_status_message = message
        except Exception:
            self.last_status_message = message

    def _load_initial_rois(self):
        """Load ROIs from the last used config file on startup."""
        if self.config_file and os.path.exists(self.config_file):
            self.update_status(f"Loading ROIs from {os.path.basename(self.config_file)}...")
            try:
                rois, loaded_path = load_rois(initial_path=self.config_file)
                if loaded_path and rois is not None:
                    self.rois = rois
                    self.config_file = loaded_path  # Ensure config_file is updated
                    set_setting("last_roi_config", loaded_path)  # Save path

                    # Update UI elements that depend on ROIs
                    if hasattr(self, "roi_tab"):
                        self.roi_tab.update_roi_list()
                    if hasattr(self, "overlay_manager"):
                        self.overlay_manager.rebuild_overlays()

                    self.update_status(
                        f"Loaded {len(rois)} ROIs from {os.path.basename(loaded_path)}"
                    )
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
                elif rois is None and loaded_path is None:
                    self.update_status(
                        f"Error loading ROIs from {os.path.basename(self.config_file)}. See console."
                    )
            except Exception as e:
                self.update_status(f"Error loading initial ROIs: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            self.update_status("No previous ROI config found or file missing.")

    def update_ocr_engine(self, lang_code, initial_load=False):
        """Initialize or update the PaddleOCR engine in a separate thread."""
        def init_engine():
            global OCR_ENGINE_LOCK
            lang_map = {
                "jpn": "japan",
                "jpn_vert": "japan",
                "eng": "en",
                "chi_sim": "ch",
                "chi_tra": "ch",
                "kor": "ko",
            }
            ocr_lang_paddle = lang_map.get(lang_code, "en")

            with OCR_ENGINE_LOCK:
                current_paddle_lang = getattr(self.ocr, "lang", None) if self.ocr else None
                if current_paddle_lang == ocr_lang_paddle and self.ocr is not None:
                    if not initial_load:
                        print(f"OCR engine already initialized with {lang_code}.")
                    self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))
                    return

            if not initial_load:
                print(f"Initializing OCR engine for {lang_code}...")
            self.master.after_idle(lambda: self.update_status(f"Initializing OCR ({lang_code})..."))

            try:
                # Explicitly check for GPU availability if desired
                # use_gpu = paddleocr.is_gpu_available() # Requires GPU-enabled PaddlePaddle
                # print(f"Using GPU for OCR: {use_gpu}")
                # new_ocr_engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang_paddle, show_log=False, use_gpu=use_gpu)
                new_ocr_engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang_paddle, show_log=False)
                with OCR_ENGINE_LOCK:
                    self.ocr = new_ocr_engine
                    self.ocr_lang = lang_code  # Store the requested code ('jpn', 'eng')
                print(f"OCR engine ready for {lang_code}.")
                self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))
            except Exception as e:
                print(f"!!! Error initializing PaddleOCR for lang {lang_code}: {e}")
                import traceback
                traceback.print_exc()
                self.master.after_idle(lambda: self.update_status(f"OCR Error ({lang_code}): Check console"))
                with OCR_ENGINE_LOCK:
                    self.ocr = None

        threading.Thread(target=init_engine, daemon=True).start()

    def start_capture(self):
        """Start capturing from the selected window."""
        if self.capturing:
            return
        if not self.selected_hwnd:
            messagebox.showwarning("Warning", "No visual novel window selected.", parent=self.master)
            return

        with OCR_ENGINE_LOCK:
            ocr_ready = bool(self.ocr)
        if not ocr_ready:
            current_lang = self.ocr_lang or "jpn"
            self.update_ocr_engine(current_lang)
            messagebox.showinfo(
                "OCR Not Ready",
                "OCR is initializing. Capture starting, but text extraction may be delayed.",
                parent=self.master,
            )

        if self.using_snapshot:
            self.return_to_live()

        self.capturing = True
        self.capture_thread = threading.Thread(target=self.capture_process, daemon=True)
        self.capture_thread.start()

        if hasattr(self, "capture_tab"):
            self.capture_tab.on_capture_started()
        title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
        self.update_status(f"Capturing: {title}")
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.rebuild_overlays()

    def stop_capture(self):
        """Stop the current capture process gracefully."""
        if not self.capturing:
            return
        print("Stop capture requested...")
        self.capturing = False
        self.master.after(100, self._check_thread_and_finalize_stop)

    def _check_thread_and_finalize_stop(self):
        """Checks if capture thread finished, calls finalize or re-schedules check."""
        if self.capture_thread and self.capture_thread.is_alive():
            self.master.after(100, self._check_thread_and_finalize_stop)
        else:
            self.capture_thread = None
            if not hasattr(self, "_finalize_stop_called") or not self._finalize_stop_called:
                self._finalize_stop_called = True
                self._finalize_stop_capture()

    def _finalize_stop_capture(self):
        """Actions to perform in the main thread after capture stops."""
        if self.capturing:  # Safety check
            print("Warning: Finalizing stop capture while flag is still true.")
            self.capturing = False

        print("Finalizing stop capture UI updates...")
        self._finalize_stop_called = False
        if hasattr(self, "capture_tab") and self.capture_tab.frame.winfo_exists():
            self.capture_tab.on_capture_stopped()
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.hide_all_overlays()  # Hide overlays
        self.update_status("Capture stopped.")

    def take_snapshot(self):
        """Take a snapshot of the current frame for static analysis."""
        if not self.capturing and self.current_frame is None:
            messagebox.showwarning("Warning", "Capture not running and no frame available.", parent=self.master)
            return
        if self.current_frame is None:
            messagebox.showwarning("Warning", "No frame captured yet.", parent=self.master)
            return

        print("Taking snapshot...")
        self.snapshot_frame = self.current_frame.copy()
        self.using_snapshot = True
        self._display_frame(self.snapshot_frame)

        if hasattr(self, "capture_tab"):
            self.capture_tab.on_snapshot_taken()
        self.update_status("Snapshot taken. Define ROIs or return to live.")

    def return_to_live(self):
        """Return to live view from snapshot mode."""
        if not self.using_snapshot:
            return
        print("Returning to live view...")
        self.using_snapshot = False
        self.snapshot_frame = None
        self._display_frame(self.current_frame if self.current_frame is not None else None)
        if hasattr(self, "capture_tab"):
            self.capture_tab.on_live_view_resumed()
        # Update status based on whether capture is still running
        if self.capturing:
            title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
            self.update_status(f"Capturing: {title}")
        else:
            self.update_status("Capture stopped.")


    def toggle_roi_selection(self):
        """Enable or disable ROI selection mode."""
        if not self.roi_selection_active:
            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                messagebox.showwarning(
                    "Warning",
                    "Start capture or take snapshot before defining ROIs.",
                    parent=self.master,
                )
                return
            if self.capturing and not self.using_snapshot:
                self.take_snapshot()
                if not self.using_snapshot:
                    return  # Snapshot failed

            self.roi_selection_active = True
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(True)
        else:
            self.roi_selection_active = False
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(False)
            if self.roi_draw_rect_id:
                self.canvas.delete(self.roi_draw_rect_id)
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            self.update_status("ROI selection cancelled.")
            # If cancelled while in snapshot mode, return to live
            if self.using_snapshot:
                self.return_to_live()

    def capture_process(self):
        """Background thread for capture and processing."""
        last_frame_time = time.time()
        target_sleep_time = FRAME_DELAY
        print("Capture thread started.")
        while self.capturing:
            loop_start_time = time.time()
            frame_to_display = None
            try:
                if self.using_snapshot:
                    time.sleep(0.05)
                    continue

                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    if self.capturing:
                        self.master.after_idle(self.handle_capture_failure)
                    break

                self.current_frame = frame
                frame_to_display = frame

                ocr_engine_instance = None
                with OCR_ENGINE_LOCK:
                    ocr_engine_instance = self.ocr

                if self.rois and ocr_engine_instance:
                    self._process_rois(frame, ocr_engine_instance)

                current_time = time.time()
                if current_time - last_frame_time >= target_sleep_time:
                    if frame_to_display is not None:
                        frame_copy = frame_to_display.copy()
                        self.master.after_idle(lambda f=frame_copy: self._display_frame(f))
                    last_frame_time = current_time

                elapsed = time.time() - loop_start_time
                sleep_duration = max(0.001, target_sleep_time - elapsed)
                time.sleep(sleep_duration)

            except Exception as e:
                print(f"!!! Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                self.master.after_idle(
                    lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}...")
                )
                time.sleep(1)
        print("Capture thread finished or exited.")

    def handle_capture_failure(self):
        """Called from main thread if capture fails."""
        if self.capturing:
            self.update_status("Window lost or uncapturable. Stopping capture.")
            print("Failed to capture the selected window.")
            self.stop_capture()
            if hasattr(self, "capture_tab"):
                self.capture_tab.refresh_window_list()

    def on_canvas_resize(self, event=None):
        """Debounced canvas resize handler."""
        if self._resize_job:
            self.master.after_cancel(self._resize_job)
        self._resize_job = self.master.after(100, self._perform_resize_redraw)

    def _perform_resize_redraw(self):
        """Actual redraw logic after resize debounce."""
        self._resize_job = None
        if not self.canvas.winfo_exists():
            return
        frame = self.snapshot_frame if self.using_snapshot else self.current_frame
        self._display_frame(frame)

    def _display_frame(self, frame):
        """Display frame on canvas, fitting and centering."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
            return
        self.canvas.delete("display_content")
        self.display_frame_tk = None

        if frame is None:
            try:
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                if cw > 1 and ch > 1:
                    self.canvas.create_text(
                        cw / 2, ch / 2, text="No Image", fill="gray50", tags="display_content"
                    )
            except Exception:
                pass
            return

        try:
            fh, fw = frame.shape[:2]
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            if fw <= 0 or fh <= 0 or cw <= 1 or ch <= 1:
                return

            scale = min(cw / fw, ch / fh)
            nw, nh = int(fw * scale), int(fh * scale)
            if nw < 1 or nh < 1:
                return

            self.scale_x, self.scale_y = scale, scale
            self.frame_display_coords = {
                "x": (cw - nw) // 2,
                "y": (ch - nh) // 2,
                "w": nw,
                "h": nh,
            }

            resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
            display_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(display_rgb)
            self.display_frame_tk = ImageTk.PhotoImage(image=img)

            self.canvas.create_image(
                self.frame_display_coords["x"],
                self.frame_display_coords["y"],
                anchor=tk.NW,
                image=self.display_frame_tk,
                tags=("display_content", "frame_image"),
            )
            self._draw_rois()

        except Exception as e:
            print(f"Error displaying frame: {e}")

    def _process_rois(self, frame, ocr_engine):
        """Process ROIs on frame, update text/stability, schedule UI updates."""
        if frame is None or ocr_engine is None:
            return

        extracted = {}
        stable_changed = False
        new_stable = self.stable_texts.copy()

        for roi in self.rois:
            roi_img = roi.extract_roi(frame)
            if roi_img is None or roi_img.size == 0:
                extracted[roi.name] = ""
                continue

            try:
                ocr_result_raw = ocr_engine.ocr(roi_img, cls=True)
                text_lines = []
                if ocr_result_raw and isinstance(ocr_result_raw, list) and len(ocr_result_raw) > 0:
                    # Handle potential nested list structure from PaddleOCR
                    current_result_set = ocr_result_raw[0] if isinstance(ocr_result_raw[0], list) else ocr_result_raw
                    if current_result_set:
                        for item in current_result_set:
                            # Extract text part, handling different possible structures
                            text_info = None
                            if isinstance(item, list) and len(item) >= 2:
                                text_info = item[1] # Often [box, (text, confidence)]
                            elif isinstance(item, tuple) and len(item) >= 2:
                                text_info = item # Sometimes just (text, confidence)? Check Paddle docs/output.

                            # Check if text_info is valid and extract text
                            if (
                                    isinstance(text_info, (tuple, list))
                                    and len(text_info) >= 1
                                    and text_info[0]
                            ):
                                text_lines.append(str(text_info[0]))
                text = " ".join(text_lines).strip()
                extracted[roi.name] = text

                history = self.text_history.get(roi.name, {"text": "", "count": 0})
                if text == history["text"]:
                    history["count"] += 1
                else:
                    history = {"text": text, "count": 1}
                self.text_history[roi.name] = history

                is_now_stable = history["count"] >= self.stable_threshold
                was_stable = roi.name in self.stable_texts
                current_stable = self.stable_texts.get(roi.name)

                if is_now_stable:
                    if not was_stable or current_stable != text:
                        new_stable[roi.name] = text
                        stable_changed = True
                elif was_stable:
                    del new_stable[roi.name]
                    stable_changed = True

            except Exception as e:
                print(f"!!! OCR Error for ROI {roi.name}: {e}")
                extracted[roi.name] = "[OCR Error]"
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True

        if hasattr(self, "text_tab") and self.text_tab.frame.winfo_exists():
            self.master.after_idle(lambda et=extracted.copy(): self.text_tab.update_text(et))

        if stable_changed:
            self.stable_texts = new_stable
            if hasattr(self, "stable_text_tab") and self.stable_text_tab.frame.winfo_exists():
                self.master.after_idle(
                    lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st)
                )
            if (
                    hasattr(self, "translation_tab")
                    and self.translation_tab.frame.winfo_exists()
                    and self.translation_tab.is_auto_translate_enabled()
            ):
                self.master.after_idle(self.translation_tab.perform_translation)

    def _draw_rois(self):
        """Draw ROI rectangles on the canvas."""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists() or self.frame_display_coords["w"] <= 0:
            return
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        for i, roi in enumerate(self.rois):
            try:
                dx1 = int(roi.x1 * self.scale_x) + ox
                dy1 = int(roi.y1 * self.scale_y) + oy
                dx2 = int(roi.x2 * self.scale_x) + ox
                dy2 = int(roi.y2 * self.scale_y) + oy
                self.canvas.create_rectangle(
                    dx1, dy1, dx2, dy2, outline="lime", width=1, tags=("display_content", f"roi_{i}")
                )
                self.canvas.create_text(
                    dx1 + 3,
                    dy1 + 1,
                    text=roi.name,
                    fill="lime",
                    anchor=tk.NW,
                    font=("TkDefaultFont", 8),
                    tags=("display_content", f"roi_label_{i}"),
                    )
            except Exception as e:
                print(f"Error drawing ROI {roi.name}: {e}")

    # --- Mouse Events for ROI Definition ---
    def on_mouse_down(self, event):
        """Start ROI definition drag."""
        if not self.roi_selection_active or not self.using_snapshot:
            return
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        if not (img_x <= event.x < img_x + img_w and img_y <= event.y < img_y + img_h):
            self.roi_start_coords = None
            if self.roi_draw_rect_id:
                self.canvas.delete(self.roi_draw_rect_id)
            self.roi_draw_rect_id = None
            return
        self.roi_start_coords = (event.x, event.y)
        if self.roi_draw_rect_id:
            self.canvas.delete(self.roi_draw_rect_id)
        self.roi_draw_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=2, tags="roi_drawing"
        )

    def on_mouse_drag(self, event):
        """Update ROI definition rectangle during drag."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            return
        sx, sy = self.roi_start_coords
        cx = max(0, min(event.x, self.canvas.winfo_width()))
        cy = max(0, min(event.y, self.canvas.winfo_height()))
        try:
            self.canvas.coords(self.roi_draw_rect_id, sx, sy, cx, cy)
        except tk.TclError:
            self.roi_draw_rect_id = None
            self.roi_start_coords = None

    def on_mouse_up(self, event):
        """Finalize ROI definition on mouse release."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            if self.roi_draw_rect_id:
                try:
                    self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError:
                    pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # --- If user cancelled or drew too small, we might still be in snapshot mode ---
            # --- Decide if we should return to live even on failure/cancel ---
            # --- Current logic returns to live only on SUCCESSFUL ROI creation ---
            # if self.using_snapshot: # Optionally return even on cancel?
            #     self.return_to_live()
            return

        try:
            coords = self.canvas.coords(self.roi_draw_rect_id)
        except tk.TclError:
            coords = None
        if self.roi_draw_rect_id:
            try:
                self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError:
                pass
        self.roi_draw_rect_id = None
        self.roi_start_coords = None
        self.roi_selection_active = False  # Turn off mode
        if hasattr(self, "roi_tab"):
            self.roi_tab.on_roi_selection_toggled(False)

        if coords is None or len(coords) != 4:
            # If coords are invalid, return to live if we were in snapshot mode
            if self.using_snapshot:
                self.return_to_live()
            return

        x1d, y1d, x2d, y2d = map(int, coords)
        min_size = 5
        if abs(x2d - x1d) < min_size or abs(y2d - y1d) < min_size:
            messagebox.showwarning(
                "ROI Too Small",
                f"Selected region too small (min {min_size}x{min_size} px).",
                parent=self.master,
            )
            # Return to live even if ROI was too small
            if self.using_snapshot:
                self.return_to_live()
            return

        roi_name = self.roi_tab.roi_name_entry.get().strip()
        overwrite_name = None
        if not roi_name:
            i = 1
            roi_name = f"roi_{i}"
            while roi_name in [r.name for r in self.rois]:
                i += 1
                roi_name = f"roi_{i}"
        elif roi_name in [r.name for r in self.rois]:
            if not messagebox.askyesno("ROI Exists", f"Overwrite ROI '{roi_name}'?", parent=self.master):
                # User cancelled overwrite, return to live
                if self.using_snapshot:
                    self.return_to_live()
                return
            overwrite_name = roi_name

        # ... (rest of the coordinate calculations ox, oy, rx1, etc.) ...
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]
        rx1 = min(x1d, x2d) - ox
        ry1 = min(y1d, y2d) - oy
        rx2 = max(x1d, x2d) - ox
        ry2 = max(y1d, y2d) - oy
        crx1 = max(0, min(rx1, img_w))
        cry1 = max(0, min(ry1, img_h))
        crx2 = max(0, min(rx2, img_w))
        cry2 = max(0, min(ry2, img_h))

        if crx2 - crx1 < min_size or cry2 - cry1 < min_size:
            messagebox.showwarning(
                "ROI Too Small", "Effective region too small after clamping.", parent=self.master
            )
            # Return to live even if ROI was too small
            if self.using_snapshot:
                self.return_to_live()
            return

        if self.scale_x == 0 or self.scale_y == 0:
            # Return to live if scale is invalid
            if self.using_snapshot:
                self.return_to_live()
            return  # Avoid division by zero
        ox1 = int(crx1 / self.scale_x)
        oy1 = int(cry1 / self.scale_y)
        ox2 = int(crx2 / self.scale_x)
        oy2 = int(cry2 / self.scale_y)

        new_roi = ROI(roi_name, ox1, oy1, ox2, oy2)

        if overwrite_name:
            self.rois = [r for r in self.rois if r.name != overwrite_name]
            if hasattr(self, "overlay_manager"):
                all_settings = get_setting("overlay_settings", {})
                if overwrite_name in all_settings:
                    del all_settings[overwrite_name]
                update_settings({"overlay_settings": all_settings})
                self.overlay_manager.destroy_overlay(overwrite_name)

        self.rois.append(new_roi)
        print(f"Created/Updated ROI: {new_roi.to_dict()}")

        if hasattr(self, "roi_tab"):
            self.roi_tab.update_roi_list()
        self._draw_rois()  # Redraw on snapshot
        action = "created" if not overwrite_name else "updated"
        self.update_status(f"ROI '{roi_name}' {action}.")

        # Suggest next name
        if hasattr(self, "roi_tab"):
            next_name = "dialogue" if "dialogue" not in [r.name for r in self.rois] else ""
            if not next_name:
                i = 1
                next_name = f"roi_{i}"
                while next_name in [r.name for r in self.rois]:
                    i += 1
                    next_name = f"roi_{i}"
            self.roi_tab.roi_name_entry.delete(0, tk.END)
            self.roi_tab.roi_name_entry.insert(0, next_name)

        if hasattr(self, "overlay_manager"):
            self.overlay_manager.create_overlay_for_roi(new_roi)

        # <<< --- ADD THIS LINE --- >>>
        if self.using_snapshot:
            self.return_to_live()
        # <<< --- END OF ADDITION --- >>>


    def show_floating_controls(self):
        """Creates/shows the floating control window."""
        try:
            if self.floating_controls is None or not self.floating_controls.winfo_exists():
                self.floating_controls = FloatingControls(self.master, self)
            else:
                self.floating_controls.deiconify()
                self.floating_controls.lift()
                self.floating_controls.update_button_states()
        except Exception as e:
            print(f"Error showing floating controls: {e}")
            self.update_status("Error showing floating controls.")

    def hide_floating_controls(self):
        """Hides the floating control window."""
        if self.floating_controls and self.floating_controls.winfo_exists():
            self.floating_controls.withdraw()

    def on_close(self):
        """Handle application closing."""
        print("Close requested...")
        if self.capturing:
            self.update_status("Stopping capture before closing...")
            self.stop_capture()
            self.master.after(100, self.check_capture_stopped_and_close)
        else:
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Check if capture stopped before finalizing close."""
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            self._finalize_close()
        else:
            self.master.after(200, self.check_capture_stopped_and_close)

    def _finalize_close(self):
        """Final cleanup and destroy window."""
        print("Finalizing close...")
        self.capturing = False
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.destroy_all_overlays()
        if self.floating_controls and self.floating_controls.winfo_exists():
            try:
                # Save position only if it's currently visible/normal
                if self.floating_controls.state() == "normal":
                    # Extract geometry parts carefully
                    geo = self.floating_controls.geometry() # e.g., "150x50+100+200"
                    parts = geo.split('+')
                    if len(parts) == 3: # Should have size, x, y
                        x, y = parts[1], parts[2]
                        set_setting("floating_controls_pos", f"{x},{y}")
                    else:
                        print(f"Warning: Could not parse floating controls geometry for saving: {geo}")
            except Exception as e:
                print(f"Error saving floating controls position: {e}")
            try:
                self.floating_controls.destroy()
            except tk.TclError:
                pass

        print("Exiting application.")
        try:
            self.master.quit()
            self.master.destroy()
        except tk.TclError:
            pass
        except Exception as e:
            print(f"Error during final destruction: {e}")

# --- END OF FILE app.py ---
```

**`main.py`**
```python
# --- START OF FILE main.py ---

import tkinter as tk
import os # Import os
from app import VisualNovelTranslatorApp
from pathlib import Path # For user home directory
from utils.translation import CACHE_DIR # Import CACHE_DIR

if __name__ == "__main__":
    root = tk.Tk()
    # Title is set within the App class now based on config

    # --- Set app icon if available ---
    try:
        # Get the directory where main.py is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "icon.ico") # Assume icon is in the same folder
        if os.path.exists(icon_path):
            # Use platform-specific method if needed, iconbitmap works on Windows
            root.iconbitmap(default=icon_path)
            print(f"Icon loaded from {icon_path}")
        else:
            print(f"icon.ico not found at {icon_path}, using default Tk icon.")
    except Exception as e:
        print(f"Could not set application icon: {e}")

    # --- Ensure required directories exist ---
    # Cache directory (now defined relative to app in translation.py)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Cache directory ensured at: {CACHE_DIR}")
    except Exception as e:
        print(f"Warning: Could not create cache directory {CACHE_DIR}: {e}")

    # --- Run the App ---
    try:
        app = VisualNovelTranslatorApp(root)
        root.mainloop()
    except Exception as e:
        # Catch major errors during app initialization or main loop
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!      UNEXPECTED APPLICATION ERROR     !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        import traceback
        traceback.print_exc()
        # Show error in a simple Tkinter message box if possible
        try:
            from tkinter import messagebox
            messagebox.showerror("Fatal Error", f"An unexpected error occurred:\n\n{e}\n\nSee console for details.")
        except:
            pass # Ignore if even messagebox fails

# --- END OF FILE main.py ---
```

**No changes were required in the following files based on the request:**

*   `overlay_manager.py`
*   `overlay_tab.py`
*   `roi_tab.py`
*   `text_tab.py`
*   `base.py`
*   `capture_tab.py`
*   `floating_controls.py`
*   `floating_overlay_window.py`
*   `config.py`
*   `ocr.py`
*   `settings.py`
*   `roi.py`

This revised system should provide portable, game-specific caching with simplified keys and appropriate clearing options. Remember to test thoroughly, especially the game identification and cache file handling.