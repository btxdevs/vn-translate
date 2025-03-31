# --- START OF FILE ocr.py ---

import time
import threading
import numpy as np
import cv2 # Keep cv2 for image handling and initial conversion
import io # For in-memory byte streams
import re # Import regex module
import platform # To check OS

# --- Prerequisites for GPU Acceleration ---
# For PaddleOCR GPU:
# 1. Install NVIDIA drivers, CUDA Toolkit, and cuDNN.
# 2. Install the GPU version of PaddlePaddle:
#    pip install paddlepaddle-gpu -U # Or specify a version compatible with your CUDA/cuDNN
#    pip install paddleocr
#
# For EasyOCR GPU:
# 1. Install NVIDIA drivers, CUDA Toolkit, and cuDNN.
# 2. Install PyTorch with CUDA support *first*. Go to https://pytorch.org/get-started/locally/
#    and select the correct options for your system (OS, Package, Python, CUDA version).
#    Example command (verify on PyTorch site): pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
# 3. Then install EasyOCR: pip install easyocr

# --- Engine Specific Imports ---
_paddle_available = False
try:
    from paddleocr import PaddleOCR
    _paddle_available = True
except ImportError:
    print("PaddleOCR not found. Install with 'pip install paddlepaddle paddleocr'. For GPU, install 'paddlepaddle-gpu'.")

_easyocr_available = False
try:
    import easyocr
    _easyocr_available = True
except ImportError:
    print("EasyOCR not found. Install with 'pip install easyocr'. For GPU, ensure PyTorch with CUDA is installed first.")

_windows_ocr_available = False
# Only attempt Windows OCR import on Windows
if platform.system() == "Windows":
    try:
        # Corrected import and usage pattern for winsdk
        import asyncio
        # Import the specific namespaces/classes needed directly or with aliases
        import winsdk.windows.media.ocr as win_ocr
        import winsdk.windows.graphics.imaging as win_imaging
        import winsdk.windows.storage.streams as win_streams
        import winsdk.windows.globalization # Import the globalization namespace
        # Import foundation for async operations if needed, though await handles it
        # from winsdk.windows.foundation import IAsyncOperation
        _windows_ocr_available = True
    except ImportError:
        print("Windows SDK components (winsdk) not found or failed to import. Install with 'pip install winsdk'. Ensure Windows SDK is installed if issues persist.")
    except OSError as e:
        # Catches errors like "cannot load library" if underlying WinRT components are missing/corrupt
        print(f"Error loading Windows SDK components (winsdk): {e}. Windows OCR disabled.")
else:
    print("Windows OCR is only available on the Windows platform.")


# --- Globals for Engine Instances (Lazy Initialization) ---
_paddle_ocr_instance = None
_paddle_lang_loaded = None
_easyocr_instance = None
_easyocr_lang_loaded = None
_windows_ocr_engines = {} # Cache engines per language
_init_lock = threading.Lock() # Lock for initializing engines

# --- Language Mappings ---
# Map internal codes ('jpn', 'eng', etc.) to engine-specific codes
PADDLE_LANG_MAP = {
    "jpn": "japan", "jpn_vert": "japan", "eng": "en",
    "chi_sim": "ch", "chi_tra": "ch", "kor": "ko",
}
EASYOCR_LANG_MAP = {
    "jpn": "ja", "jpn_vert": "ja", "eng": "en",
    "chi_sim": "ch_sim", "chi_tra": "ch_tra", "kor": "ko",
}
# Windows uses BCP-47 tags. Ensure these match installed language packs on your system.
WINDOWS_OCR_LANG_MAP = {
    "jpn": "ja", # Japanese (generic tag often works) - "ja-JP" also valid
    "jpn_vert": "ja",
    "eng": "en-US", # English (United States) - adjust if needed
    "chi_sim": "zh-Hans", # Chinese (Simplified)
    "chi_tra": "zh-Hant", # Chinese (Traditional)
    "kor": "ko", # Korean
}

# --- Engine Initialization Functions ---

