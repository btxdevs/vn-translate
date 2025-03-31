# --- START OF FILE ocr.py ---

import time
import threading
import numpy as np
import cv2 # Keep cv2 for image handling and initial conversion
import io # For in-memory byte streams
import re # Import regex module
import platform # To check OS
import gc # Import garbage collector
import os # For checking Tesseract path
import shutil # For finding executables
import warnings # To suppress specific warnings if needed

# Suppress specific warnings if they become noisy, e.g., from underlying libraries
# warnings.filterwarnings("ignore", category=UserWarning, module='paddleocr')

# --- Prerequisites for GPU Acceleration ---
# (Comments remain unchanged)

# --- Engine Specific Imports ---
_paddle_available = False
try:
    os.environ['PP_DISABLE_BANNER'] = '1'
    from paddleocr import PaddleOCR
    _paddle_available = True
except ImportError:
    print("INFO: PaddleOCR not found. Install with 'pip install paddlepaddle paddleocr'. For GPU, install 'paddlepaddle-gpu'.")
except Exception as e:
    print(f"WARN: Error during PaddleOCR import: {e}")


_easyocr_available = False
try:
    import easyocr
    _easyocr_available = True
except ImportError:
    print("INFO: EasyOCR not found. Install with 'pip install easyocr'. For GPU, ensure PyTorch with CUDA is installed first.")
except Exception as e:
    print(f"WARN: Error during EasyOCR import: {e}")

_windows_ocr_available = False
if platform.system() == "Windows":
    try:
        import asyncio
        import winsdk.windows.media.ocr as win_ocr
        import winsdk.windows.graphics.imaging as win_imaging
        import winsdk.windows.storage.streams as win_streams
        import winsdk.windows.globalization
        _windows_ocr_available = True
    except ImportError:
        print("INFO: Windows SDK components (winsdk) not found or failed to import. Install with 'pip install winsdk'. Ensure Windows SDK is installed if issues persist.")
    except OSError as e:
        print(f"WARN: Error loading Windows SDK components (winsdk): {e}. Windows OCR disabled.")
else:
    print("INFO: Windows OCR is only available on the Windows platform.")

_tesseract_available = False
_tesseract_cmd = None
try:
    import pytesseract
    # 1. Check PATH first (most standard)
    _tesseract_cmd = shutil.which("tesseract")

    # 2. If not in PATH, check common Windows locations explicitly, deriving from SystemDrive
    if not _tesseract_cmd and platform.system() == "Windows":
        # print("DEBUG: Tesseract not found in PATH, checking common locations...") # Optional debug

        # Get the system drive letter (e.g., "C:"), default to "C:" if not found
        system_drive = os.environ.get("SystemDrive", "C:")

        # Construct paths based on the dynamic system drive
        program_files_path = os.path.join(system_drive, os.sep, "Program Files") # Use os.sep for robustness
        program_files_x86_path = os.path.join(system_drive, os.sep, "Program Files (x86)")

        # List of paths to check, starting with dynamically constructed common paths
        common_paths_to_check = [
            os.path.join(program_files_path, "Tesseract-OCR", "tesseract.exe"),
            os.path.join(program_files_x86_path, "Tesseract-OCR", "tesseract.exe"),
        ]

        # Also check paths derived directly from environment variables, as they might differ
        # (e.g., if Program Files is on a different drive than SystemDrive)
        env_program_files = os.environ.get("ProgramFiles")
        env_program_files_x86 = os.environ.get("ProgramFiles(x86)")
        env_local_app_data = os.environ.get("LOCALAPPDATA")

        if env_program_files:
            common_paths_to_check.append(os.path.join(env_program_files, "Tesseract-OCR", "tesseract.exe"))
        if env_program_files_x86:
            common_paths_to_check.append(os.path.join(env_program_files_x86, "Tesseract-OCR", "tesseract.exe"))
        if env_local_app_data:
            common_paths_to_check.append(os.path.join(env_local_app_data, "Tesseract-OCR", "tesseract.exe")) # User install

        # Normalize and check existence for the list of potential paths, avoiding duplicates
        checked_paths = set()
        for path in common_paths_to_check:
            if not path: continue # Skip if an env var was empty
            normalized_path = os.path.normpath(path)
            if normalized_path in checked_paths:
                continue
            checked_paths.add(normalized_path)

            # print(f"DEBUG: Checking for Tesseract at: {normalized_path}") # Optional debug
            if os.path.exists(normalized_path):
                # print(f"DEBUG: Found Tesseract at: {normalized_path}") # Optional debug
                _tesseract_cmd = normalized_path
                break # Found it, stop checking

    # 3. If a command path was found (either via PATH or common locations), verify it
    if _tesseract_cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd
            version = pytesseract.get_tesseract_version()
            if version:
                _tesseract_available = True
                # print(f"DEBUG: Tesseract version {version} detected at {_tesseract_cmd}.") # Optional debug
            else:
                _tesseract_cmd = None
                _tesseract_available = False
                print(f"WARN: Found Tesseract at '{_tesseract_cmd}' but could not get version. Marking as unavailable.")
        except pytesseract.TesseractNotFoundError:
            _tesseract_cmd = None
            _tesseract_available = False
            print(f"WARN: Tesseract command '{_tesseract_cmd}' set but pytesseract could not find/run it.")
        except Exception as e:
            print(f"WARN: Error checking Tesseract version (path: {_tesseract_cmd}): {e}")
            _tesseract_available = True # Assume it might work despite version check error

    # 4. Final check and info message
    if not _tesseract_available:
        print(f"INFO: Tesseract executable not found in PATH or common locations (like {os.path.join(os.environ.get('SystemDrive', 'C:'), os.sep, 'Program Files', 'Tesseract-OCR')}), or failed verification. Install Tesseract OCR (https://github.com/tesseract-ocr/tessdoc) and ensure it's runnable.")

