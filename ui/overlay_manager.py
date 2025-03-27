# --- START OF FILE ui/overlay_manager.py ---

import tkinter as tk
from ui.floating_overlay_window import FloatingOverlayWindow
from utils.settings import get_setting, set_setting, update_settings, get_overlay_config_for_roi, save_overlay_config_for_roi
import win32gui

class OverlayManager:
    """Manages multiple FloatingOverlayWindow instances."""

    def __init__(self, master, app_ref):
        self.master = master
        self.app = app_ref
        self.overlays = {}
        self.global_overlays_enabled = get_setting("global_overlays_enabled", True)

    def _get_roi_config(self, roi_name):
        return get_overlay_config_for_roi(roi_name)

    def create_overlay_for_roi(self, roi):
        """Creates or recreates a floating overlay window for a given ROI object."""
        roi_name = roi.name
        if roi_name in self.overlays:
            print(f"Overlay for {roi_name} already exists. Destroying before recreating.")
            self.destroy_overlay(roi_name)

        config = self._get_roi_config(roi_name)

        # Only create if globally enabled AND this specific ROI is enabled
        # Note: global_overlays_enabled is checked again inside update_text for showing
        if self.global_overlays_enabled and config.get("enabled", True):
            try:
                # <<< Pass self (the manager) as the manager_ref >>>
                overlay = FloatingOverlayWindow(self.master, roi_name, config, manager_ref=self)
                self.overlays[roi_name] = overlay
                print(f"Created floating overlay for ROI: {roi_name}")
            except Exception as e:
                print(f"Error creating floating overlay window for {roi_name}: {e}")
                import traceback
                traceback.print_exc()

    # <<< Modify to pass global state >>>
    def update_overlay(self, roi_name, text):
        """Updates the text of a specific overlay, passing global state."""
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            # <<< Pass current global state >>>
            overlay.update_text(text, global_overlays_enabled=self.global_overlays_enabled)

    def update_overlays(self, translated_segments):
        """Updates all relevant overlays based on the translation results dictionary."""
        # This initial check prevents unnecessary iteration if globally off
        if not self.global_overlays_enabled:
            self.hide_all_overlays()
            return

        all_roi_names = {roi.name for roi in self.app.rois}
        translated_roi_names = set(translated_segments.keys())

        for roi_name in all_roi_names:
            overlay_exists = roi_name in self.overlays
            roi = next((r for r in self.app.rois if r.name == roi_name), None)
            config = self._get_roi_config(roi_name)
            is_roi_enabled = config.get("enabled", True)
            text_to_display = translated_segments.get(roi_name, "")

            if roi and is_roi_enabled:
                if not overlay_exists:
                    # create_overlay_for_roi internally checks global state too
                    print(f"Recreating missing overlay for enabled ROI: {roi_name}")
                    self.create_overlay_for_roi(roi)
                    overlay_exists = roi_name in self.overlays

                if overlay_exists:
                    # update_overlay now handles passing the global state
                    self.update_overlay(roi_name, text_to_display)

            elif overlay_exists:
                self.destroy_overlay(roi_name)


    def clear_all_overlays(self):
        """Clears text from all managed overlays (hides them)."""
        for overlay in self.overlays.values():
            # Pass global state (likely True if clearing, but good practice)
            overlay.update_text("", global_overlays_enabled=self.global_overlays_enabled)

    def hide_all_overlays(self):
        """Hides all managed overlay windows."""
        for overlay in self.overlays.values():
            if overlay.winfo_exists():
                overlay.withdraw()

    # <<< Modify to pass global state >>>
    def show_all_overlays(self):
        """Shows all managed overlay windows *if* they have text and are enabled (globally & individually)."""
        if not self.global_overlays_enabled:
            return
        print("Attempting to show all enabled overlays with text...")
        for roi_name, overlay in self.overlays.items():
            if overlay.winfo_exists():
                current_text = overlay.label_var.get()
                # <<< Pass current global state >>>
                overlay.update_text(current_text, global_overlays_enabled=self.global_overlays_enabled)

    def destroy_overlay(self, roi_name):
        """Destroys a specific overlay window."""
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            if overlay.winfo_exists():
                overlay.destroy_window()
            del self.overlays[roi_name]
            print(f"Destroyed overlay for ROI: {roi_name}")


    def destroy_all_overlays(self):
        """Destroys all managed overlay windows."""
        names = list(self.overlays.keys())
        for name in names:
            self.destroy_overlay(name)
        self.overlays = {}
        print("Destroyed all overlays.")


    def rebuild_overlays(self):
        """Destroys and recreates all overlays based on current ROIs and settings."""
        print("Rebuilding overlays...")
        self.destroy_all_overlays()
        if not self.global_overlays_enabled:
            print("Skipping overlay creation as globally disabled.")
            return
        if hasattr(self.app, 'rois'):
            for roi in self.app.rois:
                # create_overlay_for_roi checks global state internally for creation
                self.create_overlay_for_roi(roi)


    def update_overlay_config(self, roi_name, new_partial_config):
        """
        Updates the config for a specific overlay, saves it, and applies live changes.
        """
        if save_overlay_config_for_roi(roi_name, new_partial_config):
            print(f"Overlay settings saved for {roi_name}.")

            if roi_name in self.overlays:
                live_config = self._get_roi_config(roi_name)
                # update_config in FloatingOverlayWindow now handles visibility re-check
                self.overlays[roi_name].update_config(live_config)
            elif new_partial_config.get('enabled', False) and self.global_overlays_enabled:
                roi = next((r for r in self.app.rois if r.name == roi_name), None)
                if roi:
                    print(f"Creating overlay for {roi_name} as it was enabled.")
                    self.create_overlay_for_roi(roi)
            elif not new_partial_config.get('enabled', True) and roi_name in self.overlays:
                print(f"Hiding/Destroying overlay for {roi_name} as it was disabled.")
                self.destroy_overlay(roi_name)
        else:
            print(f"Error saving overlay settings for {roi_name}.")


    def set_global_overlays_enabled(self, enabled):
        """Sets the global enable state, saves it, and shows/hides overlays."""
        if enabled == self.global_overlays_enabled:
            return

        self.global_overlays_enabled = enabled
        if set_setting("global_overlays_enabled", enabled):
            print(f"Global overlays {'enabled' if enabled else 'disabled'}.")

            if enabled:
                # Rebuild necessary to create overlays that might have been skipped before
                self.rebuild_overlays()
                # Explicitly tell existing/newly created overlays to re-evaluate visibility
                self.show_all_overlays() # Passes the new global state
            else:
                # Hide all unconditionally
                self.hide_all_overlays()

            # Update UI Elements
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
            self.global_overlays_enabled = not enabled # Revert state


    def reset_overlay_geometry(self, roi_name):
        """Resets the position and size for a specific overlay."""
        print(f"Requesting geometry reset for overlay: {roi_name}")
        if save_overlay_config_for_roi(roi_name, {'geometry': None}):
            if roi_name in self.overlays:
                live_config = self._get_roi_config(roi_name)
                self.overlays[roi_name].update_config(live_config)
                # update_config now handles visibility re-check based on global state
                self.overlays[roi_name].lift()
            return True
        else:
            print(f"Error saving geometry reset for {roi_name}.")
            return False

# --- END OF FILE ui/overlay_manager.py ---