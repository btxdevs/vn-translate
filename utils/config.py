import json
import os
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
from utils.roi import ROI
from utils.settings import set_setting, get_setting # Import get_setting

# Default configuration file paths
DEFAULT_ROI_CONFIG_FILE = "vn_translator_config.json"
PRESETS_FILE = "translation_presets.json"

def save_rois(rois, current_config_file=None):
    """
    Save ROIs to a JSON configuration file. Prompts user if no file specified.

    Args:
        rois: List of ROI objects
        current_config_file: The path currently used by the app.

    Returns:
        The path to the saved config file or None if cancelled/failed
    """
    if not rois:
        messagebox.showwarning("Warning", "No ROIs to save.")
        return current_config_file # Return the original path if nothing saved

    try:
        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(current_config_file) if current_config_file else ".",
            initialfile=os.path.basename(current_config_file) if current_config_file else DEFAULT_ROI_CONFIG_FILE,
            title="Save ROI Configuration As"
        )
        if not save_path:
            print("ROI save cancelled by user.")
            return current_config_file # Return original path if cancelled

        roi_data = [roi.to_dict() for roi in rois]
        with open(save_path, 'w', encoding="utf-8") as f:
            json.dump(roi_data, f, indent=2)

        # Save the path in application settings
        set_setting("last_roi_config", save_path)
        print(f"ROIs saved successfully to {save_path}")
        return save_path # Return the new path
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save ROIs: {str(e)}")
        return current_config_file # Return original path on error

def load_rois(initial_path=None):
    """
    Load ROIs from a JSON configuration file. Uses initial_path or prompts user.

    Args:
        initial_path: Path to attempt loading from first.

    Returns:
        A tuple of (list of ROI objects, config_file_path) or ([], None) on failure/cancel
        Returns (None, None) on explicit error during load after selection.
    """
    open_path = initial_path
    rois = []

    # Try loading from initial_path first if it exists
    if open_path and os.path.exists(open_path):
        try:
            with open(open_path, 'r', encoding="utf-8") as f:
                roi_data = json.load(f)
            rois = [ROI.from_dict(data) for data in roi_data]
            set_setting("last_roi_config", open_path)
            print(f"ROIs loaded successfully from {open_path}")
            return rois, open_path
        except Exception as e:
            print(f"Failed to load ROIs from '{open_path}': {str(e)}. Prompting user.")
            # Fall through to prompt user
            open_path = None # Clear path so file dialog opens

    # If initial load failed or no path provided, prompt user
    if not open_path:
        # Get the directory of the last known config file
        last_config_path = get_setting("last_roi_config")
        initial_dir = "."
        if last_config_path and os.path.exists(os.path.dirname(last_config_path)):
            initial_dir = os.path.dirname(last_config_path)


        open_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=initial_dir,
            title="Load ROI Configuration"
        )
        if not open_path:
            print("ROI load cancelled by user.")
            return [], None # Return empty list and None path if cancelled

    # Try loading from the selected path
    if open_path and os.path.exists(open_path):
        try:
            with open(open_path, 'r', encoding="utf-8") as f:
                roi_data = json.load(f)
            rois = [ROI.from_dict(data) for data in roi_data]
            set_setting("last_roi_config", open_path)
            print(f"ROIs loaded successfully from {open_path}")
            return rois, open_path
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ROIs from '{open_path}': {str(e)}")
            return None, None # Explicit error indication
    elif open_path:
        messagebox.showerror("Error", f"File not found: '{open_path}'")
        return None, None # Explicit error indication
    else:
        # Should not happen if askopenfilename was used, but handle just in case
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
        print(f"Translation presets saved to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving translation presets: {e}")
        messagebox.showerror("Error", f"Failed to save translation presets: {e}")
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
                content = f.read()
                if not content: return {} # Handle empty file
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Error: Translation presets file '{file_path}' is corrupted or empty.")
            messagebox.showerror("Preset Load Error", f"Could not load presets from '{file_path}'. File might be corrupted.")
            return {}
        except Exception as e:
            print(f"Error loading translation presets: {e}")
            messagebox.showerror("Error", f"Failed to load translation presets: {e}. Using defaults or empty.")
    return {}