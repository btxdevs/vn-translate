import time
import threading
import numpy as np
import cv2
import io
import re

try:
    from paddleocr import PaddleOCR
    _paddle_available = True
except ImportError:
    _paddle_available = False

try:
    import easyocr
    _easyocr_available = True
except ImportError:
    _easyocr_available = False

try:
    import asyncio
    import winsdk.windows.media.ocr as win_ocr
    import winsdk.windows.graphics.imaging as win_imaging
    import winsdk.windows.storage.streams as win_streams
    import winsdk.windows.globalization
    _windows_ocr_available = True
except ImportError:
    _windows_ocr_available = False
except OSError:
    _windows_ocr_available = False

_paddle_ocr_instance = None
_paddle_lang_loaded = None
_easyocr_instance = None
_easyocr_lang_loaded = None
_windows_ocr_engines = {}
_init_lock = threading.Lock()

PADDLE_LANG_MAP = {
    "jpn": "japan",
    "jpn_vert": "japan",
    "eng": "en",
    "chi_sim": "ch",
    "chi_tra": "ch",
    "kor": "ko",
}

EASYOCR_LANG_MAP = {
    "jpn": "ja",
    "jpn_vert": "ja",
    "eng": "en",
    "chi_sim": "ch_sim",
    "chi_tra": "ch_tra",
    "kor": "ko",
}

WINDOWS_OCR_LANG_MAP = {
    "jpn": "ja",
    "jpn_vert": "ja",
    "eng": "en-US",
    "chi_sim": "zh-Hans",
    "chi_tra": "zh-Hant",
    "kor": "ko",
}


def _init_paddle(lang_code):
    global _paddle_ocr_instance, _paddle_lang_loaded
    if not _paddle_available:
        raise RuntimeError("PaddleOCR library is not installed.")
    target_lang = PADDLE_LANG_MAP.get(lang_code, "en")
    if _paddle_ocr_instance and _paddle_lang_loaded == target_lang:
        return _paddle_ocr_instance
    try:
        instance = PaddleOCR(use_angle_cls=True, lang=target_lang, show_log=False)
        _paddle_ocr_instance = instance
        _paddle_lang_loaded = target_lang
        return instance
    except Exception as e:
        _paddle_ocr_instance = None
        _paddle_lang_loaded = None
        raise RuntimeError(f"Failed to initialize PaddleOCR: {e}")


def _init_easyocr(lang_code):
    global _easyocr_instance, _easyocr_lang_loaded
    if not _easyocr_available:
        raise RuntimeError("EasyOCR library is not installed.")
    target_lang = EASYOCR_LANG_MAP.get(lang_code)
    if not target_lang:
        raise ValueError(f"Language code '{lang_code}' not supported by EasyOCR mapping.")
    target_lang_list = [target_lang]
    if _easyocr_instance and _easyocr_lang_loaded == target_lang_list:
        return _easyocr_instance
    try:
        instance = easyocr.Reader(target_lang_list, gpu=True)
        _easyocr_instance = instance
        _easyocr_lang_loaded = target_lang_list
        return instance
    except Exception as e:
        _easyocr_instance = None
        _easyocr_lang_loaded = None
        raise RuntimeError(f"Failed to initialize EasyOCR: {e}")


def _is_windows_ocr_lang_available(win_lang_tag):
    if not _windows_ocr_available:
        return False
    try:
        lang = winsdk.windows.globalization.Language(win_lang_tag)
        return win_ocr.OcrEngine.is_language_supported(lang)
    except Exception:
        return False


def _init_windows_ocr(lang_code):
    global _windows_ocr_engines
    if not _windows_ocr_available:
        raise RuntimeError("Windows OCR components (winsdk) are not available.")
    target_lang_tag = WINDOWS_OCR_LANG_MAP.get(lang_code)
    if not target_lang_tag:
        raise ValueError(f"Language code '{lang_code}' not supported by Windows OCR mapping.")
    if target_lang_tag in _windows_ocr_engines:
        return _windows_ocr_engines[target_lang_tag]
    try:
        win_lang = winsdk.windows.globalization.Language(target_lang_tag)
        if not win_ocr.OcrEngine.is_language_supported(win_lang):
            raise RuntimeError(f"Windows OCR language '{target_lang_tag}' is not installed or supported.")
        engine = win_ocr.OcrEngine.try_create_from_language(win_lang)
        if engine is None:
            raise RuntimeError(f"Failed to create Windows OCR engine for '{target_lang_tag}'.")
        _windows_ocr_engines[target_lang_tag] = engine
        return engine
    except Exception as e:
        if target_lang_tag in _windows_ocr_engines:
            del _windows_ocr_engines[target_lang_tag]
        raise RuntimeError(f"Failed to initialize Windows OCR for {target_lang_tag}: {e}")


async def _convert_cv_to_software_bitmap(img_bgr):
    is_success, buffer = cv2.imencode(".png", img_bgr)
    if not is_success:
        raise RuntimeError("Failed to encode OpenCV image to PNG format.")
    image_bytes = buffer.tobytes()
    stream = win_streams.InMemoryRandomAccessStream()
    writer = win_streams.DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(image_bytes)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)
    decoder = await win_imaging.BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    return software_bitmap


async def _run_windows_ocr_async(engine, img_bgr):
    try:
        software_bitmap = await _convert_cv_to_software_bitmap(img_bgr)
        ocr_result = await engine.recognize_async(software_bitmap)
        if ocr_result is None:
            return "[Windows OCR Error: No Result]"
        extracted_lines = []
        if ocr_result.lines is not None:
            for line in ocr_result.lines:
                processed_line_text = line.text.replace(" ", "")
                extracted_lines.append(processed_line_text)
        final_text = "\n".join(extracted_lines)
        return final_text
    except Exception:
        import traceback
        traceback.print_exc()
        return "[Windows OCR Error]"


def extract_text(img, lang="jpn", engine_type="paddle"):
    if img is None or img.size == 0:
        return ""
    engine_instance = None
    try:
        with _init_lock:
            if engine_type == "paddle":
                engine_instance = _init_paddle(lang)
            elif engine_type == "easyocr":
                engine_instance = _init_easyocr(lang)
            elif engine_type == "windows":
                engine_instance = _init_windows_ocr(lang)
            else:
                raise ValueError(f"Unsupported OCR engine type: {engine_type}")

        if engine_type == "paddle":
            ocr_result_raw = engine_instance.ocr(img, cls=True)
            lines = []
            if ocr_result_raw and ocr_result_raw[0] is not None:
                for line_info in ocr_result_raw[0]:
                    if line_info and isinstance(line_info, list) and len(line_info) >= 2:
                        text_part = line_info[1]
                        if text_part and isinstance(text_part, (tuple, list)) and len(text_part) > 0:
                            lines.append(str(text_part[0]))
            extracted_text = " ".join(lines).strip()
        elif engine_type == "easyocr":
            ocr_result_raw = engine_instance.readtext(img)
            lines = [item[1] for item in ocr_result_raw if item and isinstance(item, (list, tuple)) and len(item) >= 2]
            extracted_text = " ".join(lines).strip()
        elif engine_type == "windows":
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            extracted_text = loop.run_until_complete(_run_windows_ocr_async(engine_instance, img))
            extracted_text = str(extracted_text).strip()
        return extracted_text
    except RuntimeError:
        return f"[{engine_type.upper()} Init Error]"
    except ValueError:
        return f"[{engine_type.upper()} Config Error]"
    except Exception:
        import traceback
        traceback.print_exc()
        return f"[{engine_type.upper()} Runtime Error]"