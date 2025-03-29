import cv2
import numpy as np
import tkinter as tk


class ROI:
    DEFAULT_REPLACEMENT_COLOR_RGB = (128, 128, 128)

    def __init__(
            self,
            name,
            x1,
            y1,
            x2,
            y2,
            color_filter_enabled=False,
            target_color=(255, 255, 255),
            color_threshold=30,
            replacement_color=DEFAULT_REPLACEMENT_COLOR_RGB,
    ):
        self.name = name
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)
        self.color_filter_enabled = color_filter_enabled
        self.target_color = self._parse_color_input(target_color, (255, 255, 255))
        self.replacement_color = self._parse_color_input(replacement_color, self.DEFAULT_REPLACEMENT_COLOR_RGB)
        try:
            self.color_threshold = int(color_threshold)
        except (ValueError, TypeError):
            self.color_threshold = 30

    def _parse_color_input(self, color_input, default_rgb):
        if isinstance(color_input, str):
            try:
                return ROI.hex_to_rgb(color_input)
            except Exception:
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
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "color_filter_enabled": self.color_filter_enabled,
            "target_color": self.target_color,
            "color_threshold": self.color_threshold,
            "replacement_color": self.replacement_color,
        }

    @classmethod
    def from_dict(cls, data):
        color_filter_enabled = data.get("color_filter_enabled", False)
        target_color = data.get("target_color", (255, 255, 255))
        color_threshold = data.get("color_threshold", 30)
        replacement_color = data.get("replacement_color", cls.DEFAULT_REPLACEMENT_COLOR_RGB)
        return cls(
            data["name"],
            data["x1"],
            data["y1"],
            data["x2"],
            data["y2"],
            color_filter_enabled,
            target_color,
            color_threshold,
            replacement_color,
        )

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
        except Exception:
            return None

    def apply_color_filter(self, roi_img):
        if not self.color_filter_enabled or roi_img is None:
            return roi_img
        try:
            target_bgr = self.target_color[::-1]
            replacement_bgr = self.replacement_color[::-1]
            thresh = self.color_threshold
            lower_bound = np.array([max(0, c - thresh) for c in target_bgr], dtype=np.uint8)
            upper_bound = np.array([min(255, c + thresh) for c in target_bgr], dtype=np.uint8)
            mask = cv2.inRange(roi_img, lower_bound, upper_bound)
            background = np.full_like(roi_img, replacement_bgr)
            filtered_img = cv2.bitwise_and(roi_img, roi_img, mask=mask)
            background_masked = cv2.bitwise_and(background, background, mask=cv2.bitwise_not(mask))
            result_img = cv2.add(filtered_img, background_masked)
            return result_img
        except Exception:
            return roi_img

    def get_overlay_config(self, global_settings):
        try:
            from ui.overlay_manager import OverlayManager

            defaults = OverlayManager.DEFAULT_OVERLAY_CONFIG.copy()
        except (ImportError, AttributeError):
            defaults = {
                "enabled": True,
                "font_family": "Segoe UI",
                "font_size": 14,
                "font_color": "white",
                "bg_color": "#222222",
                "alpha": 1.0,
                "wraplength": 450,
                "justify": "left",
                "geometry": None,
            }
        roi_specific_settings = global_settings.get("overlay_settings", {}).get(self.name, {})
        config = defaults.copy()
        config.update(roi_specific_settings)
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value
        return config

    @staticmethod
    def rgb_to_hex(rgb_tuple):
        try:
            r, g, b = [max(0, min(255, int(c))) for c in rgb_tuple]
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, TypeError, IndexError):
            return "#808080"

    @staticmethod
    def hex_to_rgb(hex_string):
        hex_color = str(hex_string).lstrip("#")
        if len(hex_color) == 6:
            try:
                return tuple(int(hex_color[i : i+2], 16) for i in (0, 2, 4))
            except ValueError:
                return ROI.DEFAULT_REPLACEMENT_COLOR_RGB
        elif len(hex_color) == 3:
            try:
                return tuple(int(c * 2, 16) for c in hex_color)
            except ValueError:
                return ROI.DEFAULT_REPLACEMENT_COLOR_RGB
        else:
            return ROI.DEFAULT_REPLACEMENT_COLOR_RGB