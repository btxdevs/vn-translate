Okay, let's implement persistent, game-specific context history.

**Summary of Changes:**

1.  **Context Directory (`utils/translation.py`):** Defined `CONTEXT_DIR` within the app directory.
2.  **Context Filename (`utils/translation.py`):** Context files named `<game_hash>_context.json`.
3.  **Saving Context (`utils/translation.py`):**
    *   Created `_save_context(hwnd)` to save the global `context_messages` to the game-specific file.
    *   `translate_text` now calls `_save_context(hwnd)` after successfully adding messages to the history.
4.  **Loading Context (`utils/translation.py`):**
    *   Created `_load_context(hwnd)` to load history from the game-specific file into the global `context_messages`. Handles file not found/errors.
5.  **Reset Context (`utils/translation.py`):**
    *   `reset_context(hwnd)` now clears the global list *and* deletes the corresponding context file.
6.  **Integration (`app.py`):**
    *   Ensure `CONTEXT_DIR` exists on startup.
    *   `load_rois_for_hwnd` now calls `_load_context(hwnd)`.
7.  **UI Update (`ui/translation_tab.py`):**
    *   Updated the "Reset Translation Context" button command to pass the current `hwnd`.

---

Here are the full scripts for the modified files:

**`utils/translation.py`**
```python
# --- START OF FILE utils/translation.py ---

import json
import re
import os
from openai import OpenAI, APIError # Import APIError for specific handling
from pathlib import Path
import hashlib # For cache key generation
import time # For potential corrupted cache backup naming
from utils.capture import get_executable_details # Import the new function

# File-based cache settings
APP_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Get app root directory
CACHE_DIR = APP_DIR / "cache"
CONTEXT_DIR = APP_DIR / "context_history" # NEW: Directory for context files

# Context management (global list - represents the currently loaded context)
context_messages = []

# --- Logging Helper ---
def format_message_for_log(message):
    """Formats a message dictionary for concise logging."""
    role = message.get('role', 'unknown')
    content = message.get('content', '')
    # Truncate long content for logs
    content_display = (content[:75] + '...') if len(content) > 78 else content
    # Replace newlines in the snippet for cleaner single-line logging
    content_display = content_display.replace('\n', '\\n')
    return f"[{role}] '{content_display}'"

# --- Directory and Hashing ---

def _ensure_cache_dir():
    """Make sure the cache directory exists"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating cache directory {CACHE_DIR}: {e}")

def _ensure_context_dir():
    """Make sure the context history directory exists"""
    try:
        CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating context directory {CONTEXT_DIR}: {e}")

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

def _get_context_file_path(hwnd):
    """Gets the specific context history file path for the given game window."""
    game_hash = _get_game_hash(hwnd)
    if game_hash:
        return CONTEXT_DIR / f"{game_hash}_context.json"
    else:
        print("Warning: Could not determine game hash for context file path.")
        return None


# --- Cache Handling ---

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

# --- Context History Handling ---

def _load_context(hwnd):
    """Loads context history from the game-specific file into the global list."""
    global context_messages
    _ensure_context_dir()
    context_file_path = _get_context_file_path(hwnd)
    context_messages = [] # Start fresh before loading

    if not context_file_path:
        print("[CONTEXT] Cannot load context, failed to get file path.")
        return # Keep context_messages empty

    if context_file_path.exists():
        try:
            with open(context_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    loaded_history = json.loads(content)
                    # Basic validation: check if it's a list
                    if isinstance(loaded_history, list):
                        context_messages = loaded_history
                        print(f"[CONTEXT] Loaded {len(context_messages)} messages from {context_file_path.name}")
                    else:
                        print(f"[CONTEXT] Error: Loaded context from {context_file_path.name} is not a list. Resetting history.")
                else:
                    print(f"[CONTEXT] Context file {context_file_path.name} is empty.")
        except json.JSONDecodeError:
            print(f"[CONTEXT] Error: Context file {context_file_path.name} is corrupted. Resetting history.")
            # Optionally backup corrupted file here too
        except Exception as e:
            print(f"[CONTEXT] Error loading context from {context_file_path.name}: {e}. Resetting history.")
    else:
        print(f"[CONTEXT] No context file found for current game ({context_file_path.name}). Starting fresh history.")

def _save_context(hwnd):
    """Saves the current global context_messages to the game-specific file."""
    global context_messages
    _ensure_context_dir()
    context_file_path = _get_context_file_path(hwnd)

    if not context_file_path:
        print("[CONTEXT] Cannot save context, failed to get file path.")
        return

    try:
        with open(context_file_path, 'w', encoding='utf-8') as f:
            json.dump(context_messages, f, ensure_ascii=False, indent=2)
        # print(f"[CONTEXT] Saved {len(context_messages)} messages to {context_file_path.name}") # Less verbose
    except Exception as e:
        print(f"[CONTEXT] Error saving context to {context_file_path.name}: {e}")


def reset_context(hwnd):
    """Reset the global translation context history AND delete the game-specific file."""
    global context_messages
    context_messages = []
    print("[CONTEXT] In-memory context history reset.")

    # Also delete the file for the current game
    context_file_path = _get_context_file_path(hwnd)
    if context_file_path and context_file_path.exists():
        try:
            os.remove(context_file_path)
            print(f"[CONTEXT] Deleted context file: {context_file_path.name}")
            return "Translation context history reset and file deleted."
        except Exception as e:
            print(f"[CONTEXT] Error deleting context file {context_file_path.name}: {e}")
            return f"Context history reset, but error deleting file: {e}"
    elif context_file_path:
        return "Context history reset (no file found to delete)."
    else:
        return "Context history reset (could not determine file path)."


def add_context_message(message, context_limit):
    """Add a message to the global translation context history, enforcing the limit."""
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
    current_length = len(context_messages)

    if current_length > max_messages:
        context_messages = context_messages[-max_messages:]
        new_length = len(context_messages)
        # Log the trimming action
        print(f"[CONTEXT] History limit ({max_messages} msgs / {limit} exchanges) exceeded ({current_length} msgs). Trimmed to {new_length}.")
    # else:
        # Optional: Log when context is added but not trimmed
        # print(f"[CONTEXT] Added message. History length: {current_length}/{max_messages}")


# --- Translation Core Logic ---

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
    (Function unchanged)
    """
    parsed_segments = {}
    pattern = r"<\|(\d+)\|>(.*?)(?=<\|\d+\|>|$)"
    matches = re.findall(pattern, response_text, re.DOTALL | re.MULTILINE)

    if matches:
        for segment_number, content in matches:
            original_roi_name = original_tag_mapping.get(segment_number)
            if original_roi_name:
                cleaned_content = content.strip()
                parsed_segments[original_roi_name] = cleaned_content
            else:
                print(f"Warning: Received segment number '{segment_number}' which was not in the original mapping.")
    else:
        line_pattern = r"^\s*<\|(\d+)\|>\s*(.*)$"
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
            print("[LLM PARSE] Failed to parse any <|n|> segments from response.")
            if not response_text.startswith("<|") and len(original_tag_mapping) == 1:
                first_tag = next(iter(original_tag_mapping))
                first_roi = original_tag_mapping[first_tag]
                print(f"[LLM PARSE] Warning: Response had no tags, assuming plain text response for single ROI '{first_roi}'.")
                parsed_segments[first_roi] = response_text.strip()
            else:
                return {"error": f"Error: Unable to extract formatted translation.\nRaw response:\n{response_text}"}

    missing_tags = set(original_tag_mapping.values()) - set(parsed_segments.keys())
    if missing_tags:
        print(f"[LLM PARSE] Warning: Translation response missing segments for ROIs: {', '.join(missing_tags)}")
        for roi_name in missing_tags:
            parsed_segments[roi_name] = "[Translation Missing]"

    return parsed_segments


def preprocess_text_for_translation(aggregated_text):
    """
    Convert input text with tags like [tag]: content to the numbered format <|1|> content.
    (Function unchanged)
    """
    lines = aggregated_text.strip().split('\n')
    preprocessed_lines = []
    tag_mapping = {}
    segment_count = 1
    for line in lines:
        match = re.match(r'^\s*\[\s*([^\]]+)\s*\]\s*:\s*(.*)$', line)
        if match:
            roi_name, content = match.groups()
            roi_name = roi_name.strip()
            content = content.strip()
            if content:
                tag_mapping[str(segment_count)] = roi_name
                preprocessed_lines.append(f"<|{segment_count}|> {content}")
                segment_count += 1
            else:
                print(f"Skipping empty content for ROI: {roi_name}")
        else:
            print(f"Ignoring line, does not match '[ROI]: content' format: {line}")
    if not tag_mapping:
        print("Warning: No lines matched the '[ROI]: content' format during preprocessing.")
    return '\n'.join(preprocessed_lines), tag_mapping


def translate_text(aggregated_input_text, hwnd, preset, target_language="en", additional_context="", context_limit=10, force_recache=False):
    """
    Translate the given text using an OpenAI-compatible API client, using game-specific caching and context.
    """
    # 0. Determine Cache and Context File Paths
    cache_file_path = _get_cache_file_path(hwnd)
    # context_file_path = _get_context_file_path(hwnd) # Not needed directly here, used by load/save helpers

    if not cache_file_path: # If we can't get cache path, likely can't get context path either
        print("Error: Cannot proceed with translation without a valid game identifier.")
        return {"error": "Could not determine file paths for the game."}

    # 1. Preprocess input text to <|n|> format and get mapping
    preprocessed_text_for_llm, tag_mapping = preprocess_text_for_translation(aggregated_input_text)

    if not preprocessed_text_for_llm or not tag_mapping:
        print("No valid text segments found after preprocessing. Nothing to translate.")
        return {} # Return empty dict if nothing to translate

    # 2. Check Cache (Using simplified key), skip if force_recache is True
    cache_key = get_cache_key(preprocessed_text_for_llm, target_language)
    if not force_recache:
        cached_result = get_cached_translation(cache_key, cache_file_path)
        if cached_result:
            print(f"[CACHE] HIT for key: {cache_key[:10]}... in {cache_file_path.name}")
            if isinstance(cached_result, dict) and not 'error' in cached_result:
                if all(roi_name in cached_result for roi_name in tag_mapping.values()):
                    return cached_result
                else:
                    print("[CACHE] WARN: Cached result seems incomplete for current request, fetching fresh translation.")
            else:
                print("[CACHE] WARN: Cached result format mismatch or error, fetching fresh translation.")
    elif force_recache:
        print(f"[CACHE] SKIP requested for key: {cache_key[:10]}...")
    else: # Cache miss
         print(f"[CACHE] MISS for key: {cache_key[:10]}... in {cache_file_path.name}")


    # 3. Prepare messages for API
    # System Prompt
    system_prompt = preset.get('system_prompt', "You are a translator.")
    system_content = (
        f"{system_prompt}\n\n"
        f"Translate the following text segments into {target_language}. "
        "Input segments are tagged like <|1|>, <|2|>, etc. "
        "Your response MUST replicate this format exactly, using the same tags for the corresponding translated segments. "
        "For example, input '<|1|> Hello\n<|2|> World' requires output '<|1|> [Translation of Hello]\n<|2|> [Translation of World]'. "
        "Output ONLY the tagged translated lines. Do NOT add introductions, explanations, apologies, or any text outside the <|n|> tags."
    )
    system_message = {"role": "system", "content": system_content}

    # Get context history (if any) - uses the current global context_messages
    global context_messages
    history_to_send = list(context_messages) # Send a copy

    # --- Construct the CURRENT user message WITH additional_context ---
    current_user_message_parts = []
    if additional_context.strip():
        current_user_message_parts.append(f"Additional context: {additional_context.strip()}")
    current_user_message_parts.append(f"Translate these segments to {target_language}, maintaining the exact <|n|> tags:")
    current_user_message_parts.append(preprocessed_text_for_llm)
    current_user_content_with_context = "\n\n".join(current_user_message_parts)
    current_user_message_for_api = {"role": "user", "content": current_user_content_with_context}
    # --- End Construct CURRENT user message ---

    # --- Construct the user message to be SAVED in HISTORY (WITHOUT additional_context) ---
    history_user_message_parts = [
        f"Translate these segments to {target_language}, maintaining the exact <|n|> tags:",
        preprocessed_text_for_llm
    ]
    history_user_content = "\n\n".join(history_user_message_parts)
    history_user_message = {"role": "user", "content": history_user_content}
    # --- End Construct user message for HISTORY ---


    # Combine messages for the API call
    messages_for_api = [system_message] + history_to_send + [current_user_message_for_api]


    # 4. Prepare API Payload
    # Validate required preset fields
    if not preset.get("model") or not preset.get("api_url"):
        missing = [f for f in ["model", "api_url"] if not preset.get(f)]
        errmsg = f"Missing required preset fields: {', '.join(missing)}"
        print(f"[API] Error: {errmsg}")
        return {"error": errmsg}

    payload = {
        "model": preset["model"],
        "messages": messages_for_api, # Use the combined list
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


    # --- LLM Request Logging ---
    print("-" * 20 + " LLM Request " + "-" * 20)
    print(f"[API] Endpoint: {preset.get('api_url')}")
    print(f"[API] Model: {preset['model']}")
    print(f"[API] Payload Parameters (excluding messages):")
    for key, value in payload.items():
        if key != "messages":
            print(f"  - {key}: {value}")
    print(f"[API] Messages ({len(messages_for_api)} total):")
    # Log system prompt presence without full content potentially
    if messages_for_api[0]['role'] == 'system':
         print(f"  - [system] (System prompt configured)")
    # Log context messages (if any)
    if history_to_send:
         print(f"  - [CONTEXT HISTORY - {len(history_to_send)} messages]:")
         for msg in history_to_send:
             print(f"    - {format_message_for_log(msg)}")
    # Log the current user message (the one with additional context)
    print(f"  - {format_message_for_log(current_user_message_for_api)}")
    print("-" * 55)
    # --- End LLM Request Logging ---


    # 5. Initialize API Client
    try:
        # Ensure API key is handled correctly (might be None or empty string)
        # DO NOT LOG THE API KEY
        api_key = preset.get("api_key") or None # Treat empty string as None for client
        client = OpenAI(
            base_url=preset.get("api_url"),
            api_key=api_key
        )
    except Exception as e:
        print(f"[API] Error creating API client: {e}")
        return {"error": f"Error creating API client: {e}"}

    # 6. Make API Request
    response_text = None
    try:
        completion = client.chat.completions.create(**payload)
        # Check for valid response structure
        if not completion.choices or not completion.choices[0].message or completion.choices[0].message.content is None:
            print("[API] Error: Invalid response structure received from API.")
            # Log the raw completion object for debugging
            try:
                print(f"[API] Raw Response Object: {completion}")
            except Exception as log_err:
                 print(f"[API] Error logging raw response object: {log_err}")
            return {"error": "Invalid response structure received from API."}

        response_text = completion.choices[0].message.content.strip()

        # --- LLM Response Logging ---
        print("-" * 20 + " LLM Response " + "-" * 20)
        print(f"[API] Raw Response Text ({len(response_text)} chars):")
        print(response_text)
        print("-" * 56)
        # --- End LLM Response Logging ---

    except APIError as e: # Catch specific OpenAI errors first
        error_message = str(e)
        status_code = getattr(e, 'status_code', 'N/A')
        try:
            # Attempt to parse error body if it's JSON
            error_body = json.loads(getattr(e, 'body', '{}') or '{}')
            detail = error_body.get('error', {}).get('message', '')
            if detail: error_message = detail
        except:
            pass # Ignore parsing errors
        log_msg = f"[API] APIError during translation request: Status {status_code}, Error: {error_message}"
        print(log_msg)
        # Log request details that might have caused it (e.g., model name)
        print(f"[API] Request Model: {payload.get('model')}")
        return {"error": f"API Error ({status_code}): {error_message}"}
    except Exception as e: # Catch other potential errors (network, etc.)
        error_message = str(e)
        log_msg = f"[API] Error during translation request: {error_message}"
        print(log_msg)
        import traceback
        traceback.print_exc() # Print full traceback for unexpected errors
        return {"error": f"Error during API request: {error_message}"}


    # 7. Parse LLM Response
    # Use the tag_mapping from preprocessing to convert back to ROI names
    final_translations = parse_translation_output(response_text, tag_mapping)

    # Check if parsing resulted in an error
    if 'error' in final_translations:
        print("[LLM PARSE] Parsing failed after receiving response.")
        # Error message already contains details and raw response
        return final_translations

    # 8. Update Context and Cache
    # --- Check if the input text is the same as the last user message in history ---
    add_to_history = True
    if len(context_messages) >= 2: # Need at least one user/assistant pair to compare
        last_user_message_in_history = context_messages[-2] # Second to last is the previous user msg
        if last_user_message_in_history.get('role') == 'user':
            if last_user_message_in_history.get('content') == history_user_message.get('content'):
                add_to_history = False
                print("[CONTEXT] Input identical to previous user message. Skipping history update.")

    if add_to_history:
        # Add the exchange to context, using the user message WITHOUT additional_context
        current_assistant_message = {"role": "assistant", "content": response_text}
        add_context_message(history_user_message, context_limit) # Add the simplified user message
        add_context_message(current_assistant_message, context_limit) # Add the assistant response
        # --- Save the updated context to file ---
        _save_context(hwnd)
    # --- End Update Context ---

    # Add/Update cache using the key generated earlier and the game-specific file
    # This happens regardless of force_recache flag or history update skip, overwriting previous entry
    set_cache_translation(cache_key, final_translations, cache_file_path)
    print(f"[CACHE] Translation cached/updated successfully in {cache_file_path.name}")

    return final_translations

# --- END OF FILE utils/translation.py ---
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
import win32gui # Needed for IsWindow check in capture loop
from paddleocr import PaddleOCR, paddleocr
import platform
from pathlib import Path # Import Path

# Import utilities
from utils.capture import get_window_title, capture_window
from utils.config import load_rois, ROI_CONFIGS_DIR, _get_game_hash # Import load_rois, directory and hash func
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
from utils.translation import CACHE_DIR, CONTEXT_DIR, _load_context # Import dirs and load_context

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
        # config_file is now dynamic, based on loaded game
        self.config_file = None # Start with no config file loaded

        window_title = "Visual Novel Translator"
        # Title updated later when ROIs are loaded for a game
        master.title(window_title)
        master.geometry("1200x800")
        master.minsize(1000, 700)
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- Ensure Required Directories Exist ---
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Cache directory ensured at: {CACHE_DIR}")
        except Exception as e:
            print(f"Warning: Could not create cache directory {CACHE_DIR}: {e}")
        try:
            ROI_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
            print(f"ROI Configs directory ensured at: {ROI_CONFIGS_DIR}")
        except Exception as e:
            print(f"Warning: Could not create ROI Configs directory {ROI_CONFIGS_DIR}: {e}")
        try: # NEW: Ensure context directory exists
            CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Context History directory ensured at: {CONTEXT_DIR}")
        except Exception as e:
            print(f"Warning: Could not create Context History directory {CONTEXT_DIR}: {e}")


        # --- Initialize variables ---
        self.capturing = False
        self.roi_selection_active = False
        self.selected_hwnd = None
        self.capture_thread = None
        self.rois = [] # Start with empty ROIs
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
        # REMOVED: ROIs are now loaded when a window is selected
        # self._load_initial_rois()

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
        # Removed Load/Save As, kept Save (which is now game-specific)
        file_menu.add_command(label="Save ROIs for Current Game", command=lambda: self.roi_tab.save_rois_for_current_game() if hasattr(self, 'roi_tab') else None)
        # file_menu.add_command(label="Load ROI Config...", command=lambda: self.roi_tab.load_rois() if hasattr(self, 'roi_tab') else None) # REMOVED
        # file_menu.add_command(label="Save ROI Config As...", command=lambda: self.roi_tab.save_rois() if hasattr(self, 'roi_tab') else None) # REMOVED
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
        self.update_status("Ready. Select a window.") # Updated initial status

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

    def load_game_context(self, hwnd):
        """Loads the game-specific context and updates the TranslationTab."""
        # Load context from file (updates global context_messages in translation.py)
        _load_context(hwnd)

        # Get the loaded context (which is now in the global list)
        # We don't need the text content here, just need to trigger UI update
        # context_to_load = "" # Default if load failed or no context
        # if hwnd:
        #     game_hash = _get_game_hash(hwnd)
        #     if game_hash:
        #         all_contexts = get_setting("game_specific_context", {})
        #         context_to_load = all_contexts.get(game_hash, "")

        # Update the UI in TranslationTab using the loaded global context
        # (This part seems redundant if _load_context updates the global var directly)
        # Let's simplify: _load_context handles the global var, UI just reads it when needed.
        # However, we DO need to update the *display* in the TranslationTab UI.
        # We need the actual text loaded by _load_context for this.
        # Let's modify _load_context to return the loaded list or empty list.

        # --- Reworked approach: _load_context updates global, we read global for UI ---
        from utils.translation import context_messages as loaded_context_list # Import the global list

        # Reconstruct the text representation if needed for display (though maybe not necessary?)
        # For now, just signal that context was loaded/cleared.
        # The translation tab itself reads the global context_messages when sending.
        # We *do* need to update the "Additional Context" text box though.
        all_game_contexts = get_setting("game_specific_context", {})
        game_hash = _get_game_hash(hwnd) if hwnd else None
        context_text_for_ui = all_game_contexts.get(game_hash, "") if game_hash else ""

        if hasattr(self, 'translation_tab') and self.translation_tab.frame.winfo_exists():
            self.translation_tab.load_context_for_game(context_text_for_ui)
        else:
            print("Translation tab not available to display context.")


    def load_rois_for_hwnd(self, hwnd):
        """Load ROIs and context automatically for the given window handle."""
        if not hwnd:
            # Clear ROIs if hwnd is None (e.g., window closed or selection cleared)
            if self.rois: # Only update if there were ROIs before
                print("Clearing ROIs as no window is selected.")
                self.rois = []
                self.config_file = None
                if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
                if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
                self.master.title("Visual Novel Translator")
                self.update_status("No window selected. ROIs cleared.")
                # Clear text displays and context
                self._clear_text_data()
                self.load_game_context(None) # Clear context display and global context list
            return

        self.update_status(f"Checking for ROIs for HWND {hwnd}...")
        try:
            loaded_rois, loaded_path = load_rois(hwnd) # Pass hwnd to load_rois

            if loaded_path: # ROIs were found and loaded
                self.rois = loaded_rois
                self.config_file = loaded_path
                self.update_status(f"Loaded {len(loaded_rois)} ROIs for current game.")
                self.master.title(f"Visual Novel Translator - {os.path.basename(loaded_path)}")
            else: # No ROI file found for this game
                if self.rois: # If there were ROIs from a previous game, clear them
                    print(f"No ROIs found for HWND {hwnd}. Clearing previous ROIs.")
                    self.rois = []
                    self.config_file = None
                    self.master.title("Visual Novel Translator")
                    self.update_status(f"No ROIs found for current game. Define new ROIs.")
                else:
                    # No previous ROIs and none found for current game
                    self.update_status(f"No ROIs found for current game. Define new ROIs.")

            # --- Load Game Context and History ---
            self.load_game_context(hwnd) # Loads game-specific additional context text
            _load_context(hwnd) # Loads game-specific history into global list
            # --- End Load Game Context ---

            # Update UI regardless of whether ROIs were loaded or cleared
            if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
            # Clear stale text data when switching games/configs
            self._clear_text_data()

        except Exception as e:
            self.update_status(f"Error loading ROIs/Context for HWND {hwnd}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Clear ROIs and context on error
            self.rois = []
            self.config_file = None
            if hasattr(self, "roi_tab"): self.roi_tab.update_roi_list()
            if hasattr(self, "overlay_manager"): self.overlay_manager.rebuild_overlays()
            self.master.title("Visual Novel Translator")
            self._clear_text_data()
            self.load_game_context(None) # Clear context display and global list

    def _clear_text_data(self):
        """Clears text history, stable text, and updates relevant UI tabs."""
        self.text_history = {}
        self.stable_texts = {}
        if hasattr(self, 'text_tab') and self.text_tab.frame.winfo_exists():
             try: self.text_tab.update_text({})
             except tk.TclError: pass
        if hasattr(self, 'stable_text_tab') and self.stable_text_tab.frame.winfo_exists():
             try: self.stable_text_tab.update_text({})
             except tk.TclError: pass
        if hasattr(self, 'translation_tab') and self.translation_tab.frame.winfo_exists():
             try:
                 # Clear translation preview
                 self.translation_tab.translation_display.config(state=tk.NORMAL)
                 self.translation_tab.translation_display.delete(1.0, tk.END)
                 self.translation_tab.translation_display.config(state=tk.DISABLED)
                 # Clear additional context display (loading new one handles this)
                 # self.translation_tab.load_context_for_game("")
             except tk.TclError: pass # Ignore if widget destroyed
        if hasattr(self, 'overlay_manager'):
             self.overlay_manager.clear_all_overlays()


    # def _load_initial_rois(self): # REMOVED
    #     """Load ROIs from the last used config file on startup."""
    #     # ... (logic removed as loading is now triggered by window selection) ...
    #     pass

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

        # Attempt to load ROIs/Context for the selected window if not already loaded
        if not self.rois and self.selected_hwnd:
             self.load_rois_for_hwnd(self.selected_hwnd) # This now also loads context

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
        # Rebuild overlays ensures they are created if ROIs were just loaded
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
            # Use a flag to prevent multiple calls if check runs again before flag is reset
            if not getattr(self, "_finalize_stop_in_progress", False):
                self._finalize_stop_in_progress = True
                self._finalize_stop_capture()


    def _finalize_stop_capture(self):
        """Actions to perform in the main thread after capture stops."""
        try:
            if self.capturing:  # Safety check
                print("Warning: Finalizing stop capture while flag is still true.")
                self.capturing = False

            print("Finalizing stop capture UI updates...")
            if hasattr(self, "capture_tab") and self.capture_tab.frame.winfo_exists():
                self.capture_tab.on_capture_stopped()
            if hasattr(self, "overlay_manager"):
                self.overlay_manager.hide_all_overlays()  # Hide overlays
            self.update_status("Capture stopped.")
        finally:
            self._finalize_stop_in_progress = False # Reset flag


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
            # Check if a window is selected first
            if not self.selected_hwnd:
                 messagebox.showwarning("Warning", "Select a game window first.", parent=self.master)
                 return

            frame_available = self.current_frame is not None or self.snapshot_frame is not None
            if not frame_available:
                # If no frame, try taking a snapshot now if capture isn't running
                if not self.capturing:
                    print("No frame available, attempting snapshot...")
                    frame = capture_window(self.selected_hwnd)
                    if frame is not None:
                        self.current_frame = frame # Store it even if not capturing
                        self.take_snapshot()
                        # Check if snapshot was successful
                        if not self.using_snapshot: return # Exit if snapshot failed
                    else:
                         messagebox.showwarning("Warning", "Could not capture frame. Start capture or check window.", parent=self.master)
                         return
                else: # Capture running but no frame yet
                    messagebox.showwarning("Warning", "Waiting for first frame. Try again shortly.", parent=self.master)
                    return

            # If capture is running, ensure we are in snapshot mode
            if self.capturing and not self.using_snapshot:
                self.take_snapshot()
                if not self.using_snapshot:
                    return  # Snapshot failed

            # If we got here, we have a snapshot (or were already in snapshot mode)
            self.roi_selection_active = True
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(True)
        else:
            # --- Deactivating ROI selection ---
            self.roi_selection_active = False
            if hasattr(self, "roi_tab"):
                self.roi_tab.on_roi_selection_toggled(False)
            if self.roi_draw_rect_id:
                try:
                    self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass # Ignore if already deleted
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

                # Ensure hwnd is still valid before capturing
                if not self.selected_hwnd or not win32gui.IsWindow(self.selected_hwnd):
                     print("Capture target window lost or invalid. Stopping.")
                     # Use after_idle to ensure thread-safe call to stop_capture
                     self.master.after_idle(self.handle_capture_failure)
                     break # Exit the loop

                frame = capture_window(self.selected_hwnd)
                if frame is None:
                    # Don't immediately stop, could be a temporary glitch (e.g., window minimized briefly)
                    # Log the failure, maybe add a counter?
                    print("Warning: capture_window returned None.")
                    time.sleep(0.5) # Wait a bit before retrying
                    continue # Skip processing this cycle

                self.current_frame = frame
                frame_to_display = frame

                ocr_engine_instance = None
                with OCR_ENGINE_LOCK:
                    ocr_engine_instance = self.ocr

                if self.rois and ocr_engine_instance:
                    self._process_rois(frame, ocr_engine_instance)

                current_time = time.time()
                # Update display frame less frequently if needed, or based on change
                if current_time - last_frame_time >= target_sleep_time:
                    if frame_to_display is not None:
                        frame_copy = frame_to_display.copy()
                        # Use after_idle for thread safety when updating Tkinter UI
                        self.master.after_idle(lambda f=frame_copy: self._display_frame(f))
                    last_frame_time = current_time

                elapsed = time.time() - loop_start_time
                sleep_duration = max(0.001, target_sleep_time - elapsed)
                time.sleep(sleep_duration)

            except Exception as e:
                print(f"!!! Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                # Use after_idle for thread safety when updating Tkinter UI
                self.master.after_idle(
                    lambda msg=str(e): self.update_status(f"Capture loop error: {msg[:60]}...")
                )
                time.sleep(1) # Pause after error before retrying
        print("Capture thread finished or exited.")

    def handle_capture_failure(self):
        """Called from main thread if capture fails definitively."""
        if self.capturing: # Check if stop wasn't already called
            self.update_status("Window lost or uncapturable. Stopping capture.")
            print("Failed to capture the selected window.")
            self.stop_capture() # This will handle UI updates
            # Optionally refresh window list? Might be redundant if user needs to select anyway.
            # if hasattr(self, "capture_tab"):
            #     self.capture_tab.refresh_window_list()

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
                        cw / 2, ch / 2, text="No Image\n(Select Window and Start Capture)", fill="gray50", tags="display_content", justify=tk.CENTER
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
                    # Text became unstable or disappeared
                    if roi.name in new_stable: # Check if it exists before deleting
                        del new_stable[roi.name]
                        stable_changed = True

            except Exception as e:
                print(f"!!! OCR Error for ROI {roi.name}: {e}")
                extracted[roi.name] = "[OCR Error]"
                self.text_history[roi.name] = {"text": "[OCR Error]", "count": 1}
                if roi.name in new_stable:
                    del new_stable[roi.name]
                    stable_changed = True

        # Schedule UI updates only if the widgets exist and use after_idle for thread safety
        if hasattr(self, "text_tab") and self.text_tab.frame.winfo_exists():
            self.master.after_idle(lambda et=extracted.copy(): self.text_tab.update_text(et))

        if stable_changed:
            self.stable_texts = new_stable
            if hasattr(self, "stable_text_tab") and self.stable_text_tab.frame.winfo_exists():
                self.master.after_idle(
                    lambda st=self.stable_texts.copy(): self.stable_text_tab.update_text(st)
                )
            # Trigger auto-translation if enabled and stable text changed
            if (
                    hasattr(self, "translation_tab")
                    and self.translation_tab.frame.winfo_exists()
                    and self.translation_tab.is_auto_translate_enabled()
            ):
                # Only trigger if there's actually stable text to translate
                if any(self.stable_texts.values()):
                    self.master.after_idle(self.translation_tab.perform_translation)
                else:
                    # If stable text disappeared, clear overlays/translation preview
                     if hasattr(self, 'overlay_manager'):
                         self.master.after_idle(self.overlay_manager.clear_all_overlays)
                     if hasattr(self, 'translation_tab'):
                         self.master.after_idle(lambda: self.translation_tab.update_translation_results({}, "[No stable text detected]"))


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
        # Only start drawing if click is within the displayed image bounds
        if not (img_x <= event.x < img_x + img_w and img_y <= event.y < img_y + img_h):
            self.roi_start_coords = None
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            return
        self.roi_start_coords = (event.x, event.y)
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        self.roi_draw_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="red", width=2, tags="roi_drawing"
        )

    def on_mouse_drag(self, event):
        """Update ROI definition rectangle during drag."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            return
        sx, sy = self.roi_start_coords
        img_x, img_y = self.frame_display_coords["x"], self.frame_display_coords["y"]
        img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"]

        # Clamp current coordinates to be within the image bounds on canvas
        cx = max(img_x, min(event.x, img_x + img_w))
        cy = max(img_y, min(event.y, img_y + img_h))

        try:
            # Ensure start coords are also clamped in case mouse down was slightly off
            clamped_sx = max(img_x, min(sx, img_x + img_w))
            clamped_sy = max(img_y, min(sy, img_y + img_h))
            self.canvas.coords(self.roi_draw_rect_id, clamped_sx, clamped_sy, cx, cy)
        except tk.TclError:
            self.roi_draw_rect_id = None
            self.roi_start_coords = None

    def on_mouse_up(self, event):
        """Finalize ROI definition on mouse release."""
        if not self.roi_selection_active or not self.roi_start_coords or not self.roi_draw_rect_id:
            # Clean up drawing rectangle if it exists but shouldn't
            if self.roi_draw_rect_id:
                try: self.canvas.delete(self.roi_draw_rect_id)
                except tk.TclError: pass
            self.roi_draw_rect_id = None
            self.roi_start_coords = None
            # If ROI selection wasn't active, don't return to live unnecessarily
            # if self.using_snapshot:
            #     self.return_to_live()
            return

        try:
            coords = self.canvas.coords(self.roi_draw_rect_id)
        except tk.TclError:
            coords = None # Rectangle was likely deleted

        # Clean up drawing rectangle ID and state
        if self.roi_draw_rect_id:
            try: self.canvas.delete(self.roi_draw_rect_id)
            except tk.TclError: pass
        self.roi_draw_rect_id = None
        self.roi_start_coords = None
        self.roi_selection_active = False  # Turn off mode
        if hasattr(self, "roi_tab"):
            self.roi_tab.on_roi_selection_toggled(False) # Update button text

        # --- Finalize ROI Creation ---
        if coords is None or len(coords) != 4:
            print("ROI definition failed or cancelled (invalid coords).")
            if self.using_snapshot: self.return_to_live()
            return

        x1d, y1d, x2d, y2d = map(int, coords)
        min_size = 5 # Minimum pixel size on canvas
        if abs(x2d - x1d) < min_size or abs(y2d - y1d) < min_size:
            messagebox.showwarning(
                "ROI Too Small",
                f"Selected region too small (min {min_size}x{min_size} px on preview).",
                parent=self.master,
            )
            if self.using_snapshot: self.return_to_live()
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
                if self.using_snapshot: self.return_to_live() # User cancelled overwrite
                return
            overwrite_name = roi_name

        # Convert canvas coordinates back to original frame coordinates
        ox, oy = self.frame_display_coords["x"], self.frame_display_coords["y"]
        # img_w, img_h = self.frame_display_coords["w"], self.frame_display_coords["h"] # Not needed directly here

        # Coordinates relative to the displayed image top-left corner
        rx1 = min(x1d, x2d) - ox
        ry1 = min(y1d, y2d) - oy
        rx2 = max(x1d, x2d) - ox
        ry2 = max(y1d, y2d) - oy

        # Clamp relative coordinates just in case (should be within bounds due to drag clamping)
        # crx1 = max(0, min(rx1, img_w))
        # cry1 = max(0, min(ry1, img_h))
        # crx2 = max(0, min(rx2, img_w))
        # cry2 = max(0, min(ry2, img_h))

        # Check scale validity before division
        if self.scale_x <= 0 or self.scale_y <= 0:
             print("Error: Invalid display scale factor.")
             if self.using_snapshot: self.return_to_live()
             return

        # Convert clamped relative coordinates to original frame coordinates
        ox1 = int(rx1 / self.scale_x)
        oy1 = int(ry1 / self.scale_y)
        ox2 = int(rx2 / self.scale_x)
        oy2 = int(ry2 / self.scale_y)

        # Final check on original coordinates size
        if abs(ox2 - ox1) < 1 or abs(oy2 - oy1) < 1:
             messagebox.showwarning("ROI Too Small", "Calculated ROI size is too small in original image.", parent=self.master)
             if self.using_snapshot: self.return_to_live()
             return

        new_roi = ROI(roi_name, ox1, oy1, ox2, oy2)

        if overwrite_name:
            self.rois = [r for r in self.rois if r.name != overwrite_name]
            # Overwriting: Keep existing overlay settings unless explicitly reset?
            # Or clear them? Let's keep them for now.
            # if hasattr(self, "overlay_manager"):
            #     all_settings = get_setting("overlay_settings", {})
            #     if overwrite_name in all_settings:
            #         del all_settings[overwrite_name]
            #     update_settings({"overlay_settings": all_settings})
            #     self.overlay_manager.destroy_overlay(overwrite_name) # Destroy old overlay if needed

        self.rois.append(new_roi)
        print(f"Created/Updated ROI: {new_roi.to_dict()}")

        if hasattr(self, "roi_tab"):
            self.roi_tab.update_roi_list() # Update listbox
        self._draw_rois()  # Redraw ROIs on the snapshot
        action = "created" if not overwrite_name else "updated"
        self.update_status(f"ROI '{roi_name}' {action}. Remember to save.") # Remind user to save

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

        # Create or update overlay window for the new/modified ROI
        if hasattr(self, "overlay_manager"):
            self.overlay_manager.create_overlay_for_roi(new_roi)

        # Return to live view after successful ROI creation/update
        if self.using_snapshot:
            self.return_to_live()


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
            # Give capture thread time to stop before finalizing
            self.master.after(500, self.check_capture_stopped_and_close) # Increased delay slightly
        else:
            self._finalize_close()

    def check_capture_stopped_and_close(self):
        """Check if capture stopped before finalizing close."""
        if not self.capturing and (self.capture_thread is None or not self.capture_thread.is_alive()):
            self._finalize_close()
        else:
            # If still capturing, wait longer
            print("Waiting for capture thread to stop...")
            self.master.after(500, self.check_capture_stopped_and_close)

    def _finalize_close(self):
        """Final cleanup and destroy window."""
        print("Finalizing close...")
        self.capturing = False # Ensure flag is false
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
                        x_str, y_str = parts[1], parts[2]
                        # Validate they are numbers before saving
                        if x_str.isdigit() and y_str.isdigit():
                             set_setting("floating_controls_pos", f"{x_str},{y_str}")
                        else:
                             print(f"Warning: Invalid coordinates in floating controls geometry: {geo}")
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
            pass # Ignore errors if already destroyed
        except Exception as e:
            print(f"Error during final destruction: {e}")

# --- END OF FILE app.py ---
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
from utils.config import save_translation_presets, load_translation_presets, _get_game_hash # Import _get_game_hash
from utils.settings import get_setting, set_setting, update_settings # Import settings functions

# Default presets configuration (remains the same)
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
        # self.additional_context = get_setting("additional_context", "") # REMOVED - now game specific
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

        # Additional context (Now game-specific, loaded dynamically)
        ttk.Label(self.basic_frame, text="Additional Context (Game Specific):", anchor=tk.NW).grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        self.additional_context_text = tk.Text(self.basic_frame, width=40, height=5, wrap=tk.WORD)
        self.additional_context_text.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=5) # Expand fully
        scroll_ctx = ttk.Scrollbar(self.basic_frame, command=self.additional_context_text.yview)
        scroll_ctx.grid(row=1, column=2, sticky=tk.NS, pady=5)
        self.additional_context_text.config(yscrollcommand=scroll_ctx.set)
        # self.additional_context_text.insert("1.0", self.additional_context) # REMOVED - loaded by app
        # Bind to game-specific save function
        self.additional_context_text.bind("<FocusOut>", self.save_context_for_current_game)
        # Use Shift+Return to insert newline, regular Return to save
        self.additional_context_text.bind("<Return>", self.save_context_for_current_game)
        self.additional_context_text.bind("<Shift-Return>", lambda e: self.additional_context_text.insert(tk.INSERT, '\n'))


        # Make context column expandable
        self.basic_frame.columnconfigure(1, weight=1)
        self.basic_frame.rowconfigure(1, weight=1) # Allow context text to expand vertically


        # === Preset Settings Tab === (No changes needed here)
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

        self.reset_context_btn = ttk.Button(cache_context_frame, text="Reset Translation Context", command=self.reset_translation_context) # Command updated below
        self.reset_context_btn.pack(side=tk.TOP, padx=5, pady=(5,2), anchor=tk.W) # Add some top padding

        # --- Translate Buttons (Grouped) ---
        translate_btn_frame = ttk.Frame(action_frame)
        translate_btn_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        self.translate_btn = ttk.Button(translate_btn_frame, text="Translate", command=self.perform_translation)
        self.translate_btn.pack(side=tk.LEFT, padx=(0, 2)) # Normal translate

        self.force_translate_btn = ttk.Button(translate_btn_frame, text="Force Retranslate", command=self.perform_force_translation)
        self.force_translate_btn.pack(side=tk.LEFT, padx=(2, 0)) # Force retranslate


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

    def load_context_for_game(self, context_text):
        """Loads the game-specific context into the text widget."""
        try:
            # Ensure widget exists before modifying
            if not self.additional_context_text.winfo_exists():
                return
            self.additional_context_text.config(state=tk.NORMAL)
            self.additional_context_text.delete("1.0", tk.END)
            if context_text:
                self.additional_context_text.insert("1.0", context_text)
            # Keep state normal for editing
            # self.additional_context_text.config(state=tk.DISABLED) # Keep editable
        except tk.TclError:
            print("Error updating context text widget (might be destroyed).")
        except Exception as e:
            print(f"Unexpected error loading context: {e}")


    def save_context_for_current_game(self, event=None):
        """Save the content of the context text widget for the current game."""
        # Prevent saving if Return was pressed without Shift
        if event and event.keysym == 'Return' and not (event.state & 0x0001): # Check if Shift key is NOT pressed
             # We want Shift+Return to insert newline, regular Return saves
             pass # Proceed to save
        elif event and event.keysym == 'Return':
             return "break" # Prevent default Return behavior (newline insertion) if Shift is pressed

        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            # Don't save if no game is selected
            # print("Cannot save context: No game selected.")
            return

        game_hash = _get_game_hash(current_hwnd)
        if not game_hash:
            print("Cannot save context: Could not get game hash.")
            return

        try:
            # Ensure widget exists
            if not self.additional_context_text.winfo_exists():
                return

            new_context = self.additional_context_text.get("1.0", tk.END).strip()

            all_game_contexts = get_setting("game_specific_context", {})
            # Only save if context actually changed
            if all_game_contexts.get(game_hash) != new_context:
                all_game_contexts[game_hash] = new_context
                if update_settings({"game_specific_context": all_game_contexts}):
                    print(f"Game-specific context saved for hash {game_hash[:8]}...")
                    self.app.update_status("Game context saved.")
                else:
                    messagebox.showerror("Error", "Failed to save game-specific context.")
            # else:
                # print("Context unchanged, not saving.") # Optional debug message

        except tk.TclError:
             print("Error accessing context text widget (might be destroyed).")
        except Exception as e:
             print(f"Error saving game context: {e}")
             messagebox.showerror("Error", f"Failed to save game context: {e}")

        # Important for Return binding: prevent default newline insertion after saving
        if event and event.keysym == 'Return':
            return "break"


    def save_basic_settings(self, event=None):
        """Save non-preset, non-game-specific settings like target language."""
        new_target_lang = self.target_lang_entry.get().strip()
        # Context is now saved separately by save_context_for_current_game

        settings_to_update = {}
        changed = False
        if new_target_lang != self.target_language:
            settings_to_update["target_language"] = new_target_lang
            self.target_language = new_target_lang
            changed = True

        if changed and settings_to_update:
            if update_settings(settings_to_update):
                print("General translation settings (language) updated.")
                self.app.update_status("Target language saved.")
            else:
                messagebox.showerror("Error", "Failed to save target language setting.")


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
        """Get the current translation preset AND general settings (including current game context)."""
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
        except tk.TclError: # Handle case where UI elements might be destroyed
             messagebox.showerror("Error", "UI elements missing. Cannot read preset details.", parent=self.app.master)
             return None


        # --- Get general settings from UI / saved state ---
        target_lang = self.target_lang_entry.get().strip()
        # --- Get current context directly from the text widget ---
        try:
            additional_ctx = self.additional_context_text.get("1.0", tk.END).strip()
        except tk.TclError:
             additional_ctx = "" # Handle case where widget might be destroyed

        # --- Combine into a working configuration ---
        # Use the preset settings currently displayed in the UI
        working_config = preset_config_from_ui
        # Add the non-preset settings
        working_config["target_language"] = target_lang
        working_config["additional_context"] = additional_ctx # Use current value from widget

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
        """Load the selected preset into the UI fields."""
        preset_name = self.preset_combo.get()
        if not preset_name or preset_name not in self.translation_presets:
            # Keep current UI values if selection is invalid
            print(f"Invalid preset selected: {preset_name}")
            return

        preset = self.translation_presets[preset_name]
        print(f"Loading preset '{preset_name}' into UI.")

        try:
            # --- Load preset values into UI ---
            # ALWAYS load the saved API key for the selected preset
            preset_api_key = preset.get("api_key", "")
            self.api_key_entry.delete(0, tk.END)
            self.api_key_entry.insert(0, preset_api_key) # Changed logic here

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
        except tk.TclError:
             print("Error updating preset UI elements (might be destroyed).")


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
        except tk.TclError:
             messagebox.showerror("Error", "UI elements missing. Cannot read preset details.", parent=self.app.master)
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


    def _start_translation_thread(self, force_recache=False):
        """Internal helper to start the translation thread."""
        config = self.get_translation_config()
        if config is None:
            print("Translation cancelled due to configuration error.")
            self.app.update_status("Translation cancelled: Configuration error.")
            return

        current_hwnd = self.app.selected_hwnd
        if not current_hwnd:
            messagebox.showwarning("Warning", "No game window selected. Cannot translate.", parent=self.app.master)
            self.app.update_status("Translation cancelled: No window selected.")
            return

        texts_to_translate = {name: text for name, text in self.app.stable_texts.items() if text and text.strip()}
        if not texts_to_translate:
            print("No stable text available to translate.")
            self.app.update_status("No stable text to translate.")
            try: # Protect UI updates
                if self.translation_display.winfo_exists():
                    self.translation_display.config(state=tk.NORMAL)
                    self.translation_display.delete(1.0, tk.END)
                    self.translation_display.insert(tk.END, "[No stable text detected]")
                    self.translation_display.config(state=tk.DISABLED)
            except tk.TclError: pass
            if hasattr(self.app, 'overlay_manager'):
                self.app.overlay_manager.clear_all_overlays()
            return

        aggregated_input_text = "\n".join([f"[{name}]: {text}" for name, text in texts_to_translate.items()])

        status_msg = "Translating..." if not force_recache else "Forcing retranslation..."
        self.app.update_status(status_msg)
        try: # Protect UI updates
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, f"{status_msg}\n")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError: pass

        if hasattr(self.app, 'overlay_manager'):
            for roi_name in texts_to_translate:
                self.app.overlay_manager.update_overlay(roi_name, "...")

        def translation_thread():
            try:
                translated_segments = translate_text(
                    aggregated_input_text=aggregated_input_text,
                    hwnd=current_hwnd,
                    preset=config,
                    target_language=config["target_language"],
                    additional_context=config["additional_context"], # Context from widget passed in config
                    context_limit=config.get("context_limit", 10),
                    force_recache=force_recache # Pass the flag
                )

                if "error" in translated_segments:
                    error_msg = translated_segments["error"]
                    print(f"Translation API Error: {error_msg}")
                    self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                    if hasattr(self.app, 'overlay_manager'):
                        first_roi = next(iter(texts_to_translate), None)
                        if first_roi:
                            self.app.master.after_idle(lambda name=first_roi: self.app.overlay_manager.update_overlay(name, f"Error!"))
                            for r_name in texts_to_translate:
                                if r_name != first_roi:
                                    self.app.master.after_idle(lambda n=r_name: self.app.overlay_manager.update_overlay(n, ""))
                else:
                    print("Translation successful.")
                    preview_lines = []
                    # Use app's current ROI order for consistency
                    rois_to_iterate = self.app.rois if hasattr(self.app, 'rois') else []
                    for roi in rois_to_iterate:
                        roi_name = roi.name
                        original_text = self.app.stable_texts.get(roi_name, "")
                        translated_text = translated_segments.get(roi_name)
                        if original_text.strip():
                            preview_lines.append(f"[{roi_name}]:")
                            preview_lines.append(translated_text if translated_text else "[Translation N/A]")
                            preview_lines.append("")
                    preview_text = "\n".join(preview_lines).strip()
                    self.app.master.after_idle(lambda seg=translated_segments, prev=preview_text: self.update_translation_results(seg, prev))

            except Exception as e:
                error_msg = f"Unexpected error during translation thread: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                self.app.master.after_idle(lambda: self.update_translation_display_error(error_msg))
                if hasattr(self.app, 'overlay_manager'):
                    self.app.master.after_idle(self.app.overlay_manager.clear_all_overlays)

        threading.Thread(target=translation_thread, daemon=True).start()


    def perform_translation(self):
        """Translate the stable text using the current settings (uses cache)."""
        self._start_translation_thread(force_recache=False)

    def perform_force_translation(self):
        """Force re-translation of the stable text, skipping cache check but updating cache."""
        self._start_translation_thread(force_recache=True)


    def update_translation_results(self, translated_segments, preview_text):
        """Update the preview display and overlays with translation results. Runs in main thread."""
        self.app.update_status("Translation complete.")
        # Update preview text box
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, preview_text if preview_text else "[No translation received]")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError: pass # Ignore if destroyed

        # Update overlays
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.update_overlays(translated_segments)

        # Store last successful translation for potential re-translation/copy
        self.last_translation_result = translated_segments
        self.last_translation_input = self.app.stable_texts.copy() # Store the input that led to this


    def update_translation_display_error(self, error_message):
        """Update the preview display with an error message. Runs in main thread."""
        self.app.update_status(f"Translation Error: {error_message[:50]}...") # Show snippet in status
        try:
            if self.translation_display.winfo_exists():
                self.translation_display.config(state=tk.NORMAL)
                self.translation_display.delete(1.0, tk.END)
                self.translation_display.insert(tk.END, f"Translation Error:\n\n{error_message}")
                self.translation_display.config(state=tk.DISABLED)
        except tk.TclError: pass # Ignore if destroyed
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
        """Reset the translation context history and delete the file for the current game."""
        current_hwnd = self.app.selected_hwnd
        # Ask for confirmation
        if messagebox.askyesno("Confirm Reset Context", "Are you sure you want to reset the translation context history for the current game?\n(This will delete the saved history file)", parent=self.app.master):
            result = reset_context(current_hwnd) # Pass hwnd to delete the correct file
            messagebox.showinfo("Context Reset", result, parent=self.app.master)
            self.app.update_status("Translation context reset.")

# --- END OF FILE ui/translation_tab.py ---
```

With these changes, the context history (`context_messages`) will be loaded from a game-specific file when a window is selected, used (but not modified with `additional_context`) during API calls, updated only if the input text differs from the last entry, saved back to the file after a successful translation, and deleted when the "Reset Translation Context" button is pressed.