def _init_paddle(lang_code):
    """Initializes and caches the PaddleOCR engine. Attempts GPU usage if available."""
    global _paddle_ocr_instance, _paddle_lang_loaded
    if not _paddle_available:
        raise RuntimeError("PaddleOCR library is not installed.")

    target_lang = PADDLE_LANG_MAP.get(lang_code, "en")
    # Return cached instance if language matches
    if _paddle_ocr_instance and _paddle_lang_loaded == target_lang:
        return _paddle_ocr_instance

    print(f"[OCR Init] Initializing PaddleOCR for language: {target_lang} (requested: {lang_code}) - Attempting GPU")
    start_time = time.time()
    try:
        # --- Enable GPU ---
        # Set use_gpu=True. Paddle will automatically use GPU if paddlepaddle-gpu
        # is installed and CUDA is configured correctly. Otherwise, it falls back to CPU.
        instance = PaddleOCR(use_angle_cls=True, lang=target_lang, show_log=False, use_gpu=True)
        # ------------------
        _paddle_ocr_instance = instance
        _paddle_lang_loaded = target_lang
        # Note: Paddle might print messages about GPU/CPU usage internally
        print(f"[OCR Init] PaddleOCR initialized (GPU requested) in {time.time() - start_time:.2f}s")
        return instance
    except Exception as e:
        print(f"[OCR Init] !!! Error initializing PaddleOCR: {e}")
        _paddle_ocr_instance = None; _paddle_lang_loaded = None # Reset on error
        raise RuntimeError(f"Failed to initialize PaddleOCR: {e}")

def _init_easyocr(lang_code):
    """Initializes and caches the EasyOCR engine. Attempts GPU usage if available."""
    global _easyocr_instance, _easyocr_lang_loaded
    if not _easyocr_available:
        raise RuntimeError("EasyOCR library is not installed.")

    target_lang = EASYOCR_LANG_MAP.get(lang_code)
    if not target_lang:
        raise ValueError(f"Language code '{lang_code}' not supported by EasyOCR mapping.")

    target_lang_list = [target_lang] # EasyOCR expects a list
    # Return cached instance if language list matches
    if _easyocr_instance and _easyocr_lang_loaded == target_lang_list:
        return _easyocr_instance

    print(f"[OCR Init] Initializing EasyOCR for language: {target_lang_list} (requested: {lang_code}) - Attempting GPU")
    start_time = time.time()
    try:
        # --- Enable GPU ---
        # gpu=True tells EasyOCR to use the GPU if PyTorch with CUDA support is found.
        # If not found, it automatically falls back to CPU.
        instance = easyocr.Reader(target_lang_list, gpu=True)
        # ------------------
        _easyocr_instance = instance
        _easyocr_lang_loaded = target_lang_list
        # Note: EasyOCR might print messages about CUDA availability/usage
        print(f"[OCR Init] EasyOCR initialized (GPU requested) in {time.time() - start_time:.2f}s")
        return instance
    except Exception as e:
        print(f"[OCR Init] !!! Error initializing EasyOCR: {e}")
        _easyocr_instance = None; _easyocr_lang_loaded = None # Reset on error
        raise RuntimeError(f"Failed to initialize EasyOCR: {e}")

def _is_windows_ocr_lang_available(win_lang_tag):
    """Checks if a specific BCP-47 language tag is supported by Windows OCR."""
    if not _windows_ocr_available: # Will be False if not on Windows or winsdk failed
        return False
    try:
        # Use globalization.Language
        lang = winsdk.windows.globalization.Language(win_lang_tag)
        # Call static method on OcrEngine class
        return win_ocr.OcrEngine.is_language_supported(lang)
    except Exception as e:
        # Catches errors from invalid tags or if WinRT components fail
        print(f"[OCR Check] Windows OCR language check failed for '{win_lang_tag}': {e}")
        return False

