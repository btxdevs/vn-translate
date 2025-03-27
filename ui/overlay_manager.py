# --- START OF FILE ui/overlay_manager.py ---

import tkinter as tk
# Import the new floating window class
from ui.floating_overlay_window import FloatingOverlayWindow
# Import settings functions to get/save config for specific ROIs
from utils.settings import get_setting, set_setting, update_settings, get_overlay_config_for_roi, save_overlay_config_for_roi
import win32gui # To check game window validity (still potentially useful)

class OverlayManager:
    """Manages multiple FloatingOverlayWindow instances."""

    # Default config is now primarily handled by utils.settings
    # We mostly rely on get_overlay_config_for_roi which merges defaults.

    def __init__(self, master, app_ref):
        self.master = master
        self.app = app_ref # Reference to the main application
        self.overlays = {}  # roi_name: FloatingOverlayWindow instance
        # Load global enabled state
        self.global_overlays_enabled = get_setting("global_overlays_enabled", True)
        # Individual ROI settings (including geometry) are loaded by the window itself using utils.settings

    def _get_roi_config(self, roi_name):
        """Gets the specific config for an ROI using the utility function."""
        # This now includes the 'geometry' field if saved
        return get_overlay_config_for_roi(roi_name)

    def create_overlay_for_roi(self, roi):
        """Creates or recreates a floating overlay window for a given ROI object."""
        roi_name = roi.name
        if roi_name in self.overlays:
            print(f"Overlay for {roi_name} already exists. Destroying before recreating.")
            # If already exists, destroy and recreate to ensure fresh state/geometry loading
            self.destroy_overlay(roi_name)

        # Game window check is less critical for positioning, but good for context
        # if not self.app.selected_hwnd or not win32gui.IsWindow(self.app.selected_hwnd):
        #     print(f"Skipping overlay creation for {roi_name}: Game window might be invalid.")
        #     return

        # Get the full configuration for this ROI (includes defaults, saved specifics, geometry)
        config = self._get_roi_config(roi_name)

        # Only create if globally enabled AND this specific ROI is enabled in its config
        if self.global_overlays_enabled and config.get("enabled", True):
            try:
                # Pass the full config, window handles its own geometry loading
                overlay = FloatingOverlayWindow(self.master, roi_name, config)
                self.overlays[roi_name] = overlay
                print(f"Created floating overlay for ROI: {roi_name}")
                # Visibility is handled internally based on text/enabled status
            except Exception as e:
                print(f"Error creating floating overlay window for {roi_name}: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Intentionally disabled, don't create
            pass


    def update_overlay(self, roi_name, text):
        """Updates the text of a specific overlay. Visibility is handled internally."""
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            overlay.update_text(text)
            # Position/size updates are handled by user interaction (drag/resize)
            # or config changes (e.g., reset geometry) via update_config.
        # else: If overlay doesn't exist (e.g., disabled), do nothing.


    def update_overlays(self, translated_segments):
        """Updates all relevant overlays based on the translation results dictionary."""
        if not self.global_overlays_enabled:
            self.hide_all_overlays() # Ensure all are hidden if globally disabled
            return

        # Get all current ROI names defined in the app
        all_roi_names = {roi.name for roi in self.app.rois}
        # Get names of ROIs that received a translation this time
        translated_roi_names = set(translated_segments.keys())

        # Iterate through all known ROIs in the app
        for roi_name in all_roi_names:
            # Check if an overlay instance exists
            overlay_exists = roi_name in self.overlays
            # Find the ROI object (needed for checking if it should exist)
            roi = next((r for r in self.app.rois if r.name == roi_name), None)
            # Get config to check if this specific ROI is enabled
            config = self._get_roi_config(roi_name)
            is_roi_enabled = config.get("enabled", True)

            # Get the translated text, default to empty string if none provided
            text_to_display = translated_segments.get(roi_name, "")

            if roi and is_roi_enabled: # If the ROI exists and should be displayed
                if not overlay_exists:
                    # Create overlay if it's missing but should be shown
                    print(f"Recreating missing overlay for enabled ROI: {roi_name}")
                    self.create_overlay_for_roi(roi) # Create it
                    overlay_exists = roi_name in self.overlays # Check again if creation succeeded

                if overlay_exists:
                    # Update the overlay with text (handles show/hide internally)
                    self.update_overlay(roi_name, text_to_display)

            elif overlay_exists:
                # If ROI is disabled or deleted (roi object is None), ensure overlay is hidden/destroyed
                # print(f"Hiding/Destroying overlay for disabled/deleted ROI: {roi_name}")
                self.destroy_overlay(roi_name) # Destroy might be cleaner than just hiding


    def clear_all_overlays(self):
        """Clears text from all managed overlays (hides them)."""
        for overlay in self.overlays.values():
            overlay.update_text("")

    def hide_all_overlays(self):
        """Hides all managed overlay windows."""
        for overlay in self.overlays.values():
            if overlay.winfo_exists():
                overlay.withdraw()

    def show_all_overlays(self):
        """Shows all managed overlay windows *if* they have text and are enabled."""
        if not self.global_overlays_enabled:
            return
        print("Attempting to show all enabled overlays with text...")
        for roi_name, overlay in self.overlays.items():
            # Config is checked internally by update_text, just call it
            # We need the current text to decide whether to show
            current_text = overlay.label_var.get()
            overlay.update_text(current_text) # This will deiconify if needed


    def destroy_overlay(self, roi_name):
        """Destroys a specific overlay window."""
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            if overlay.winfo_exists():
                overlay.destroy_window() # Use the safe destruction method
            del self.overlays[roi_name]
            print(f"Destroyed overlay for ROI: {roi_name}")


    def destroy_all_overlays(self):
        """Destroys all managed overlay windows."""
        # Iterate over a copy of keys as dict changes during iteration
        names = list(self.overlays.keys())
        for name in names:
            self.destroy_overlay(name)
        # Ensure dictionary is empty
        self.overlays = {}
        print("Destroyed all overlays.")


    def rebuild_overlays(self):
        """Destroys and recreates all overlays based on current ROIs and settings."""
        print("Rebuilding overlays...")
        self.destroy_all_overlays()
        if not self.global_overlays_enabled:
            print("Skipping overlay creation as globally disabled.")
            return
        # Ensure ROI list is current before iterating
        if hasattr(self.app, 'rois'):
            for roi in self.app.rois:
                self.create_overlay_for_roi(roi) # Creates only if enabled


    def update_overlay_config(self, roi_name, new_partial_config):
        """
        Updates the config for a specific overlay, saves it, and applies live changes.
        The saving is now handled by save_overlay_config_for_roi.
        """
        # Use the utility to save the changes persistently
        if save_overlay_config_for_roi(roi_name, new_partial_config):
            print(f"Overlay settings saved for {roi_name}.")

            # Apply changes to the live overlay if it exists
            if roi_name in self.overlays:
                # Get the fully merged config (defaults + ALL saved specifics for this ROI) to apply
                live_config = self._get_roi_config(roi_name)
                self.overlays[roi_name].update_config(live_config)
            # Handle case where overlay was disabled but now enabled
            elif new_partial_config.get('enabled', False) and self.global_overlays_enabled:
                # If overlay doesn't exist, but config now says enabled, try to create it
                roi = next((r for r in self.app.rois if r.name == roi_name), None)
                if roi:
                    print(f"Creating overlay for {roi_name} as it was enabled.")
                    self.create_overlay_for_roi(roi)
            # Handle case where overlay exists but is now disabled
            elif not new_partial_config.get('enabled', True) and roi_name in self.overlays:
                print(f"Hiding/Destroying overlay for {roi_name} as it was disabled.")
                # self.overlays[roi_name].withdraw() # Just hide?
                self.destroy_overlay(roi_name) # Or destroy? Destroy seems cleaner.

        else:
            print(f"Error saving overlay settings for {roi_name}.")


    def set_global_overlays_enabled(self, enabled):
        """Sets the global enable state, saves it, and shows/hides overlays."""
        if enabled == self.global_overlays_enabled:
            return # No change

        self.global_overlays_enabled = enabled
        if set_setting("global_overlays_enabled", enabled): # Save setting
            print(f"Global overlays {'enabled' if enabled else 'disabled'}.")

            if enabled:
                # When enabling globally, rebuild overlays to create any that were missing
                # but are individually enabled.
                self.rebuild_overlays()
                # Show overlays that have text
                self.show_all_overlays()
            else:
                # When disabling globally, hide all existing overlays.
                self.hide_all_overlays()

            # Update floating controls state if they exist
            if self.app.floating_controls and self.app.floating_controls.winfo_exists():
                self.app.floating_controls.overlay_var.set(enabled)
        else:
            print("Error saving global overlay enabled state.")
            self.global_overlays_enabled = not enabled # Revert state


    def reset_overlay_geometry(self, roi_name):
        """Resets the position and size for a specific overlay."""
        print(f"Requesting geometry reset for overlay: {roi_name}")
        # Save 'None' for geometry in settings
        if save_overlay_config_for_roi(roi_name, {'geometry': None}):
            # If the overlay exists, trigger it to reload its config (which includes geometry)
            if roi_name in self.overlays:
                live_config = self._get_roi_config(roi_name) # Get updated config with geometry=None
                self.overlays[roi_name].update_config(live_config) # This should trigger _load_geometry
                # Force visibility update in case it was hidden
                current_text = self.overlays[roi_name].label_var.get()
                self.overlays[roi_name].update_text(current_text)
                self.overlays[roi_name].lift() # Bring to front after reset
            # If overlay doesn't exist (e.g., disabled), the change will be picked up if/when it's created.
            return True
        else:
            print(f"Error saving geometry reset for {roi_name}.")
            return False

# --- END OF FILE ui/overlay_manager.py ---