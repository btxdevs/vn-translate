import json
import os
import tkinter.messagebox as messagebox
from pathlib import Path
import hashlib
from utils.roi import ROI
from utils.settings import set_setting, get_setting
from utils.capture import get_executable_details

PRESETS_FILE = "translation_presets.json"
APP_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROI_CONFIGS_DIR = APP_DIR / "roi_configs"


def _ensure_roi_configs_dir():
    ROI_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)


def _get_game_hash(hwnd):
    exe_path, file_size = get_executable_details(hwnd)
    if exe_path and file_size is not None:
        identity_string = f"{os.path.normpath(exe_path).lower()}|{file_size}"
        hasher = hashlib.sha256()
        hasher.update(identity_string.encode("utf-8"))
        return hasher.hexdigest()
    return None


def _get_roi_config_path(hwnd):
    game_hash = _get_game_hash(hwnd)
    if game_hash:
        return ROI_CONFIGS_DIR / f"{game_hash}_rois.json"
    messagebox.showwarning("Warning", "Could not determine game hash for ROI config path.")
    return None


def save_rois(rois, hwnd):
    if not hwnd:
        messagebox.showerror("Error", "Cannot save ROIs: No game window selected.")
        return None

    _ensure_roi_configs_dir()
    save_path = _get_roi_config_path(hwnd)
    if not save_path:
        messagebox.showerror("Error", "Could not determine game-specific file path to save ROIs.")
        return None

    try:
        roi_data = [roi.to_dict() for roi in rois]
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(roi_data, f, indent=2)
        return str(save_path)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save ROIs to {save_path.name}: {e}")
        return None


def load_rois(hwnd):
    if not hwnd:
        return [], None

    _ensure_roi_configs_dir()
    load_path = _get_roi_config_path(hwnd)
    rois = []
    if not load_path:
        return [], None

    if load_path.exists():
        try:
            with open(load_path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return [], str(load_path)
            roi_data = json.loads(content)
            if not isinstance(roi_data, list):
                return [], str(load_path)
            rois = [ROI.from_dict(data) for data in roi_data]
            return rois, str(load_path)
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Failed to load ROIs from '{load_path.name}': Invalid JSON - {e}")
            return [], None
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ROIs from '{load_path.name}': {e}")
            return [], None
    else:
        return [], None


def save_translation_presets(presets, file_path=PRESETS_FILE):
    try:
        preset_path_obj = Path(file_path)
        preset_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(preset_path_obj, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save translation presets: {e}")
        return False


def load_translation_presets(file_path=PRESETS_FILE):
    preset_path_obj = Path(file_path)
    if preset_path_obj.exists():
        try:
            with open(preset_path_obj, "r", encoding="utf-8") as f:
                content = f.read()
            if not content:
                return {}
            return json.loads(content)
        except json.JSONDecodeError:
            messagebox.showerror("Preset Load Error", f"Could not load presets from '{file_path}'. File might be corrupted.")
            return {}
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load translation presets: {e}.")
            return {}
    return {}