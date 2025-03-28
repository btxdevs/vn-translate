import json
import re
import os
from openai import OpenAI, APIError
from pathlib import Path
import hashlib
import time
from utils.capture import get_executable_details

APP_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = APP_DIR / "cache"
CONTEXT_DIR = APP_DIR / "context_history"

context_messages = []

def format_message_for_log(message):
    role = message.get('role', 'unknown')
    content = message.get('content', '')
    content_display = (content[:75] + '...') if len(content) > 78 else content
    content_display = content_display.replace('\n', '\\n')
    return f"[{role}] '{content_display}'"

def _ensure_cache_dir():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating cache directory {CACHE_DIR}: {e}")

def _ensure_context_dir():
    try:
        CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating context directory {CONTEXT_DIR}: {e}")

def _get_game_hash(hwnd):
    if not hwnd:
        return None
    exe_path, file_size = get_executable_details(hwnd)
    if exe_path and file_size is not None:
        try:
            identity_string = f"{os.path.normpath(exe_path).lower()}|{file_size}"
            hasher = hashlib.sha256()
            hasher.update(identity_string.encode('utf-8'))
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error generating game hash: {e}")
    return None

def _get_cache_file_path(hwnd):
    if hwnd is None:
        return None
    game_hash = _get_game_hash(hwnd)
    if game_hash:
        return CACHE_DIR / f"{game_hash}.json"
    else:
        print("Warning: Could not determine game hash. Using default cache file.")
        return CACHE_DIR / "default_cache.json"

def _get_context_file_path(hwnd):
    if hwnd is None:
        return None
    game_hash = _get_game_hash(hwnd)
    if game_hash:
        return CONTEXT_DIR / f"{game_hash}_context.json"
    else:
        print("Warning: Could not determine game hash for context file path.")
        return None

def _load_cache(cache_file_path):
    _ensure_cache_dir()
    try:
        if cache_file_path.exists():
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content:
                    return {}
                return json.loads(content)
    except json.JSONDecodeError:
        print(f"Warning: Cache file {cache_file_path} is corrupted or empty. Starting fresh cache.")
        try:
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
    _ensure_cache_dir()
    try:
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving cache to {cache_file_path}: {e}")

def clear_current_game_cache(hwnd):
    cache_file_path = _get_cache_file_path(hwnd)
    if not cache_file_path:
        return "Could not identify game to clear cache (or cache skipped)."
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

