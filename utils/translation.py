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
    content_display = content.replace('\n', '\\n')
    return f"[{role}] '{content_display}'"

# --- Directory and Hashing ---

def _ensure_cache_dir():
    """Make sure the cache directory exists"""
    try: CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e: print(f"Error creating cache directory {CACHE_DIR}: {e}")

def _ensure_context_dir():
    """Make sure the context history directory exists"""
    try: CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e: print(f"Error creating context directory {CONTEXT_DIR}: {e}")

def _get_game_hash(hwnd):
    """Generates a hash based on the game's executable path and size."""
    if not hwnd: return None
    exe_path, file_size = get_executable_details(hwnd)
    if exe_path and file_size is not None:
        try:
            identity_string = f"{os.path.normpath(exe_path).lower()}|{file_size}"
            hasher = hashlib.sha256()
            hasher.update(identity_string.encode('utf-8'))
            return hasher.hexdigest()
        except Exception as e: print(f"Error generating game hash: {e}")
    return None

def _get_cache_file_path(hwnd):
    """Gets the specific cache file path for the given game window."""
    if hwnd is None: return None
    game_hash = _get_game_hash(hwnd)
    if game_hash: return CACHE_DIR / f"{game_hash}.json"
    else: print("Warning: Could not determine game hash. Using default cache file."); return CACHE_DIR / "default_cache.json"

def _get_context_file_path(hwnd):
    """Gets the specific context history file path for the given game window."""
    if hwnd is None: return None
    game_hash = _get_game_hash(hwnd)
    if game_hash: return CONTEXT_DIR / f"{game_hash}_context.json"
    else: print("Warning: Could not determine game hash for context file path."); return None

# --- Cache Handling ---

def _load_cache(cache_file_path):
    """Load the translation cache from the specified game file"""
    _ensure_cache_dir()
    try:
        if cache_file_path.exists():
            with open(cache_file_path, 'r', encoding='utf-8') as f: content = f.read()
            if not content: return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"Warning: Cache file {cache_file_path} is corrupted or empty. Starting fresh cache.")
        try:
            corrupted_path = cache_file_path.parent / f"{cache_file_path.name}.corrupted_{int(time.time())}"
            os.rename(cache_file_path, corrupted_path)
            print(f"Corrupted cache backed up to {corrupted_path}")
        except Exception as backup_err: print(f"Error backing up corrupted cache file: {backup_err}")
        return {}
    except Exception as e: print(f"Error loading cache from {cache_file_path}: {e}")
    return {}

def _save_cache(cache, cache_file_path):
    """Save the translation cache to the specified game file"""
    _ensure_cache_dir()
    try:
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"Error saving cache to {cache_file_path}: {e}")

def clear_current_game_cache(hwnd):
    """Clear the translation cache for the currently selected game."""
    cache_file_path = _get_cache_file_path(hwnd)
    if not cache_file_path: return "Could not identify game to clear cache (or cache skipped)."
    if cache_file_path.exists():
        try:
            os.remove(cache_file_path)
            print(f"Cache file deleted: {cache_file_path}")
            return f"Cache cleared for the current game ({cache_file_path.stem})."
        except Exception as e: print(f"Error deleting cache file {cache_file_path}: {e}"); return f"Error clearing current game cache: {e}"
    else: print(f"Cache file not found for current game: {cache_file_path}"); return "Cache for the current game was already empty."

def clear_all_cache():
    """Clear all translation cache files in the cache directory."""
    _ensure_cache_dir()
    cleared_count = 0
    errors = []
    try:
        for item in CACHE_DIR.iterdir():
            if item.is_file() and item.suffix == '.json':
                try: os.remove(item); cleared_count += 1; print(f"Deleted cache file: {item.name}")
                except Exception as e: errors.append(item.name); print(f"Error deleting cache file {item.name}: {e}")
        if errors: return f"Cleared {cleared_count} cache files. Errors deleting: {', '.join(errors)}."
        elif cleared_count > 0: return f"Successfully cleared all {cleared_count} translation cache files."
        else: return "Cache directory was empty or contained no cache files."
    except Exception as e: print(f"Error iterating cache directory {CACHE_DIR}: {e}"); return f"Error accessing cache directory: {e}"

