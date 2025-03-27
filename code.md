Okay, understood. Apologies for the previous format. Here are the complete scripts for each file, incorporating all the changes and including previously omitted sections.

--- START OF FILE utils/settings.py ---

```python
import json
import os

# Default settings file
SETTINGS_FILE = "vn_translator_settings.json"

# Default settings
DEFAULT_SETTINGS = {
    "last_roi_config": "vn_translator_config.json",
    "last_preset_name": None, # Store the name of the last used preset
    "target_language": "en",
    "additional_context": "",
    "stable_threshold": 3,
    "max_display_width": 800,
    "max_display_height": 600,
    "auto_translate": False,
    "ocr_language": "jpn", # Added OCR language setting
    "global_overlays_enabled": True, # Added global overlay toggle
    "overlay_settings": {}, # roi_name: {enabled: bool, font_size: int, ...}
    "floating_controls_pos": None # "x,y"
}

def load_settings():
    """Load application settings."""
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
            settings.update(loaded_settings) # Merge loaded settings over defaults
        except Exception as e:
            print(f"Error loading settings: {e}. Using defaults.")
    return settings

def save_settings(settings):
    """Save application settings."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        print(f"Settings saved to {SETTINGS_FILE}") # Add confirmation
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def get_setting(key, default=None):
    """Get a specific setting value."""
    settings = load_settings()
    # Use default from DEFAULT_SETTINGS if key exists there, otherwise use passed default
    fallback_default = DEFAULT_SETTINGS.get(key, default)
    return settings.get(key, fallback_default)

def set_setting(key, value):
    """Set a specific setting value and save immediately."""
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)

def update_settings(new_values):
    """Update multiple settings values and save."""
    settings = load_settings()
    settings.update(new_values)
    return save_settings(settings)
```

--- END OF FILE utils/settings.py ---

--- START OF FILE utils/config.py ---

```python
import json
import os
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
from utils.roi import ROI
from utils.settings import set_setting, get_setting # Import get_setting

# Default configuration file paths
DEFAULT_ROI_CONFIG_FILE = "vn_translator_config.json"
PRESETS_FILE = "translation_presets.json"

def save_rois(rois, current_config_file=None):
    """
    Save ROIs to a JSON configuration file. Prompts user if no file specified.

    Args:
        rois: List of ROI objects
        current_config_file: The path currently used by the app.

    Returns:
        The path to the saved config file or None if cancelled/failed
    """
    if not rois:
        messagebox.showwarning("Warning", "No ROIs to save.")
        return current_config_file # Return the original path if nothing saved

    try:
        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(current_config_file) if current_config_file else ".",
            initialfile=os.path.basename(current_config_file) if current_config_file else DEFAULT_ROI_CONFIG_FILE,
            title="Save ROI Configuration As"
        )
        if not save_path:
            print("ROI save cancelled by user.")
            return current_config_file # Return original path if cancelled

        roi_data = [roi.to_dict() for roi in rois]
        with open(save_path, 'w', encoding="utf-8") as f:
            json.dump(roi_data, f, indent=2)

        # Save the path in application settings
        set_setting("last_roi_config", save_path)
        print(f"ROIs saved successfully to {save_path}")
        return save_path # Return the new path
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save ROIs: {str(e)}")
        return current_config_file # Return original path on error

def load_rois(initial_path=None):
    """
    Load ROIs from a JSON configuration file. Uses initial_path or prompts user.

    Args:
        initial_path: Path to attempt loading from first.

    Returns:
        A tuple of (list of ROI objects, config_file_path) or ([], None) on failure/cancel
        Returns (None, None) on explicit error during load after selection.
    """
    open_path = initial_path
    rois = []

    # Try loading from initial_path first if it exists
    if open_path and os.path.exists(open_path):
        try:
            with open(open_path, 'r', encoding="utf-8") as f:
                roi_data = json.load(f)
            rois = [ROI.from_dict(data) for data in roi_data]
            set_setting("last_roi_config", open_path)
            print(f"ROIs loaded successfully from {open_path}")
            return rois, open_path
        except Exception as e:
            print(f"Failed to load ROIs from '{open_path}': {str(e)}. Prompting user.")
            # Fall through to prompt user
            open_path = None # Clear path so file dialog opens

    # If initial load failed or no path provided, prompt user
    if not open_path:
         # Get the directory of the last known config file
        last_config_path = get_setting("last_roi_config")
        initial_dir = "."
        if last_config_path and os.path.exists(os.path.dirname(last_config_path)):
             initial_dir = os.path.dirname(last_config_path)


        open_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=initial_dir,
            title="Load ROI Configuration"
        )
        if not open_path:
            print("ROI load cancelled by user.")
            return [], None # Return empty list and None path if cancelled

    # Try loading from the selected path
    if open_path and os.path.exists(open_path):
        try:
            with open(open_path, 'r', encoding="utf-8") as f:
                roi_data = json.load(f)
            rois = [ROI.from_dict(data) for data in roi_data]
            set_setting("last_roi_config", open_path)
            print(f"ROIs loaded successfully from {open_path}")
            return rois, open_path
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ROIs from '{open_path}': {str(e)}")
            return None, None # Explicit error indication
    elif open_path:
        messagebox.showerror("Error", f"File not found: '{open_path}'")
        return None, None # Explicit error indication
    else:
        # Should not happen if askopenfilename was used, but handle just in case
        return [], None


def save_translation_presets(presets, file_path=PRESETS_FILE):
    """
    Save translation presets to a JSON file.

    Args:
        presets: Dictionary of translation presets
        file_path: Path to save to

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
        print(f"Translation presets saved to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving translation presets: {e}")
        messagebox.showerror("Error", f"Failed to save translation presets: {e}")
        return False

def load_translation_presets(file_path=PRESETS_FILE):
    """
    Load translation presets from a JSON file.

    Args:
        file_path: Path to load from

    Returns:
        Dictionary of translation presets
    """
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content: return {} # Handle empty file
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Error: Translation presets file '{file_path}' is corrupted or empty.")
            messagebox.showerror("Preset Load Error", f"Could not load presets from '{file_path}'. File might be corrupted.")
            return {}
        except Exception as e:
            print(f"Error loading translation presets: {e}")
            messagebox.showerror("Error", f"Failed to load translation presets: {e}. Using defaults or empty.")
    return {}
```

--- END OF FILE utils/config.py ---

--- START OF FILE utils/roi.py ---

```python
class ROI:
    """Represents a Region of Interest for text extraction."""
    def __init__(self, name, x1, y1, x2, y2):
        self.name = name
        # Ensure coordinates are ordered correctly
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)

    def to_dict(self):
        """Convert the ROI to a dictionary for serialization."""
        return {"name": self.name, "x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, data):
        """Create an ROI instance from a dictionary."""
        return cls(data["name"], data["x1"], data["y1"], data["x2"], data["y2"])

    def extract_roi(self, frame):
        """Extract the ROI region from the given frame."""
        try:
            # Ensure coordinates are integers and within frame bounds
            h, w = frame.shape[:2]
            y1 = max(0, int(self.y1))
            y2 = min(h, int(self.y2))
            x1 = max(0, int(self.x1))
            x2 = min(w, int(self.x2))
            if y1 >= y2 or x1 >= x2:
                # print(f"Warning: Invalid ROI dimensions for '{self.name}' after clamping.")
                return None # Return None if dimensions are invalid
            return frame[y1:y2, x1:x2]
        except Exception as e:
            print(f"Error extracting ROI image for {self.name}: {e}")
            return None

    def get_overlay_config(self, global_settings):
        """Gets overlay config for this ROI, merging specific settings over defaults."""
        # Use the default structure defined in OverlayManager or OverlayTab
        from ui.overlay_manager import OverlayManager # Avoid circular import at top level
        defaults = OverlayManager.DEFAULT_OVERLAY_CONFIG.copy()

        roi_specific_settings = global_settings.get('overlay_settings', {}).get(self.name, {})

        # Merge defaults with specific settings
        config = defaults.copy()
        config.update(roi_specific_settings)
        return config
```

--- END OF FILE utils/roi.py ---

--- START OF FILE utils/translation.py ---

```python
import json
import re
import os
from openai import OpenAI
from pathlib import Path
import hashlib # For cache key generation
import time # For potential corrupted cache backup naming


# File-based cache settings
CACHE_DIR = Path(os.path.expanduser("~/.ocrtrans/cache"))
CACHE_FILE = CACHE_DIR / "translation_cache.json"

# Context management (global list)
context_messages = []

def _ensure_cache_dir():
    """Make sure the cache directory exists"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _load_cache():
    """Load the translation cache from disk"""
    _ensure_cache_dir()
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                # Check if file is empty
                content = f.read()
                if not content:
                    return {}
                return json.loads(content)
    except json.JSONDecodeError:
        print(f"Warning: Cache file {CACHE_FILE} is corrupted or empty. Starting fresh cache.")
        try:
             # Optionally backup corrupted file
             corrupted_path = CACHE_FILE.parent / f"{CACHE_FILE.name}.corrupted_{int(time.time())}"
             os.rename(CACHE_FILE, corrupted_path)
             print(f"Corrupted cache backed up to {corrupted_path}")
        except Exception as backup_err:
             print(f"Error backing up corrupted cache file: {backup_err}")
        return {}
    except Exception as e:
        print(f"Error loading cache: {e}")
    return {}


def _save_cache(cache):
    """Save the translation cache to disk"""
    _ensure_cache_dir()
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}")

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


def clear_cache():
    """Clear the translation cache."""
    if CACHE_FILE.exists():
         try:
              os.remove(CACHE_FILE)
              print("Translation cache file deleted.")
              return "Translation cache has been cleared."
         except Exception as e:
              print(f"Error deleting cache file {CACHE_FILE}: {e}")
              return f"Error clearing cache: {e}"
    else:
         print("Translation cache file not found.")
         return "Translation cache was already empty."

def get_cache_key(text, preset, target_language, additional_context):
    """Generate a unique cache key based on input parameters."""
    # Use a hash to keep keys manageable
    hasher = hashlib.sha256()
    hasher.update(text.encode('utf-8'))
    hasher.update(str(preset.get('model', '')).encode('utf-8'))
    hasher.update(str(preset.get('temperature', '')).encode('utf-8'))
    hasher.update(str(preset.get('api_url', '')).encode('utf-8'))
    hasher.update(target_language.encode('utf-8'))
    hasher.update(additional_context.encode('utf-8'))
    # Include system prompt hash? Can make cache less effective if prompts change often.
    hasher.update(preset.get('system_prompt', '').encode('utf-8'))
    return hasher.hexdigest()

def get_cached_translation(cache_key):
    """Get a cached translation if it exists."""
    cache = _load_cache()
    return cache.get(cache_key)

def set_cache_translation(cache_key, translation):
    """Cache a translation result."""
    cache = _load_cache()
    cache[cache_key] = translation
    _save_cache(cache)


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


def translate_text(aggregated_input_text, preset, target_language="en", additional_context="", context_limit=10):
    """
    Translate the given text using an OpenAI-compatible API client.

    Args:
        aggregated_input_text: Text in "[ROI_Name]: Content" format.
        preset: The translation preset configuration (LLM specific parts).
        target_language: The target language code (e.g., "en", "Spanish").
        additional_context: General instructions or context from the UI.
        context_limit: Max number of conversational exchanges (user+assistant pairs) to keep.

    Returns:
        A dictionary mapping original ROI names to translated text,
        or {'error': message} on failure.
    """
    # 1. Preprocess input text to <|n|> format and get mapping
    preprocessed_text_for_llm, tag_mapping = preprocess_text_for_translation(aggregated_input_text)

    if not preprocessed_text_for_llm or not tag_mapping:
        print("No valid text segments found after preprocessing. Nothing to translate.")
        return {} # Return empty dict if nothing to translate

    # 2. Check Cache
    cache_key = get_cache_key(preprocessed_text_for_llm, preset, target_language, additional_context)
    cached_result = get_cached_translation(cache_key)
    if cached_result:
        print(f"[LOG] Using cached translation for key: {cache_key[:10]}...")
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

    # Add to cache using the key generated earlier
    set_cache_translation(cache_key, final_translations)
    print(f"[LOG] Translation cached successfully.")

    return final_translations
```

--- END OF FILE utils/translation.py ---

--- START OF FILE utils/capture.py ---

```python
import win32gui
import win32ui
import win32con
import mss
import numpy as np
import cv2
from ctypes import windll, byref, wintypes
import time # For performance timing

# Flag to reduce repetitive logging
LOG_CAPTURE_DETAILS = False # Set to True for debugging capture methods/rects

def enum_window_callback(hwnd, windows):
    """Callback for win32gui.EnumWindows; adds visible, non-minimized windows with titles."""
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
        print_window_flag = 1 if rect_type == "Client" else 0

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
```

--- END OF FILE utils/capture.py ---

--- START OF FILE ui/base.py ---

```python
from tkinter import ttk

class BaseTab:
    """Base class for application tabs."""

    def __init__(self, parent, app):
        """
        Initialize a tab.

        Args:
            parent: The parent widget (usually a ttk.Notebook)
            app: The main application instance
        """
        self.parent = parent
        self.app = app
        # Use frame directly for content
        self.frame = ttk.Frame(parent, padding="10")
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components. Should be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement setup_ui")

    def on_tab_selected(self):
        """Called when this tab is selected. Can be overridden by subclasses."""
        pass
```

--- END OF FILE ui/base.py ---

--- START OF FILE ui/text_tab.py ---

```python
import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab

class TextTab(BaseTab):
    """Tab for displaying extracted text."""

    def setup_ui(self):
        text_frame = ttk.LabelFrame(self.frame, text="Live Extracted Text (per frame)", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5) # Reduced pady

        self.text_display = tk.Text(text_frame, wrap=tk.WORD, height=10, width=40, # Reduced height
                                     font=("Consolas", 9) ) # Monospace font?
        self.text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=self.text_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_display.config(yscrollcommand=scrollbar.set)
        self.text_display.config(state=tk.DISABLED) # Start disabled

    def update_text(self, text_dict):
        """
        Update the text display with extracted text.

        Args:
            text_dict: Dictionary mapping ROI names to extracted text
        """
        self.text_display.config(state=tk.NORMAL)
        self.text_display.delete(1.0, tk.END)

        # Maintain ROI order from app.rois
        for roi in self.app.rois:
            roi_name = roi.name
            text = text_dict.get(roi_name, "") # Get text or default empty
            if text: # Only display if text was extracted
                 self.text_display.insert(tk.END, f"[{roi_name}]:\n{text}\n\n")
            else:
                 self.text_display.insert(tk.END, f"[{roi_name}]:\n-\n\n") # Placeholder


        self.text_display.config(state=tk.DISABLED)

class StableTextTab(BaseTab):
    """Tab for displaying stable extracted text."""

    def setup_ui(self):
        stable_text_frame = ttk.LabelFrame(self.frame, text="Stable Text (Input for Translation)", padding="10")
        stable_text_frame.pack(fill=tk.BOTH, expand=True, pady=5) # Reduced pady

        self.stable_text_display = tk.Text(stable_text_frame, wrap=tk.WORD, height=10, width=40, # Reduced height
                                            font=("Consolas", 9))
        self.stable_text_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(stable_text_frame, command=self.stable_text_display.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stable_text_display.config(yscrollcommand=scrollbar.set)
        self.stable_text_display.config(state=tk.DISABLED)

    def update_text(self, stable_texts):
        """
        Update the stable text display.

        Args:
            stable_texts: Dictionary mapping ROI names to stable text
        """
        self.stable_text_display.config(state=tk.NORMAL)
        self.stable_text_display.delete(1.0, tk.END)

        # Maintain ROI order from app.rois
        has_stable_text = False
        for roi in self.app.rois:
            roi_name = roi.name
            text = stable_texts.get(roi_name, "")
            if text:
                has_stable_text = True
                self.stable_text_display.insert(tk.END, f"[{roi_name}]:\n{text}\n\n")
            # Optionally show placeholder even if no stable text for that ROI?
            # else:
            #     self.stable_text_display.insert(tk.END, f"[{roi_name}]:\n[No stable text]\n\n")

        if not has_stable_text:
             self.stable_text_display.insert(tk.END, "[Waiting for stable text...]")


        self.stable_text_display.config(state=tk.DISABLED)
```

