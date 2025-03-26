from paddleocr import PaddleOCR

def preprocess_image(img):
    """
    Preprocess the image if necessary.
    For PaddleOCR, you may pass the image directly or add custom preprocessing.
    """
    return img

def extract_text(img, lang="jpn"):
    """
    Extract text from an image using PaddleOCR.
    The 'lang' parameter is mapped to PaddleOCR's language codes.

    Args:
        img: The input image (numpy array)
        lang: Language code ("jpn", "eng", etc.)

    Returns:
        Extracted text as a string
    """
    lang_map = {
        "jpn": "japan",
        "jpn_vert": "japan",
        "eng": "en",
        "chi_sim": "ch",
        "chi_tra": "ch",
        "kor": "ko"
    }
    ocr_lang = lang_map.get(lang, "en")
    # Create a new OCR engine instance with the desired language.
    ocr = PaddleOCR(use_angle_cls=True, lang=ocr_lang, show_log=False)
    processed = preprocess_image(img)
    result = ocr.ocr(processed, cls=True)

    # Handle None result
    if result is None:
        return ""

    text = ""
    for line in result:
        # Some versions of PaddleOCR may return empty lists
        if line:
            for word_info in line:
                if word_info and len(word_info) >= 2 and word_info[1] and len(word_info[1]) >= 1:
                    text += word_info[1][0] + " "
    return text.strip()