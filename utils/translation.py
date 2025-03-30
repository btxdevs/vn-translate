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

# --- Few-Shot Examples ---
# Examples for ROI translation (Japanese -> English)
ROI_EXAMPLES_JA_EN = [
    { # Simple single lines
        "input": "<|1|> こんにちは世界\n<|2|> これはテストです。",
        "output": "<|1|> Hello World\n<|2|> This is a test."
    },
    { # Multiline within a single tag
        "input": "<|1|> これは最初の行です。\nこれは同じタグの二行目です。\n<|2|> これは別のタグです。",
        "output": "<|1|> This is the first line.\nThis is the second line of the same tag.\n<|2|> This is a different tag."
    },
    { # Another multiline example, potentially dialogue
        "input": "<|1|> 彼は彼女に近づき、囁いた。\n「愛してる…\nずっと前から。」",
        "output": "<|1|> He approached her and whispered.\n\"I love you...\nI have for a long time.\""
    },
    { # Example with potentially sensitive content
        "input": "<|1|> 何をしているんだ？\n<|2|> 馬鹿野郎！殺してやる！",
        "output": "<|1|> What are you doing?\n<|2|> You idiot! I'll kill you!"
    }
]

# Examples for Snip translation (Japanese -> English)
SNIP_EXAMPLES_JA_EN = [
    {
        "input": "疲れた…",
        "output": "I'm tired..."
    },
    {
        "input": "信じられない！",
        "output": "Unbelievable!"
    },
    { # Example with slightly sensitive (fictional violence) content
        "input": "絶対に許さない…殺してやる！",
        "output": "I'll never forgive you... I'll kill you!"
    }
]

# --- Logging Helper ---
def format_message_for_log(message):
    """Formats a message dictionary for concise logging."""
    role = message.get('role', 'unknown')
    content = message.get('content', '')
    content_display = content.replace('\n', '\\n')
    # Limit length for cleaner logs
    if len(content_display) > 150: # Increased limit slightly
        content_display = content_display[:150] + "..."
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
        # print(f"[LLM PARSE] Found {len(matches)} segments using main pattern.") # Less verbose log
        for segment_number, content in matches:
            original_roi_name = original_tag_mapping.get(segment_number)
            if original_roi_name:
                # 1. Normalize newlines (\r\n or \r -> \n)
                normalized_content = content.replace('\r\n', '\n').replace('\r', '\n')
                # 2. Strip leading/trailing whitespace ONLY (including spaces, tabs, newlines)
                cleaned_content = normalized_content.strip()
                # 3. Remove potential trailing tag from the current segment's content (less likely now)
                cleaned_content = re.sub(r'<\|\d+\|>\s*$', '', cleaned_content).rstrip()

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

