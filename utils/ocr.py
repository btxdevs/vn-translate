# --- START OF FILE ocr.py ---

import time
import threading
import numpy as np
import cv2 # Keep cv2 for image handling and initial conversion
import io # For in-memory byte streams
import re # Import regex module
import platform # To check OS
import gc # Import garbage collector

# --- Prerequisites for GPU Acceleration ---
# (Keep comments as before)

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
        _windows_ocr_available = True
    except ImportError:
        print("Windows SDK components (winsdk) not found or failed to import. Install with 'pip install winsdk'. Ensure Windows SDK is installed if issues persist.")
    except OSError as e:
        # Catches errors like "cannot load library" if underlying WinRT components are missing/corrupt
        print(f"Error loading Windows SDK components (winsdk): {e}. Windows OCR disabled.")
else:
    print("Windows OCR is only available on the Windows platform.")


# --- Globals for Engine Instances (Unified Management) ---
_current_engine_instance = None
_current_engine_type = None
_current_engine_lang = None # Tracks language ('en', 'ja', ['ja'], etc.)
_windows_ocr_engines = {} # Cache engines per language *within* Windows OCR
_init_lock = threading.Lock() # Lock for initializing engines

# --- Language Mappings ---
# (Keep mappings as before)
PADDLE_LANG_MAP = {
    "jpn": "japan", "jpn_vert": "japan", "eng": "en",
    "chi_sim": "ch", "chi_tra": "ch", "kor": "ko",
}
EASYOCR_LANG_MAP = {
    "jpn": "ja", "jpn_vert": "ja", "eng": "en",
    "chi_sim": "ch_sim", "chi_tra": "ch_tra", "kor": "ko",
}
WINDOWS_OCR_LANG_MAP = {
    "jpn": "ja", "jpn_vert": "ja", "eng": "en-US",
    "chi_sim": "zh-Hans", "chi_tra": "zh-Hant", "kor": "ko",
}

# --- Engine Cleanup Function ---
def _cleanup_ocr_engine():
    """Explicitly cleans up the current OCR engine instance."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang
    if _current_engine_instance is not None:
        print(f"[OCR Cleanup] Cleaning up previous OCR engine: {_current_engine_type}")
        engine_type_being_cleaned = _current_engine_type
        try:
            # Attempt to delete the instance
            del _current_engine_instance
        except Exception as e:
            print(f"[OCR Cleanup] Error deleting instance: {e}")

        _current_engine_instance = None
        _current_engine_type = None
        _current_engine_lang = None

        # Force garbage collection
        gc.collect()

        # Optional: Add specific cleanup if needed, e.g., for PyTorch/EasyOCR GPU memory
        if engine_type_being_cleaned == "easyocr":
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    print("[OCR Cleanup] Cleared PyTorch CUDA cache.")
            except ImportError:
                # PyTorch not installed, ignore
                pass
            except Exception as e:
                print(f"[OCR Cleanup] Error clearing CUDA cache: {e}")
        print("[OCR Cleanup] Cleanup finished.")


# --- Engine Initialization Functions (with cleanup logic) ---

def _init_paddle(lang_code):
    """Initializes PaddleOCR, cleaning up previous engines if necessary."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang
    if not _paddle_available:
        raise RuntimeError("PaddleOCR library is not installed.")

    target_lang = PADDLE_LANG_MAP.get(lang_code, "en")

    # Check if already initialized with the correct type and language
    if _current_engine_type == "paddle" and _current_engine_lang == target_lang:
        # print("[OCR Init] Using cached PaddleOCR instance.") # Optional: less verbose
        return _current_engine_instance

    # --- Cleanup required ---
    _cleanup_ocr_engine() # Clean up whatever was loaded before

    print(f"[OCR Init] Initializing PaddleOCR for language: {target_lang} (requested: {lang_code}) - Attempting GPU")
    start_time = time.time()
    try:
        instance = PaddleOCR(use_angle_cls=True, lang=target_lang, show_log=False, use_gpu=True)
        _current_engine_instance = instance
        _current_engine_type = "paddle"
        _current_engine_lang = target_lang
        print(f"[OCR Init] PaddleOCR initialized (GPU requested) in {time.time() - start_time:.2f}s")
        return instance
    except Exception as e:
        print(f"[OCR Init] !!! Error initializing PaddleOCR: {e}")
        _cleanup_ocr_engine() # Ensure cleanup even on init failure
        raise RuntimeError(f"Failed to initialize PaddleOCR: {e}")