except ImportError:
    print("INFO: pytesseract not found. Install with 'pip install pytesseract'. You also need the Tesseract OCR engine.")
except Exception as e:
    print(f"WARN: An unexpected error occurred during Tesseract setup: {e}")


# --- Globals for Engine Instances (Unified Management) ---
_current_engine_instance = None
_current_engine_type = None
_current_engine_lang = None # Tracks language ('en', 'ja', ['ja'], 'jpn+eng', etc.)
_windows_ocr_engines = {} # Cache engines per language *within* Windows OCR
_init_lock = threading.Lock() # Lock for initializing engines

# --- Language Mappings ---
# (Mappings remain unchanged)
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
TESSERACT_LANG_MAP = {
    "jpn": "jpn", "jpn_vert": "jpn_vert", "eng": "eng",
    "chi_sim": "chi_sim", "chi_tra": "chi_tra", "kor": "kor",
}

# --- Engine Cleanup Function ---
def _cleanup_ocr_engine():
    """Explicitly cleans up the current OCR engine instance (silently)."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang, _windows_ocr_engines
    if _current_engine_instance is not None or _current_engine_type is not None:
        engine_type_being_cleaned = _current_engine_type
        try:
            if _current_engine_instance is not None:
                del _current_engine_instance
        except Exception:
            pass # Ignore errors during deletion

        if engine_type_being_cleaned == "windows":
            _windows_ocr_engines.clear()

        _current_engine_instance = None
        _current_engine_type = None
        _current_engine_lang = None

        gc.collect()

        if engine_type_being_cleaned == "easyocr":
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            except Exception:
                pass


# --- Engine Initialization Functions (with cleanup logic, silent) ---

def _init_paddle(lang_code):
    """Initializes PaddleOCR (silently), cleaning up previous engines."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang
    if not _paddle_available:
        raise RuntimeError("PaddleOCR library is not installed.")

    target_lang = PADDLE_LANG_MAP.get(lang_code, "en")

    if _current_engine_type == "paddle" and _current_engine_lang == target_lang:
        return _current_engine_instance

    _cleanup_ocr_engine()

    try:
        instance = PaddleOCR(use_angle_cls=True, lang=target_lang, show_log=False, use_gpu=True)
        _current_engine_instance = instance
        _current_engine_type = "paddle"
        _current_engine_lang = target_lang
        return instance
    except Exception as e:
        print(f"ERROR: Failed to initialize PaddleOCR: {e}") # Keep critical errors
        _cleanup_ocr_engine()
        raise RuntimeError(f"Failed to initialize PaddleOCR: {e}")