# --- Context History Handling ---

def _load_context(hwnd):
    """Loads context history from the game-specific file into the global list."""
    global context_messages
    context_messages = []
    if hwnd is None: print("[CONTEXT] HWND is None, skipping context load."); return
    _ensure_context_dir()
    context_file_path = _get_context_file_path(hwnd)
    if not context_file_path: print("[CONTEXT] Cannot load context, failed to get file path."); return
    if context_file_path.exists():
        try:
            with open(context_file_path, 'r', encoding='utf-8') as f: content = f.read()
            if content:
                loaded_history = json.loads(content)
                if isinstance(loaded_history, list):
                    context_messages = loaded_history
                    print(f"[CONTEXT] Loaded {len(context_messages)} messages from {context_file_path.name}")
                else: print(f"[CONTEXT] Error: Loaded context from {context_file_path.name} is not a list. Resetting history.")
            else: print(f"[CONTEXT] Context file {context_file_path.name} is empty.")
        except json.JSONDecodeError: print(f"[CONTEXT] Error: Context file {context_file_path.name} is corrupted. Resetting history.")
        except Exception as e: print(f"[CONTEXT] Error loading context from {context_file_path.name}: {e}. Resetting history.")
    else: print(f"[CONTEXT] No context file found for current game ({context_file_path.name}). Starting fresh history.")

def _save_context(hwnd):
    """Saves the current global context_messages (full history) to the game-specific file."""
    global context_messages
    if hwnd is None: return
    _ensure_context_dir()
    context_file_path = _get_context_file_path(hwnd)
    if not context_file_path: print("[CONTEXT] Cannot save context, failed to get file path."); return
    try:
        with open(context_file_path, 'w', encoding='utf-8') as f:
            # Save the entire context_messages list
            json.dump(context_messages, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"Error saving context to {context_file_path.name}: {e}")

def reset_context(hwnd):
    """Reset the global translation context history AND delete the game-specific file."""
    global context_messages
    context_messages = []
    print("[CONTEXT] In-memory context history reset.")
    if hwnd is None: return "Context history reset (no game specified to delete file)."
    context_file_path = _get_context_file_path(hwnd)
    if context_file_path and context_file_path.exists():
        try:
            os.remove(context_file_path)
            print(f"[CONTEXT] Deleted context file: {context_file_path.name}")
            return "Translation context history reset and file deleted."
        except Exception as e: print(f"[CONTEXT] Error deleting context file {context_file_path.name}: {e}"); return f"Context history reset, but error deleting file: {e}"
    elif context_file_path: return "Context history reset (no file found to delete)."
    else: return "Context history reset (could not determine file path)."

# MODIFIED add_context_message
def add_context_message(message):
    """Add a message to the global translation context history. No trimming here."""
    global context_messages
    context_messages.append(message)
    # No trimming logic here - the full history is maintained in context_messages

# --- Translation Core Logic ---

def get_cache_key(text, target_language):
    """Generate a unique cache key based ONLY on the input text and target language."""
    hasher = hashlib.sha256()
    # Normalize newlines in text for consistent hashing
    normalized_text = text.replace('\r\n', '\n').replace('\r', '\n')
    hasher.update(normalized_text.encode('utf-8'))
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

