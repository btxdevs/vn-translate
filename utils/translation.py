import json
import re
import os
from openai import OpenAI
from pathlib import Path


# File-based cache settings
CACHE_DIR = Path(os.path.expanduser("~/.ocrtrans/cache"))
CACHE_FILE = CACHE_DIR / "translation_cache.json"

# Context management
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
                return json.load(f)
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
    return "Translation context has been reset."

def add_context(message, context_limit):
    """Add a message to the translation context history."""
    global context_messages
    context_messages.append(message)
    if len(context_messages) > context_limit:
        context_messages = context_messages[-context_limit:]

def clear_cache():
    """Clear the translation cache."""
    _save_cache({})
    return "Translation cache has been cleared."

def get_cached_translation(text, preset_hash):
    """Get a cached translation if it exists."""
    cache = _load_cache()
    key = f"{preset_hash}:{text}"
    return cache.get(key)

def set_cache_translation(text, preset_hash, translation):
    """Cache a translation result."""
    cache = _load_cache()
    key = f"{preset_hash}:{text}"
    cache[key] = translation
    _save_cache(cache)

def get_preset_hash(preset):
    """Create a simple hash of the preset to use as a cache key."""
    # Just use the model, temperature, and API URL as a simple hash
    return f"{preset.get('model')}_{preset.get('temperature')}_{preset.get('api_url')}"

def parse_translation_output(response_text):
    """
    Parse the translation output from a tagged format.

    Given a response text in the format:
       <|1|> translated text for segment 1
       <|2|> translated text for segment 2
       ...
    return a dictionary mapping segment numbers (as strings) to their text.
    """
    segments = {}
    pattern = r"<\|(\d+)\|>\s*(.+)"

    # Check for line-by-line format
    for line in response_text.splitlines():
        match = re.match(pattern, line)
        if match:
            key, content = match.groups()
            segments[key] = content.strip()

    # If no matches found, try to extract from continuous text
    if not segments:
        matches = re.findall(pattern, response_text)
        for key, content in matches:
            segments[key] = content.strip()

    return segments

def preprocess_text_for_translation(text):
    """
    Convert input text with tags like [tag]: content to the numbered format <|1|> content.
    Returns preprocessed text and a mapping of segment numbers to original tags.
    """
    lines = text.strip().split('\n')
    preprocessed_lines = []
    tag_mapping = {}
    segment_count = 1

    for line in lines:
        # Look for tags in the format [tag]: content
        match = re.match(r'\[([^\]]+)\]:\s*(.*)', line)
        if match:
            tag, content = match.groups()
            tag_mapping[str(segment_count)] = tag
            preprocessed_lines.append(f"<|{segment_count}|> {content}")
            segment_count += 1
        else:
            # If not a tagged line, append as is (could handle differently if needed)
            preprocessed_lines.append(line)

    return '\n'.join(preprocessed_lines), tag_mapping

def translate_text(text, preset, target_language="en", additional_context=""):
    """
    Translate the given text using an OpenAI-compatible API client.

    Args:
        text: The text to translate
        preset: The translation preset configuration
        target_language: The target language code
        additional_context: Additional context for the translation

    Returns:
        A dictionary mapping segment numbers to translated text
    """
    # Preprocess text to match expected output format
    preprocessed_text, tag_mapping = preprocess_text_for_translation(text)

    # Check cache first
    preset_hash = get_preset_hash(preset)
    cached = get_cached_translation(text, preset_hash)
    if cached:
        print(f"[LOG] Using cached translation")
        return cached

    # Prepare system message with additional context if provided
    system_content = (
        f"{preset['system_prompt']}\n\n"
        "IMPORTANT: Maintain the exact same segment numbering as in the input. "
        "Do NOT split sentences into multiple segments or create new segments. "
        "Always translate each <|n|> segment as a complete unit."
    )
    if additional_context.strip():
        system_content += f"\n\nAdditional Context: {additional_context.strip()}"

    # Build message history with example formatting
    messages = [{"role": "system", "content": system_content}]

    # Add example exchanges to guide the model
    example_exchanges = [
        {
            "role": "user",
            "content": "Translate the following text to English following the specified format:"
                       "\n<|1|> これは一つの文章です。二つ目の文もあります。"
                       "\n\nPlease provide only the tagged translated lines using the <|n|> format."
        },
        {
            "role": "assistant",
            "content": "<|1|> This is one sentence. There is also a second sentence."
        },
        {
            "role": "user",
            "content": "Translate the following text to English following the specified format:"
                       "\n<|1|> 彼女の名前は、月社婚という. 別居した両親のうちの。 母親の方に残された、 実の妹."
                       "\n\nPlease provide only the tagged translated lines using the <|n|> format."
        },
        {
            "role": "assistant",
            "content": "<|1|> Her name is Tsukimiya. Among my separated parents. The real sister who remained with my mother."
        }
    ]

    # Only include example exchanges if there are no context messages
    if not context_messages:
        for msg in example_exchanges:
            messages.append(msg)
    else:
        for msg in context_messages:
            messages.append(msg)

    # Add current translation request
    user_message = (
        f"Translate the following text to {target_language}. "
        f"Each segment must keep its original numbering:\n\n{preprocessed_text}\n\n"
        "Respond using EXACTLY the same segment numbers. "
        "Do NOT split sentences into multiple segments. "
        "Format each segment as: <|n|> translated_text"
    )
    messages.append({"role": "user", "content": user_message})
    add_context({"role": "user", "content": user_message}, preset.get("context_limit", 10))

    # Prepare API request payload
    payload = {
        "model": preset["model"],
        "messages": messages,
        "temperature": preset.get("temperature", 0.3),
        "max_tokens": preset.get("max_tokens", 1000)
    }

    # Add optional parameters if present in the preset
    for param in ["top_p", "frequency_penalty", "presence_penalty"]:
        if param in preset and preset[param] is not None:
            payload[param] = preset[param]

    print("[LOG] Translation payload:")
    print(json.dumps(payload, indent=2))

    # Create API client
    try:
        client = OpenAI(
            base_url=preset["api_url"],
            api_key=preset["api_key"]
        )
    except Exception as e:
        print(f"[LOG] Error creating API client: {e}")
        return {"error": f"Error creating API client: {e}"}

    # Make API request
    try:
        completion = client.chat.completions.create(**payload)
    except Exception as e:
        print(f"[LOG] HTTP error during translation request: {e}")
        return {"error": f"Error: {e}"}

    # Process response
    try:
        response_text = completion.choices[0].message.content.strip()
        print(f"[LOG] Raw response: {response_text}")
    except (KeyError, IndexError, AttributeError) as e:
        print(f"[LOG] Unexpected response structure: {e}")
        return {"error": f"Error parsing response: {e}"}

    # Parse segments
    segments = parse_translation_output(response_text)
    if not segments:
        print("[LOG] Failed to parse segments from response:")
        print(response_text)
        return {"error": f"Error: Unable to extract formatted translation.\nRaw response:\n{response_text}"}

    # Cache result and update context
    set_cache_translation(text, preset_hash, segments)
    add_context({"role": "assistant", "content": response_text}, preset.get("context_limit", 10))

    return segments