def _init_easyocr(lang_code):
    """Initializes EasyOCR, cleaning up previous engines if necessary."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang
    if not _easyocr_available:
        raise RuntimeError("EasyOCR library is not installed.")

    target_lang = EASYOCR_LANG_MAP.get(lang_code)
    if not target_lang:
        raise ValueError(f"Language code '{lang_code}' not supported by EasyOCR mapping.")
    target_lang_list = [target_lang] # EasyOCR expects a list

    # Check if already initialized with the correct type and language list
    if _current_engine_type == "easyocr" and _current_engine_lang == target_lang_list:
        # print("[OCR Init] Using cached EasyOCR instance.") # Optional: less verbose
        return _current_engine_instance

    # --- Cleanup required ---
    _cleanup_ocr_engine() # Clean up whatever was loaded before

    print(f"[OCR Init] Initializing EasyOCR for language: {target_lang_list} (requested: {lang_code}) - Attempting GPU")
    start_time = time.time()
    try:
        instance = easyocr.Reader(target_lang_list, gpu=True)
        _current_engine_instance = instance
        _current_engine_type = "easyocr"
        _current_engine_lang = target_lang_list
        print(f"[OCR Init] EasyOCR initialized (GPU requested) in {time.time() - start_time:.2f}s")
        return instance
    except Exception as e:
        print(f"[OCR Init] !!! Error initializing EasyOCR: {e}")
        _cleanup_ocr_engine() # Ensure cleanup even on init failure
        raise RuntimeError(f"Failed to initialize EasyOCR: {e}")

def _is_windows_ocr_lang_available(win_lang_tag):
    """Checks if a specific BCP-47 language tag is supported by Windows OCR."""
    # (Keep implementation as before)
    if not _windows_ocr_available:
        return False
    try:
        lang = winsdk.windows.globalization.Language(win_lang_tag)
        return win_ocr.OcrEngine.is_language_supported(lang)
    except Exception as e:
        print(f"[OCR Check] Windows OCR language check failed for '{win_lang_tag}': {e}")
        return False

def _init_windows_ocr(lang_code):
    """Initializes Windows OCR, cleaning up previous engines if necessary."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang, _windows_ocr_engines
    if not _windows_ocr_available:
        raise RuntimeError("Windows OCR components (winsdk) are not available on this system.")

    target_lang_tag = WINDOWS_OCR_LANG_MAP.get(lang_code)
    if not target_lang_tag:
        raise ValueError(f"Language code '{lang_code}' not supported by Windows OCR mapping.")

    # Check if the specific language engine is already cached within Windows OCR
    if target_lang_tag in _windows_ocr_engines:
        # If the *currently active* engine is already Windows, just return the cached lang engine
        if _current_engine_type == "windows":
            # print(f"[OCR Init] Using cached Windows OCR engine for {target_lang_tag}.") # Optional
            # Update language tracker if needed
            _current_engine_lang = target_lang_tag
            # Set the current instance to this specific language engine
            _current_engine_instance = _windows_ocr_engines[target_lang_tag]
            return _current_engine_instance
        # Otherwise (if current engine is Paddle/EasyOCR), fall through to cleanup

    # --- Cleanup required if switching *from another type* ---
    if _current_engine_type != "windows":
        _cleanup_ocr_engine() # Clean up Paddle/EasyOCR

    # Now, initialize or retrieve the specific Windows language engine
    print(f"[OCR Init] Initializing Windows OCR for language: {target_lang_tag} (requested: {lang_code})")
    start_time = time.time()
    try:
        # Check again if it was cached just before cleanup (unlikely but safe)
        if target_lang_tag in _windows_ocr_engines:
            engine = _windows_ocr_engines[target_lang_tag]
        else:
            # Initialize the specific language engine
            win_lang = winsdk.windows.globalization.Language(target_lang_tag)
            if not win_ocr.OcrEngine.is_language_supported(win_lang):
                available_langs = win_ocr.OcrEngine.get_available_recognizer_languages()
                available_tags = [lang.language_tag for lang in available_langs]
                print(f"[OCR Init] Available Windows OCR languages: {available_tags}")
                raise RuntimeError(f"Windows OCR language '{target_lang_tag}' is not installed or supported.")

            engine = win_ocr.OcrEngine.try_create_from_language(win_lang)
            if engine is None:
                raise RuntimeError(f"Failed to create Windows OCR engine for '{target_lang_tag}'.")
            _windows_ocr_engines[target_lang_tag] = engine # Cache it

        # Set this engine as the currently active one
        _current_engine_instance = engine
        _current_engine_type = "windows"
        _current_engine_lang = target_lang_tag
        print(f"[OCR Init] Windows OCR initialized/set for {target_lang_tag} in {time.time() - start_time:.2f}s")
        return engine
    except Exception as e:
        print(f"[OCR Init] !!! Error initializing Windows OCR: {e}")
        # Don't call global cleanup here, as we might still be 'windows' type
        # Just ensure the failed language isn't wrongly cached as current
        if _current_engine_type == "windows" and _current_engine_lang == target_lang_tag:
            _current_engine_instance = None
            _current_engine_lang = None
            # Keep _current_engine_type as "windows" if other langs might still work
        raise RuntimeError(f"Failed to initialize Windows OCR for {target_lang_tag}: {e}")