--- END OF FILE ui/text_tab.py ---

--- START OF FILE ui/capture_tab.py ---

```python
import tkinter as tk
from tkinter import ttk
from ui.base import BaseTab
from utils.capture import get_windows, get_window_title
from utils.settings import get_setting, set_setting # Import settings functions

class CaptureTab(BaseTab):
    """Tab for window capture settings."""

    OCR_LANGUAGES = ["jpn", "jpn_vert", "eng", "chi_sim", "chi_tra", "kor"] # Add more if Paddle supports

    def setup_ui(self):
        capture_frame = ttk.LabelFrame(self.frame, text="Capture Settings", padding="10")
        capture_frame.pack(fill=tk.X, pady=10)

        # --- Window selection ---
        win_frame = ttk.Frame(capture_frame)
        win_frame.pack(fill=tk.X)
        ttk.Label(win_frame, text="Visual Novel Window:").pack(anchor=tk.W)

        self.window_var = tk.StringVar()
        self.window_combo = ttk.Combobox(win_frame, textvariable=self.window_var, width=50, state="readonly") # Increased width
        self.window_combo.pack(fill=tk.X, pady=(5, 0))
        self.window_combo.bind("<<ComboboxSelected>>", self.on_window_selected)


        # --- Buttons ---
        btn_frame = ttk.Frame(capture_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 10))

        self.refresh_btn = ttk.Button(btn_frame, text="Refresh List",
                                      command=self.refresh_window_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.start_btn = ttk.Button(btn_frame, text="Start Capture",
                                    command=self.app.start_capture)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="Stop Capture",
                                   command=self.app.stop_capture, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.snapshot_btn = ttk.Button(btn_frame, text="Take Snapshot",
                                       command=self.app.take_snapshot, state=tk.DISABLED) # Initially disabled
        self.snapshot_btn.pack(side=tk.LEFT, padx=5)

        self.live_view_btn = ttk.Button(btn_frame, text="Return to Live",
                                        command=self.app.return_to_live, state=tk.DISABLED)
        self.live_view_btn.pack(side=tk.LEFT, padx=5)

        # --- Language selection ---
        lang_frame = ttk.Frame(capture_frame)
        lang_frame.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(lang_frame, text="OCR Language:").pack(side=tk.LEFT, anchor=tk.W)

        self.lang_var = tk.StringVar()
        self.lang_combo = ttk.Combobox(lang_frame, textvariable=self.lang_var, width=15,
                                       values=self.OCR_LANGUAGES, state="readonly")

        # Load last used language or default
        default_lang = get_setting("ocr_language", "jpn")
        if default_lang in self.OCR_LANGUAGES:
             self.lang_combo.set(default_lang)
        elif self.OCR_LANGUAGES:
             self.lang_combo.current(0) # Fallback to first

        self.lang_combo.pack(side=tk.LEFT, anchor=tk.W, padx=5)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_language_changed)

        # --- Status label ---
        # This label is now mostly redundant as status is shown in main window's status bar
        # We keep it for structure but rely on app.update_status()
        self.status_label = ttk.Label(capture_frame, text="Status: Ready")
        self.status_label.pack(fill=tk.X, pady=(10, 0), anchor=tk.W)

        # Initialize window list
        self.refresh_window_list()

    def refresh_window_list(self):
        """Refresh the list of available windows."""
        self.app.update_status("Refreshing window list...") # Use app's status update
        self.window_combo.config(state=tk.NORMAL) # Allow clearing
        self.window_combo.set("") # Clear current selection
        self.app.selected_hwnd = None # Clear app's selected handle
        try:
            windows = get_windows()
            # Filter out windows with no title or specific unwanted titles (like this app itself)
            filtered_windows = {}
            app_title = self.app.master.title()
            for hwnd in windows:
                 title = get_window_title(hwnd)
                 # Basic filtering - might need refinement
                 if title and title != app_title and "Program Manager" not in title and "Default IME" not in title:
                      filtered_windows[hwnd] = f"{hwnd}: {title}"

            window_titles = list(filtered_windows.values())
            self.window_handles = list(filtered_windows.keys()) # Store handles separately
            self.window_combo['values'] = window_titles

            if window_titles:
                 # Try to re-select the previously selected window if it still exists
                 last_hwnd = getattr(self.app, 'selected_hwnd_on_refresh', None) # Use a temp attr if needed
                 if last_hwnd and last_hwnd in self.window_handles:
                      try:
                           idx = self.window_handles.index(last_hwnd)
                           self.window_combo.current(idx)
                           self.on_window_selected() # Update app's selected HWND
                      except ValueError:
                           pass # Handle not found
                 self.app.update_status(f"Found {len(window_titles)} windows. Select one.")
            else:
                 self.app.update_status("No suitable windows found.")
            self.window_combo.config(state="readonly")

        except Exception as e:
             self.app.update_status(f"Error refreshing windows: {e}")
             self.window_combo.config(state="readonly")


    def on_window_selected(self, event=None):
        """Update the application's selected HWND when a window is chosen."""
        try:
            selected_index = self.window_combo.current()
            if selected_index >= 0 and selected_index < len(self.window_handles):
                new_hwnd = self.window_handles[selected_index]
                if new_hwnd != self.app.selected_hwnd:
                     self.app.selected_hwnd = new_hwnd
                     title = self.window_combo.get().split(":", 1)[-1].strip()
                     self.app.update_status(f"Window selected: {title}")
                     print(f"Selected window HWND: {self.app.selected_hwnd}")
                     # If capture is running, changing window might require restart?
                     if self.app.capturing:
                          self.app.update_status(f"Window changed to {title}. Restart capture if needed.")
                          # self.app.stop_capture() # Or maybe just let it fail/recover?
            else:
                 # This case should ideally not happen with readonly combobox selection
                 if self.app.selected_hwnd is not None:
                      self.app.selected_hwnd = None
                      self.app.update_status("No window selected.")
        except Exception as e:
            self.app.selected_hwnd = None
            self.app.update_status(f"Error selecting window: {e}")


    def on_language_changed(self, event=None):
        """Callback when OCR language is changed."""
        new_lang = self.lang_var.get()
        if new_lang in self.OCR_LANGUAGES:
            print(f"OCR Language changed to: {new_lang}")
            # Save the setting
            set_setting("ocr_language", new_lang)
            # Notify the main app to update the OCR engine
            self.app.update_ocr_engine(new_lang)
            # Status update handled by update_ocr_engine
        else:
            self.app.update_status("Invalid language selected.")


    def update_status(self, message):
        """Update the local status label (mirroring main status bar)."""
        self.status_label.config(text=f"Status: {message}")
        # Main status bar updated by self.app.update_status()


    def on_capture_started(self):
        """Update UI when capture starts."""
        self.start_btn.config(state=tk.DISABLED)
        self.refresh_btn.config(state=tk.DISABLED)
        self.window_combo.config(state=tk.DISABLED) # Disable window change during capture
        self.stop_btn.config(state=tk.NORMAL)
        self.snapshot_btn.config(state=tk.NORMAL) # Enable snapshot after starting
        self.live_view_btn.config(state=tk.DISABLED)

    def on_capture_stopped(self):
        """Update UI when capture stops."""
        self.start_btn.config(state=tk.NORMAL)
        self.refresh_btn.config(state=tk.NORMAL)
        self.window_combo.config(state="readonly") # Re-enable window selection
        self.stop_btn.config(state=tk.DISABLED)
        self.snapshot_btn.config(state=tk.DISABLED)
        self.live_view_btn.config(state=tk.DISABLED)

    def on_snapshot_taken(self):
        """Update UI when a snapshot is taken."""
        # Keep snapshot button enabled, user might return to live and take another
        self.live_view_btn.config(state=tk.NORMAL) # Allow returning to live
        # Stop button remains enabled
        # Status updated by app.take_snapshot calling app.update_status

    def on_live_view_resumed(self):
        """Update UI when returning to live view."""
        self.live_view_btn.config(state=tk.DISABLED)
        if self.app.capturing: # Only enable snapshot if capture is actually running
             self.snapshot_btn.config(state=tk.NORMAL)
             # Status updated by app.return_to_live calling app.update_status
        else:
             # If capture stopped while in snapshot mode (unlikely but possible)
             self.snapshot_btn.config(state=tk.DISABLED)
             self.on_capture_stopped() # Ensure UI reflects stopped state
```

--- END OF FILE ui/capture_tab.py ---

--- START OF FILE ui/translation_tab.py ---

```python
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import copy
from ui.base import BaseTab
from utils.translation import translate_text, clear_cache, reset_context
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

        self.clear_cache_btn = ttk.Button(action_frame, text="Clear Translation Cache", command=self.clear_translation_cache)
        self.clear_cache_btn.pack(side=tk.LEFT, padx=5)

        self.reset_context_btn = ttk.Button(action_frame, text="Reset Translation Context", command=self.reset_translation_context)
        self.reset_context_btn.pack(side=tk.LEFT, padx=5)

        self.translate_btn = ttk.Button(action_frame, text="Translate Stable Text Now", command=self.perform_translation)
        self.translate_btn.pack(side=tk.RIGHT, padx=5)

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
                    aggregated_input_text, # Text with "[ROI_Name]: content" format
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

    def clear_translation_cache(self):
        """Clear the translation cache and show confirmation."""
        result = clear_cache()
        messagebox.showinfo("Cache Cleared", result, parent=self.app.master)
        self.app.update_status("Translation cache cleared.")

    def reset_translation_context(self):
        """Reset the translation context history and show confirmation."""
        result = reset_context()
        messagebox.showinfo("Context Reset", result, parent=self.app.master)
        self.app.update_status("Translation context reset.")
```

--- END OF FILE ui/translation_tab.py ---

--- START OF FILE ui/roi_tab.py ---

