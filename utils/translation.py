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