# MODIFIED parse_translation_output
def parse_translation_output(response_text, original_tag_mapping):
    """
    Parse the translation output from a tagged format (<|n|>)
    and map it back to the original ROI names using the tag_mapping.
    Improved handling of newlines and whitespace.
    """
    parsed_segments = {}
    # Pattern to capture tag number and content until the next tag or end of string
    # DOTALL allows '.' to match newlines. Non-greedy '.*?' is crucial.
    pattern = r"<\|(\d+)\|>(.*?)(?=<\|\d+\|>|$)"
    matches = re.findall(pattern, response_text, re.DOTALL) # Removed MULTILINE, DOTALL is key

    if matches:
        print(f"[LLM PARSE] Found {len(matches)} segments using main pattern.")
        for segment_number, content in matches:
            original_roi_name = original_tag_mapping.get(segment_number)
            if original_roi_name:
                # 1. Normalize newlines (\r\n or \r -> \n)
                normalized_content = content.replace('\r\n', '\n').replace('\r', '\n')
                # 2. Strip leading/trailing whitespace ONLY (including spaces, tabs, newlines)
                #    Do NOT strip internal newlines here.
                cleaned_content = normalized_content.strip()
                # 3. Remove potential trailing tag from the current segment's content (less likely now)
                cleaned_content = re.sub(r'<\|\d+\|>\s*$', '', cleaned_content).rstrip()

                # print(f"[LLM PARSE DEBUG] Raw content for <|{segment_number}|>: {repr(content)}")
                # print(f"[LLM PARSE DEBUG] Cleaned content for {original_roi_name}: {repr(cleaned_content)}")
                parsed_segments[original_roi_name] = cleaned_content
            else:
                print(f"Warning: Received segment number '{segment_number}' which was not in the original mapping.")
    else:
        # Fallback: Try line-based parsing (less reliable for multi-line content)
        print("[LLM PARSE] Main pattern failed, attempting line-based fallback...")
        line_pattern = r"^\s*<\|(\d+)\|>\s*(.*)$"
        lines = response_text.strip().split('\n')
        found_line_match = False
        current_roi_name = None
        current_content = []
        for line in lines:
            match = re.match(line_pattern, line)
            if match:
                # Finish previous segment if any
                if current_roi_name and current_content:
                    parsed_segments[current_roi_name] = "\n".join(current_content).strip()
                    found_line_match = True

                # Start new segment
                segment_number, content_part = match.groups()
                current_roi_name = original_tag_mapping.get(segment_number)
                if current_roi_name:
                    current_content = [content_part.strip()] # Start new content list
                else:
                    print(f"Warning: Received segment number '{segment_number}' (line match) which was not in original mapping.")
                    current_roi_name = None # Ignore content until next valid tag
                    current_content = []
            elif current_roi_name:
                # Append line to current segment if it doesn't start with a tag
                current_content.append(line.strip())

        # Add the last segment found
        if current_roi_name and current_content:
            parsed_segments[current_roi_name] = "\n".join(current_content).strip()
            found_line_match = True

        # If still no matches and only one ROI was expected, assume plain text response
        if not found_line_match and len(original_tag_mapping) == 1 and not response_text.startswith("<|"):
            first_tag = next(iter(original_tag_mapping))
            first_roi = original_tag_mapping[first_tag]
            print(f"[LLM PARSE] Warning: No tags found, assuming plain text response for single ROI '{first_roi}'.")
            # Normalize and strip the whole response
            normalized_response = response_text.replace('\r\n', '\n').replace('\r', '\n')
            parsed_segments[first_roi] = normalized_response.strip()
            found_line_match = True # Mark as found to avoid error message

        if not found_line_match:
            # If multiple ROIs were expected but no tags found by either method
            print("[LLM PARSE] Failed to parse any <|n|> segments from response.")
            # Return error with raw response for debugging
            raw_preview = response_text[:200] + ('...' if len(response_text) > 200 else '')
            return {"error": f"Error: Unable to extract formatted translation.\nRaw response (start):\n{raw_preview}"}

    # Check for missing ROIs compared to the original input
    missing_rois = set(original_tag_mapping.values()) - set(parsed_segments.keys())
    if missing_rois:
        print(f"[LLM PARSE] Warning: Translation response missing segments for ROIs: {', '.join(missing_rois)}")
        for roi_name in missing_rois:
            parsed_segments[roi_name] = "[Translation Missing]" # Add placeholder

    # Final check if parsing completely failed (should be caught earlier now)
    if not parsed_segments and original_tag_mapping:
        print("[LLM PARSE] Error: Failed to parse any segments despite expecting tags.")
        raw_preview = response_text[:200] + ('...' if len(response_text) > 200 else '')
        return {"error": f"Error: Failed to extract any segments.\nRaw response (start):\n{raw_preview}"}

    return parsed_segments