def _init_easyocr(lang_code):
    """Initializes EasyOCR (silently), cleaning up previous engines."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang
    if not _easyocr_available:
        raise RuntimeError("EasyOCR library is not installed.")

    target_lang = EASYOCR_LANG_MAP.get(lang_code)
    if not target_lang:
        raise ValueError(f"Language code '{lang_code}' not supported by EasyOCR mapping.")
    target_lang_list = [target_lang]

    if _current_engine_type == "easyocr" and _current_engine_lang == target_lang_list:
        return _current_engine_instance

    _cleanup_ocr_engine()

    try:
        instance = easyocr.Reader(target_lang_list, gpu=True, verbose=False)
        _current_engine_instance = instance
        _current_engine_type = "easyocr"
        _current_engine_lang = target_lang_list
        return instance
    except Exception as e:
        print(f"ERROR: Failed to initialize EasyOCR: {e}") # Keep critical errors
        _cleanup_ocr_engine()
        raise RuntimeError(f"Failed to initialize EasyOCR: {e}")

def _is_windows_ocr_lang_available(win_lang_tag):
    """Checks if a specific BCP-47 language tag is supported by Windows OCR (silently)."""
    if not _windows_ocr_available:
        return False
    try:
        lang = winsdk.windows.globalization.Language(win_lang_tag)
        return win_ocr.OcrEngine.is_language_supported(lang)
    except Exception as e:
        return False

def _init_windows_ocr(lang_code):
    """Initializes Windows OCR (silently), cleaning up previous engines."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang, _windows_ocr_engines
    if not _windows_ocr_available:
        raise RuntimeError("Windows OCR components (winsdk) are not available on this system.")

    target_lang_tag = WINDOWS_OCR_LANG_MAP.get(lang_code)
    if not target_lang_tag:
        raise ValueError(f"Language code '{lang_code}' not supported by Windows OCR mapping.")

    if target_lang_tag in _windows_ocr_engines:
        if _current_engine_type == "windows":
            _current_engine_lang = target_lang_tag
            _current_engine_instance = _windows_ocr_engines[target_lang_tag]
            return _current_engine_instance

    if _current_engine_type != "windows":
        _cleanup_ocr_engine()

    try:
        if target_lang_tag in _windows_ocr_engines:
            engine = _windows_ocr_engines[target_lang_tag]
        else:
            win_lang = winsdk.windows.globalization.Language(target_lang_tag)
            if not win_ocr.OcrEngine.is_language_supported(win_lang):
                available_langs = win_ocr.OcrEngine.get_available_recognizer_languages()
                available_tags = [lang.language_tag for lang in available_langs]
                print(f"ERROR: Windows OCR language '{target_lang_tag}' is not installed/supported. Available: {available_tags}. Install via Windows Settings.")
                raise RuntimeError(f"Windows OCR language '{target_lang_tag}' not available.")

            engine = win_ocr.OcrEngine.try_create_from_language(win_lang)
            if engine is None:
                raise RuntimeError(f"Failed to create Windows OCR engine for '{target_lang_tag}'.")
            _windows_ocr_engines[target_lang_tag] = engine

        _current_engine_instance = engine
        _current_engine_type = "windows"
        _current_engine_lang = target_lang_tag
        return engine
    except Exception as e:
        print(f"ERROR: Failed to initialize Windows OCR for {target_lang_tag}: {e}") # Keep critical errors
        if _current_engine_type == "windows" and _current_engine_lang == target_lang_tag:
            _current_engine_instance = None
            _current_engine_lang = None
            if target_lang_tag in _windows_ocr_engines:
                del _windows_ocr_engines[target_lang_tag]
        raise RuntimeError(f"Failed to initialize Windows OCR for {target_lang_tag}: {e}")


