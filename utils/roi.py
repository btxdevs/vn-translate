from paddleocr import PaddleOCR

class ROI:
    """Represents a Region of Interest for text extraction."""
    def __init__(self, name, x1, y1, x2, y2):
        self.name = name
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)

    def to_dict(self):
        """Convert the ROI to a dictionary for serialization."""
        return {"name": self.name, "x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, data):
        """Create an ROI instance from a dictionary."""
        return cls(data["name"], data["x1"], data["y1"], data["x2"], data["y2"])

    def extract_roi(self, frame):
        """Extract the ROI region from the given frame."""
        return frame[self.y1:self.y2, self.x1:self.x2]

    def extract_text(self, frame, lang="jpn"):
        """
        Extract text from the ROI region in the given frame using PaddleOCR.
        The 'lang' parameter is mapped to PaddleOCR's language codes.
        """
        try:
            roi_img = self.extract_roi(frame)
            lang_map = {
                "jpn": "japan",
                "jpn_vert": "japan",
                "eng": "en",
                "chi_sim": "ch",
                "chi_tra": "ch",
                "kor": "ko"
            }
            ocr_lang = lang_map.get(lang, "en")
            ocr = PaddleOCR(use_angle_cls=True, lang=ocr_lang, show_log=False)
            result = ocr.ocr(roi_img, cls=True)

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
        except Exception as e:
            print(f"Error extracting text from ROI {self.name}: {e}")
            return ""