```python
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import BaseTab
from utils.config import save_rois, load_rois
from utils.settings import update_settings # For removing overlay settings
import os

class ROITab(BaseTab):
    """Tab for ROI management."""

    def setup_ui(self):
        roi_frame = ttk.LabelFrame(self.frame, text="Regions of Interest (ROIs)", padding="10")
        roi_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # --- New ROI creation ---
        create_frame = ttk.Frame(roi_frame)
        create_frame.pack(fill=tk.X, pady=(0,10))

        ttk.Label(create_frame, text="New ROI Name:").pack(side=tk.LEFT, anchor=tk.W, pady=(5, 0), padx=(0,5))

        self.roi_name_entry = ttk.Entry(create_frame, width=15)
        self.roi_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(5, 0))
        self.roi_name_entry.insert(0, "dialogue") # Default name

        self.create_roi_btn = ttk.Button(create_frame, text="Define ROI",
                                         command=self.app.toggle_roi_selection)
        self.create_roi_btn.pack(side=tk.LEFT, padx=(5, 0), pady=(5,0))
        # Add tooltip later if needed

        ttk.Label(roi_frame, text="Click 'Define ROI', then click and drag on the image preview.",
                  font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))


        # --- ROI List and Management ---
        list_manage_frame = ttk.Frame(roi_frame)
        list_manage_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Listbox with Scrollbar
        list_frame = ttk.Frame(list_manage_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(list_frame, text="Current ROIs (Select to manage):").pack(anchor=tk.W)

        roi_scrollbar = ttk.Scrollbar(list_frame)
        roi_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.roi_listbox = tk.Listbox(list_frame, height=6, selectmode=tk.SINGLE,
                                      exportselection=False, # Prevent selection changing when focus moves
                                      yscrollcommand=roi_scrollbar.set)
        self.roi_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roi_scrollbar.config(command=self.roi_listbox.yview)
        self.roi_listbox.bind("<<ListboxSelect>>", self.on_roi_selected)


        # Management Buttons (Vertical)
        manage_btn_frame = ttk.Frame(list_manage_frame)
        manage_btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5,0))

        self.move_up_btn = ttk.Button(manage_btn_frame, text="▲ Up", width=8,
                                      command=self.move_roi_up, state=tk.DISABLED)
        self.move_up_btn.pack(pady=2, anchor=tk.N)

        self.move_down_btn = ttk.Button(manage_btn_frame, text="▼ Down", width=8,
                                        command=self.move_roi_down, state=tk.DISABLED)
        self.move_down_btn.pack(pady=2, anchor=tk.N)

        self.delete_roi_btn = ttk.Button(manage_btn_frame, text="Delete", width=8,
                                         command=self.delete_selected_roi, state=tk.DISABLED)
        self.delete_roi_btn.pack(pady=(10, 2), anchor=tk.N)

        self.config_overlay_btn = ttk.Button(manage_btn_frame, text="Overlay...", width=8,
                                           command=self.configure_selected_overlay, state=tk.DISABLED)
        self.config_overlay_btn.pack(pady=(5, 2), anchor=tk.N) # Moved closer


        # --- Save/Load Buttons ---
        file_btn_frame = ttk.Frame(roi_frame)
        file_btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.save_rois_btn = ttk.Button(file_btn_frame, text="Save ROIs As...",
                                        command=self.save_rois)
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)

        self.load_rois_btn = ttk.Button(file_btn_frame, text="Load ROIs...",
                                        command=self.load_rois)
        self.load_rois_btn.pack(side=tk.LEFT, padx=5)


    def on_roi_selected(self, event=None):
        """Enable/disable management buttons based on selection."""
        selection = self.roi_listbox.curselection()
        has_selection = bool(selection)
        num_items = self.roi_listbox.size()
        idx = selection[0] if has_selection else -1

        self.move_up_btn.config(state=tk.NORMAL if has_selection and idx > 0 else tk.DISABLED)
        self.move_down_btn.config(state=tk.NORMAL if has_selection and idx < num_items - 1 else tk.DISABLED)
        self.delete_roi_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        # Enable overlay config button only if overlay tab exists
        can_config_overlay = has_selection and hasattr(self.app, 'overlay_tab')
        self.config_overlay_btn.config(state=tk.NORMAL if can_config_overlay else tk.DISABLED)


    def on_roi_selection_toggled(self, active):
        """Update UI when ROI selection mode is toggled."""
        if active:
            self.create_roi_btn.config(text="Cancel Define")
            self.app.update_status("ROI selection active. Drag on preview.")
            self.app.master.config(cursor="crosshair") # Change cursor
        else:
            self.create_roi_btn.config(text="Define ROI")
            # Status update handled by app.toggle_roi_selection completion/cancellation
            self.app.master.config(cursor="") # Restore default cursor


    def update_roi_list(self):
        """Update the ROI listbox with current ROIs."""
        # Store current selection index to try and restore it
        current_selection_index = self.roi_listbox.curselection()
        idx_to_select = current_selection_index[0] if current_selection_index else -1

        self.roi_listbox.delete(0, tk.END)
        for roi in self.app.rois:
            # Maybe add an indicator if overlay is enabled? [O] ?
            is_overlay_enabled = False
            if hasattr(self.app, 'overlay_manager'):
                 config = self.app.overlay_manager._get_roi_config(roi.name)
                 is_overlay_enabled = config.get('enabled', False)
            prefix = "[O] " if is_overlay_enabled else "[ ] "
            self.roi_listbox.insert(tk.END, f"{prefix}{roi.name}") # Show name with overlay indicator

        # Try to restore selection
        if 0 <= idx_to_select < self.roi_listbox.size():
            self.roi_listbox.select_set(idx_to_select)
            self.roi_listbox.activate(idx_to_select)
        elif self.roi_listbox.size() > 0:
             idx_to_select = -1 # Reset selection if previous index invalid


        # Update the ROI list in the Overlay Tab as well
        if hasattr(self.app, 'overlay_tab'):
            self.app.overlay_tab.update_roi_list()

        # Update button states based on new selection state
        self.on_roi_selected()


    def save_rois(self):
        """Save ROIs using the config utility."""
        if not self.app.rois:
             messagebox.showwarning("Save ROIs", "There are no ROIs defined to save.", parent=self.app.master)
             return

        new_config_file = save_rois(self.app.rois, self.app.config_file)
        if new_config_file and new_config_file != self.app.config_file:
            self.app.config_file = new_config_file
            self.app.update_status(f"Saved {len(self.app.rois)} ROIs to {os.path.basename(new_config_file)}")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(new_config_file)}") # Update title
        elif new_config_file:
            # Saved to the same file (or user cancelled but path was returned)
            self.app.update_status(f"Saved {len(self.app.rois)} ROIs to {os.path.basename(new_config_file)}")
        # else: User cancelled, no status update needed


    def load_rois(self):
        """Load ROIs using the config utility."""
        rois, loaded_config_file = load_rois(self.app.config_file) # Pass current as suggestion

        if loaded_config_file and rois is not None: # Check success (path returned, rois not None)
            self.app.rois = rois
            self.app.config_file = loaded_config_file
            self.update_roi_list()
            self.app.overlay_manager.rebuild_overlays() # Rebuild overlays for new ROIs
            self.app.update_status(f"Loaded {len(rois)} ROIs from {os.path.basename(loaded_config_file)}")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(loaded_config_file)}") # Update title
            # Clear stale text data associated with old ROIs
            self.app.text_history = {}
            self.app.stable_texts = {}
            self.app.text_tab.update_text({})
            self.app.stable_text_tab.update_text({})
            self.app.translation_tab.translation_display.config(state=tk.NORMAL)
            self.app.translation_tab.translation_display.delete(1.0, tk.END)
            self.app.translation_tab.translation_display.config(state=tk.DISABLED)


        elif rois is None and loaded_config_file is None: # Explicit failure from load_rois
             self.app.update_status("ROI loading failed. See console or previous message.")
        else: # User cancelled (rois=[], loaded_config_file=None)
             self.app.update_status("ROI loading cancelled.")


    def move_roi_up(self):
        """Move the selected ROI up in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0: return
        idx = selection[0]

        self.app.rois[idx - 1], self.app.rois[idx] = self.app.rois[idx], self.app.rois[idx - 1]

        self.update_roi_list() # Redraws listbox and updates overlay tab list
        # Restore selection
        new_idx = idx - 1
        self.roi_listbox.select_set(new_idx)
        self.roi_listbox.activate(new_idx)
        self.on_roi_selected() # Update button states
        self.app.overlay_manager.rebuild_overlays() # Order might matter for some overlay logic


    def move_roi_down(self):
        """Move the selected ROI down in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == len(self.app.rois) - 1: return
        idx = selection[0]

        self.app.rois[idx], self.app.rois[idx + 1] = self.app.rois[idx + 1], self.app.rois[idx]

        self.update_roi_list() # Redraws listbox and updates overlay tab list
        # Restore selection
        new_idx = idx + 1
        self.roi_listbox.select_set(new_idx)
        self.roi_listbox.activate(new_idx)
        self.on_roi_selected() # Update button states
        self.app.overlay_manager.rebuild_overlays()


    def delete_selected_roi(self):
        """Delete the selected ROI."""
        selection = self.roi_listbox.curselection()
        if not selection: return # Button should be disabled anyway

        index = selection[0]
        # Get name from listbox item (includes prefix) and strip prefix
        listbox_text = self.roi_listbox.get(index)
        roi_name = listbox_text.split("]", 1)[-1].strip() # Get text after "[O] " or "[ ] "

        # Confirm deletion
        confirm = messagebox.askyesno("Delete ROI", f"Are you sure you want to delete ROI '{roi_name}'?", parent=self.app.master)
        if not confirm: return

        # Find the actual ROI object by name (safer than relying on index if list changes)
        roi_to_delete = next((roi for roi in self.app.rois if roi.name == roi_name), None)
        if not roi_to_delete:
             print(f"Error: Could not find ROI object for name '{roi_name}' to delete.")
             return

        # Remove from list
        self.app.rois.remove(roi_to_delete)

        # Remove associated overlay settings (needs access to overlay_manager instance)
        if hasattr(self.app, 'overlay_manager') and roi_name in self.app.overlay_manager.overlay_settings:
             del self.app.overlay_manager.overlay_settings[roi_name]
             update_settings({"overlay_settings": self.app.overlay_manager.overlay_settings}) # Save removal

        # Destroy the overlay window if it exists
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.destroy_overlay(roi_name)

        # Remove from text history and stable text
        if roi_name in self.app.text_history: del self.app.text_history[roi_name]
        if roi_name in self.app.stable_texts: del self.app.stable_texts[roi_name]
        # Refresh displays (which will use the updated self.app.rois)
        self.app.text_tab.update_text(self.app.text_history) # Might need just current texts?
        self.app.stable_text_tab.update_text(self.app.stable_texts)


        self.update_roi_list() # Updates listbox and overlay tab's list
        self.app.update_status(f"ROI '{roi_name}' deleted.")


    def configure_selected_overlay(self):
        """Switch to the Overlay tab and select the corresponding ROI."""
        selection = self.roi_listbox.curselection()
        if not selection: return

        # Get name from listbox item (includes prefix) and strip prefix
        listbox_text = self.roi_listbox.get(selection[0])
        roi_name = listbox_text.split("]", 1)[-1].strip()

        # Check if overlay tab exists
        if not hasattr(self.app, 'overlay_tab') or not self.app.overlay_tab.winfo_exists():
             messagebox.showerror("Error", "Overlay configuration tab is not available.", parent=self.app.master)
             return

        # Find the index of the Overlay tab
        try:
             overlay_tab_widget = self.app.overlay_tab.frame
             # Find the notebook containing this frame
             notebook_widget = overlay_tab_widget.master
             while notebook_widget and not isinstance(notebook_widget, ttk.Notebook):
                  notebook_widget = notebook_widget.master

             if not notebook_widget:
                 raise tk.TclError("Could not find parent Notebook.")

             # Select the tab
             notebook_widget.select(overlay_tab_widget)

             # Set the selected ROI in the Overlay tab's combobox
             if roi_name in self.app.overlay_tab.roi_names:
                 self.app.overlay_tab.selected_roi_var.set(roi_name)
                 # Load the config for this ROI in the overlay tab
                 self.app.overlay_tab.load_roi_config()
             else:
                  print(f"ROI '{roi_name}' not found in Overlay Tab's list.")


        except (tk.TclError, AttributeError) as e:
             print(f"Error switching to overlay config tab: {e}")
             messagebox.showerror("Error", "Could not switch to Overlay configuration tab.", parent=self.app.master)
        except Exception as e:
             print(f"Unexpected error configuring overlay: {e}")

```

--- END OF FILE ui/roi_tab.py ---

--- START OF FILE ui/overlay.py ---

```python
import tkinter as tk
from tkinter import font as tkFont
import platform
import win32gui # For positioning relative to game window and click-through
import win32con
import win32api # For GetSystemMetrics

class OverlayWindow(tk.Toplevel):
    """A transparent, topmost window to display translated text for an ROI."""

    def __init__(self, master, roi_name, config, game_hwnd):
        super().__init__(master)
        self.roi_name = roi_name
        self.config = config
        self.game_hwnd = game_hwnd
        self.last_geometry = "" # To avoid unnecessary geometry updates

        # --- Window Configuration ---
        self.overrideredirect(True)  # No window decorations (title bar, borders)
        self.wm_attributes("-topmost", True) # Keep on top

        # --- Transparency & Click-Through (Windows Specific) ---
        self.transparent_color = 'gray1' # A color unlikely to be used
        self.configure(bg=self.transparent_color)

        if platform.system() == "Windows":
            try:
                # Set background color to be transparent
                self.wm_attributes("-transparentcolor", self.transparent_color)

                # Set window style for click-through (WS_EX_LAYERED | WS_EX_TRANSPARENT)
                hwnd = self.winfo_id() # Get HWND after window is created
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                # Remove WS_EX_APPWINDOW to prevent appearing in taskbar/alt+tab
                style &= ~win32con.WS_EX_APPWINDOW
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

                # Optional: Set alpha for the whole window (might affect text readability)
                # alpha_percent = int(config.get('alpha', 0.85) * 255) # Use config alpha
                # win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha_percent, win32con.LWA_ALPHA) # 0=ColorKey, 1=Alpha

            except Exception as e:
                print(f"Error setting window attributes for {self.roi_name}: {e}")
        else:
             print("Warning: Overlay transparency/click-through might not work correctly on non-Windows OS.")
             # Basic alpha setting for other platforms (might not be click-through)
             alpha = config.get('alpha', 0.85)
             self.wm_attributes("-alpha", alpha)

        # --- Content Label ---
        self.label_var = tk.StringVar()
        self._update_label_config() # Apply initial config to label

        self.label.pack(fill=tk.BOTH, expand=True)

        self.withdraw() # Start hidden

    def _update_label_config(self):
        """Applies current self.config to the label widget."""
        font_family = self.config.get('font_family', 'Segoe UI')
        font_size = self.config.get('font_size', 14)
        font_color = self.config.get('font_color', 'white')
        bg_color = self.config.get('bg_color', '#222222') # Use actual bg color for the label
        wraplength = self.config.get('wraplength', 450) # Wrap text width
        justify_map = {'left': tk.LEFT, 'center': tk.CENTER, 'right': tk.RIGHT}
        justify_align = justify_map.get(self.config.get('justify', 'left'), tk.LEFT)

        try:
             label_font = tkFont.Font(family=font_family, size=font_size)
        except tk.TclError:
             print(f"Warning: Font '{font_family}' not found. Using default.")
             label_font = tkFont.Font(size=font_size) # Use default family

        if hasattr(self, 'label'): # If label exists, reconfigure
            self.label.config(
                font=label_font,
                fg=font_color,
                bg=bg_color,
                wraplength=wraplength,
                justify=justify_align
            )
        else: # Create label if it doesn't exist
             self.label = tk.Label(
                 self,
                 textvariable=self.label_var,
                 font=label_font,
                 fg=font_color,
                 bg=bg_color,
                 wraplength=wraplength,
                 justify=justify_align,
                 padx=5, pady=2
             )

        # Optional: Re-apply alpha based on config if needed for non-Windows
        # if platform.system() != "Windows":
        #     alpha = self.config.get('alpha', 0.85)
        #     self.wm_attributes("-alpha", alpha)


    def update_text(self, text):
        """Update the text displayed in the overlay."""
        if not isinstance(text, str):
            text = str(text) # Ensure it's a string

        # Limit length?
        # max_len = 500
        # if len(text) > max_len:
        #     text = text[:max_len] + "..."

        current_text = self.label_var.get()
        # Only update if text actually changed
        if text != current_text:
            self.label_var.set(text)

        # Update visibility based on text and enabled status
        should_be_visible = bool(text) and self.config.get('enabled', True)
        is_visible = self.state() == 'normal'

        if should_be_visible:
            # Update position before showing, but only if needed
            self.update_position_if_needed()
            if not is_visible:
                self.deiconify() # Show window if hidden
                self.lift() # Ensure it's on top
        elif is_visible:
            self.withdraw() # Hide if no text or disabled


    def update_config(self, new_config):
        """Update the appearance based on new configuration."""
        self.config = new_config
        self._update_label_config() # Apply changes to label

        # Update visibility based on new enabled status and current text
        is_enabled = new_config.get('enabled', True)
        has_text = bool(self.label_var.get())

        if is_enabled and has_text:
            self.update_position_if_needed() # Recalc position
            self.deiconify()
            self.lift()
        else:
            self.withdraw()


    def update_position_if_needed(self, roi_rect_in_game_coords=None):
         """Calculates desired geometry and applies it only if changed."""
         new_geometry = self._calculate_geometry(roi_rect_in_game_coords)
         if new_geometry and new_geometry != self.last_geometry:
              self.geometry(new_geometry)
              self.last_geometry = new_geometry


    def _calculate_geometry(self, roi_rect_in_game_coords=None):
        """
        Calculates the desired geometry string "+x+y" for the overlay.
        roi_rect_in_game_coords: tuple (x1, y1, x2, y2) of the ROI within the game window's client area.
        Returns "+x+y" string or None if calculation fails.
        """
        try:
            # Check game window validity
            if not self.game_hwnd or not win32gui.IsWindow(self.game_hwnd) or win32gui.IsIconic(self.game_hwnd):
                if self.state() == 'normal': # Only print if window was visible
                     print(f"Game window {self.game_hwnd} not found or minimized. Hiding overlay {self.roi_name}.")
                     self.withdraw()
                return None

            # Get game window's client area in screen coordinates
            game_client_rect = get_client_rect(self.game_hwnd) # Uses utils.capture function
            if not game_client_rect:
                 print(f"Could not get game client rect for HWND {self.game_hwnd}.")
                 # Fallback to full window rect? Might be less accurate for positioning relative to client area.
                 game_client_rect = get_window_rect(self.game_hwnd)
                 if not game_client_rect:
                      if self.state() == 'normal': self.withdraw()
                      return None

            game_x, game_y, game_r, game_b = game_client_rect
            game_width = game_r - game_x
            game_height = game_b - game_y

            # If specific ROI coords relative to game client area are given
            if roi_rect_in_game_coords:
                roi_x1_rel, roi_y1_rel, roi_x2_rel, roi_y2_rel = roi_rect_in_game_coords
                # Ensure ROI coords are within game client bounds before calculating screen coords
                roi_x1_rel = max(0, min(roi_x1_rel, game_width))
                roi_y1_rel = max(0, min(roi_y1_rel, game_height))
                roi_x2_rel = max(0, min(roi_x2_rel, game_width))
                roi_y2_rel = max(0, min(roi_y2_rel, game_height))

                # Absolute screen coordinates of the ROI
                roi_abs_x1 = game_x + roi_x1_rel
                roi_abs_y1 = game_y + roi_y1_rel
                roi_abs_x2 = game_x + roi_x2_rel
                roi_abs_y2 = game_y + roi_y2_rel
                roi_width = roi_abs_x2 - roi_abs_x1
                roi_height = roi_abs_y2 - roi_abs_y1
            else:
                # Fallback: Position relative to the game window itself if no ROI provided
                # E.g., bottom center of the game window
                roi_abs_x1 = game_x + game_width // 4
                roi_abs_y1 = game_y + game_height - 100 # Guess a position
                roi_abs_x2 = game_x + 3 * game_width // 4
                roi_abs_y2 = game_y + game_height - 20 # Guess a position
                roi_width = roi_abs_x2 - roi_abs_x1
                roi_height = roi_abs_y2 - roi_abs_y1


            # --- Calculate Overlay Position based on config ---
            position_mode = self.config.get('position', 'bottom_roi')
            # Ensure overlay window size is calculated accurately
            self.update_idletasks()
            overlay_width = self.label.winfo_reqwidth() # Use requested width of the label
            overlay_height = self.label.winfo_reqheight() # Use requested height of the label

            # Add small safety margin?
            overlay_width += 2
            overlay_height += 2

            x, y = 0, 0
            offset = 5 # Default pixel offset from ROI/Game edge

            if position_mode == 'bottom_roi':
                x = roi_abs_x1 + roi_width // 2 - overlay_width // 2
                y = roi_abs_y2 + offset
            elif position_mode == 'top_roi':
                x = roi_abs_x1 + roi_width // 2 - overlay_width // 2
                y = roi_abs_y1 - overlay_height - offset
            elif position_mode == 'center_roi':
                 x = roi_abs_x1 + roi_width // 2 - overlay_width // 2
                 y = roi_abs_y1 + roi_height // 2 - overlay_height // 2
            elif position_mode == 'bottom_game':
                 x = game_x + game_width // 2 - overlay_width // 2
                 y = game_b - overlay_height - offset
            elif position_mode == 'top_game':
                 x = game_x + game_width // 2 - overlay_width // 2
                 y = game_y + offset
            elif position_mode == 'center_game':
                 x = game_x + game_width // 2 - overlay_width // 2
                 y = game_y + game_height // 2 - overlay_height // 2
            # Add more modes: fixed coordinates? bottom_left_roi etc.
            else: # Default to bottom_roi
                x = roi_abs_x1 + roi_width // 2 - overlay_width // 2
                y = roi_abs_y2 + offset

            # --- Ensure overlay stays within screen bounds ---
            # Use win32api for potentially multi-monitor aware screen size
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            screen_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            screen_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

            # Clamp position
            x = max(screen_left, min(x, screen_left + screen_width - overlay_width))
            y = max(screen_top, min(y, screen_top + screen_height - overlay_height))

            return f"+{int(x)}+{int(y)}"

        except Exception as e:
            print(f"Error calculating position for overlay {self.roi_name}: {e}")
            if self.state() == 'normal': self.withdraw() # Hide if positioning fails
            return None

    def destroy_window(self):
        """Safely destroy the overlay window."""
        try:
             self.destroy()
        except tk.TclError as e:
             print(f"Error destroying overlay {self.roi_name} (already destroyed?): {e}")
        except Exception as e:
            print(f"Unexpected error destroying overlay {self.roi_name}: {e}")

# Helper function (outside class) needed by capture.py if used there
def get_client_rect(hwnd):
    """Helper to get client rect in screen coords. Avoids circular import."""
    try:
        if not win32gui.IsWindow(hwnd): return None
        client_rect_rel = win32gui.GetClientRect(hwnd)
        pt_tl = wintypes.POINT(client_rect_rel[0], client_rect_rel[1])
        pt_br = wintypes.POINT(client_rect_rel[2], client_rect_rel[3])
        if not windll.user32.ClientToScreen(hwnd, byref(pt_tl)): return None
        if not windll.user32.ClientToScreen(hwnd, byref(pt_br)): return None
        return (pt_tl.x, pt_tl.y, pt_br.x, pt_br.y)
    except Exception:
        return None

# Helper function (outside class) needed by capture.py if used there
def get_window_rect(hwnd):
    """Helper to get window rect in screen coords. Avoids circular import."""
    try:
        if not win32gui.IsWindow(hwnd): return None
        return win32gui.GetWindowRect(hwnd)
    except Exception:
        return None

```

