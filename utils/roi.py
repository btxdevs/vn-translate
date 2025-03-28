# --- START OF FILE utils/roi.py ---

import cv2
import numpy as np
import tkinter as tk # Added for color conversion

class ROI:
    DEFAULT_REPLACEMENT_COLOR_RGB = (128, 128, 128) # Default to gray

    def __init__(self, name, x1, y1, x2, y2,
                 color_filter_enabled=False, target_color=(255, 255, 255), color_threshold=30,
                 replacement_color=DEFAULT_REPLACEMENT_COLOR_RGB): # Added replacement_color
        self.name = name
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)

        # Color Filtering Attributes
        self.color_filter_enabled = color_filter_enabled

        # Store target_color consistently as an RGB tuple (int, int, int)
        self.target_color = self._parse_color_input(target_color, (255, 255, 255))

        # Store replacement_color consistently as an RGB tuple
        self.replacement_color = self._parse_color_input(replacement_color, self.DEFAULT_REPLACEMENT_COLOR_RGB)

        try:
            self.color_threshold = int(color_threshold)
        except (ValueError, TypeError):
            self.color_threshold = 30

    def _parse_color_input(self, color_input, default_rgb):
        """Parses hex string or tuple/list into an RGB tuple."""
        if isinstance(color_input, str):
            try:
                return ROI.hex_to_rgb(color_input)
            except:
                return default_rgb
        elif isinstance(color_input, (list, tuple)) and len(color_input) == 3:
            try:
                return tuple(int(c) for c in color_input)
            except (ValueError, TypeError):
                return default_rgb
        else:
            return default_rgb

    def to_dict(self):
        return {
            "name": self.name,
            "x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2,
            "color_filter_enabled": self.color_filter_enabled,
            "target_color": self.target_color, # Save as RGB tuple
            "color_threshold": self.color_threshold,
            "replacement_color": self.replacement_color # Save replacement color
        }

    @classmethod
    def from_dict(cls, data):
        # Provide defaults for backward compatibility
        color_filter_enabled = data.get("color_filter_enabled", False)
        target_color = data.get("target_color", (255, 255, 255)) # Expecting RGB tuple
        color_threshold = data.get("color_threshold", 30)
        # Default replacement color if missing in saved data
        replacement_color = data.get("replacement_color", cls.DEFAULT_REPLACEMENT_COLOR_RGB)

        return cls(data["name"], data["x1"], data["y1"], data["x2"], data["y2"],
                   color_filter_enabled, target_color, color_threshold, replacement_color)

    def extract_roi(self, frame):
        """Extracts the ROI portion from the frame."""
        try:
            h, w = frame.shape[:2]
            # Ensure coordinates are within frame bounds
            y1 = max(0, int(self.y1))
            y2 = min(h, int(self.y2))
            x1 = max(0, int(self.x1))
            x2 = min(w, int(self.x2))
            # Check for invalid dimensions after clamping
            if y1 >= y2 or x1 >= x2:
                return None
            return frame[y1:y2, x1:x2]
        except Exception as e:
            print(f"Error extracting ROI image for {self.name}: {e}")
            return None

    def apply_color_filter(self, roi_img):
        """Applies color filtering to the extracted ROI image if enabled."""
        if not self.color_filter_enabled or roi_img is None:
            return roi_img

        try:
            # Target color is stored as RGB, convert to BGR for OpenCV
            target_bgr = self.target_color[::-1]
            # Replacement color is stored as RGB, convert to BGR
            replacement_bgr = self.replacement_color[::-1]
            thresh = self.color_threshold

            # Calculate lower and upper bounds in BGR for the target color
            lower_bound = np.array([max(0, c - thresh) for c in target_bgr], dtype=np.uint8)
            upper_bound = np.array([min(255, c + thresh) for c in target_bgr], dtype=np.uint8)

            # Create a mask where pixels are within the threshold of the target color
            mask = cv2.inRange(roi_img, lower_bound, upper_bound)

            # Create a background image filled with the replacement color
            background = np.full_like(roi_img, replacement_bgr)

            # Copy only the pixels *within* the mask (matching target color) from the original ROI
            filtered_img = cv2.bitwise_and(roi_img, roi_img, mask=mask)

            # Copy only the pixels *outside* the mask from the replacement background
            background_masked = cv2.bitwise_and(background, background, mask=cv2.bitwise_not(mask))

            # Combine the filtered pixels (matching target) and the background pixels (non-matching)
            result_img = cv2.add(filtered_img, background_masked)

            return result_img

        except Exception as e:
            print(f"Error applying color filter for ROI {self.name}: {e}")
            return roi_img # Return original on error

    def get_overlay_config(self, global_settings):
        # This remains unchanged, deals only with overlay appearance
        from ui.overlay_manager import OverlayManager # Keep import local if needed
        try:
            defaults = OverlayManager.DEFAULT_OVERLAY_CONFIG.copy()
        except AttributeError:
            defaults = {
                "enabled": True, "font_family": "Segoe UI", "font_size": 14,
                "font_color": "white", "bg_color": "#222222", "alpha": 1.0,
                "wraplength": 450, "justify": "left", "geometry": None
            }

        roi_specific_settings = global_settings.get('overlay_settings', {}).get(self.name, {})
        config = defaults.copy()
        config.update(roi_specific_settings)
        return config

    @staticmethod
    def rgb_to_hex(rgb_tuple):
        """Converts an (R, G, B) tuple to #RRGGBB hex string."""
        try:
            # Ensure values are integers within 0-255 range
            r, g, b = [max(0, min(255, int(c))) for c in rgb_tuple]
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, TypeError, IndexError):
            return "#808080" # Fallback to gray

    @staticmethod
    def hex_to_rgb(hex_string):
        """Converts an #RRGGBB hex string to (R, G, B) tuple."""
        hex_color = str(hex_string).lstrip('#')
        if len(hex_color) == 6:
            try:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            except ValueError:
                return ROI.DEFAULT_REPLACEMENT_COLOR_RGB # Fallback
        elif len(hex_color) == 3: # Handle shorthand hex (e.g., #F00)
            try:
                return tuple(int(c*2, 16) for c in hex_color)
            except ValueError:
                return ROI.DEFAULT_REPLACEMENT_COLOR_RGB # Fallback
        else:
            return ROI.DEFAULT_REPLACEMENT_COLOR_RGB # Fallback for invalid length

# --- END OF FILE utils/roi.py ---