def _init_windows_ocr(lang_code):
    """Initializes and caches the Windows OCR engine for a given language."""
    global _windows_ocr_engines
    if not _windows_ocr_available: # Check if platform/import allows it
        raise RuntimeError("Windows OCR components (winsdk) are not available on this system.")

    target_lang_tag = WINDOWS_OCR_LANG_MAP.get(lang_code)
    if not target_lang_tag:
        raise ValueError(f"Language code '{lang_code}' not supported by Windows OCR mapping.")

    # Return cached engine if available
    if target_lang_tag in _windows_ocr_engines:
        return _windows_ocr_engines[target_lang_tag]

    print(f"[OCR Init] Initializing Windows OCR for language: {target_lang_tag} (requested: {lang_code})")
    start_time = time.time()
    try:
        # Use globalization.Language
        win_lang = winsdk.windows.globalization.Language(target_lang_tag)

        # Check support using static method
        if not win_ocr.OcrEngine.is_language_supported(win_lang):
            # Provide more info if language not supported
            available_langs = win_ocr.OcrEngine.get_available_recognizer_languages()
            available_tags = [lang.language_tag for lang in available_langs]
            print(f"[OCR Init] Available Windows OCR languages: {available_tags}")
            raise RuntimeError(f"Windows OCR language '{target_lang_tag}' is not installed or supported. Check installed language packs.")

        # Create engine using static factory method
        engine = win_ocr.OcrEngine.try_create_from_language(win_lang)
        if engine is None:
            # This might happen even if supported, e.g., component issues
            raise RuntimeError(f"Failed to create Windows OCR engine for '{target_lang_tag}'.")

        _windows_ocr_engines[target_lang_tag] = engine
        print(f"[OCR Init] Windows OCR initialized in {time.time() - start_time:.2f}s")
        return engine
    except Exception as e:
        print(f"[OCR Init] !!! Error initializing Windows OCR: {e}")
        # Clean up cache entry if initialization failed
        if target_lang_tag in _windows_ocr_engines:
            del _windows_ocr_engines[target_lang_tag]
        # Re-raise the exception to be caught by the caller
        raise RuntimeError(f"Failed to initialize Windows OCR for {target_lang_tag}: {e}")


# --- Windows OCR Async Helper ---
async def _convert_cv_to_software_bitmap(img_bgr):
    """Converts an OpenCV BGR image to a SoftwareBitmap via PNG encoding."""
    is_success, buffer = cv2.imencode(".png", img_bgr)
    if not is_success:
        raise RuntimeError("Failed to encode OpenCV image to PNG format.")

    image_bytes = buffer.tobytes()

    # Create an in-memory stream and write the PNG bytes
    stream = win_streams.InMemoryRandomAccessStream()
    writer = win_streams.DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(image_bytes)
    # Need to await store_async to ensure data is written before decoding
    stored_bytes = await writer.store_async()
    # Flushing might also be necessary depending on the stream implementation
    await writer.flush_async()
    stream.seek(0) # Reset stream position for the decoder

    # Decode the PNG stream into a SoftwareBitmap
    decoder = await win_imaging.BitmapDecoder.create_async(stream)
    # Get the software bitmap
    # We don't need to specify pixel format here as decoder handles the PNG format
    software_bitmap = await decoder.get_software_bitmap_async()
    return software_bitmap


async def _run_windows_ocr_async(engine, img_bgr):
    """Helper to run Windows OCR asynchronously and remove inter-character spaces."""
    if not _windows_ocr_available:
        return "[Windows OCR Error: Not Available]"
    try:
        # Convert OpenCV image to SoftwareBitmap
        software_bitmap = await _convert_cv_to_software_bitmap(img_bgr)

        # Perform OCR using the engine instance's recognize_async method
        ocr_result = await engine.recognize_async(software_bitmap)

        if ocr_result is None:
            print("[OCR Error] Windows OCR recognize_async returned None.")
            return "[Windows OCR Error: No Result]"

        # --- FIX: Post-process to remove spaces ---
        extracted_lines = []
        if ocr_result.lines is not None:
            for line in ocr_result.lines:
                # Get the text for the line
                line_text = line.text
                # Remove *all* spaces within the line's text
                # Assumes target languages (like Japanese) don't use spaces between characters.
                processed_line_text = line_text.replace(" ", "")
                extracted_lines.append(processed_line_text)
        else:
            # No lines detected, result is empty string
            pass

        # Join the processed lines with newlines
        final_text = "\n".join(extracted_lines)
        # --- End FIX ---

        return final_text

    except Exception as e:
        print(f"[OCR Error] Windows OCR async processing failed: {e}")
        import traceback
        traceback.print_exc()
        return "[Windows OCR Error]"