# --- Windows OCR Async Helper ---
async def _convert_cv_to_software_bitmap(img_bgr):
    """Converts an OpenCV BGR image to a SoftwareBitmap via PNG encoding."""
    # (Keep implementation as before)
    is_success, buffer = cv2.imencode(".png", img_bgr)
    if not is_success:
        raise RuntimeError("Failed to encode OpenCV image to PNG format.")
    image_bytes = buffer.tobytes()
    stream = win_streams.InMemoryRandomAccessStream()
    writer = win_streams.DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(image_bytes)
    stored_bytes = await writer.store_async()
    await writer.flush_async()
    stream.seek(0)
    decoder = await win_imaging.BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    return software_bitmap


async def _run_windows_ocr_async(engine, img_bgr):
    """Helper to run Windows OCR asynchronously and remove inter-character spaces."""
    # (Keep implementation as before)
    if not _windows_ocr_available:
        return "[Windows OCR Error: Not Available]"
    try:
        software_bitmap = await _convert_cv_to_software_bitmap(img_bgr)
        ocr_result = await engine.recognize_async(software_bitmap)
        if ocr_result is None:
            print("[OCR Error] Windows OCR recognize_async returned None.")
            return "[Windows OCR Error: No Result]"
        extracted_lines = []
        if ocr_result.lines is not None:
            for line in ocr_result.lines:
                line_text = line.text
                processed_line_text = line_text.replace(" ", "")
                extracted_lines.append(processed_line_text)
        final_text = "\n".join(extracted_lines)
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
    Handles engine initialization and cleanup.
    """
    if img is None or img.size == 0:
        return "" # Return empty string for invalid input

    start_time = time.time()
    extracted_text = ""
    engine_instance = None

    try:
        # --- Engine Initialization (Thread Safe & with Cleanup) ---
        with _init_lock:
            if engine_type == "paddle":
                engine_instance = _init_paddle(lang)
            elif engine_type == "easyocr":
                engine_instance = _init_easyocr(lang)
            elif engine_type == "windows":
                engine_instance = _init_windows_ocr(lang)
            else:
                raise ValueError(f"Unsupported OCR engine type: {engine_type}")

        # Ensure an instance was successfully obtained
        if engine_instance is None:
            # This case should ideally be caught by exceptions in init functions,
            # but added as a safeguard.
            raise RuntimeError(f"Failed to get a valid engine instance for {engine_type}")

        # --- Perform OCR ---
        # (Keep the OCR processing logic for each engine type as before)
        if engine_type == "paddle":
            ocr_result_raw = engine_instance.ocr(img, cls=True)
            lines = []
            if ocr_result_raw and ocr_result_raw[0] is not None:
                for line_info in ocr_result_raw[0]:
                    if line_info and isinstance(line_info, list) and len(line_info) >= 2:
                        text_part = line_info[1]
                        if text_part and isinstance(text_part, (tuple, list)) and len(text_part) > 0:
                            lines.append(str(text_part[0]))
            extracted_text = " ".join(lines).strip() # Adjust joining as needed

        elif engine_type == "easyocr":
            ocr_result_raw = engine_instance.readtext(img)
            lines = [item[1] for item in ocr_result_raw if item and isinstance(item, (list, tuple)) and len(item) >= 2]
            extracted_text = " ".join(lines).strip() # Adjust joining as needed

        elif engine_type == "windows":
            if not _windows_ocr_available:
                extracted_text = "[Windows OCR Error: Not Available]"
            else:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                extracted_text = loop.run_until_complete(_run_windows_ocr_async(engine_instance, img))
                extracted_text = str(extracted_text).strip()

        elapsed = time.time() - start_time
        # print(f"[OCR] Extracted ({engine_type}/{lang}) in {elapsed:.3f}s: '{extracted_text[:50]}...'") # Optional log
        return extracted_text

    except RuntimeError as e: # Catch initialization or instance errors
        print(f"[OCR Error] Engine initialization/retrieval failed: {e}")
        return f"[{engine_type.upper()} Init Error]"
    except ValueError as e: # Catch language mapping/config errors
        print(f"[OCR Error] Configuration error: {e}")
        return f"[{engine_type.upper()} Config Error]"
    except Exception as e: # Catch runtime OCR errors
        print(f"[OCR Error] Failed during {engine_type} OCR: {e}")
        import traceback
        traceback.print_exc()
        # Attempt cleanup if runtime error occurs, as state might be bad
        with _init_lock:
            _cleanup_ocr_engine()
        return f"[{engine_type.upper()} Runtime Error]"

# --- END OF FILE utils/ocr.py ---