# MODIFIED preprocess_text_for_translation
def preprocess_text_for_translation(stable_texts_dict):
    """
    Convert input dictionary {roi_name: text} to the numbered format <|1|> text.
    Handles multi-line text within each ROI's content correctly.
    Returns the preprocessed string and the tag mapping.
    """
    preprocessed_lines = []
    tag_mapping = {}
    segment_count = 1

    # Iterate through the dictionary items directly
    # Ensure consistent order for cache key generation (sort by ROI name)
    sorted_roi_names = sorted(stable_texts_dict.keys())

    for roi_name in sorted_roi_names:
        content = stable_texts_dict[roi_name]
        # Normalize newlines first
        normalized_content = content.replace('\r\n', '\n').replace('\r', '\n') if content else ""
        content_stripped = normalized_content.strip() # Strip leading/trailing whitespace/newlines

        if content_stripped: # Only process if content is not empty after stripping
            tag_mapping[str(segment_count)] = roi_name
            # Append the stripped content (preserving internal newlines) with the tag
            preprocessed_lines.append(f"<|{segment_count}|> {content_stripped}")
            segment_count += 1
        else:
            print(f"Skipping empty content for ROI: {roi_name}")

    if not tag_mapping:
        print("Warning: No non-empty text found in input dictionary during preprocessing.")

    # Join the processed lines with newlines for the final string
    return '\n'.join(preprocessed_lines), tag_mapping