# --- Main Extraction Function ---

def extract_text(img, lang="jpn", engine_type="paddle"):
    """
    Extracts text from an image using the specified engine and language.
    Attempts GPU acceleration for PaddleOCR and EasyOCR if available.

    Args:
        img (numpy.ndarray): The image (BGR format expected).
        lang (str): The language code (e.g., 'jpn', 'eng').
        engine_type (str): The OCR engine to use ('paddle', 'easyocr', 'windows').

    Returns:
        str: The extracted text, or an error message string starting with '['.
    """
    if img is None or img.size == 0:
        return "" # Return empty string for invalid input

    start_time = time.time()
    extracted_text = ""
    engine_instance = None

    try:
        # --- Engine Initialization (Thread Safe) ---
        with _init_lock:
            if engine_type == "paddle":
                engine_instance = _init_paddle(lang) # Will attempt GPU
            elif engine_type == "easyocr":
                engine_instance = _init_easyocr(lang) # Will attempt GPU
            elif engine_type == "windows":
                engine_instance = _init_windows_ocr(lang) # CPU only
            else:
                raise ValueError(f"Unsupported OCR engine type: {engine_type}")

        # --- Perform OCR ---
        if engine_type == "paddle":
            # PaddleOCR processing (GPU or CPU handled during init)
            ocr_result_raw = engine_instance.ocr(img, cls=True)
            lines = []
            # Safely extract text (handle None results from Paddle)
            if ocr_result_raw and ocr_result_raw[0] is not None:
                for line_info in ocr_result_raw[0]:
                    # Check structure before accessing elements
                    if line_info and isinstance(line_info, list) and len(line_info) >= 2:
                        text_part = line_info[1]
                        if text_part and isinstance(text_part, (tuple, list)) and len(text_part) > 0:
                            lines.append(str(text_part[0]))
            extracted_text = " ".join(lines).strip() # Note: Paddle might need different joining logic

        elif engine_type == "easyocr":
            # EasyOCR processing (GPU or CPU handled during init)
            ocr_result_raw = engine_instance.readtext(img)
            # Extract text part (index 1) from results, checking structure
            lines = [item[1] for item in ocr_result_raw if item and isinstance(item, (list, tuple)) and len(item) >= 2]
            extracted_text = " ".join(lines).strip() # Note: EasyOCR might need different joining logic

        elif engine_type == "windows":
            # Windows OCR uses asyncio (CPU only)
            if not _windows_ocr_available:
                extracted_text = "[Windows OCR Error: Not Available]"
            else:
                # Manage asyncio event loop for the background thread
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError: # No loop in current thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Run the async helper function (which now removes spaces)
                extracted_text = loop.run_until_complete(_run_windows_ocr_async(engine_instance, img))
                extracted_text = str(extracted_text).strip() # Ensure string and strip again

        elapsed = time.time() - start_time
        # Optional: Log successful extraction time and snippet
        # You could add logic here to check if GPU was actually used by inspecting
        # library-specific flags or messages, but simply reporting time is often sufficient.
        # print(f"[OCR] Extracted ({engine_type}/{lang}) in {elapsed:.3f}s: '{extracted_text[:50]}...'")
        return extracted_text

    except RuntimeError as e: # Catch initialization errors
        print(f"[OCR Error] Engine initialization failed: {e}")
        return f"[{engine_type.upper()} Init Error]"
    except ValueError as e: # Catch language mapping/config errors
        print(f"[OCR Error] Configuration error: {e}")
        return f"[{engine_type.upper()} Config Error]"
    except Exception as e: # Catch runtime OCR errors
        print(f"[OCR Error] Failed during {engine_type} OCR: {e}")
        import traceback
        traceback.print_exc()
        return f"[{engine_type.upper()} Runtime Error]"