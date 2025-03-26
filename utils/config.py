import json
import os
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
from utils.roi import ROI
from utils.settings import set_setting

# Default configuration file paths
DEFAULT_CONFIG_FILE = "vn_translator_config.json"
PRESETS_FILE = "translation_presets.json"

def save_rois(rois, config_file=None):
    """
    Save ROIs to a JSON configuration file.

    Args:
        rois: List of ROI objects
        config_file: Path to config file (or None to prompt user)

    Returns:
        The path to the saved config file or None if cancelled
    """
    if not rois:
        messagebox.showwarning("Warning", "No ROIs to save.")
        return None

    try:
        save_path = config_file
        if not save_path:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=DEFAULT_CONFIG_FILE
            )
            if not save_path:
                return None

        roi_data = [roi.to_dict() for roi in rois]
        with open(save_path, 'w', encoding="utf-8") as f:
            json.dump(roi_data, f, indent=2)

        # Save the path in application settings
        set_setting("last_roi_config", save_path)

        return save_path
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save ROIs: {str(e)}")
        return None

def load_rois(config_file=None, silent=False):
    """
    Load ROIs from a JSON configuration file.

    Args:
        config_file: Path to config file (or None to prompt user)
        silent: If True, don't show error messages for missing files

    Returns:
        A tuple of (list of ROI objects, config_file_path)
    """
    try:
        open_path = config_file
        if not open_path:
            open_path = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Load ROI Configuration"
            )
            if not open_path:
                return [], None

        # Check if file exists
        if not os.path.exists(open_path):
            if not silent:
                messagebox.showerror("Error", f"Failed to load ROIs: File '{open_path}' not found")
            return [], None

        with open(open_path, 'r', encoding="utf-8") as f:
            roi_data = json.load(f)

        rois = [ROI.from_dict(data) for data in roi_data]

        # Save the path in application settings
        set_setting("last_roi_config", open_path)

        return rois, open_path
    except Exception as e:
        if not silent:
            messagebox.showerror("Error", f"Failed to load ROIs: {str(e)}")
        return [], None

def save_translation_presets(presets, file_path=PRESETS_FILE):
    """
    Save translation presets to a JSON file.

    Args:
        presets: Dictionary of translation presets
        file_path: Path to save to

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving translation presets: {e}")
        return False

def load_translation_presets(file_path=PRESETS_FILE):
    """
    Load translation presets from a JSON file.

    Args:
        file_path: Path to load from

    Returns:
        Dictionary of translation presets
    """
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading translation presets: {e}")
    return {}