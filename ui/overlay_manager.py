import tkinter as tk
from ui.floating_overlay_window import FloatingOverlayWindow
from utils.settings import get_setting, set_setting, get_overlay_config_for_roi, save_overlay_config_for_roi

class OverlayManager:
    def __init__(self, master, app_ref):
        self.master = master
        self.app = app_ref
        self.overlays = {}
        self.global_overlays_enabled = get_setting("global_overlays_enabled", True)

    def _get_roi_config(self, roi_name):
        return get_overlay_config_for_roi(roi_name)

    def create_overlay_for_roi(self, roi):
        roi_name = roi.name
        if roi_name in self.overlays:
            self.destroy_overlay(roi_name)
        config = self._get_roi_config(roi_name)
        if self.global_overlays_enabled and config.get("enabled", True):
            try:
                overlay = FloatingOverlayWindow(self.master, roi_name, config, manager_ref=self)
                self.overlays[roi_name] = overlay
            except Exception as e:
                print(f"Error creating floating overlay for {roi_name}: {e}")

    def update_overlay(self, roi_name, text):
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            overlay.update_text(text, global_overlays_enabled=self.global_overlays_enabled)

    def update_overlays(self, translated_segments):
        if not self.global_overlays_enabled:
            self.hide_all_overlays()
            return
        all_roi_names = {roi.name for roi in self.app.rois}
        for roi_name in all_roi_names:
            overlay_exists = roi_name in self.overlays
            roi = next((r for r in self.app.rois if r.name == roi_name), None)
            config = self._get_roi_config(roi_name)
            is_roi_enabled = config.get("enabled", True)
            text_to_display = translated_segments.get(roi_name, "")
            if roi and is_roi_enabled:
                if not overlay_exists:
                    self.create_overlay_for_roi(roi)
                    overlay_exists = roi_name in self.overlays
                if overlay_exists:
                    self.update_overlay(roi_name, text_to_display)
            elif overlay_exists:
                self.destroy_overlay(roi_name)

    def clear_all_overlays(self):
        for overlay in self.overlays.values():
            overlay.update_text("", global_overlays_enabled=self.global_overlays_enabled)

    def hide_all_overlays(self):
        for overlay in self.overlays.values():
            if overlay.winfo_exists():
                overlay.withdraw()

    def show_all_overlays(self):
        if not self.global_overlays_enabled:
            return
        for roi_name, overlay in self.overlays.items():
            if overlay.winfo_exists():
                current_text = overlay.label_var.get()
                overlay.update_text(current_text, global_overlays_enabled=self.global_overlays_enabled)

    def destroy_overlay(self, roi_name):
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            if overlay.winfo_exists():
                overlay.destroy_window()
            del self.overlays[roi_name]

    def destroy_all_overlays(self):
        for name in list(self.overlays.keys()):
            self.destroy_overlay(name)
        self.overlays = {}

    def rebuild_overlays(self):
        self.destroy_all_overlays()
        if not self.global_overlays_enabled:
            return
        if hasattr(self.app, 'rois'):
            for roi in self.app.rois:
                self.create_overlay_for_roi(roi)

    def update_overlay_config(self, roi_name, new_partial_config):
        if save_overlay_config_for_roi(roi_name, new_partial_config):
            if roi_name in self.overlays:
                live_config = self._get_roi_config(roi_name)
                self.overlays[roi_name].update_config(live_config)
            elif new_partial_config.get('enabled', False) and self.global_overlays_enabled:
                roi = next((r for r in self.app.rois if r.name == roi_name), None)
                if roi:
                    self.create_overlay_for_roi(roi)
            elif not new_partial_config.get('enabled', True) and roi_name in self.overlays:
                self.destroy_overlay(roi_name)
        else:
            print(f"Error saving overlay settings for {roi_name}.")

    def set_global_overlays_enabled(self, enabled):
        if enabled == self.global_overlays_enabled:
            return
        self.global_overlays_enabled = enabled
        if set_setting("global_overlays_enabled", enabled):
            if enabled:
                self.rebuild_overlays()
                self.show_all_overlays()
            else:
                self.hide_all_overlays()
            try:
                if self.app.floating_controls and self.app.floating_controls.winfo_exists():
                    if hasattr(self.app.floating_controls, 'overlay_var'):
                        self.app.floating_controls.overlay_var.set(enabled)
            except Exception as e:
                print(f"Error updating floating controls overlay state: {e}")
            try:
                if hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists():
                    if hasattr(self.app.overlay_tab, 'global_enable_var'):
                        self.app.overlay_tab.global_enable_var.set(enabled)
                    if hasattr(self.app.overlay_tab, 'set_widgets_state'):
                        current_roi_selected = bool(self.app.overlay_tab.selected_roi_var.get()) if hasattr(self.app.overlay_tab, 'selected_roi_var') else False
                        new_widget_state = tk.NORMAL if enabled and current_roi_selected else tk.DISABLED
                        self.app.overlay_tab.set_widgets_state(new_widget_state)
            except Exception as e:
                print(f"Error updating overlay tab global checkbox state: {e}")
        else:
            print("Error saving global overlay enabled state.")
            self.global_overlays_enabled = not enabled

    def reset_overlay_geometry(self, roi_name):
        if save_overlay_config_for_roi(roi_name, {'geometry': None}):
            if roi_name in self.overlays:
                live_config = self._get_roi_config(roi_name)
                self.overlays[roi_name].update_config(live_config)
                self.overlays[roi_name].lift()
            return True
        else:
            print(f"Error saving geometry reset for {roi_name}.")
            return False