def _load_context(hwnd):
    global context_messages
    context_messages = []
    if hwnd is None:
        print("[CONTEXT] HWND is None, skipping context load.")
        return
    _ensure_context_dir()
    context_file_path = _get_context_file_path(hwnd)
    if not context_file_path:
        print("[CONTEXT] Cannot load context, failed to get file path.")
        return
    if context_file_path.exists():
        try:
            with open(context_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    loaded_history = json.loads(content)
                    if isinstance(loaded_history, list):
                        context_messages = loaded_history
                        print(f"[CONTEXT] Loaded {len(context_messages)} messages from {context_file_path.name}")
                    else:
                        print(f"[CONTEXT] Error: Loaded context from {context_file_path.name} is not a list. Resetting history.")
                else:
                    print(f"[CONTEXT] Context file {context_file_path.name} is empty.")
        except json.JSONDecodeError:
            print(f"[CONTEXT] Error: Context file {context_file_path.name} is corrupted. Resetting history.")
        except Exception as e:
            print(f"[CONTEXT] Error loading context from {context_file_path.name}: {e}. Resetting history.")
    else:
        print(f"[CONTEXT] No context file found for current game ({context_file_path.name}). Starting fresh history.")

def _save_context(hwnd):
    global context_messages
    if hwnd is None:
        return
    _ensure_context_dir()
    context_file_path = _get_context_file_path(hwnd)
    if not context_file_path:
        print("[CONTEXT] Cannot save context, failed to get file path.")
        return
    try:
        with open(context_file_path, 'w', encoding='utf-8') as f:
            json.dump(context_messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CONTEXT] Error saving context to {context_file_path.name}: {e}")

def reset_context(hwnd):
    global context_messages
    context_messages = []
    print("[CONTEXT] In-memory context history reset.")
    if hwnd is None:
        return "Context history reset (no game specified to delete file)."
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
    global context_messages
    try:
        limit = int(context_limit)
        if limit <= 0:
            limit = 1
    except (ValueError, TypeError):
        limit = 10
    context_messages.append(message)
    max_messages = limit * 2
    if len(context_messages) > max_messages:
        context_messages = context_messages[-max_messages:]
        print(f"[CONTEXT] History limit exceeded. Trimmed to {len(context_messages)} messages.")

def get_cache_key(text, target_language):
    hasher = hashlib.sha256()
    hasher.update(text.encode('utf-8'))
    hasher.update(target_language.encode('utf-8'))
    return hasher.hexdigest()

def get_cached_translation(cache_key, cache_file_path):
    if not cache_file_path:
        return None
    cache = _load_cache(cache_file_path)
    return cache.get(cache_key)

def set_cache_translation(cache_key, translation, cache_file_path):
    if not cache_file_path:
        return
    cache = _load_cache(cache_file_path)
    cache[cache_key] = translation
    _save_cache(cache, cache_file_path)

def parse_translation_output(response_text, original_tag_mapping):
    parsed_segments = {}
    pattern = r"<\|(\d+)\|>(.*?)(?=<\|\d+\|>|$)"
    matches = re.findall(pattern, response_text, re.DOTALL | re.MULTILINE)
    if matches:
        for segment_number, content in matches:
            original_roi_name = original_tag_mapping.get(segment_number)
            if original_roi_name:
                cleaned_content = re.sub(r'<\|\d+\|>$', '', content.strip()).strip()
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
                    print(f"Warning: Received segment number '{segment_number}' which was not in original mapping.")
        if not found_line_match and len(original_tag_mapping) == 1 and not response_text.startswith("<|"):
            first_tag = next(iter(original_tag_mapping))
            first_roi = original_tag_mapping[first_tag]
            print(f"[LLM PARSE] Warning: No tags found; assuming plain text for ROI '{first_roi}'.")
            parsed_segments[first_roi] = response_text.strip()
        elif not found_line_match and not matches:
            print("[LLM PARSE] Failed to parse any segments.")
            return {"error": f"Error: Unable to extract formatted translation.\nRaw response:\n{response_text}"}
    missing_rois = set(original_tag_mapping.values()) - set(parsed_segments.keys())
    if missing_rois:
        print(f"[LLM PARSE] Warning: Missing segments for ROIs: {', '.join(missing_rois)}")
        for roi_name in missing_rois:
            parsed_segments[roi_name] = "[Translation Missing]"
    if not parsed_segments and original_tag_mapping:
        print("[LLM PARSE] Error: Failed to parse any segments.")
        return {"error": f"Error: Failed to extract any segments.\nRaw response:\n{response_text}"}
    return parsed_segments

def preprocess_text_for_translation(aggregated_text):
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
            print(f"Ignoring line (format mismatch): {line}")
    if not tag_mapping:
        print("Warning: No valid lines found during preprocessing.")
    return '\n'.join(preprocessed_lines), tag_mapping

def translate_text(aggregated_input_text, hwnd, preset, target_language="en", additional_context="", context_limit=10, force_recache=False, skip_cache=False, skip_history=False):
    cache_file_path = None if skip_cache else _get_cache_file_path(hwnd)
    if not skip_cache and not cache_file_path and hwnd is not None:
        print("Error: No valid cache file path.")
        return {"error": "Could not determine cache file path for the game."}
    preprocessed_text_for_llm, tag_mapping = preprocess_text_for_translation(aggregated_input_text)
    if not preprocessed_text_for_llm or not tag_mapping:
        print("No valid text segments found after preprocessing.")
        return {}
    cache_key = get_cache_key(preprocessed_text_for_llm, target_language)
    if not skip_cache and not force_recache:
        cached_result = get_cached_translation(cache_key, cache_file_path)
        if cached_result:
            if isinstance(cached_result, dict) and 'error' not in cached_result:
                if all(roi_name in cached_result for roi_name in tag_mapping.values()):
                    print(f"[CACHE] HIT for key: {cache_key[:10]}...")
                    return cached_result
                else:
                    print("[CACHE] WARN: Cached result incomplete.")
            else:
                print("[CACHE] WARN: Cached result format error.")
        else:
            print(f"[CACHE] MISS for key: {cache_key[:10]}...")
    elif skip_cache:
        print("[CACHE] SKIP requested")
    elif force_recache:
        print(f"[CACHE] Force recache for key: {cache_key[:10]}...")

    system_prompt = preset.get('system_prompt', "You are a translator.")
    system_content = (
        f"{system_prompt}\n\n"
        f"Translate the following text segments into {target_language}. "
        "Input segments are tagged like <|1|>, <|2|>, etc. "
        "Your response MUST replicate this format exactly, using the same tags. "
        "Output ONLY the tagged translated lines."
        "Do NOT include ANY extra text, commentary, explanations, greetings, summaries, apologies, or any conversational filler before, between, or after the tagged translations."
    )
    system_message = {"role": "system", "content": system_content}

    history_to_send = []
    if not skip_history:
        global context_messages
        history_to_send = list(context_messages)

    current_user_message_parts = []
    if additional_context.strip():
        current_user_message_parts.append(f"Additional context: {additional_context.strip()}")
    current_user_message_parts.append(f"Translate these segments to {target_language}, maintaining the exact <|n|> tags:")
    current_user_message_parts.append(preprocessed_text_for_llm)
    current_user_content_with_context = "\n\n".join(current_user_message_parts)
    current_user_message_for_api = {"role": "user", "content": current_user_content_with_context}

    history_user_message = None
    if not skip_history:
        history_user_message_parts = [
            f"Translate these segments to {target_language}, maintaining the exact <|n|> tags:",
            preprocessed_text_for_llm
        ]
        history_user_content = "\n\n".join(history_user_message_parts)
        history_user_message = {"role": "user", "content": history_user_content}

    messages_for_api = [system_message] + history_to_send + [current_user_message_for_api]

    if not preset.get("model") or not preset.get("api_url"):
        missing = [f for f in ["model", "api_url"] if not preset.get(f)]
        errmsg = f"Missing required preset fields: {', '.join(missing)}"
        print(f"[API] Error: {errmsg}")
        return {"error": errmsg}

    payload = {
        "model": preset["model"],
        "messages": messages_for_api,
        "temperature": preset.get("temperature", 0.3),
        "max_tokens": preset.get("max_tokens", 1000)
    }
    for param in ["top_p", "frequency_penalty", "presence_penalty"]:
        if param in preset and preset[param] is not None:
            try:
                payload[param] = float(preset[param])
            except (ValueError, TypeError):
                print(f"Warning: Invalid value for parameter '{param}': {preset[param]}. Skipping.")

    print("-" * 20 + " LLM Request " + "-" * 20)
    print(f"[API] Endpoint: {preset.get('api_url')}")
    print(f"[API] Model: {preset['model']}")
    print(f"[API] Payload Parameters (excluding messages):")
    for key, value in payload.items():
        if key != "messages":
            print(f"  - {key}: {value}")
    print(f"[API] Messages ({len(messages_for_api)} total):")
    if messages_for_api[0]['role'] == 'system':
        print("  - [system] (System prompt configured)")
    if history_to_send:
        print(f"  - [CONTEXT HISTORY - {len(history_to_send)} messages]")
        for msg in history_to_send:
            print(f"    - {format_message_for_log(msg)}")
    print(f"  - {format_message_for_log(current_user_message_for_api)}")
    print("-" * 55)

    try:
        api_key = preset.get("api_key") or None
        client = OpenAI(base_url=preset.get("api_url"), api_key=api_key)
    except Exception as e:
        print(f"[API] Error creating API client: {e}")
        return {"error": f"Error creating API client: {e}"}

    response_text = None
    try:
        completion = client.chat.completions.create(**payload)
        if not completion.choices or not completion.choices[0].message or completion.choices[0].message.content is None:
            print("[API] Error: Invalid response structure.")
            return {"error": "Invalid response structure received from API."}
        response_text = completion.choices[0].message.content.strip()
        print("-" * 20 + " LLM Response " + "-" * 20)
        print(f"[API] Raw Response Text ({len(response_text)} chars):")
        print(response_text)
        print("-" * 56)
    except APIError as e:
        error_message = str(e)
        status_code = getattr(e, 'status_code', 'N/A')
        try:
            error_body = json.loads(getattr(e, 'body', '{}') or '{}')
            detail = error_body.get('error', {}).get('message', '')
            if detail:
                error_message = detail
        except:
            pass
        print(f"[API] APIError: Status {status_code}, Error: {error_message}")
        return {"error": f"API Error ({status_code}): {error_message}"}
    except Exception as e:
        error_message = str(e)
        print(f"[API] Error during translation request: {error_message}")
        return {"error": f"Error during API request: {error_message}"}

    final_translations = parse_translation_output(response_text, tag_mapping)
    if 'error' in final_translations:
        print("[LLM PARSE] Parsing failed.")
        return final_translations

    if not skip_history and history_user_message:
        add_to_history = True
        if len(context_messages) >= 2:
            last_user_message_in_history = context_messages[-2]
            if last_user_message_in_history.get('role') == 'user' and last_user_message_in_history.get('content') == history_user_message.get('content'):
                add_to_history = False
                print("[CONTEXT] Input identical to previous user message. Skipping history update.")
        if add_to_history:
            current_assistant_message = {"role": "assistant", "content": response_text}
            add_context_message(history_user_message, context_limit)
            add_context_message(current_assistant_message, context_limit)
            _save_context(hwnd)

    if not skip_cache and cache_file_path:
        set_cache_translation(cache_key, final_translations, cache_file_path)
        print(f"[CACHE] Cached translation in {cache_file_path.name}")
    elif not skip_cache and not cache_file_path:
        print("[CACHE] Warning: Could not cache translation (invalid path).")

    return final_translations
