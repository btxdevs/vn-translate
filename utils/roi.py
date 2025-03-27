class ROI:
    """Represents a Region of Interest for text extraction."""
    def __init__(self, name, x1, y1, x2, y2):
        self.name = name
        # Ensure coordinates are ordered correctly
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
        try:
            # Ensure coordinates are integers and within frame bounds
            h, w = frame.shape[:2]
            y1 = max(0, int(self.y1))
            y2 = min(h, int(self.y2))
            x1 = max(0, int(self.x1))
            x2 = min(w, int(self.x2))
            if y1 >= y2 or x1 >= x2:
                # print(f"Warning: Invalid ROI dimensions for '{self.name}' after clamping.")
                return None # Return None if dimensions are invalid
            return frame[y1:y2, x1:x2]
        except Exception as e:
            print(f"Error extracting ROI image for {self.name}: {e}")
            return None

    def get_overlay_config(self, global_settings):
        """Gets overlay config for this ROI, merging specific settings over defaults."""
        # Use the default structure defined in OverlayManager or OverlayTab
        from ui.overlay_manager import OverlayManager # Avoid circular import at top level
        defaults = OverlayManager.DEFAULT_OVERLAY_CONFIG.copy()

        roi_specific_settings = global_settings.get('overlay_settings', {}).get(self.name, {})

        # Merge defaults with specific settings
        config = defaults.copy()
        config.update(roi_specific_settings)
        return config