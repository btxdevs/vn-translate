class ROI:
    def __init__(self, name, x1, y1, x2, y2):
        self.name = name
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)

    def to_dict(self):
        return {"name": self.name, "x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["x1"], data["y1"], data["x2"], data["y2"])

    def extract_roi(self, frame):
        try:
            h, w = frame.shape[:2]
            y1 = max(0, int(self.y1))
            y2 = min(h, int(self.y2))
            x1 = max(0, int(self.x1))
            x2 = min(w, int(self.x2))
            if y1 >= y2 or x1 >= x2:
                return None
            return frame[y1:y2, x1:x2]
        except Exception as e:
            print(f"Error extracting ROI image for {self.name}: {e}")
            return None

    def get_overlay_config(self, global_settings):
        from ui.overlay_manager import OverlayManager
        defaults = OverlayManager.DEFAULT_OVERLAY_CONFIG.copy()
        roi_specific_settings = global_settings.get('overlay_settings', {}).get(self.name, {})
        config = defaults.copy()
        config.update(roi_specific_settings)
        return config
