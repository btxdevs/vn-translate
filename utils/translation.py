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

# Context management (global list)
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

# --- Cache and Context Functions (Mostly unchanged, added logging to add_context_message) ---

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
    current_length = len(context_messages)

    if current_length > max_messages:
        context_messages = context_messages[-max_messages:]
        new_length = len(context_messages)
        # Log the trimming action
        print(f"[CONTEXT] History limit ({max_messages} msgs / {limit} exchanges) exceeded ({current_length} msgs). Trimmed to {new_length}.")
    # else:
    # Optional: Log when context is added but not trimmed
    # print(f"[CONTEXT] Added message. History length: {current_length}/{max_messages}")


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
            print("[LLM PARSE] Failed to parse any <|n|> segments from response.")
            # print(f"Raw Response: '{response_text}'") # Logged elsewhere now
            # Attempt a very basic extraction if response is just plain text (single segment case?)
            if not response_text.startswith("<|") and len(original_tag_mapping) == 1:
                first_tag = next(iter(original_tag_mapping))
                first_roi = original_tag_mapping[first_tag]
                print(f"[LLM PARSE] Warning: Response had no tags, assuming plain text response for single ROI '{first_roi}'.")
                parsed_segments[first_roi] = response_text.strip()
            else:
                # Only return error if it's not a single segment plain text response
                return {"error": f"Error: Unable to extract formatted translation.\nRaw response:\n{response_text}"}


    # Check if all original tags were translated
    missing_tags = set(original_tag_mapping.values()) - set(parsed_segments.keys())
    if missing_tags:
        print(f"[LLM PARSE] Warning: Translation response missing segments for ROIs: {', '.join(missing_tags)}")
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


def translate_text(aggregated_input_text, hwnd, preset, target_language="en", additional_context="", context_limit=10, force_recache=False):
    """
    Translate the given text using an OpenAI-compatible API client, using game-specific caching.

    Args:
        aggregated_input_text: Text in "[ROI_Name]: Content" format.
        hwnd: The window handle of the game (used for cache identification).
        preset: The translation preset configuration (LLM specific parts).
        target_language: The target language code (e.g., "en", "Spanish").
        additional_context: General instructions or context from the UI (used only for the current call).
        context_limit: Max number of conversational exchanges (user+assistant pairs) to keep in history.
        force_recache: If True, skip cache check and force API call, then update cache.

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

    # 2. Check Cache (Using simplified key), skip if force_recache is True
    cache_key = get_cache_key(preprocessed_text_for_llm, target_language)
    if not force_recache:
        cached_result = get_cached_translation(cache_key, cache_file_path)
        if cached_result:
            print(f"[CACHE] HIT for key: {cache_key[:10]}... in {cache_file_path.name}")
            # Ensure cache returns the expected format (roi_name -> translation)
            if isinstance(cached_result, dict) and not 'error' in cached_result:
                # Quick check: does cached result contain keys for current request?
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
    # Refined System Prompt for clarity
    system_content = (
        f"{system_prompt}\n\n"
        f"Translate the following text segments into {target_language}. "
        "Input segments are tagged like <|1|>, <|2|>, etc. "
        "Your response MUST replicate this format exactly, using the same tags for the corresponding translated segments. "
        "For example, input '<|1|> Hello\n<|2|> World' requires output '<|1|> [Translation of Hello]\n<|2|> [Translation of World]'. "
        "Output ONLY the tagged translated lines. Do NOT add introductions, explanations, apologies, or any text outside the <|n|> tags."
    )
    system_message = {"role": "system", "content": system_content}

    # Get context history (if any) - make a copy
    global context_messages
    history_to_send = list(context_messages)

    # --- Construct the CURRENT user message WITH additional_context ---
    current_user_message_parts = []
    if additional_context.strip():
        current_user_message_parts.append(f"{additional_context.strip()}")
    # The core request
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
    # --- End Update Context ---

    # Add/Update cache using the key generated earlier and the game-specific file
    # This happens regardless of force_recache flag or history update skip, overwriting previous entry
    set_cache_translation(cache_key, final_translations, cache_file_path)
    print(f"[CACHE] Translation cached/updated successfully in {cache_file_path.name}")

    return final_translations

# --- END OF FILE utils/translation.py ---