def _init_tesseract(lang_code):
    """Initializes Tesseract (silently), cleaning up previous engines."""
    global _current_engine_instance, _current_engine_type, _current_engine_lang
    if not _tesseract_available:
        # This error is crucial if the user selected Tesseract
        raise RuntimeError("Tesseract is not available or configured correctly (check PATH or common install locations).")

    target_lang = TESSERACT_LANG_MAP.get(lang_code)
    if not target_lang:
        raise ValueError(f"Language code '{lang_code}' not supported by Tesseract mapping.")

    if _current_engine_type == "tesseract" and _current_engine_lang == target_lang:
        return None # Tesseract is stateless via pytesseract

    _cleanup_ocr_engine()

    try:
        # Check if the command path is still valid according to pytesseract
        current_tess_cmd = pytesseract.pytesseract.tesseract_cmd
        if not current_tess_cmd or not os.path.exists(current_tess_cmd):
            # This could happen if the executable was removed after initial check
            raise pytesseract.TesseractNotFoundError(f"Tesseract command path '{current_tess_cmd}' not set or invalid during initialization.")

        _current_engine_instance = None
        _current_engine_type = "tesseract"
        _current_engine_lang = target_lang
        return None
    except pytesseract.TesseractNotFoundError as e:
        print(f"ERROR: Tesseract executable check failed during init: {e}") # Keep critical errors
        _cleanup_ocr_engine()
        raise RuntimeError(f"Tesseract executable error during init: {e}.")
    except Exception as e:
        print(f"ERROR: Failed Tesseract setup: {e}") # Keep critical errors
        _cleanup_ocr_engine()
        raise RuntimeError(f"Failed Tesseract setup: {e}")


# --- Windows OCR Async Helper ---
async def _convert_cv_to_software_bitmap(img_bgr):
    """Converts an OpenCV BGR image to a SoftwareBitmap via PNG encoding (silently)."""
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
    software_bitmap = await decoder.get_software_bitmap_async(
        win_imaging.BitmapPixelFormat.BGRA8,
        win_imaging.BitmapAlphaMode.PREMULTIPLIED
    )
    return software_bitmap


async def _run_windows_ocr_async(engine, img_bgr):
    """Helper to run Windows OCR asynchronously (silently on success)."""
    if not _windows_ocr_available:
        return "[Windows OCR Error: Not Available]"
    try:
        software_bitmap = await _convert_cv_to_software_bitmap(img_bgr)
        if engine is None:
            return "[Windows OCR Error: Engine not initialized]"
        ocr_result = await engine.recognize_async(software_bitmap)
        if ocr_result is None:
            return "[Windows OCR Error: No Result]"
        extracted_lines = []
        if ocr_result.lines is not None:
            for line in ocr_result.lines:
                processed_line_text = line.text # Keep spaces by default
                extracted_lines.append(processed_line_text)
        final_text = "\n".join(extracted_lines)
        return final_text
    except Exception as e:
        print(f"ERROR: Windows OCR async processing failed: {e}") # Keep critical errors
        return "[Windows OCR Error]"

# --- Main Extraction Function ---