# MODIFIED translate_text function signature and preprocessing call
def translate_text(stable_texts_dict, hwnd, preset, target_language="en", additional_context="", context_limit=10, force_recache=False, skip_cache=False, skip_history=False):
    """
    Translate the given text segments (from a dictionary) using an OpenAI-compatible API client,
    using game-specific caching and context. System prompt is constructed internally.
    Context history sent to the API is limited by context_limit.
    """
    cache_file_path = None if skip_cache else _get_cache_file_path(hwnd)
    if not skip_cache and not cache_file_path and hwnd is not None:
        print("Error: Cannot proceed with cached translation without a valid game identifier.")
        return {"error": "Could not determine cache file path for the game."}

    # Preprocess the input dictionary into the tagged string format
    preprocessed_text_for_llm, tag_mapping = preprocess_text_for_translation(stable_texts_dict)

    if not preprocessed_text_for_llm or not tag_mapping:
        print("No valid text segments found after preprocessing. Nothing to translate.")
        return {} # Return empty dict if nothing to translate

    # Cache key is based on the preprocessed text (what the LLM sees) and target language
    cache_key = get_cache_key(preprocessed_text_for_llm, target_language)

    # --- Cache Check ---
    if not skip_cache and not force_recache:
        cached_result = get_cached_translation(cache_key, cache_file_path)
        if cached_result:
            # Validate cache integrity (ensure all expected ROIs are present)
            if isinstance(cached_result, dict) and not 'error' in cached_result:
                # Check if all ROI names from the *original input* (that had text) are keys in the cached result
                expected_rois = {name for name, text in stable_texts_dict.items() if text and text.strip()}
                if expected_rois.issubset(cached_result.keys()):
                    print(f"[CACHE] HIT for key: {cache_key[:10]}... in {cache_file_path.name if cache_file_path else 'N/A'}")
                    return cached_result
                else:
                    print("[CACHE] WARN: Cached result incomplete or missing expected ROIs, fetching fresh translation.")
                    print(f"[CACHE DEBUG] Expected: {expected_rois}, Cached keys: {set(cached_result.keys())}")
            else:
                print("[CACHE] WARN: Cached result format mismatch or error, fetching fresh translation.")
        else:
            print(f"[CACHE] MISS for key: {cache_key[:10]}... in {cache_file_path.name if cache_file_path else 'N/A'}")
    elif skip_cache: print(f"[CACHE] SKIP requested (skip_cache=True)")
    elif force_recache: print(f"[CACHE] SKIP requested (force_recache=True) for key: {cache_key[:10]}...")
    # --- End Cache Check ---


    # --- Construct System Prompt Internally ---
    base_system_prompt = (
        "You are a professional translation assistant. Your task is to translate text segments accurately "
        "from their source language into the target language specified in the user prompt. "
        "The input text segments are marked with tags like <|1|>, <|2|>, etc. "
        "Your response MUST strictly adhere to this format, reproducing the exact same tags for each corresponding translated segment. "
        "For example, if the input is '<|1|> Hello\n<|2|> World' and the target language is French, the output must be '<|1|> Bonjour\n<|2|> Le monde'. "
        "Do NOT include ANY extra text, commentary, explanations, greetings, summaries, apologies, or any conversational filler before, between, or after the tagged translations."
    )
    system_content = base_system_prompt
    system_message = {"role": "system", "content": system_content}
    # --- End System Prompt Construction ---

    # --- Prepare Context History for API Call (Apply Limit) ---
    history_to_send = []
    if not skip_history:
        global context_messages # Use the full history stored globally
        try:
            # Use the context_limit passed to this function (originating from the preset)
            limit_exchanges = int(context_limit)
            limit_exchanges = max(1, limit_exchanges) # Ensure at least 1 exchange
        except (ValueError, TypeError):
            limit_exchanges = 10 # Fallback default if invalid
            print(f"[CONTEXT] Warning: Invalid context_limit value '{context_limit}'. Using default: {limit_exchanges}")

        # Calculate the number of messages (user + assistant) to send based on the exchange limit
        max_messages_to_send = limit_exchanges * 2

        # Slice the global context_messages list to get only the most recent messages
        if len(context_messages) > max_messages_to_send:
            # Select the last 'max_messages_to_send' items from the full history
            history_to_send = context_messages[-max_messages_to_send:]
            print(f"[CONTEXT] Sending last {len(history_to_send)} messages ({limit_exchanges} exchanges limit) to API.")
        else:
            # Send the entire history if it's shorter than the limit
            history_to_send = list(context_messages)
            print(f"[CONTEXT] Sending all {len(history_to_send)} available messages (within {limit_exchanges} exchanges limit) to API.")
    # --- End Context History Preparation ---

    # --- Construct User Message for API ---
    current_user_message_parts = []
    if additional_context.strip():
        current_user_message_parts.append(f"Additional context for this translation: {additional_context.strip()}")
    current_user_message_parts.append(f"Translate the following segments into {target_language}, maintaining the exact <|n|> tags:")
    # Use the preprocessed text string here
    current_user_message_parts.append(preprocessed_text_for_llm)
    current_user_content_with_context = "\n\n".join(current_user_message_parts)
    current_user_message_for_api = {"role": "user", "content": current_user_content_with_context}
    # --- End Construct User Message ---

    # Prepare the user message that will be *added* to the full history (without additional context)
    history_user_message = None
    if not skip_history:
        history_user_message_parts = [
            f"Translate the following segments into {target_language}, maintaining the exact <|n|> tags:",
            preprocessed_text_for_llm # Use the same preprocessed text for history
        ]
        history_user_content = "\n\n".join(history_user_message_parts)
        history_user_message = {"role": "user", "content": history_user_content}

    # Construct the final list of messages for the API call (using the potentially sliced history_to_send)
    messages_for_api = [system_message] + history_to_send + [current_user_message_for_api]

    if not preset.get("model") or not preset.get("api_url"):
        missing = [f for f in ["model", "api_url"] if not preset.get(f)]
        errmsg = f"Missing required preset fields: {', '.join(missing)}"
        print(f"[API] Error: {errmsg}")
        return {"error": errmsg}

    payload = {
        "model": preset["model"], "messages": messages_for_api,
        "temperature": preset.get("temperature", 0.3), "max_tokens": preset.get("max_tokens", 1000)
    }
    for param in ["top_p", "frequency_penalty", "presence_penalty"]:
        if param in preset and preset[param] is not None:
            try: payload[param] = float(preset[param])
            except (ValueError, TypeError): print(f"Warning: Invalid value for parameter '{param}': {preset[param]}. Skipping.")

    print("-" * 20 + " LLM Request " + "-" * 20)
    print(f"[API] Endpoint: {preset.get('api_url')}")
    print(f"[API] Model: {preset['model']}")
    print(f"[API] Payload Parameters (excluding messages):")
    for key, value in payload.items():
        if key != "messages": print(f"  - {key}: {value}")
    print(f"[API] Messages ({len(messages_for_api)} total):")
    if messages_for_api[0]['role'] == 'system': print(f"  - [system] (Internal prompt used)")
    if history_to_send:
        # Log the number of messages *actually sent*
        print(f"  - [CONTEXT HISTORY - {len(history_to_send)} messages sent]:")
        for msg in history_to_send: print(f"    - {format_message_for_log(msg)}")
    print(f"  - {format_message_for_log(current_user_message_for_api)}")
    print("-" * 55)

    try:
        api_key = preset.get("api_key") or None
        client = OpenAI(base_url=preset.get("api_url"), api_key=api_key)
    except Exception as e: print(f"[API] Error creating API client: {e}"); return {"error": f"Error creating API client: {e}"}

    response_text = None
    try:
        completion = client.chat.completions.create(**payload)
        if not completion.choices or not completion.choices[0].message or completion.choices[0].message.content is None:
            print("[API] Error: Invalid response structure received from API.")
            try: print(f"[API] Raw Response Object: {completion}")
            except Exception as log_err: print(f"[API] Error logging raw response object: {log_err}")
            return {"error": "Invalid response structure received from API."}
        response_text = completion.choices[0].message.content # Keep original response text
        print("-" * 20 + " LLM Response " + "-" * 20)
        print(f"[API] Raw Response Text ({len(response_text)} chars):\n{response_text}")
        print("-" * 56)
    except APIError as e:
        error_message = str(e)
        status_code = getattr(e, 'status_code', 'N/A')
        try:
            error_body = json.loads(getattr(e, 'body', '{}') or '{}')
            detail = error_body.get('error', {}).get('message', '')
            if detail: error_message = detail
        except: pass
        log_msg = f"[API] APIError during translation request: Status {status_code}, Error: {error_message}"
        print(log_msg)
        print(f"[API] Request Model: {payload.get('model')}")
        return {"error": f"API Error ({status_code}): {error_message}"}
    except Exception as e:
        error_message = str(e)
        log_msg = f"[API] Error during translation request: {error_message}"
        print(log_msg)
        import traceback
        traceback.print_exc()
        return {"error": f"Error during API request: {error_message}"}

    # Parse the response using the original tag mapping
    # Pass the raw response_text here
    final_translations = parse_translation_output(response_text, tag_mapping)
    if 'error' in final_translations:
        print("[LLM PARSE] Parsing failed after receiving response.")
        return final_translations # Return the error dictionary

    # --- Add to Stored History (using history_user_message) ---
    # Use the raw response_text for the assistant message in history
    if not skip_history and history_user_message:
        add_to_history = True
        # Check if the exact same user input was the last user input in the *full stored* history
        if len(context_messages) >= 2:
            last_user_message_in_stored_history = context_messages[-2]
            if last_user_message_in_stored_history.get('role') == 'user':
                if last_user_message_in_stored_history.get('content') == history_user_message.get('content'):
                    add_to_history = False
                    print("[CONTEXT] Input identical to previous user message in stored history. Skipping history update.")

        if add_to_history:
            # Use the raw response_text here for accurate history
            current_assistant_message = {"role": "assistant", "content": response_text}
            # Add to the full global history list (no limit applied here)
            add_context_message(history_user_message)
            add_context_message(current_assistant_message)
            _save_context(hwnd) # Save the updated full history
    # --- End Add to Stored History ---

    # --- Cache the successful result ---
    if not skip_cache and cache_file_path:
        # Cache the parsed dictionary result, not the raw response
        set_cache_translation(cache_key, final_translations, cache_file_path)
        print(f"[CACHE] Translation cached/updated successfully in {cache_file_path.name}")
    elif not skip_cache and not cache_file_path:
        print("[CACHE] Warning: Could not cache translation (invalid path).")
    # --- End Cache ---

    return final_translations

# --- END OF FILE utils/translation.py ---