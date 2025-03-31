
import cv2
import numpy as np
import tkinter as tk # Added for color conversion

class ROI:
    DEFAULT_REPLACEMENT_COLOR_RGB = (128, 128, 128) # Default to gray
    BINARIZATION_TYPES = ["None", "Otsu", "Adaptive Gaussian"]
    DEFAULT_PREPROCESSING = {
        "grayscale": False,
        "binarization_type": "None",
        "adaptive_block_size": 11,
        "adaptive_c_value": 2,
        "scaling_enabled": False,
        "scale_factor": 1.5,
        "sharpening_strength": 0.0, # Changed from boolean to float (0.0 = off)
        "median_blur_enabled": False,
        "median_blur_ksize": 3,
        "dilation_enabled": False,
        "erosion_enabled": False,
        "morph_ksize": 3,
        # New Cutout settings
        "cutout_enabled": False,
        "cutout_padding": 5,
        "cutout_bg_threshold": 15, # Threshold to consider a pixel as background (for near black/white)
        # New Invert setting
        "invert_colors": False,
    }

    def __init__(self, name, x1, y1, x2, y2,
                 color_filter_enabled=False, target_color=(255, 255, 255), color_threshold=30,
                 replacement_color=DEFAULT_REPLACEMENT_COLOR_RGB,
                 preprocessing_settings=None): # Added preprocessing_settings
        self.name = name
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)

        # Color Filtering Attributes
        self.color_filter_enabled = color_filter_enabled
        self.target_color = self._parse_color_input(target_color, (255, 255, 255))
        self.replacement_color = self._parse_color_input(replacement_color, self.DEFAULT_REPLACEMENT_COLOR_RGB)
        try:
            self.color_threshold = int(color_threshold)
        except (ValueError, TypeError):
            self.color_threshold = 30

        # OCR Preprocessing Attributes
        self.preprocessing = self.DEFAULT_PREPROCESSING.copy()
        if preprocessing_settings and isinstance(preprocessing_settings, dict):
            # Validate and update defaults with provided settings
            for key, default_value in self.DEFAULT_PREPROCESSING.items():
                if key in preprocessing_settings:
                    value = preprocessing_settings[key]
                    # Basic type validation (can be expanded)
                    if isinstance(value, type(default_value)):
                        # Specific validation for certain keys
                        if key == "binarization_type" and value not in self.BINARIZATION_TYPES:
                            print(f"Warning: Invalid binarization_type '{value}' for ROI '{name}'. Using default.")
                            self.preprocessing[key] = default_value
                        elif key == "adaptive_block_size" and (not isinstance(value, int) or value < 3 or value % 2 == 0):
                            print(f"Warning: Invalid adaptive_block_size '{value}' for ROI '{name}'. Using default.")
                            self.preprocessing[key] = default_value
                        elif key == "median_blur_ksize" and (not isinstance(value, int) or value < 3 or value % 2 == 0):
                            print(f"Warning: Invalid median_blur_ksize '{value}' for ROI '{name}'. Using default.")
                            self.preprocessing[key] = default_value
                        elif key == "morph_ksize" and (not isinstance(value, int) or value < 1):
                            print(f"Warning: Invalid morph_ksize '{value}' for ROI '{name}'. Using default.")
                            self.preprocessing[key] = default_value
                        elif key == "scale_factor" and (not isinstance(value, (int, float)) or value <= 0):
                            print(f"Warning: Invalid scale_factor '{value}' for ROI '{name}'. Using default.")
                            self.preprocessing[key] = default_value
                        elif key == "sharpening_strength" and (not isinstance(value, (int, float)) or value < 0): # Check >= 0
                            print(f"Warning: Invalid sharpening_strength '{value}' for ROI '{name}'. Using default.")
                            self.preprocessing[key] = default_value
                        elif key == "cutout_padding" and (not isinstance(value, int) or value < 0):
                            print(f"Warning: Invalid cutout_padding '{value}' for ROI '{name}'. Using default.")
                            self.preprocessing[key] = default_value
                        elif key == "cutout_bg_threshold" and (not isinstance(value, int) or not (0 <= value <= 127)):
                            print(f"Warning: Invalid cutout_bg_threshold '{value}' for ROI '{name}'. Using default.")
                            self.preprocessing[key] = default_value
                        else:
                            self.preprocessing[key] = value
                    # Handle case where sharpening_enabled (bool) might be in old config
                    elif key == "sharpening_strength" and isinstance(value, bool):
                        print(f"Warning: Found boolean 'sharpening_enabled' for ROI '{name}'. Converting to strength (0.0 or 0.5).")
                        self.preprocessing[key] = 0.5 if value else 0.0 # Convert old bool to float
                    else:
                        print(f"Warning: Type mismatch for preprocessing key '{key}' for ROI '{name}'. Using default.")
                        self.preprocessing[key] = default_value


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
            "replacement_color": self.replacement_color, # Save replacement color
            "preprocessing": self.preprocessing # Save preprocessing settings
        }

    @classmethod
    def from_dict(cls, data):
        # Provide defaults for backward compatibility
        color_filter_enabled = data.get("color_filter_enabled", False)
        target_color = data.get("target_color", (255, 255, 255)) # Expecting RGB tuple
        color_threshold = data.get("color_threshold", 30)
        replacement_color = data.get("replacement_color", cls.DEFAULT_REPLACEMENT_COLOR_RGB)
        # Load preprocessing settings, falling back to defaults if missing
        preprocessing_settings = cls.DEFAULT_PREPROCESSING.copy() # Start with defaults
        loaded_preprocessing = data.get("preprocessing", {})
        if isinstance(loaded_preprocessing, dict):
            preprocessing_settings.update(loaded_preprocessing) # Update with loaded values

        # Handle potential old boolean 'sharpening_enabled' key when loading
        if "sharpening_enabled" in preprocessing_settings and isinstance(preprocessing_settings["sharpening_enabled"], bool):
            print("Note: Converting old 'sharpening_enabled' key during load.")
            strength = 0.5 if preprocessing_settings["sharpening_enabled"] else 0.0
            preprocessing_settings["sharpening_strength"] = strength
            del preprocessing_settings["sharpening_enabled"] # Remove old key

        return cls(data["name"], data["x1"], data["y1"], data["x2"], data["y2"],
                   color_filter_enabled, target_color, color_threshold, replacement_color,
                   preprocessing_settings) # Pass loaded settings

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
                print(f"Warning: Invalid dimensions after clamping for ROI {self.name}")
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

    def _cutout_blank_space(self, img, padding, bg_threshold):
        """Removes blank (near black or near white) borders from an image."""
        if img is None: return None
        try:
            # Convert to grayscale for thresholding
            if len(img.shape) == 3 and img.shape[2] == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            elif len(img.shape) == 2:
                gray = img
            else:
                print("Warning: Unsupported image format for cutout.")
                return img

            # Threshold to identify potential background pixels (near black OR near white)
            # Pixels *below* bg_threshold or *above* (255 - bg_threshold) are considered background
            _, thresh_dark = cv2.threshold(gray, bg_threshold, 255, cv2.THRESH_BINARY_INV)
            _, thresh_light = cv2.threshold(gray, 255 - bg_threshold, 255, cv2.THRESH_BINARY)
            # Combine masks: non-dark AND non-light pixels are foreground
            foreground_mask = cv2.bitwise_and(thresh_dark, cv2.bitwise_not(thresh_light))

            # Find contours of the foreground regions
            contours, _ = cv2.findContours(foreground_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                # print(f"Warning: No foreground contours found for cutout in ROI {self.name}.")
                return img # Return original if no content found

            # Find the bounding box encompassing all contours
            min_x, min_y = img.shape[1], img.shape[0]
            max_x, max_y = 0, 0
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x + w)
                max_y = max(max_y, y + h)

            # Add padding, ensuring bounds stay within the original image dimensions
            pad = max(0, padding) # Ensure padding is non-negative
            x1 = max(0, min_x - pad)
            y1 = max(0, min_y - pad)
            x2 = min(img.shape[1], max_x + pad)
            y2 = min(img.shape[0], max_y + pad)

            # Crop the original image (color or grayscale)
            if y1 < y2 and x1 < x2:
                return img[y1:y2, x1:x2]
            else:
                # print(f"Warning: Invalid cutout dimensions after padding for ROI {self.name}.")
                return img # Return original if dimensions invalid

        except Exception as e:
            print(f"Error during cutout for ROI {self.name}: {e}")
            return img # Return original on error

    def _invert_colors(self, img):
        """Inverts the colors of the image."""
        if img is None: return None
        try:
            return cv2.bitwise_not(img)
        except Exception as e:
            print(f"Error inverting colors for ROI {self.name}: {e}")
            return img # Return original on error

    def apply_ocr_preprocessing(self, roi_img):
        """Applies configured OCR preprocessing steps to the ROI image."""
        if roi_img is None:
            return None

        img = roi_img.copy() # Work on a copy

        try:
            # --- Scaling ---
            if self.preprocessing.get("scaling_enabled", False):
                factor = self.preprocessing.get("scale_factor", 1.5)
                if factor > 0 and factor != 1.0:
                    new_width = int(img.shape[1] * factor)
                    new_height = int(img.shape[0] * factor)
                    if new_width > 0 and new_height > 0:
                        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

            # --- Cutout Blank Space (After Scaling) ---
            if self.preprocessing.get("cutout_enabled", False):
                padding = self.preprocessing.get("cutout_padding", 5)
                threshold = self.preprocessing.get("cutout_bg_threshold", 15)
                img = self._cutout_blank_space(img, padding, threshold)
                if img is None or img.size == 0: # Check if cutout resulted in empty image
                    print(f"Warning: Cutout resulted in empty image for ROI {self.name}")
                    return None # Return None if cutout failed or removed everything

            # --- Grayscaling ---
            # Grayscale is often needed before binarization or sharpening
            is_gray = False
            if self.preprocessing.get("grayscale", False) or self.preprocessing.get("binarization_type", "None") != "None":
                if len(img.shape) == 3 and img.shape[2] == 3: # Check if it's color
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    is_gray = True
                elif len(img.shape) == 2: # Already grayscale
                    is_gray = True

            # --- Sharpening (using blending) ---
            strength = self.preprocessing.get("sharpening_strength", 0.0)
            if strength > 0.0:
                # Keep a copy of the image *before* potential grayscale conversion if needed
                # If already gray, use the gray version for blending base
                img_before_sharpen = img.copy()

                # Apply sharpening kernel
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
                # Apply kernel to the current state of 'img' (could be gray or color)
                sharpened_img = cv2.filter2D(img, -1, kernel)

                # Ensure strength is within a reasonable range (e.g., 0 to 1 for blending weight)
                blend_strength = max(0.0, min(1.0, strength))

                # Blend the original (before sharpening) and the sharpened image
                # Weight for original = 1 - blend_strength
                # Weight for sharpened = blend_strength
                img = cv2.addWeighted(img_before_sharpen, 1.0 - blend_strength, sharpened_img, blend_strength, 0)

                # Ensure the output type remains uint8 if it was before blending
                img = np.clip(img, 0, 255).astype(np.uint8)

                # Update is_gray flag if sharpening was applied to a color image and resulted in grayscale (unlikely with blend)
                if not is_gray and len(img.shape) == 2:
                    is_gray = True


            # --- Binarization ---
            bin_type = self.preprocessing.get("binarization_type", "None")
            if bin_type != "None":
                if not is_gray: # Ensure image is grayscale for thresholding
                    if len(img.shape) == 3 and img.shape[2] == 3:
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        is_gray = True
                    elif len(img.shape) != 2:
                        print(f"Warning: Cannot binarize non-grayscale image for ROI {self.name}")
                        # Decide whether to return original or current state
                        # Returning current state might be more useful for debugging
                        return img

                if is_gray: # Proceed only if grayscale
                    if bin_type == "Otsu":
                        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    elif bin_type == "Adaptive Gaussian":
                        block_size = self.preprocessing.get("adaptive_block_size", 11)
                        c_value = self.preprocessing.get("adaptive_c_value", 2)
                        # Ensure block_size is odd and >= 3
                        if block_size < 3 or block_size % 2 == 0: block_size = 11
                        img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                    cv2.THRESH_BINARY, block_size, c_value)

            # --- Color Inversion (Applied after potential binarization) ---
            if self.preprocessing.get("invert_colors", False):
                img = self._invert_colors(img)

            # --- Noise Reduction (Median Blur) ---
            if self.preprocessing.get("median_blur_enabled", False):
                ksize = self.preprocessing.get("median_blur_ksize", 3)
                # Ensure ksize is odd and >= 3
                if ksize < 3 or ksize % 2 == 0: ksize = 3
                img = cv2.medianBlur(img, ksize)

            # --- Morphological Operations (Dilation/Erosion) ---
            # These often work best on binary images
            morph_ksize = self.preprocessing.get("morph_ksize", 3)
            if morph_ksize < 1: morph_ksize = 3
            kernel = np.ones((morph_ksize, morph_ksize), np.uint8)

            if self.preprocessing.get("dilation_enabled", False):
                img = cv2.dilate(img, kernel, iterations=1)

            if self.preprocessing.get("erosion_enabled", False):
                img = cv2.erode(img, kernel, iterations=1)

            return img

        except Exception as e:
            print(f"Error applying OCR preprocessing for ROI {self.name}: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
            return roi_img # Return original on error


    # --- Static Color Conversion Methods ---
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