def extract_text(img, lang="jpn", engine_type="paddle"):
    """
    Extracts text from an image using the specified engine and language.
    Handles engine initialization and cleanup. Reduced logging.

    Args:
        img (numpy.ndarray): The input image in BGR format (from OpenCV).
        lang (str): The desired language code (e.g., "jpn", "eng", "chi_sim").
        engine_type (str): The OCR engine to use ("paddle", "easyocr", "windows", "tesseract").

    Returns:
        str: The extracted text, or an error message string on failure.
    """
    if img is None or img.size == 0:
        return "" # Return empty string for invalid input

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
            elif engine_type == "tesseract":
                engine_instance = _init_tesseract(lang) # Returns None on success
            else:
                raise ValueError(f"Unsupported OCR engine type: {engine_type}")

        # --- Perform OCR ---
        current_type = _current_engine_type # Cache locally for this run
        current_lang = _current_engine_lang # Cache locally

        if current_type == "paddle":
            if engine_instance is None: raise RuntimeError("PaddleOCR instance is None after init.")
            ocr_result_raw = engine_instance.ocr(img, cls=True)
            lines = []
            if ocr_result_raw and isinstance(ocr_result_raw, list) and len(ocr_result_raw) > 0 and ocr_result_raw[0] is not None:
                for line_info in ocr_result_raw[0]:
                    if line_info and isinstance(line_info, list) and len(line_info) == 2:
                        text_part = line_info[1]
                        if text_part and isinstance(text_part, (tuple, list)) and len(text_part) > 0:
                            lines.append(str(text_part[0]))
            extracted_text = " ".join(lines).strip()

        elif current_type == "easyocr":
            if engine_instance is None: raise RuntimeError("EasyOCR instance is None after init.")
            ocr_result_raw = engine_instance.readtext(img)
            lines = [item[1] for item in ocr_result_raw if item and isinstance(item, (list, tuple)) and len(item) >= 2]
            extracted_text = " ".join(lines).strip()

        elif current_type == "windows":
            if engine_instance is None: raise RuntimeError("Windows OCR instance is None after init.")
            if not _windows_ocr_available:
                extracted_text = "[Windows OCR Error: Not Available]"
            else:
                try:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if not loop.is_running():
                    extracted_text = loop.run_until_complete(_run_windows_ocr_async(engine_instance, img))
                else:
                    future = asyncio.run_coroutine_threadsafe(_run_windows_ocr_async(engine_instance, img), loop)
                    extracted_text = future.result()

                extracted_text = str(extracted_text).strip()

        elif current_type == "tesseract":
            if not _tesseract_available:
                extracted_text = "[Tesseract Error: Not Available]"
            else:
                try:
                    current_tess_cmd = pytesseract.pytesseract.tesseract_cmd
                    if not current_tess_cmd:
                        raise pytesseract.TesseractNotFoundError("Tesseract command path not configured.")
                    # Check existence again just before use, belt-and-suspenders
                    if not os.path.exists(current_tess_cmd):
                        raise pytesseract.TesseractNotFoundError(f"Tesseract executable not found at '{current_tess_cmd}' during OCR.")

                    extracted_text = pytesseract.image_to_string(img, lang=current_lang)
                    extracted_text = extracted_text.strip().replace('\f', '')
                except pytesseract.TesseractNotFoundError as e:
                    print(f"ERROR: Tesseract executable not found or failed during OCR: {e}") # Keep critical error
                    extracted_text = "[Tesseract Error: Not Found]"
                    with _init_lock: _cleanup_ocr_engine() # Attempt cleanup as Tesseract state is now invalid
                except Exception as e_tess:
                    print(f"ERROR: Tesseract failed during image processing: {e_tess}") # Keep critical error
                    extracted_text = "[Tesseract Runtime Error]"
                    # No need to cleanup here usually, as it's likely an image issue

        return extracted_text

    except RuntimeError as e: # Catch initialization or instance errors
        print(f"ERROR: OCR Engine initialization failed ({engine_type}): {e}") # Simplified critical error
        with _init_lock:
            if _current_engine_type == engine_type:
                _cleanup_ocr_engine()
        return f"[{engine_type.upper()} Init Error]"
    except ValueError as e: # Catch language mapping/config errors
        print(f"ERROR: OCR Configuration error ({engine_type}): {e}") # Simplified critical error
        with _init_lock: _cleanup_ocr_engine()
        return f"[{engine_type.upper()} Config Error]"
    except Exception as e: # Catch runtime OCR errors or unexpected issues
        print(f"ERROR: OCR Runtime failed ({engine_type}): {e}") # Simplified critical error
        # import traceback # Keep traceback for debugging if needed
        # traceback.print_exc()
        with _init_lock:
            _cleanup_ocr_engine()
        return f"[{engine_type.upper()} Runtime Error]"

# --- END OF FILE ocr.py ---