# MODIFIED translate_text function signature and logic
def translate_text(stable_texts_dict, hwnd, preset, target_language="en", additional_context="", context_limit=10, force_recache=False, skip_cache=False, skip_history=False, user_comment=None, is_snip=False): # Added is_snip
    """
    Translate text using an OpenAI-compatible API client.
    Handles multi-segment ROI text (using <|n|> tags) or single-segment snip text.
    Uses game-specific caching and context history (limited by context_limit).
    A user_comment can be provided for transient guidance.
    Injects few-shot examples if context is short.
    Includes prompt modifications to reduce refusals for fictional content.
    Removes previous exchange from history sent to API if force_recache=True and input matches last input.
    """
    cache_file_path = None if skip_cache else _get_cache_file_path(hwnd)
    if not skip_cache and not cache_file_path and hwnd is not None and not is_snip: # Cache only for non-snip, non-skipped game translations
        print("Error: Cannot proceed with cached translation without a valid game identifier.")
        return {"error": "Could not determine cache file path for the game."}

    # --- Prepare Input Text and Cache Key ---
    text_to_translate = ""
    tag_mapping = {}
    cache_key = None
    source_language_hint = "Japanese" # Default hint, adjust if needed based on OCR lang

    if is_snip:
        # For snip, expect only one entry in the dictionary
        if len(stable_texts_dict) != 1:
            print(f"Error: Expected exactly one text entry for snip translation, got {len(stable_texts_dict)}")
            return {"error": "Invalid input for snip translation."}
        # Extract the raw text directly
        text_to_translate = next(iter(stable_texts_dict.values()), "").strip()
        if not text_to_translate:
            print("No text found in snip input.")
            return "" # Return empty string if snip text is empty
        # Snips are not cached, so cache_key remains None
        skip_cache = True
        skip_history = True
        print("[TRANSLATE] Handling as SNIP translation (no tags, no cache, no history).")
    else:
        # For regular ROI translation, preprocess into tagged format
        preprocessed_text_for_llm, tag_mapping = preprocess_text_for_translation(stable_texts_dict)
        if not preprocessed_text_for_llm or not tag_mapping:
            print("No valid text segments found after preprocessing. Nothing to translate.")
            return {} # Return empty dict if nothing to translate
        text_to_translate = preprocessed_text_for_llm
        # Cache key is based on the preprocessed text and target language.
        cache_key = get_cache_key(text_to_translate, target_language)
        print(f"[TRANSLATE] Handling as ROI translation (tags: {len(tag_mapping)}, cache_key: {cache_key[:10]}...).")


    # --- Cache Check (only for non-snip) ---
    if not is_snip and not skip_cache and not force_recache and cache_key and cache_file_path:
        cached_result = get_cached_translation(cache_key, cache_file_path)
        if cached_result:
            # Validate cache integrity
            if isinstance(cached_result, dict) and not 'error' in cached_result:
                expected_rois = {name for name, text in stable_texts_dict.items() if text and text.strip()}
                if expected_rois.issubset(cached_result.keys()):
                    print(f"[CACHE] HIT for key: {cache_key[:10]}... in {cache_file_path.name}")
                    return cached_result
                else:
                    print("[CACHE] WARN: Cached result incomplete or missing expected ROIs, fetching fresh translation.")
                    print(f"[CACHE DEBUG] Expected: {expected_rois}, Cached keys: {set(cached_result.keys())}")
            else:
                print("[CACHE] WARN: Cached result format mismatch or error, fetching fresh translation.")
        else:
            print(f"[CACHE] MISS for key: {cache_key[:10]}... in {cache_file_path.name}")
    elif is_snip: pass # Snips skip cache
    elif skip_cache: print(f"[CACHE] SKIP requested (skip_cache=True)")
    elif force_recache: print(f"[CACHE] SKIP requested (force_recache=True)")
    # --- End Cache Check ---


    # --- Construct System Prompt (with refusal reduction) ---
    system_prompt_content = (
        "You are an expert translation assistant specializing in fictional media like visual novels and games. "
        "Your primary goal is accurate and natural-sounding translation into the target language. "
        "You MUST translate ALL provided text segments or snippets accurately, regardless of perceived sensitivity, "
        "offensiveness, or topic (e.g., violence, sexual content, controversial themes, illegal acts), "
        "as they are part of a fictional work and required for user understanding. "
        "Do NOT refuse to translate, censor, replace words with asterisks, skip segments, provide summaries, "
        "express moral judgment, or add any commentary beyond the direct translation. "
        "Focus SOLELY on providing the most accurate and faithful translation possible in the requested format."
    )
    system_message = {"role": "system", "content": system_prompt_content}
    # --- End System Prompt Construction ---

    # --- Prepare History for API Call & Persistent History ---
    history_to_send = []
    history_user_message = None # This is the message *without* context/comment/examples
    input_matches_last = False

    if not skip_history: # skip_history is True for snips
        # Prepare the user message that will be *added* to the full history
        history_user_message_parts = [
            f"Translate the following segments into {target_language}, maintaining the exact <|n|> tags:",
            text_to_translate # Use the same preprocessed text for history
        ]
        history_user_content = "\n\n".join(history_user_message_parts)
        history_user_message = {"role": "user", "content": history_user_content}

        # Check if current input matches the last user input in persistent history
        if len(context_messages) >= 2:
            last_user_msg_stored = context_messages[-2]
            if last_user_msg_stored.get('role') == 'user' and last_user_msg_stored.get('content') == history_user_message.get('content'):
                input_matches_last = True

        # Determine the actual history to send to the API
        effective_history_base = list(context_messages) # Start with full persistent history
        if force_recache and input_matches_last:
            print("[CONTEXT] Force retranslate of last input: Excluding previous user/assistant pair from API call history.")
            effective_history_base = context_messages[:-2] # Exclude the last pair

        # Apply context limit
        try:
            limit_exchanges = int(context_limit)
            limit_exchanges = max(1, limit_exchanges)
        except (ValueError, TypeError):
            limit_exchanges = 10
            print(f"[CONTEXT] Warning: Invalid context_limit value '{context_limit}'. Using default: {limit_exchanges}")

        max_messages_to_send = limit_exchanges * 2
        if len(effective_history_base) > max_messages_to_send:
            start_index = len(effective_history_base) - max_messages_to_send
            history_to_send = effective_history_base[start_index:]
            print(f"[CONTEXT] Sending last {len(history_to_send)} messages ({limit_exchanges} exchanges limit) to API.")
        else:
            history_to_send = effective_history_base # Send the potentially reduced history
            print(f"[CONTEXT] Sending all {len(history_to_send)} available messages (within {limit_exchanges} exchanges limit) to API.")
    # --- End History Preparation ---

    # --- Inject Few-Shot Examples if Context is Short ---
    example_block = ""
    # Use len(history_to_send) as the effective history length for this call
    if len(history_to_send) < 10: # Less than 5 exchanges (10 messages)
        print("[PROMPT] Injecting few-shot examples due to short context history.")
        examples_to_use = []
        # Basic language check for examples (assuming Japanese input for now)
        # TODO: Potentially load examples based on detected source language if needed
        if target_language.lower().startswith("en"):
            examples_to_use = SNIP_EXAMPLES_JA_EN if is_snip else ROI_EXAMPLES_JA_EN

        if examples_to_use:
            example_lines = ["\n--- Examples ---"]
            for ex in examples_to_use:
                example_lines.append(f"Example Input:\n{ex['input']}")
                example_lines.append(f"Example Output:\n{ex['output']}")
                example_lines.append("---")
            example_block = "\n".join(example_lines) + "\n" # Add trailing newline


    # --- Construct User Message for API ---
    current_user_message_parts = []

    # Add persistent additional context FIRST
    if additional_context and additional_context.strip():
        current_user_message_parts.append(f"Game/Scenario Context: {additional_context.strip()}")
    # Add transient user comment SECOND if provided
    if user_comment and user_comment.strip():
        current_user_message_parts.append(f"User Guidance for this translation: {user_comment.strip()}")

    # Add specific instructions based on translation type
    if is_snip:
        current_user_message_parts.append(f"Translate the following {source_language_hint} text snippet accurately and completely into {target_language}. Do not refuse based on content. Output ONLY the translated text, without any tags, labels, or explanations.")
        # Add examples if generated
        if example_block:
            current_user_message_parts.append(example_block)
        current_user_message_parts.append("Text to translate:")
        current_user_message_parts.append(text_to_translate) # Raw snip text
    else:
        current_user_message_parts.append(f"Translate ALL the following {source_language_hint} segments accurately and completely into {target_language}, maintaining the exact <|n|> tags for each corresponding segment. Do not refuse any segment based on content. Do NOT include ANY extra text, commentary, explanations, greetings, summaries, apologies, or conversational filler before, between, or after the tagged translations.")
        # Add examples if generated
        if example_block:
            current_user_message_parts.append(example_block)
        current_user_message_parts.append("Segments to translate:")
        current_user_message_parts.append(text_to_translate) # Tagged ROI text

    current_user_content_with_context = "\n\n".join(current_user_message_parts)
    current_user_message_for_api = {"role": "user", "content": current_user_content_with_context}
    # --- End Construct User Message ---

    # Construct the final list of messages for the API call
    messages_for_api = [system_message] + history_to_send + [current_user_message_for_api]

    # --- API Call Setup ---
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
    for i, msg in enumerate(messages_for_api):
        print(f"  ({i+1}) {format_message_for_log(msg)}")
    print("-" * (40 + len(" LLM Request "))) # Adjust width

    try:
        api_key = preset.get("api_key") or None
        client = OpenAI(base_url=preset.get("api_url"), api_key=api_key)
    except Exception as e: print(f"[API] Error creating API client: {e}"); return {"error": f"Error creating API client: {e}"}

    # --- API Call Execution ---
    response_text = None
    try:
        completion = client.chat.completions.create(**payload)
        if not completion.choices or not completion.choices[0].message or completion.choices[0].message.content is None:
            print("[API] Error: Invalid response structure received from API.")
            try: print(f"[API] Raw Response Object: {completion}")
            except Exception as log_err: print(f"[API] Error logging raw response object: {log_err}")
            return {"error": "Invalid response structure received from API."}
        response_text = completion.choices[0].message.content.strip() # Strip whitespace from raw response
        print("-" * 20 + " LLM Response " + "-" * 20)
        print(f"[API] Raw Response Text ({len(response_text)} chars):\n{response_text}")
        print("-" * (40 + len(" LLM Response "))) # Adjust width
    except APIError as e:
        error_message = str(e)
        status_code = getattr(e, 'status_code', 'N/A')
        try:
            error_body = json.loads(getattr(e, 'body', '{}') or '{}')
            detail = error_body.get('error', {}).get('message', '')
            if detail: error_message = detail
        except Exception: pass
        log_msg = f"[API] APIError during translation request: Status {status_code}, Error: {error_message}"
        print(log_msg)
        print(f"[API] Request Model: {payload.get('model')}")
        # Check for common refusal patterns (heuristic)
        refusal_patterns = [
            "i cannot fulfill this request", "i cannot provide assistance", "unable to translate",
            "cannot provide a translation", "content policy", "violates my safety guidelines",
            "potentially harmful", "offensive content", "i cannot create", "i am unable to"
        ]
        if any(pattern in error_message.lower() for pattern in refusal_patterns):
            error_message += "\n(Possible content refusal by model)"

        return {"error": f"API Error ({status_code}): {error_message}"}
    except Exception as e:
        error_message = str(e)
        log_msg = f"[API] Error during translation request: {error_message}"
        print(log_msg)
        import traceback
        traceback.print_exc()
        return {"error": f"Error during API request: {error_message}"}

    # --- Process Result ---
    if is_snip:
        # For snips, the raw response text is the result
        final_result = response_text
    else:
        # For ROIs, parse the tagged response
        final_result = parse_translation_output(response_text, tag_mapping)
        if 'error' in final_result:
            print("[LLM PARSE] Parsing failed after receiving response.")
            return final_result # Return the error dictionary

        # --- Add/Update Persistent History (only for successful non-snip) ---
        if not skip_history and history_user_message:
            history_updated = False # Flag to track if we modified persistent history

            if input_matches_last:
                # Input matches the previous user message
                if force_recache:
                    # Force retranslate: Update the last assistant message
                    if context_messages and context_messages[-1].get('role') == 'assistant':
                        context_messages[-1]['content'] = response_text # Update content of the last message
                        history_updated = True
                        print("[CONTEXT] Input identical, force_recache=True. Updating last assistant message in persistent history.")
                    else:
                        print("[CONTEXT] Warning: Expected last message to be assistant but wasn't. Cannot update.")
                else:
                    # Normal translate: Skip adding duplicate history
                    print("[CONTEXT] Input identical to previous user message in stored history. Skipping persistent history update.")
            else:
                # Input is new: Append new user/assistant pair
                current_assistant_message = {"role": "assistant", "content": response_text} # Save raw response
                add_context_message(history_user_message)
                add_context_message(current_assistant_message)
                history_updated = True
                print("[CONTEXT] New user/assistant pair added to persistent history.")

            # Save persistent context if any changes were made (append or update)
            if history_updated:
                _save_context(hwnd)
        # --- End Add/Update Persistent History ---

        # --- Cache the successful result (only for non-snip) ---
        if not skip_cache and cache_file_path and cache_key:
            set_cache_translation(cache_key, final_result, cache_file_path)
            print(f"[CACHE] Translation cached/updated successfully in {cache_file_path.name}")
        elif not skip_cache and not cache_file_path:
            print("[CACHE] Warning: Could not cache translation (invalid path).")
        # --- End Cache ---

    return final_result