--- END OF FILE ui/overlay.py ---

--- START OF FILE ui/overlay_manager.py ---

```python
import tkinter as tk
from ui.overlay import OverlayWindow
from utils.settings import get_setting, set_setting, update_settings
import win32gui # To check game window validity

class OverlayManager:
    """Manages multiple OverlayWindow instances."""

    # Default configuration applied if no specific setting exists for an ROI
    DEFAULT_OVERLAY_CONFIG = {
        "enabled": True,
        "font_family": "Segoe UI", # Default modern font
        "font_size": 14,
        "font_color": "white",
        "bg_color": "#222222", # Dark grey background
        "alpha": 0.85, # Transparency level (used by OverlayWindow if applicable)
        "position": "bottom_roi", # Default position relative to ROI
        "wraplength": 450, # Max width in pixels before text wraps
        "justify": "left" # Text alignment (left, center, right)
    }

    def __init__(self, master, app_ref):
        self.master = master
        self.app = app_ref # Reference to the main application
        self.overlays = {}  # roi_name: OverlayWindow instance
        # Load global enabled state and individual ROI settings from persistent storage
        self.global_overlays_enabled = get_setting("global_overlays_enabled", True)
        self.overlay_settings = get_setting("overlay_settings", {}) # roi_name: config_dict

    def _get_roi_config(self, roi_name):
        """Gets the specific config for an ROI, merging with defaults."""
        # Start with a copy of the defaults
        config = self.DEFAULT_OVERLAY_CONFIG.copy()
        # Get ROI-specific saved settings
        roi_specific = self.overlay_settings.get(roi_name, {})
        # Update the defaults with any specific settings found
        config.update(roi_specific)
        return config

    def create_overlay_for_roi(self, roi):
        """Creates or recreates an overlay window for a given ROI object."""
        roi_name = roi.name
        if roi_name in self.overlays:
            # If already exists, maybe just update its config/position?
            # For simplicity now, destroy and recreate if needed.
            self.destroy_overlay(roi_name)

        # Check if game window is valid before creating
        if not self.app.selected_hwnd or not win32gui.IsWindow(self.app.selected_hwnd):
             # print(f"Cannot create overlay for {roi_name}: Invalid game window.")
             return # Silently fail if no valid game window

        config = self._get_roi_config(roi_name)

        # Only create if globally enabled AND this specific ROI is enabled in its config
        if self.global_overlays_enabled and config.get("enabled", True):
            try:
                overlay = OverlayWindow(self.master, roi_name, config, self.app.selected_hwnd)
                self.overlays[roi_name] = overlay
                print(f"Created overlay for ROI: {roi_name}")
                # It starts hidden, will be shown on update_text if needed
            except Exception as e:
                print(f"Error creating overlay window for {roi_name}: {e}")
        else:
             # Don't print spam if intentionally disabled
             # print(f"Overlay creation skipped for {roi_name} (Globally Enabled: {self.global_overlays_enabled}, ROI Enabled: {config.get('enabled', True)})")
             pass


    def update_overlay(self, roi_name, text):
        """Updates the text and position of a specific overlay."""
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            # Find the corresponding ROI object to get its coordinates
            roi = next((r for r in self.app.rois if r.name == roi_name), None)
            if roi:
                # Pass ROI coordinates relative to the game window's client area origin
                # Assuming roi.x1, roi.y1 etc. are relative to the captured frame origin
                # which should correspond to the game window client area origin.
                roi_rect = (roi.x1, roi.y1, roi.x2, roi.y2)
                # Update text first, which handles showing/hiding based on content & enabled state
                overlay.update_text(text)
                # Position update is handled within update_text -> update_position_if_needed
                # overlay.update_position_if_needed(roi_rect_in_game_coords=roi_rect) # Pass coords here
            else:
                 # If ROI object not found (e.g., deleted but overlay not yet destroyed?), just update text
                 overlay.update_text(text)
                 # Cannot update position accurately without ROI coords
                 overlay.update_position_if_needed() # Use fallback position


    def update_overlays(self, translated_segments):
        """Updates all relevant overlays based on the translation results dictionary."""
        if not self.global_overlays_enabled:
            self.hide_all_overlays() # Ensure all are hidden if globally disabled
            return

        # Get all current ROI names
        all_roi_names = {roi.name for roi in self.app.rois}
        # Get names of ROIs that received a translation
        translated_roi_names = set(translated_segments.keys())

        # Iterate through all known ROIs
        for roi_name in all_roi_names:
            # Check if an overlay exists or should exist
            overlay_exists = roi_name in self.overlays
            roi = next((r for r in self.app.rois if r.name == roi_name), None)
            config = self._get_roi_config(roi_name)
            is_roi_enabled = config.get("enabled", True)

            # Get the translated text, default to empty string if none provided
            text_to_display = translated_segments.get(roi_name, "")

            if roi and is_roi_enabled: # If the ROI exists and should be displayed
                 if not overlay_exists:
                      # Create overlay if it's missing but should be shown
                      print(f"Recreating missing overlay for enabled ROI: {roi_name}")
                      self.create_overlay_for_roi(roi) # Create it
                      overlay_exists = roi_name in self.overlays # Check again

                 if overlay_exists:
                      # Update the overlay with text (handles show/hide internally)
                      self.update_overlay(roi_name, text_to_display)

            elif overlay_exists:
                 # If ROI is disabled or deleted, ensure overlay is hidden/destroyed
                 print(f"Hiding/Destroying overlay for disabled/deleted ROI: {roi_name}")
                 self.destroy_overlay(roi_name) # Destroy might be cleaner


    def clear_all_overlays(self):
        """Clears text from all managed overlays (hides them)."""
        for overlay in self.overlays.values():
            overlay.update_text("")

    def hide_all_overlays(self):
        """Hides all managed overlay windows."""
        for overlay in self.overlays.values():
            overlay.withdraw()

    def show_all_overlays(self):
        """Shows all managed overlay windows *if* they have text and are enabled."""
        if not self.global_overlays_enabled:
            return
        print("Attempting to show all enabled overlays with text...")
        for roi_name, overlay in self.overlays.items():
            config = self._get_roi_config(roi_name)
            # Show only if globally enabled, ROI enabled, and has text
            if config.get("enabled", True) and overlay.label_var.get():
                # Find ROI for position update
                roi = next((r for r in self.app.rois if r.name == roi_name), None)
                roi_rect = (roi.x1, roi.y1, roi.x2, roi.y2) if roi else None
                overlay.update_position_if_needed(roi_rect) # Recalc position
                overlay.deiconify()
                overlay.lift()


    def destroy_overlay(self, roi_name):
        """Destroys a specific overlay window."""
        if roi_name in self.overlays:
            try:
                self.overlays[roi_name].destroy_window()
            except Exception as e:
                print(f"Error destroying overlay {roi_name}: {e}")
            del self.overlays[roi_name]
            print(f"Destroyed overlay for ROI: {roi_name}")


    def destroy_all_overlays(self):
        """Destroys all managed overlay windows."""
        names = list(self.overlays.keys())
        for name in names:
            self.destroy_overlay(name)
        # Ensure dictionary is empty
        self.overlays = {}
        print("Destroyed all overlays.")


    def rebuild_overlays(self):
        """Destroys and recreates all overlays based on current ROIs and settings."""
        print("Rebuilding overlays...")
        self.destroy_all_overlays()
        if not self.global_overlays_enabled:
             print("Skipping overlay creation as globally disabled.")
             return
        for roi in self.app.rois:
            self.create_overlay_for_roi(roi) # Creates only if enabled

    def update_overlay_config(self, roi_name, new_partial_config):
        """Updates the config for a specific overlay and saves it."""
        # Ensure the roi_name entry exists in settings
        if roi_name not in self.overlay_settings:
            self.overlay_settings[roi_name] = {}

        # Update the specific settings for this ROI
        self.overlay_settings[roi_name].update(new_partial_config)

        # Save updated settings persistently
        if update_settings({"overlay_settings": self.overlay_settings}):
             print(f"Overlay settings saved for {roi_name}.")
        else:
             print(f"Error saving overlay settings for {roi_name}.")

        # Apply changes to the live overlay if it exists
        if roi_name in self.overlays:
            # Get the fully merged config (defaults + specific) to apply
            live_config = self._get_roi_config(roi_name)
            self.overlays[roi_name].update_config(live_config)
        elif new_partial_config.get('enabled', False) and self.global_overlays_enabled:
             # If overlay was disabled but now enabled, try to create it
             roi = next((r for r in self.app.rois if r.name == roi_name), None)
             if roi:
                  print(f"Creating overlay for {roi_name} as it was enabled.")
                  self.create_overlay_for_roi(roi)


    def set_global_overlays_enabled(self, enabled):
        """Sets the global enable state, saves it, and shows/hides overlays."""
        if enabled == self.global_overlays_enabled:
            return # No change

        self.global_overlays_enabled = enabled
        set_setting("global_overlays_enabled", enabled) # Save setting

        if enabled:
             print("Global overlays enabled. Rebuilding...")
             self.rebuild_overlays() # Recreate overlays respecting individual configs
             # Optionally restore last text? Needs storing last text per overlay.
        else:
             print("Global overlays disabled. Hiding all.")
             self.hide_all_overlays()

        # Update floating controls state if they exist
        if self.app.floating_controls and self.app.floating_controls.winfo_exists():
             self.app.floating_controls.overlay_var.set(enabled)
```

--- END OF FILE ui/overlay_manager.py ---

--- START OF FILE ui/floating_controls.py ---

```python
import tkinter as tk
from tkinter import ttk
import pyperclip # For copy functionality (install: pip install pyperclip)
from utils.settings import get_setting, set_setting

class FloatingControls(tk.Toplevel):
    """A small, draggable, topmost window for quick translation actions."""

    def __init__(self, master, app_ref):
        super().__init__(master)
        self.app = app_ref

        # --- Window Configuration ---
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.title("Controls")
        # Make transparent on Windows? Less useful for controls.
        # self.wm_attributes("-transparentcolor", "gray1")
        # self.config(bg="gray1")

        # Make window draggable
        self._offset_x = 0
        self._offset_y = 0
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release) # Save position on release

        # Style
        self.configure(background='#ECECEC') # Light grey background
        style = ttk.Style(self)
        # Define a smaller button style
        style.configure("Floating.TButton", padding=2, font=('Segoe UI', 8))
        # Use 'TButton' for checkbuttons to make them look like toggle buttons
        style.map("Toolbutton.TButton",
            relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        style.configure("Toolbutton.TButton", padding=2, font=('Segoe UI', 10)) # Slightly larger font for symbols


        # --- Content ---
        button_frame = ttk.Frame(self, padding=5, style="Floating.TFrame") # Use a style?
        button_frame.pack(fill=tk.BOTH, expand=True)

        # Re-translate Button
        self.retranslate_btn = ttk.Button(button_frame, text="🔄", width=3, style="Floating.TButton",
                                           command=self.app.translation_tab.perform_translation)
        self.retranslate_btn.grid(row=0, column=0, padx=2, pady=2)
        self.add_tooltip(self.retranslate_btn, "Re-translate stable text")


        # Copy Last Translation Button
        self.copy_btn = ttk.Button(button_frame, text="📋", width=3, style="Floating.TButton",
                                     command=self.copy_last_translation)
        self.copy_btn.grid(row=0, column=1, padx=2, pady=2)
        self.add_tooltip(self.copy_btn, "Copy last translation(s)")

        # Toggle Auto-Translate Button (using Checkbutton)
        self.auto_var = tk.BooleanVar(value=self.app.translation_tab.is_auto_translate_enabled())
        self.auto_btn = ttk.Checkbutton(button_frame, text="🤖", style="Toolbutton.TButton", # Checkbutton styled as Button
                                        variable=self.auto_var, command=self.toggle_auto_translate,
                                        width=3)
        self.auto_btn.grid(row=0, column=2, padx=2, pady=2)
        self.add_tooltip(self.auto_btn, "Toggle Auto-Translate")


        # Show/Hide Overlays Button (using Checkbutton)
        self.overlay_var = tk.BooleanVar(value=self.app.overlay_manager.global_overlays_enabled)
        self.overlay_btn = ttk.Checkbutton(button_frame, text="👁️", style="Toolbutton.TButton",
                                            variable=self.overlay_var, command=self.toggle_overlays,
                                            width=3)
        self.overlay_btn.grid(row=0, column=3, padx=2, pady=2)
        self.add_tooltip(self.overlay_btn, "Show/Hide Overlays")


        # Close Button (Optional - using withdraw)
        self.close_btn = ttk.Button(button_frame, text="✕", width=2, style="Floating.TButton",
                                     command=self.withdraw) # Hide instead of destroy
        self.close_btn.grid(row=0, column=4, padx=(5, 2), pady=2)
        self.add_tooltip(self.close_btn, "Hide Controls")

        # --- Initial Position ---
        saved_pos = get_setting("floating_controls_pos")
        if saved_pos:
             try:
                 x, y = map(int, saved_pos.split(','))
                 # Check bounds roughly
                 screen_width = self.winfo_screenwidth()
                 screen_height = self.winfo_screenheight()
                 # Ensure it's fully visible
                 self.update_idletasks() # Needed to get initial size estimate
                 win_width = self.winfo_reqwidth()
                 win_height = self.winfo_reqheight()

                 if 0 <= x < screen_width - win_width and 0 <= y < screen_height - win_height:
                      self.geometry(f"+{x}+{y}")
                 else:
                      print("Saved floating controls position out of bounds, centering.")
                      self.center_window()
             except Exception as e:
                 print(f"Error parsing saved position '{saved_pos}': {e}. Centering window.")
                 self.center_window()
        else:
             self.center_window()

        # Ensure state variables match app state after initialization
        self.update_button_states()

        self.deiconify() # Show the window

    def center_window(self):
        """Positions the window near the top center of the screen."""
        self.update_idletasks() # Calculate size
        width = self.winfo_reqwidth()
        # height = self.winfo_reqheight() # Height not needed for this centering
        screen_width = self.winfo_screenwidth()
        # screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = 10 # Position near top-center
        self.geometry(f'+{x}+{y}')

    def on_press(self, event):
        """Start dragging."""
        self._offset_x = event.x
        self._offset_y = event.y
        # self.focus_force() # Bring to front when clicked (might not be needed with topmost)

    def on_drag(self, event):
        """Move window during drag."""
        new_x = self.winfo_x() + event.x - self._offset_x
        new_y = self.winfo_y() + event.y - self._offset_y
        self.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
         """Save the window position when dragging stops."""
         x = self.winfo_x()
         y = self.winfo_y()
         set_setting("floating_controls_pos", f"{x},{y}")
         print(f"Floating controls position saved: {x},{y}")

    def copy_last_translation(self):
        """Copies the last successful translation to the clipboard."""
        last_result = getattr(self.app.translation_tab, 'last_translation_result', None)
        if last_result and isinstance(last_result, dict):
            # Format: Combine translations from different ROIs in app's ROI order
            copy_text = ""
            for roi in self.app.rois: # Iterate in ROI order
                roi_name = roi.name
                if roi_name in last_result:
                     translation = last_result[roi_name]
                     if translation and translation != "[Translation Missing]":
                          if copy_text: copy_text += "\n\n" # Separator between ROIs
                          # Optionally include ROI name?
                          # copy_text += f"[{roi_name}]\n{translation}"
                          copy_text += translation # Just the translated text

            if copy_text:
                try:
                    pyperclip.copy(copy_text)
                    print("Last translation copied to clipboard.")
                    self.app.update_status("Translation copied.") # Update main status
                except pyperclip.PyperclipException as e:
                     print(f"Pyperclip Error: Could not copy to clipboard. Is it installed and configured? Error: {e}")
                     self.app.update_status("Error: Could not copy (Pyperclip).")
                     messagebox.showerror("Clipboard Error", f"Could not copy text to clipboard.\nPyperclip error: {e}", parent=self)
                except Exception as e:
                    print(f"Error copying to clipboard: {e}")
                    self.app.update_status("Error copying translation.")
            else:
                 print("No text found in last translation result.")
                 self.app.update_status("No translation to copy.")
        else:
            print("No previous translation available to copy.")
            self.app.update_status("No translation to copy.")

    def toggle_auto_translate(self):
        """Toggles the auto-translate feature via the main app's setting."""
        # The Checkbutton variable (self.auto_var) changes automatically.
        # This command should now call the main app's toggle function.
        is_enabled_after_toggle = self.auto_var.get()
        print(f"Floating controls toggling auto-translate to: {is_enabled_after_toggle}")

        # Find the Checkbutton in the translation tab and invoke its command
        try:
             main_checkbutton = self.app.translation_tab.auto_translate_check
             # Set the main variable first to ensure invoke() sees the correct state
             self.app.translation_tab.auto_translate_var.set(is_enabled_after_toggle)
             # Call the command associated with the main checkbutton
             main_checkbutton.invoke()
        except Exception as e:
             print(f"Error invoking main auto-translate toggle: {e}")
             # Revert local state if invocation failed?
             self.auto_var.set(not is_enabled_after_toggle)


    def toggle_overlays(self):
        """Toggles the global overlay visibility via the OverlayManager."""
        # Variable changes automatically via Checkbutton binding
        new_state = self.overlay_var.get()
        print(f"Floating controls toggling global overlays to: {new_state}")
        self.app.overlay_manager.set_global_overlays_enabled(new_state)
        # Status update handled by set_global_overlays_enabled


    def update_button_states(self):
         """Syncs button check states with the application state (e.g., on show)."""
         if self.app.translation_tab:
              self.auto_var.set(self.app.translation_tab.is_auto_translate_enabled())
         if self.app.overlay_manager:
              self.overlay_var.set(self.app.overlay_manager.global_overlays_enabled)


    def add_tooltip(self, widget, text):
        """Simple tooltip implementation."""
        tooltip = Tooltip(widget, text)
        #widget.bind("<Enter>", lambda event, t=tooltip: t.showtip())
        #widget.bind("<Leave>", lambda event, t=tooltip: t.hidetip())


# Simple Tooltip class (optional, basic version)
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.enter_id = None
        self.leave_id = None

        self.widget.bind("<Enter>", self.schedule_show, add='+')
        self.widget.bind("<Leave>", self.schedule_hide, add='+')
        self.widget.bind("<ButtonPress>", self.force_hide, add='+') # Hide on click

    def schedule_show(self, event=None):
        self.unschedule()
        self.enter_id = self.widget.after(500, self.showtip) # Delay showing tip

    def schedule_hide(self, event=None):
        self.unschedule()
        self.leave_id = self.widget.after(100, self.hidetip) # Slight delay hiding

    def unschedule(self):
        enter_id = self.enter_id
        self.enter_id = None
        if enter_id:
            self.widget.after_cancel(enter_id)

        leave_id = self.leave_id
        self.leave_id = None
        if leave_id:
            self.widget.after_cancel(leave_id)

    def showtip(self):
        self.unschedule() # Ensure hide isn't scheduled
        if self.tipwindow or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert") # Get position relative to widget
        # Calculate position relative to screen
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + self.widget.winfo_height() + 5 # Below widget
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"), wraplength=200) # Wrap long tooltips
        label.pack(ipadx=2, ipady=1)
        # Schedule auto-hide after some time?
        # self.leave_id = self.widget.after(5000, self.hidetip)


    def hidetip(self):
        self.unschedule()
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            try:
                tw.destroy()
            except tk.TclError:
                pass # Window might already be destroyed

    def force_hide(self, event=None):
        self.hidetip() # Hide immediately on click

```

--- END OF FILE ui/floating_controls.py ---

--- START OF FILE ui/overlay_tab.py ---

```python
import tkinter as tk
from tkinter import ttk, colorchooser
from ui.base import BaseTab
from utils.settings import get_setting, update_settings # update_settings for saving
import tkinter.font as tkFont

class OverlayTab(BaseTab):
    """Tab for configuring translation overlays."""

    # Define default values here consistent with OverlayManager
    # Import defaults from the manager to ensure consistency
    try:
         # Try importing defaults - handle potential circularity if manager imports this tab
         from ui.overlay_manager import OverlayManager
         DEFAULT_CONFIG = OverlayManager.DEFAULT_OVERLAY_CONFIG
    except ImportError:
         # Fallback defaults if import fails
         print("Warning: Could not import OverlayManager defaults. Using fallback in OverlayTab.")
         DEFAULT_CONFIG = {
             "enabled": True, "font_family": "Segoe UI", "font_size": 14,
             "font_color": "white", "bg_color": "#222222", "alpha": 0.85,
             "position": "bottom_roi", "wraplength": 450, "justify": "left"
         }


    POSITION_OPTIONS = [
        "bottom_roi", "top_roi", "center_roi",
        "bottom_game", "top_game", "center_game"
        # Add more if needed, e.g., fixed coordinates, corners
    ]

    JUSTIFY_OPTIONS = ["left", "center", "right"]

    def setup_ui(self):
        # --- Main Frame ---
        main_frame = ttk.Frame(self.frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Global Enable ---
        global_frame = ttk.Frame(main_frame)
        global_frame.pack(fill=tk.X, pady=(0, 10))

        # Check if overlay_manager exists before accessing its state
        initial_global_state = True # Default if manager not ready
        if hasattr(self.app, 'overlay_manager'):
             initial_global_state = self.app.overlay_manager.global_overlays_enabled

        self.global_enable_var = tk.BooleanVar(value=initial_global_state)
        global_check = ttk.Checkbutton(global_frame, text="Enable Translation Overlays Globally",
                                       variable=self.global_enable_var, command=self.toggle_global_overlays)
        global_check.pack(side=tk.LEFT)

        # --- ROI Selection ---
        roi_select_frame = ttk.Frame(main_frame)
        roi_select_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(roi_select_frame, text="Configure Overlay for ROI:").pack(side=tk.LEFT, padx=(0, 5))

        self.roi_names = [roi.name for roi in self.app.rois] # Get initial list
        self.selected_roi_var = tk.StringVar()
        self.roi_combo = ttk.Combobox(roi_select_frame, textvariable=self.selected_roi_var,
                                       values=self.roi_names, state="readonly", width=25) # Wider
        if self.roi_names:
            self.roi_combo.current(0)
        self.roi_combo.pack(side=tk.LEFT, fill=tk.X, expand=True) # Expand combobox
        self.roi_combo.bind("<<ComboboxSelected>>", self.load_roi_config)

        # --- Configuration Area (populated based on selection) ---
        self.config_frame = ttk.LabelFrame(main_frame, text="Overlay Settings", padding=10)
        self.config_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create the widgets holder
        self.widgets = {}
        # Build the widgets initially (they will be empty/disabled until ROI selected)
        self.build_config_widgets()

        # Load initial config for the first ROI (if any) after UI is fully built
        self.app.master.after_idle(self.load_initial_config)


    def build_config_widgets(self):
        """Creates the widgets for overlay configuration within self.config_frame."""
        frame = self.config_frame
        # Clear previous widgets if any (important if rebuilding)
        for widget in frame.winfo_children():
            widget.destroy()

        # --- Widgets Dictionary ---
        self.widgets = {} # Reset dictionary

        # Grid configuration
        frame.columnconfigure(1, weight=1) # Allow entry/combo fields to expand

        # Row counter
        row_num = 0

        # Enabled Checkbox
        self.widgets['enabled_var'] = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Enabled for this ROI", variable=self.widgets['enabled_var']).grid(row=row_num, column=0, columnspan=3, sticky=tk.W, pady=5)
        row_num += 1

        # Font Family
        ttk.Label(frame, text="Font Family:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        # List available fonts (can be slow, consider limiting or using entry with validation)
        try:
            # Filter out fonts starting with '@' (often vertical variants not useful here)
            available_fonts = sorted([f for f in tkFont.families() if not f.startswith('@')])
        except Exception as e:
             print(f"Error getting system fonts: {e}. Using fallback list.")
             available_fonts = ["Arial", "Segoe UI", "Times New Roman", "Courier New", "Verdana", "Tahoma", "MS Gothic"] # Common fonts
        self.widgets['font_family_var'] = tk.StringVar()
        # Use Combobox but allow typing for unlisted fonts
        self.widgets['font_family_combo'] = ttk.Combobox(frame, textvariable=self.widgets['font_family_var'], values=available_fonts, width=25)
        self.widgets['font_family_combo'].grid(row=row_num, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        row_num += 1

        # Font Size
        ttk.Label(frame, text="Font Size:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['font_size_var'] = tk.IntVar(value=self.DEFAULT_CONFIG['font_size'])
        # Use Spinbox for easy increment/decrement
        ttk.Spinbox(frame, from_=8, to=72, increment=1, width=5, textvariable=self.widgets['font_size_var']).grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1

        # Font Color
        ttk.Label(frame, text="Font Color:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['font_color_var'] = tk.StringVar(value=self.DEFAULT_CONFIG['font_color'])
        # Entry field for hex color
        font_color_entry = ttk.Entry(frame, textvariable=self.widgets['font_color_var'], width=10)
        font_color_entry.grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        font_color_entry.bind("<FocusOut>", lambda e, key='font_color': self.update_color_preview(key))
        font_color_entry.bind("<Return>", lambda e, key='font_color': self.update_color_preview(key))
        # Color picker button
        self.widgets['font_color_btn'] = ttk.Button(frame, text="🎨", width=3,
                     command=lambda: self.choose_color('font_color', 'Font Color'))
        self.widgets['font_color_btn'].grid(row=row_num, column=2, sticky=tk.W, padx=(0, 5), pady=2)
        # Color preview label
        self.widgets['font_color_preview'] = tk.Label(frame, text="   ", relief=tk.SUNKEN, width=3, borderwidth=1)
        self.widgets['font_color_preview'].grid(row=row_num, column=3, sticky=tk.W, padx=2)
        self.update_color_preview('font_color') # Set initial preview
        row_num += 1

        # Background Color
        ttk.Label(frame, text="Background Color:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['bg_color_var'] = tk.StringVar(value=self.DEFAULT_CONFIG['bg_color'])
        # Entry field
        bg_color_entry = ttk.Entry(frame, textvariable=self.widgets['bg_color_var'], width=10)
        bg_color_entry.grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        bg_color_entry.bind("<FocusOut>", lambda e, key='bg_color': self.update_color_preview(key))
        bg_color_entry.bind("<Return>", lambda e, key='bg_color': self.update_color_preview(key))
        # Color picker button
        self.widgets['bg_color_btn'] = ttk.Button(frame, text="🎨", width=3,
                     command=lambda: self.choose_color('bg_color', 'Background Color'))
        self.widgets['bg_color_btn'].grid(row=row_num, column=2, sticky=tk.W, padx=(0, 5), pady=2)
        # Color preview label
        self.widgets['bg_color_preview'] = tk.Label(frame, text="   ", relief=tk.SUNKEN, width=3, borderwidth=1)
        self.widgets['bg_color_preview'].grid(row=row_num, column=3, sticky=tk.W, padx=2)
        self.update_color_preview('bg_color') # Set initial preview
        row_num += 1

        # Position
        ttk.Label(frame, text="Position:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['position_var'] = tk.StringVar()
        self.widgets['position_combo'] = ttk.Combobox(frame, textvariable=self.widgets['position_var'], values=self.POSITION_OPTIONS, state="readonly", width=25)
        self.widgets['position_combo'].grid(row=row_num, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        row_num += 1

        # Justify
        ttk.Label(frame, text="Alignment:").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['justify_var'] = tk.StringVar()
        self.widgets['justify_combo'] = ttk.Combobox(frame, textvariable=self.widgets['justify_var'], values=self.JUSTIFY_OPTIONS, state="readonly", width=10)
        self.widgets['justify_combo'].grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1


        # Wraplength
        ttk.Label(frame, text="Wrap Width (px):").grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
        self.widgets['wraplength_var'] = tk.IntVar(value=self.DEFAULT_CONFIG['wraplength'])
        ttk.Spinbox(frame, from_=100, to=2000, increment=25, width=7, textvariable=self.widgets['wraplength_var']).grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
        row_num += 1


        # --- Save Button ---
        # Place save button outside the grid loop
        save_button = ttk.Button(frame, text="Apply and Save Settings for this ROI", command=self.save_roi_config)
        save_button.grid(row=row_num, column=0, columnspan=4, pady=15) # Span all columns


    def update_color_preview(self, config_key):
         """Updates the color preview label based on the entry/variable."""
         var = self.widgets.get(f"{config_key}_var")
         preview = self.widgets.get(f"{config_key}_preview")
         if var and preview:
              color = var.get()
              try:
                   preview.config(background=color)
              except tk.TclError:
                   preview.config(background=self.DEFAULT_CONFIG[config_key]) # Fallback on invalid color

    def choose_color(self, config_key, title):
        """Opens a color chooser dialog and updates the variable and preview."""
        var = self.widgets.get(f"{config_key}_var")
        preview = self.widgets.get(f"{config_key}_preview")
        if not var or not preview: return

        # Askcolor returns tuple ((r,g,b), hex) or (None, None)
        # Use the current color in the variable as the initial color
        initial_color = var.get()
        try:
            color_code = colorchooser.askcolor(title=title, initialcolor=initial_color, parent=self.frame)
        except tk.TclError: # Handle invalid initial color potentially
             color_code = colorchooser.askcolor(title=title, parent=self.frame)


        if color_code and color_code[1]: # Check if a color was selected (hex part)
            hex_color = color_code[1]
            var.set(hex_color)
            try:
                 preview.config(background=hex_color)
            except tk.TclError:
                 print(f"Error setting preview for chosen color: {hex_color}")


    def load_roi_config(self, event=None):
        """Loads the configuration for the currently selected ROI into the UI."""
        roi_name = self.selected_roi_var.get()
        if not roi_name:
            self.set_widgets_state(tk.DISABLED)
            self.config_frame.config(text="Overlay Settings (No ROI Selected)")
            return

        # Ensure overlay manager exists
        if not hasattr(self.app, 'overlay_manager'):
             print("Error: Overlay Manager not initialized yet.")
             self.set_widgets_state(tk.DISABLED)
             return

        # Get the merged config (defaults + specific) for this ROI
        config = self.app.overlay_manager._get_roi_config(roi_name)
        self.config_frame.config(text=f"Overlay Settings for [{roi_name}]")

        # Update UI widgets, using defaults from DEFAULT_CONFIG as fallback
        self.widgets['enabled_var'].set(config.get('enabled', self.DEFAULT_CONFIG['enabled']))
        self.widgets['font_family_var'].set(config.get('font_family', self.DEFAULT_CONFIG['font_family']))
        self.widgets['font_size_var'].set(config.get('font_size', self.DEFAULT_CONFIG['font_size']))
        self.widgets['font_color_var'].set(config.get('font_color', self.DEFAULT_CONFIG['font_color']))
        self.widgets['bg_color_var'].set(config.get('bg_color', self.DEFAULT_CONFIG['bg_color']))
        self.widgets['position_var'].set(config.get('position', self.DEFAULT_CONFIG['position']))
        self.widgets['justify_var'].set(config.get('justify', self.DEFAULT_CONFIG['justify']))
        self.widgets['wraplength_var'].set(config.get('wraplength', self.DEFAULT_CONFIG['wraplength']))

        # Update color previews
        self.update_color_preview('font_color')
        self.update_color_preview('bg_color')

        # Enable widgets only if global overlays are enabled
        global_state = self.global_enable_var.get()
        self.set_widgets_state(tk.NORMAL if global_state else tk.DISABLED)


    def save_roi_config(self):
        """Saves the current UI configuration for the selected ROI."""
        roi_name = self.selected_roi_var.get()
        if not roi_name:
            messagebox.showwarning("Warning", "No ROI selected to save configuration for.", parent=self.app.master)
            return

        # Read values from widgets
        new_config = {}
        try:
            new_config = {
                'enabled': self.widgets['enabled_var'].get(),
                'font_family': self.widgets['font_family_var'].get(),
                'font_size': self.widgets['font_size_var'].get(),
                'font_color': self.widgets['font_color_var'].get(),
                'bg_color': self.widgets['bg_color_var'].get(),
                'position': self.widgets['position_var'].get(),
                'justify': self.widgets['justify_var'].get(),
                'wraplength': self.widgets['wraplength_var'].get(),
                # Add alpha later if needed
            }
        except tk.TclError as e:
             messagebox.showerror("Error Reading Value", f"Could not read setting value: {e}", parent=self.app.master)
             return
        except Exception as e:
             messagebox.showerror("Error Reading Value", f"Unexpected error reading settings: {e}", parent=self.app.master)
             return


        # Validate values
        if not 8 <= new_config['font_size'] <= 72:
            messagebox.showerror("Error", "Font size must be between 8 and 72.", parent=self.app.master)
            return
        if not 100 <= new_config['wraplength'] <= 5000:
             messagebox.showerror("Error", "Wrap width must be between 100 and 5000.", parent=self.app.master)
             return
        # Validate colors (basic hex check)
        color_pattern = r'^#(?:[0-9a-fA-F]{3}){1,2}$'
        if not re.match(color_pattern, new_config['font_color']):
            messagebox.showerror("Error", f"Invalid Font Color format: '{new_config['font_color']}'. Use #RRGGBB or #RGB.", parent=self.app.master)
            return
        if not re.match(color_pattern, new_config['bg_color']):
             messagebox.showerror("Error", f"Invalid Background Color format: '{new_config['bg_color']}'. Use #RRGGBB or #RGB.", parent=self.app.master)
             return

        # Update via OverlayManager (which handles saving to settings and applying live)
        if hasattr(self.app, 'overlay_manager'):
             self.app.overlay_manager.update_overlay_config(roi_name, new_config)
             self.app.update_status(f"Overlay settings saved for {roi_name}.")
             # Update ROI list display indicator
             self.app.roi_tab.update_roi_list()
        else:
             messagebox.showerror("Error", "Overlay Manager not available. Cannot save settings.", parent=self.app.master)


    def toggle_global_overlays(self):
        """Callback for the global enable checkbox."""
        enabled = self.global_enable_var.get()
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.set_global_overlays_enabled(enabled)
            # Status update handled by manager
            # Enable/disable the ROI specific config area based on this
            self.set_widgets_state(tk.NORMAL if enabled else tk.DISABLED)
            if enabled and self.selected_roi_var.get():
                # If re-enabling, ensure the specific ROI config is loaded correctly
                self.load_roi_config()
        else:
             print("Error: Overlay Manager not available.")
             self.global_enable_var.set(not enabled) # Revert checkbox


    def update_roi_list(self):
        """Called by the main app (e.g., from roi_tab) when the ROI list changes."""
        self.roi_names = [roi.name for roi in self.app.rois]
        current_selection = self.selected_roi_var.get()

        self.roi_combo['values'] = self.roi_names

        if current_selection in self.roi_names:
            # Keep current selection if still valid
            self.roi_combo.set(current_selection)
            self.load_roi_config() # Reload config in case something changed implicitly
        elif self.roi_names:
            # Select first ROI if previous selection gone or no previous selection
            self.roi_combo.current(0)
            self.load_roi_config() # Load config for the new first item
        else:
            # No ROIs left
            self.roi_combo.set("")
            self.selected_roi_var.set("")
            self.set_widgets_state(tk.DISABLED) # Disable config if no ROIs
            self.config_frame.config(text="Overlay Settings (No ROIs Defined)")


    def load_initial_config(self):
        """Load config for the initially selected ROI after UI is built."""
        # Make sure ROI list is up-to-date first
        self.update_roi_list()
        # Now load config based on the (potentially updated) selection
        if self.selected_roi_var.get():
             self.load_roi_config()
        else:
             self.set_widgets_state(tk.DISABLED)
             self.config_frame.config(text="Overlay Settings (No ROIs Defined)")

    def set_widgets_state(self, state):
         """Enable or disable all configuration widgets in the config_frame."""
         # Check if config_frame exists and has children
         if not hasattr(self, 'config_frame') or not self.config_frame.winfo_exists():
             return

         valid_states = (tk.NORMAL, tk.DISABLED, tk.ACTIVE, tk.READONLY) # READONLY for comboboxes maybe?
         actual_state = state if state in valid_states else tk.DISABLED

         for widget in self.config_frame.winfo_children():
              # Check widget type and apply state appropriately
              widget_type = widget.winfo_class()
              try:
                  if widget_type in ('TButton', 'TSpinbox', 'TCheckbutton', 'TEntry'):
                       widget.configure(state=actual_state)
                  elif widget_type == 'TCombobox':
                       # Combobox uses 'readonly' or 'disabled'
                       combo_state = tk.DISABLED if actual_state == tk.DISABLED else 'readonly'
                       widget.configure(state=combo_state)
                  elif widget_type == 'Text':
                       widget.configure(state=actual_state)
                  # Labels generally don't have a disabled state visually unless manually changed
                  # elif widget_type == 'TLabel' or widget_type == 'Label':
                  #      widget.configure(foreground='gray' if actual_state == tk.DISABLED else 'black')
              except tk.TclError:
                  # Ignore errors for widgets that don't support state (like internal frames/labels)
                  pass
         # Special handling for color picker buttons if needed (already covered by TButton generally)
         # font_color_btn = self.widgets.get('font_color_btn')
         # if font_color_btn: font_color_btn.configure(state=actual_state)
         # bg_color_btn = self.widgets.get('bg_color_btn')
         # if bg_color_btn: bg_color_btn.configure(state=actual_state)

# Need this regex for color validation
import re
```

--- END OF FILE ui/overlay_tab.py ---

--- START OF FILE app.py ---

```python
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
import win32gui
from paddleocr import PaddleOCR, paddleocr # Import base exception class if needed
import platform # For platform-specific code if needed

# Import utilities
from utils.capture import get_window_title, capture_window
from utils.config import load_rois # Keep using config.load_rois
from utils.settings import load_settings, save_settings, get_setting, set_setting, update_settings
from utils.roi import ROI

# Import UI components
from ui.capture_tab import CaptureTab
from ui.roi_tab import ROITab
from ui.text_tab import TextTab, StableTextTab
from ui.translation_tab import TranslationTab
from ui.overlay_tab import OverlayTab # Import new tab
from ui.overlay_manager import OverlayManager # Import manager
from ui.floating_controls import FloatingControls # Import floating controls

# Constants
FPS = 10 # Target FPS for capture loop
FRAME_DELAY = 1.0 / FPS
OCR_ENGINE_LOCK = threading.Lock() # Lock for OCR engine access/reinitialization

class VisualNovelTranslatorApp:
    """Main application class for the Visual Novel Translator."""

    def __init__(self, master):
        self.master = master
        self.settings = load_settings() # Load settings early
        self.config_file = self.settings.get("last_roi_config") # Load last used path
        # Use default only if last_roi_config was None or empty in settings
        if not self.config_file:
            self.config_file = "vn_translator_config.json"


        # Update title based on loaded config
        window_title = "Visual Novel Translator"
        # Show filename in title only if it exists and is not the default name maybe?
        if self.config_file and os.path.exists(self.config_file): # and os.path.basename(self.config_file) != "vn_translator_config.json":
             window_title += f" - {os.path.basename(self.config_file)}"
        master.title(window_title)
        master.geometry("1200x800")
        master.minsize(1000, 700)
        master.protocol("WM_DELETE_WINDOW", self.on_close) # Handle closing


        # --- Initialize variables ---
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = []
        self.current_frame = None      # Raw captured frame (BGR numpy array)
        self.display_frame_tk = None # PhotoImage for canvas (keep reference)
        self.snapshot_frame = None     # Snapshot frame (BGR numpy array)
        self.using_snapshot = False
        self.roi_start_coords = None # Store (x,y) tuple during ROI drag
        self.roi_draw_rect_id = None # Canvas item ID for drawing ROI rect
        self.scale_x, self.scale_y = 1.0, 1.0 # Scaling of preview image relative to original
        self.frame_display_coords = {'x': 0, 'y': 0, 'w': 0, 'h': 0} # Image position/size on canvas

        self.text_history = {} # roi_name: {"text": str, "count": int}
        self.stable_texts = {} # roi_name: stable_text_str
        # Load settings for stability etc.
        self.stable_threshold = get_setting("stable_threshold", 3)
        self.max_display_width = get_setting("max_display_width", 800)
        self.max_display_height = get_setting("max_display_height", 600)
        self.last_status_message = ""

        self.ocr = None # Initialize later in a thread-safe way
        self.ocr_lang = get_setting("ocr_language", "jpn") # Load last used lang

        # --- Setup UI ---
        self._setup_ui() # Creates tabs and layout

        # --- Initialize Managers ---
        # Needs to happen after master is fully initialized but before loading things that need it
        self.overlay_manager = OverlayManager(self.master, self)
        self.floating_controls = None # Created later

        # --- Load initial config (ROIs) ---
        # Must happen after UI tabs are created (roi_tab) and overlay_manager exists
        self._load_initial_rois()

        # --- Initialize OCR Engine ---
        # Do this in a non-blocking way
        # Needs capture_tab to exist to get initial language if setting missing
        initial_ocr_lang = self.ocr_lang
        if hasattr(self, 'capture_tab') and not initial_ocr_lang:
             initial_ocr_lang = self.capture_tab.lang_var.get() or "jpn"
        self.update_ocr_engine(initial_ocr_lang, initial_load=True)

        # --- Show Floating Controls ---
        # Can be called after main loop starts if preferred
        self.show_floating_controls()


    def _setup_ui(self):
        """Set up the main UI layout and tabs."""
        # Main PanedWindow for resizable layout
        self.paned_window = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Left frame for preview ---
        self.left_frame = ttk.Frame(self.paned_window, padding=0) # No padding on frame itself
        self.paned_window.add(self.left_frame, weight=3) # Give more weight initially

        # Canvas fills the left frame
        self.canvas = tk.Canvas(self.left_frame, bg="gray15", highlightthickness=0) # Darker background
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Bind mouse events for ROI definition
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        # Bind resize event to redraw frame
        self.canvas.bind("<Configure>", self.on_canvas_resize)


        # --- Right frame for controls ---
        self.right_frame = ttk.Frame(self.paned_window, padding=(5, 0, 0, 0)) # Pad left side only
        self.paned_window.add(self.right_frame, weight=1) # Less weight initially

        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs (order can matter for dependencies during init)
        self.capture_tab = CaptureTab(self.notebook, self)
        self.notebook.add(self.capture_tab.frame, text="Capture")

        self.roi_tab = ROITab(self.notebook, self)
        self.notebook.add(self.roi_tab.frame, text="ROIs")

        # Add Overlay Tab after ROI Tab
        self.overlay_tab = OverlayTab(self.notebook, self)
        self.notebook.add(self.overlay_tab.frame, text="Overlays")

        self.text_tab = TextTab(self.notebook, self)
        self.notebook.add(self.text_tab.frame, text="Live Text") # Renamed

        self.stable_text_tab = StableTextTab(self.notebook, self)
        self.notebook.add(self.stable_text_tab.frame, text="Stable Text") # Renamed

        self.translation_tab = TranslationTab(self.notebook, self)
        self.notebook.add(self.translation_tab.frame, text="Translation")

        # Add a status bar at the bottom
        self.status_bar_frame = ttk.Frame(self.master, relief=tk.SUNKEN)
        self.status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar = ttk.Label(self.status_bar_frame, text="Status: Initializing...", anchor=tk.W, padding=(5, 2))
        self.status_bar.pack(fill=tk.X)
        self.update_status("Ready.") # Initial status


    def update_status(self, message):
        """Update the status bar message, preventing rapid duplicate messages."""
        # Use `after_idle` to ensure this runs in the main thread
        def _do_update():
            if message != self.last_status_message:
                 self.status_bar.config(text=f"Status: {message}")
                 self.last_status_message = message
                 # Update CaptureTab's status label too for consistency, if it exists
                 if hasattr(self, 'capture_tab') and self.capture_tab.winfo_exists():
                     self.capture_tab.status_label.config(text=f"Status: {message}")

        # Schedule the update if the widget exists
        if hasattr(self, 'status_bar') and self.status_bar.winfo_exists():
            self.master.after_idle(_do_update)
        else: # Fallback if called before UI fully ready
            print(f"STATUS (early): {message}")
            self.last_status_message = message


    def _load_initial_rois(self):
        """Load ROIs from the last used config file on startup."""
        if self.config_file and os.path.exists(self.config_file):
            self.update_status(f"Loading ROIs from {os.path.basename(self.config_file)}...")
            try:
                # Use the load_rois function from config.py
                rois, loaded_path = load_rois(initial_path=self.config_file)

                if loaded_path and rois is not None: # Check success (path returned, rois not None)
                    self.rois = rois
                    self.config_file = loaded_path # Ensure config_file is updated
                    # Update UI elements that depend on ROIs
                    if hasattr(self, 'roi_tab'): self.roi_tab.update_roi_list()
                    if hasattr(self, 'overlay_manager'): self.overlay_manager.rebuild_overlays()

                    self.update_status(f"Loaded {len(rois)} ROIs from {os.path.basename(loaded_path)}")
                    self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
                elif rois is None: # Explicit failure indication (e.g., file corrupted after selection)
                     self.update_status(f"Error loading ROIs from {os.path.basename(self.config_file)}. See console.")
                # else: # User cancelled load dialog (rois=[], loaded_path=None)
                     # Status update handled within load_rois/dialogs. Keep previous state.

            except Exception as e:
                self.update_status(f"Error loading initial ROIs: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            self.update_status("No previous ROI config found or file missing. Define new ROIs or load a file.")


    def update_ocr_engine(self, lang_code, initial_load=False):
        """Initialize or update the PaddleOCR engine in a separate thread."""
        def init_engine():
            global OCR_ENGINE_LOCK
            lang_map = {"jpn": "japan", "jpn_vert": "japan", "eng": "en", "chi_sim": "ch", "chi_tra": "ch", "kor": "ko"}
            # Add more mappings as needed based on PaddleOCR supported languages
            ocr_lang_paddle = lang_map.get(lang_code, "en") # Default to English if code unknown

            # Prevent unnecessary re-initialization if lang didn't actually change
            with OCR_ENGINE_LOCK:
                 if self.ocr and hasattr(self.ocr, 'lang') and self.ocr.lang == ocr_lang_paddle:
                      print(f"OCR engine already initialized with the correct language ({lang_code}).")
                      self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))
                      return

            # If language changed or no engine yet, proceed with initialization
            print(f"Attempting to initialize OCR engine for language: {lang_code} (Paddle code: {ocr_lang_paddle})...")
            # Update status immediately if possible
            self.master.after_idle(lambda: self.update_status(f"Initializing OCR ({lang_code})..."))

            try:
                # This can take time, especially first download
                new_ocr_engine = PaddleOCR(use_angle_cls=True, lang=ocr_lang_paddle, show_log=False)
                print(f"PaddleOCR initialized successfully for {ocr_lang_paddle}.")

                # --- Critical Section: Update self.ocr ---
                with OCR_ENGINE_LOCK:
                    self.ocr = new_ocr_engine
                    self.ocr_lang = lang_code # Store the app's lang code ('jpn', 'eng', etc.)
                # --- End Critical Section ---

                print(f"OCR engine ready for {lang_code}.")
                # Update status in main thread
                self.master.after_idle(lambda: self.update_status(f"OCR Ready ({lang_code})."))

            except paddleocr.PaddleocrError as pe: # Catch specific Paddle errors if possible
                 print(f"!!! PaddleOCR specific error initializing for lang {lang_code}: {pe}")
                 self.master.after_idle(lambda: self.update_status(f"OCR Error ({lang_code}): {pe}"))
                 with OCR_ENGINE_LOCK: self.ocr = None
            except Exception as e:
                print(f"!!! General error initializing PaddleOCR for lang {lang_code}: {e}")
                import traceback
                traceback.print_exc()
                # Update status in main thread
                self.master.after_idle(lambda: self.update_status(f"OCR Error ({lang_code}): Check console"))
                # Fallback: Disable OCR features?
                with OCR_ENGINE_LOCK:
                    self.ocr = None

        # Run in a separate thread to avoid blocking UI
        threading.Thread(target=init_engine, daemon=True).start()


    def start_capture(self):
        """Start capturing from the selected window."""
        if self.capturing:
             self.update_status("Capture already running.")
             return

        if not self.selected_hwnd:
            messagebox.showwarning("Warning", "No visual novel window selected.", parent=self.master)
            return

        # Check window validity *before* starting thread
        if not win32gui.IsWindow(self.selected_hwnd):
            messagebox.showerror("Error", "Selected window no longer exists. Refresh the list.", parent=self.master)
            if hasattr(self, 'capture_tab'): self.capture_tab.refresh_window_list() # Attempt to refresh
            return

        # Check if OCR is ready (non-blocking check)
        with OCR_ENGINE_LOCK:
            ocr_ready = bool(self.ocr)

        if not ocr_ready:
             # Maybe initiate OCR loading if not already attempting?
             # current_lang = self.capture_tab.lang_var.get() or "jpn"
             # self.update_ocr_engine(current_lang) # Re-trigger loading
             messagebox.showinfo("OCR Not Ready", "The OCR engine is still initializing. Capture will start, but text extraction may be delayed or fail until OCR is ready.", parent=self.master)
             # Proceed with capture anyway? Or prevent start? Let's proceed.


        if self.using_snapshot:
            self.return_to_live() # Ensure we are in live mode

        self.capturing = True
        # Reset text history/stable text when starting new capture session? Optional.
        # self.text_history = {}
        # self.stable_texts = {}

        self.capture_thread = threading.Thread(target=self.capture_process, daemon=True)
        self.capture_thread.start()

        # Update UI immediately
        if hasattr(self, 'capture_tab'): self.capture_tab.on_capture_started()
        title = get_window_title(self.selected_hwnd) or f"HWND {self.selected_hwnd}"
        self.update_status(f"Capturing: {title}")
        if hasattr(self, 'overlay_manager'): self.overlay_manager.rebuild_overlays() # Ensure overlays match current ROIs

    def stop_capture(self):
        """Stop the current capture process gracefully."""
        if not self.capturing:
             self.update_status("Capture is not running.")
             return

        print("Stop capture requested...")
        self.capturing = False # Signal the thread to stop

        # Don't join here, let the main loop continue.
        # The thread will exit, and _finalize_stop_capture will be called via `after`.
        # Use `after` to periodically check if the thread has finished.
        self.master.after(100, self._check_thread_and_finalize_stop)


    def _check_thread_and_finalize_stop(self):
         """Checks if capture thread finished, calls finalize or re-schedules check."""
         if self.capture_thread and self.capture_thread.is_alive():
              print("Waiting for capture thread to finish...")
              self.master.after(100, self._check_thread_and_finalize_stop) # Check again
         else:
              print("Capture thread finished.")
              self.capture_thread = None # Clear thread reference
              self._finalize_stop_capture() # Perform final UI updates


    def _finalize_stop_capture(self):
        """Actions to perform in the main thread after capture stops."""
        # Ensure this runs only once even if called multiple times
        if self.capturing: # Should be false now, but double check state
             print("Warning: _finalize_stop_capture called while capturing flag still true.")
             return # Avoid finalizing if somehow stop was cancelled

        print("Finalizing stop capture UI updates...")
        if hasattr(self, 'capture_tab') and self.capture_tab.winfo_exists():
             self.capture_tab.on_capture_stopped()
        # Clear potentially stale data? Optional.
        # self.current_frame = None
        # self._display_frame(None) # Clear canvas?
        if hasattr(self, 'overlay_manager'):
            self.overlay_manager.hide_all_overlays() # Hide overlays when capture stops
        self.update_status("Capture stopped.")


    def take_snapshot(self):
        """Take a snapshot of the current frame for static analysis (ROI definition)."""
        if not self.capturing and not self.current_frame: # Allow snapshot even if capture just stopped but frame exists
             messagebox.showwarning("Warning", "Capture is not running and no frame available. Cannot take snapshot.", parent=self.master)
             return
        if self.current_frame is None:
            messagebox.showwarning("Warning", "No frame captured yet to take snapshot.", parent=self.master)
            return

        print("Taking snapshot...")
        self.snapshot_frame = self.current_frame.copy() # Ensure it's a copy
        self.using_snapshot = True
        self._display_frame(self.snapshot_frame) # Display the static frame

        if hasattr(self, 'capture_tab'): self.capture_tab.on_snapshot_taken()
        self.update_status("Snapshot taken. Define ROIs or return to live.")


    def return_to_live(self):
        """Return to live view from snapshot mode."""
        if not self.using_snapshot:
             return

        print("Returning to live view...")
        self.using_snapshot = False
        self.snapshot_frame = None
        # If capture is running, the capture loop will provide the next frame.
        # If capture stopped, display black/placeholder?
        # Let's display the *last known* live frame immediately if available.
        if self.current_frame is not None:
             self._display_frame(self.current_frame)
        else:
             self._display_frame(None) # Or a placeholder image?

        if hasattr(self, 'capture_tab'): self.capture_tab.on_live_view_resumed()
        self.update_status("Returned to live view." if self.capturing else "Returned to stopped state.")


    def toggle_roi_selection(self):
        """Enable or disable ROI selection mode."""
        # --- If activating ROI selection ---
        if not self.roi_selection_active:
            # Must have an image (live or snapshot) to draw on
            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                messagebox.showwarning("Warning", "Start capture or take a snapshot before defining ROIs.", parent=self.master)
                return

            # If live capturing, automatically take snapshot
            if self.capturing and not self.using_snapshot:
                print("Taking snapshot automatically for ROI definition.")
                self.take_snapshot()
                # Check if snapshot succeeded before activating ROI mode
                if not self.using_snapshot:
                     print("Snapshot failed, cannot activate ROI selection.")
                     return

            # Now activate ROI selection mode
            self.roi_selection_active = True
            if hasattr(self, 'roi_tab'): self.roi_tab.on_roi_selection_toggled(True) # Updates button text, status, cursor
            # Status update handled by roi_tab

        # --- If deactivating ROI selection ---
        else:
            self.roi_selection_active = False
            if hasattr(self, 'roi_tab'): self.roi_tab.on_roi_selection_toggled(False) # Updates button text, status, cursor
            # Clean up drawing rectangle if it exists from an incomplete drag
            if self.roi_draw_rect_id:
                self.canvas.delete(self.roi_draw_rect_id)
                self.roi_draw_rect_id = None
            self.roi_start_coords = None
            self.update_status("ROI selection cancelled.")
            # Do NOT automatically return to live here. User might want to stay on snapshot.


    def capture_process(self):
        """Background thread for continuous window capture and processing."""
        last_frame_time = time.time()
        target_sleep_time = FRAME_DELAY # Target delay between frames

        print("Capture thread started.")
        while self.capturing: # Loop controlled by self.capturing flag
            loop_start_time = time.time()
            frame_to_display = None
            try:
                # If in snapshot mode, just sleep and wait
                if self.using_snapshot:
                    # Need a small sleep to prevent busy-waiting
                    time.sleep(0.05) # Sleep briefly even in snapshot mode
                    continue

                # --- Capture Frame ---
                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    # Window lost or uncapturable
                    if self.capturing: # Check flag again in case stop was requested concurrently
                         print("Capture window returned None. Signaling failure.")
                         # Schedule failure handling in main thread
                         self.master.after_idle(self.handle_capture_failure)
                    break # Exit capture loop immediately

                # --- Store & Process Frame ---
                self.current_frame = frame # Store the latest raw frame (BGR)
                frame_to_display = frame # Use this frame for display update

                # --- Process ROIs for text if OCR is ready ---
                # Check OCR readiness and lock within the loop for safety
                ocr_engine_instance = None
                with OCR_ENGINE_LOCK:
                     if self.ocr:
                          ocr_engine_instance = self.ocr

                if self.rois and ocr_engine_instance:
                     # Process ROIs using the captured frame and the OCR instance
                     # Pass the engine instance to avoid issues if it's re-initialized concurrently
                     self._process_rois(frame, ocr_engine_instance)


                # --- Schedule UI Display Update (Rate Limited) ---
                current_time = time.time()
                if current_time - last_frame_time >= target_sleep_time:
                    # Schedule _display_frame to run in the main thread
                    # Pass a copy to prevent modifications by subsequent loop iterations
                    if frame_to_display is not None:
                         frame_copy_for_display = frame_to_display.copy()
                         self.master.after_idle(lambda f=frame_copy_for_display: self._display_frame(f))
                    last_frame_time = current_time


                # --- Calculate Sleep Time ---
                elapsed = time.time() - loop_start_time
                sleep_duration = max(0, target_sleep_time - elapsed)
                time.sleep(sleep_duration)

            except Exception as e:
                print(f"!!! Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                # Update status safely via main thread
                self.master.after_idle(lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}..."))
                # Pause for a moment to prevent rapid error loops
                time.sleep(1)


        # --- Post-Loop Cleanup (runs when self.capturing becomes False or loop breaks) ---
        print("Capture thread finished or exited.")
        # Final UI state update is handled by stop_capture -> _check_thread_... -> _finalize_stop_capture
        # Or by handle_capture_failure -> stop_capture -> ...


    def handle_capture_failure(self):
         """Called from main thread if capture_window returns None while capturing."""
         # Check if we are still supposed to be capturing (flag might have been set false by stop_capture)
         if self.capturing:
              self.update_status("Window lost or uncapturable. Stopping capture.")
              messagebox.showerror("Capture Error", "Failed to capture the selected window. It might be closed, minimized, or protected.", parent=self.master)
              # Initiate stop process
              self.stop_capture()
              # Refresh window list to help user re-select
              if hasattr(self, 'capture_tab'): self.capture_tab.refresh_window_list()


    def on_canvas_resize(self, event=None):
        """Called when the canvas size changes. Redraw current/snapshot frame."""
        # Debounce this? Using `after` might help slightly.
        if hasattr(self, '_resize_job'):
             self.master.after_cancel(self._resize_job)
        self._resize_job = self.master.after(100, self._perform_resize_redraw) # Delay redraw slightly


    def _perform_resize_redraw(self):
         """Actually redraws the frame after a resize event."""
         self._resize_job = None
         frame_to_display = self.snapshot_frame if self.using_snapshot else self.current_frame
         # If no frame, maybe clear canvas or draw placeholder?
         self._display_frame(frame_to_display)


    def _display_frame(self, frame):
        """
        Display a frame on the canvas, fitting and centering it.
        Handles None frame by clearing canvas.
        """
        # Check if canvas exists and is valid
        if not hasattr(self, 'canvas') or not self.canvas.winfo_exists():
            return

        # Clear previous content (image and ROIs)
        self.canvas.delete("display_content")
        self.display_frame_tk = None # Clear PhotoImage reference

        # If frame is None, just keep canvas clear
        if frame is None:
            # Optionally draw a placeholder message?
            # cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            # self.canvas.create_text(cw/2, ch/2, text="No Image", fill="gray", tags="display_content")
            return

        try:
            frame_height, frame_width = frame.shape[:2]
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Prevent division by zero if frame or canvas dimensions are invalid
            if frame_width <= 0 or frame_height <= 0 or canvas_width <= 1 or canvas_height <= 1:
                print("Warning: Invalid frame or canvas dimensions for display.")
                return

            # Calculate scaling factor to fit frame within canvas
            scale_w = canvas_width / frame_width
            scale_h = canvas_height / frame_height
            scale = min(scale_w, scale_h)

            # Optional: Prevent upscaling beyond 1:1?
            # scale = min(scale, 1.0)

            new_width = int(frame_width * scale)
            new_height = int(frame_height * scale)

            # Ensure dimensions are at least 1 pixel
            if new_width < 1 or new_height < 1:
                 print("Warning: Calculated display dimensions too small.")
                 return

            # Store scale and position info for ROI mapping
            self.scale_x = scale
            self.scale_y = scale
            self.frame_display_coords['x'] = (canvas_width - new_width) // 2
            self.frame_display_coords['y'] = (canvas_height - new_height) // 2
            self.frame_display_coords['w'] = new_width
            self.frame_display_coords['h'] = new_height

            # Resize and convert frame for display using OpenCV
            # Use INTER_LINEAR for a good balance of speed and quality
            resized_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            # Convert BGR (from OpenCV) to RGB for PIL/Tkinter
            display_rgb = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)

            # Convert numpy array to PhotoImage
            img = Image.fromarray(display_rgb)
            self.display_frame_tk = ImageTk.PhotoImage(image=img) # Store reference on self

            # --- Draw on Canvas ---
            # Draw the image itself
            self.canvas.create_image(
                self.frame_display_coords['x'], self.frame_display_coords['y'],
                anchor=tk.NW,
                image=self.display_frame_tk, # Use the stored reference
                tags=("display_content", "frame_image")
            )

            # Draw ROIs on top of the image
            self._draw_rois()

        except Exception as e:
            print(f"Error displaying frame: {e}")
            import traceback
            traceback.print_exc()


    def _process_rois(self, frame, ocr_engine):
        """
        Process ROIs on the given frame using the provided OCR engine instance.
        This method assumes it's called from the capture thread.
        OCR lock should ideally be held by the caller if engine modification is possible elsewhere.
        """
        if frame is None or ocr_engine is None:
            print("Skipping ROI processing: No frame or OCR engine.")
            return

        extracted_texts = {}
        stable_text_changed = False
        new_stable_texts = self.stable_texts.copy() # Work on a copy for this frame's results

        for roi in self.rois:
            # Extract image for the current ROI
            roi_img = roi.extract_roi(frame)
            if roi_img is None or roi_img.size == 0:
                extracted_texts[roi.name] = "" # Mark as empty if extraction failed
                continue # Skip to next ROI

            try:
                # --- Perform OCR ---
                # The result format can vary slightly between Paddle versions.
                # Assuming result is like [[box, (text, confidence)], ...] or [[[box], (text, confidence)], ...]
                ocr_result_raw = ocr_engine.ocr(roi_img, cls=True) # cls=True is recommended

                # --- Extract Text from OCR Result ---
                text_lines = []
                if ocr_result_raw and isinstance(ocr_result_raw, list) and len(ocr_result_raw) > 0:
                     # Handle potential extra list layer added in some versions
                     current_result_set = ocr_result_raw[0] if isinstance(ocr_result_raw[0], list) else ocr_result_raw

                     if current_result_set: # Check if the result set for the image is not empty
                         for item in current_result_set:
                              # Try to extract text tuple (text, confidence) robustly
                              text_info = None
                              if isinstance(item, list) and len(item) >= 2: # Common format [[box], (text, conf)]
                                   text_info = item[1]
                              # Handle potential older/different formats if necessary...

                              if isinstance(text_info, (tuple, list)) and len(text_info) >= 1:
                                   text_content = text_info[0]
                                   # confidence = text_info[1] if len(text_info) > 1 else 0.0
                                   if text_content: # Add non-empty text
                                        text_lines.append(str(text_content))

                # Join lines (use space or newline based on language? Space is usually safer)
                text = " ".join(text_lines).strip()
                extracted_texts[roi.name] = text

                # --- Update Stability Tracking ---
                history = self.text_history.get(roi.name, {"text": "", "count": 0})
                if text == history["text"]:
                    history["count"] += 1
                else:
                    # Reset count if text changes
                    history = {"text": text, "count": 1}
                # Store updated history
                self.text_history[roi.name] = history

                # Check for new stable text
                is_now_stable = history["count"] >= self.stable_threshold
                was_stable = roi.name in self.stable_texts
                current_stable_text = self.stable_texts.get(roi.name)

                if is_now_stable:
                    if not was_stable or current_stable_text != text:
                         # Became stable or stable text changed
                         new_stable_texts[roi.name] = text
                         stable_text_changed = True
                         print(f"ROI '{roi.name}' became stable: '{text[:30]}...'")
                elif was_stable:
                     # Was stable, but text changed and is no longer stable
                     del new_stable_texts[roi.name]
                     stable_text_changed = True
                     print(f"ROI '{roi.name}' became unstable.")


            except Exception as e:
                print(f"!!! Error during OCR processing for ROI {roi.name}: {e}")
                import traceback
                traceback.print_exc()
                extracted_texts[roi.name] = "[OCR Error]"
                # Reset stability for this ROI on error
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable_texts:
                     del new_stable_texts[roi.name]
                     stable_text_changed = True # Becoming unstable is a change


        # --- Schedule UI Updates (in main thread) ---
        # Update live text display always
        if hasattr(self, 'text_tab') and self.text_tab.winfo_exists():
             self.master.after_idle(lambda et=extracted_texts.copy(): self.text_tab.update_text(et))

        # Update stable text display and potentially trigger translation only if changes occurred
        if stable_text_changed:
             self.stable_texts = new_stable_texts # Update the main stable text dict reference
             if hasattr(self, 'stable_text_tab') and self.stable_text_tab.winfo_exists():
                  self.master.after_idle(lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st))

             # Trigger auto-translation if enabled and translation tab exists
             if hasattr(self, 'translation_tab') and self.translation_tab.winfo_exists() and \
                self.translation_tab.is_auto_translate_enabled():
                  print("[Auto-Translate] Stable text changed, scheduling translation.")
                  # Use `after_idle` to ensure it runs after the stable text UI update
                  self.master.after_idle(self.translation_tab.perform_translation)


    def _draw_rois(self):
        """Draw ROI rectangles on the canvas over the displayed frame."""
        # Check if canvas and coords are valid
        if not hasattr(self, 'canvas') or not self.canvas.winfo_exists() or \
           self.frame_display_coords['w'] <= 0 or self.frame_display_coords['h'] <= 0:
            return

        offset_x = self.frame_display_coords['x']
        offset_y = self.frame_display_coords['y']

        for i, roi in enumerate(self.rois):
            try:
                # Scale ROI coords to display coords
                disp_x1 = int(roi.x1 * self.scale_x) + offset_x
                disp_y1 = int(roi.y1 * self.scale_y) + offset_y
                disp_x2 = int(roi.x2 * self.scale_x) + offset_x
                disp_y2 = int(roi.y2 * self.scale_y) + offset_y

                # Ensure coordinates are within display bounds? Might clip unnecessarily.
                # disp_x1 = max(offset_x, min(disp_x1, offset_x + self.frame_display_coords['w']))
                # ... clamp others ...

                # Draw rectangle
                self.canvas.create_rectangle(
                    disp_x1, disp_y1, disp_x2, disp_y2,
                    outline="lime", width=1, tags=("display_content", f"roi_{i}")
                )
                # Draw label slightly inside the rectangle
                self.canvas.create_text(
                    disp_x1 + 3, disp_y1 + 1, # Offset slightly from top-left
                    text=roi.name, fill="lime", anchor=tk.NW,
                    font=('TkDefaultFont', 8), tags=("display_content", f"roi_label_{i}")
                )
            except Exception as e:
                 print(f"Error drawing ROI {roi.name}: {e}")

    # --- Mouse Events for ROI Definition ---

    def on_mouse_down(self, event):
        """Handle mouse button press for starting ROI selection."""
        # Only act if ROI selection is active AND we are using a snapshot
        if not self.roi_selection_active or not self.using_snapshot:
            return

        # Check if click is within the displayed image bounds
        img_x = self.frame_display_coords['x']
        img_y = self.frame_display_coords['y']
        img_w = self.frame_display_coords['w']
        img_h = self.frame_display_coords['h']

        if not (img_x <= event.x < img_x + img_w and img_y <= event.y < img_y + img_h):
             # print("ROI start click outside image bounds.")
             self.roi_start_coords = None # Reset start coords if outside
             # Clean up any previous drawing rectangle visually
             if self.roi_draw_rect_id:
                 self.canvas.delete(self.roi_draw_rect_id)
                 self.roi_draw_rect_id = None
             return # Ignore clicks outside the image

        # Store starting coordinates relative to canvas
        self.roi_start_coords = (event.x, event.y)

        # Delete previous drawing rectangle if any (e.g., from a cancelled drag)
        if self.roi_draw_rect_id:
            self.canvas.delete(self.roi_draw_rect_id)

        # Create a new rectangle for visual feedback (initially zero size)
        self.roi_draw_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="red", width=2, tags="roi_drawing" # Use specific tag
        )
        print(f"ROI draw started at ({event.x}, {event.y})")

    def on_mouse_drag(self, event):
        """Handle mouse drag for resizing ROI selection rectangle."""
        # Only act if selection active and started correctly
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            return

        # Update the coordinates of the drawing rectangle
        start_x, start_y = self.roi_start_coords
        # Clamp drag position to canvas bounds for visual neatness
        curr_x = max(0, min(event.x, self.canvas.winfo_width()))
        curr_y = max(0, min(event.y, self.canvas.winfo_height()))

        self.canvas.coords(self.roi_draw_rect_id, start_x, start_y, curr_x, curr_y)

    def on_mouse_up(self, event):
        """Handle mouse button release for finalizing ROI selection."""
        # Only act if selection active and started correctly
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            # If drag started but ended outside, or mode deactivated during drag, just cleanup
            if self.roi_draw_rect_id: self.canvas.delete(self.roi_draw_rect_id)
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # Don't automatically deactivate ROI mode here
            return

        # Get final coordinates of the drawn rectangle from canvas item
        try:
             # Ensure coords returns 4 values
             coords = self.canvas.coords(self.roi_draw_rect_id)
             if len(coords) == 4:
                  x1_disp, y1_disp, x2_disp, y2_disp = map(int, coords)
             else:
                  raise ValueError("Invalid coordinates returned from canvas item.")
        except (tk.TclError, ValueError) as e:
             print(f"Error getting ROI rectangle coordinates: {e}")
             if self.roi_draw_rect_id: self.canvas.delete(self.roi_draw_rect_id)
             self.roi_draw_rect_id = None
             self.roi_start_coords = None
             # Deactivate ROI mode on error? Maybe.
             if hasattr(self, 'roi_tab'): self.roi_tab.on_roi_selection_toggled(False)
             self.roi_selection_active = False
             return

        # Clean up drawing rectangle (visual feedback)
        self.canvas.delete(self.roi_draw_rect_id)
        self.roi_draw_rect_id = None
        self.roi_start_coords = None # Reset start coords

        # Automatically turn off ROI selection mode after definition
        # Do this *before* potentially showing message boxes
        self.roi_selection_active = False
        if hasattr(self, 'roi_tab'): self.roi_tab.on_roi_selection_toggled(False)

        # Check if ROI is reasonably sized
        min_size = 5
        if abs(x2_disp - x1_disp) < min_size or abs(y2_disp - y1_disp) < min_size:
            messagebox.showwarning("ROI Too Small", f"The selected region is too small (min {min_size}x{min_size} pixels). Please try again.", parent=self.master)
            return # Selection mode already turned off

        # Get ROI name from entry
        roi_name = self.roi_tab.roi_name_entry.get().strip()
        original_roi_name_if_overwrite = None
        if not roi_name:
             # Find next available default name (roi_1, roi_2, ...)
             i = 1
             while f"roi_{i}" in [r.name for r in self.rois]: i += 1
             roi_name = f"roi_{i}"
        elif roi_name in [r.name for r in self.rois]:
             # Name exists, ask user to overwrite
             if not messagebox.askyesno("ROI Exists", f"An ROI named '{roi_name}' already exists. Overwrite it?", parent=self.master):
                 # User chose not to overwrite, cancel ROI creation
                 self.update_status("ROI creation cancelled (name exists).")
                 return
             else:
                  # User chose to overwrite, store name for later removal
                  original_roi_name_if_overwrite = roi_name


        # --- Convert display coordinates (relative to canvas) to original frame coordinates ---
        img_x_offset = self.frame_display_coords['x']
        img_y_offset = self.frame_display_coords['y']
        img_w = self.frame_display_coords['w']
        img_h = self.frame_display_coords['h']

        # Coordinates relative to the *displayed image* top-left
        # Clamp coordinates to be within the displayed image bounds first
        x1_rel = max(0, min(x1_disp, x2_disp) - img_x_offset)
        y1_rel = max(0, min(y1_disp, y2_disp) - img_y_offset)
        x2_rel = min(img_w, max(x1_disp, x2_disp) - img_x_offset)
        y2_rel = min(img_h, max(y1_disp, y2_disp) - img_y_offset)

        # Check again if clamping made the ROI too small
        if x2_rel - x1_rel < min_size or y2_rel - y1_rel < min_size:
             messagebox.showwarning("ROI Too Small", f"The effective region within the image is too small after clamping (min {min_size}x{min_size} pixels). Please try again.", parent=self.master)
             return

        # Convert relative coordinates back to original frame coordinates using scale
        # Handle potential zero scale factor (though unlikely if display works)
        if self.scale_x == 0 or self.scale_y == 0:
             messagebox.showerror("Error", "Image scale is zero, cannot calculate ROI coordinates.", parent=self.master)
             return

        orig_x1 = int(x1_rel / self.scale_x)
        orig_y1 = int(y1_rel / self.scale_y)
        orig_x2 = int(x2_rel / self.scale_x)
        orig_y2 = int(y2_rel / self.scale_y)

        # Final coordinates should already be ordered min,min,max,max due to clamping/conversion logic
        final_x1, final_y1, final_x2, final_y2 = orig_x1, orig_y1, orig_x2, orig_y2


        # --- Create and Add/Replace ROI ---
        new_roi = ROI(roi_name, final_x1, final_y1, final_x2, final_y2)

        # If overwriting, remove the old one first
        if original_roi_name_if_overwrite:
             self.rois = [r for r in self.rois if r.name != original_roi_name_if_overwrite]
             # Also remove old overlay settings? Keep them maybe? Let's remove.
             if hasattr(self, 'overlay_manager') and original_roi_name_if_overwrite in self.overlay_manager.overlay_settings:
                  del self.overlay_manager.overlay_settings[original_roi_name_if_overwrite]
                  # No need to save here, will be saved when new overlay config is set/saved
             if hasattr(self, 'overlay_manager'):
                  self.overlay_manager.destroy_overlay(original_roi_name_if_overwrite)


        self.rois.append(new_roi)
        print(f"Created/Updated ROI: {roi_name} ({final_x1},{final_y1}) -> ({final_x2},{final_y2})")

        # --- Update UI ---
        if hasattr(self, 'roi_tab'): self.roi_tab.update_roi_list() # Update listbox
        self._draw_rois() # Redraw ROIs including the new one on the snapshot
        # ROI selection mode was already turned off

        # Update status
        action = "created" if not original_roi_name_if_overwrite else "updated"
        self.update_status(f"ROI '{roi_name}' {action}.")

        # Automatically suggest next ROI name in the entry box
        if hasattr(self, 'roi_tab'):
             next_name_suggestion = ""
             # Prefer 'dialogue' if not present
             if "dialogue" not in [r.name for r in self.rois]:
                  next_name_suggestion = "dialogue"
             else: # Find next generic 'roi_n'
                  i = 1
                  while f"roi_{i}" in [r.name for r in self.rois]: i += 1
                  next_name_suggestion = f"roi_{i}"

             self.roi_tab.roi_name_entry.delete(0, tk.END)
             self.roi_tab.roi_name_entry.insert(0, next_name_suggestion)


        # Ensure overlay exists/is updated for the new/modified ROI
        if hasattr(self, 'overlay_manager'):
             self.overlay_manager.create_overlay_for_roi(new_roi) # Create/Recreate


    def show_floating_controls(self):
        """Creates and shows the floating control window if not already visible."""
        try:
            if self.floating_controls is None or not self.floating_controls.winfo_exists():
                self.floating_controls = FloatingControls(self.master, self)
                self.update_status("Floating controls shown.")
            else:
                # If already exists, just bring it to front and update state
                self.floating_controls.deiconify()
                self.floating_controls.lift()
                self.floating_controls.update_button_states() # Sync states
                self.update_status("Floating controls shown.")
        except Exception as e:
             print(f"Error showing floating controls: {e}")
             self.update_status("Error showing floating controls.")

    def hide_floating_controls(self):
         """Hides the floating control window."""
         if self.floating_controls and self.floating_controls.winfo_exists():
              self.floating_controls.withdraw()
              self.update_status("Floating controls hidden.")


    def on_close(self):
        """Handle application closing sequence."""
        print("Close requested...")
        # Optional: Ask user for confirmation?
        # if not messagebox.askyesno("Quit", "Are you sure you want to quit?", parent=self.master):
        #     return

        # Stop capture if running
        if self.capturing:
            self.update_status("Stopping capture before closing...")
            self.stop_capture() # Initiates the stop sequence
            # Use `after` to periodically check if capture stopped before finalizing close
            self.master.after(100, self.check_capture_stopped_and_close)
        else:
            # If capture not running, proceed directly to final close
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Check if capture thread finished before closing."""
        # Check if the capturing flag is false AND the thread reference is gone or dead
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
             print("Capture confirmed stopped.")
             self._finalize_close()
        else:
             print("Waiting a bit longer for capture thread to stop...")
             # Check again after a delay
             self.master.after(200, self.check_capture_stopped_and_close)


    def _finalize_close(self):
        """Perform final cleanup and destroy the main window."""
        print("Finalizing close...")
        # Ensure capture is definitely marked as stopped
        self.capturing = False

        # Destroy overlays and controls safely
        if hasattr(self, 'overlay_manager'):
            self.overlay_manager.destroy_all_overlays()
        if self.floating_controls and self.floating_controls.winfo_exists():
             # Save position one last time? Already saved on release drag.
             try:
                 x, y = map(int, self.floating_controls.geometry().split('+')[1:])
                 set_setting("floating_controls_pos", f"{x},{y}")
             except: pass # Ignore errors saving position on close
             self.floating_controls.destroy()

        # Optional: Save other settings explicitly if needed (most are saved incrementally)
        # update_settings({...})

        print("Exiting application.")
        try:
             self.master.destroy()
        except tk.TclError:
             print("Main window already destroyed.") # Ignore error if already gone
```

--- END OF FILE app.py ---

--- START OF FILE main.py ---

```python
import tkinter as tk
import os # Import os
from app import VisualNovelTranslatorApp
from pathlib import Path # For user home directory

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
    # Cache directory (used by translation.py)
    try:
         cache_dir = Path(os.path.expanduser("~/.ocrtrans/cache"))
         cache_dir.mkdir(parents=True, exist_ok=True)
         print(f"Cache directory ensured at: {cache_dir}")
    except Exception as e:
         print(f"Warning: Could not create cache directory {cache_dir}: {e}")

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
```

--- END OF FILE main.py ---