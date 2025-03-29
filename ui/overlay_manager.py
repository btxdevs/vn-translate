import tkinter as tk
from ui.floating_overlay_window import FloatingOverlayWindow
from utils.settings import get_setting, set_setting, get_overlay_config_for_roi, save_overlay_config_for_roi

class OverlayManager:
    def __init__(self, master, app_ref):
        self.master = master
        self.app = app_ref
        self.overlays = {} # Dictionary mapping roi_name to FloatingOverlayWindow instance
        self.global_overlays_enabled = get_setting("global_overlays_enabled", True)

    def _get_roi_config(self, roi_name):
        """Gets the full, merged configuration for a specific ROI."""
        return get_overlay_config_for_roi(roi_name)

    def create_overlay_for_roi(self, roi):
        """Creates or replaces an overlay window for a given ROI object."""
        roi_name = roi.name
        if roi_name in self.overlays:
            # If it exists, update its config instead of destroying/recreating
            # unless a full rebuild is needed for some reason.
            # For now, let's just update config and visibility.
            config = self._get_roi_config(roi_name)
            self.overlays[roi_name].update_config(config)
            self.overlays[roi_name]._update_visibility() # Ensure visibility is correct
            # print(f"Overlay for {roi_name} already exists, updated config.")
            return

        # If it doesn't exist, create it
        config = self._get_roi_config(roi_name)
        try:
            overlay = FloatingOverlayWindow(self.master, roi_name, config, manager_ref=self)
            self.overlays[roi_name] = overlay
            # Initial visibility is handled within FloatingOverlayWindow.__init__
            # print(f"Created overlay for {roi_name}")
        except Exception as e:
            print(f"Error creating floating overlay window for {roi_name}: {e}")

    def update_overlay_text(self, roi_name, text):
        """Updates the text content of a specific overlay window."""
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            # The overlay's update_text method now only handles the text variable
            overlay.update_text(text)
        # else:
        # print(f"Debug: Tried to update text for non-existent overlay {roi_name}")

    def update_overlays(self, translated_segments):
        """
        Updates text content of existing overlays based on translated_segments.
        Creates/Destroys overlays if ROIs are added/removed or enabled/disabled.
        Ensures visibility is correct based on current global/individual states.
        """
        if not hasattr(self.app, 'rois'):
            print("Warning: update_overlays called but app.rois not available.")
            return

        all_current_roi_names = {roi.name for roi in self.app.rois}
        processed_roi_names = set()

        # Update existing or newly added ROIs
        for roi in self.app.rois:
            roi_name = roi.name
            processed_roi_names.add(roi_name)
            config = self._get_roi_config(roi_name)
            is_roi_enabled_individually = config.get("enabled", True)
            text_to_display = translated_segments.get(roi_name, "")

            if is_roi_enabled_individually:
                # If enabled, ensure overlay exists and update its text
                if roi_name not in self.overlays:
                    # print(f"update_overlays: Creating overlay for enabled ROI {roi_name}")
                    self.create_overlay_for_roi(roi) # Creates and sets initial visibility

                # Update text if overlay exists (or was just created)
                if roi_name in self.overlays:
                    self.update_overlay_text(roi_name, text_to_display)
                    # Ensure visibility is correct (in case global state changed)
                    self.overlays[roi_name]._update_visibility()

            else:
                # If not enabled individually, ensure overlay is destroyed if it exists
                if roi_name in self.overlays:
                    # print(f"update_overlays: Destroying overlay for disabled ROI {roi_name}")
                    self.destroy_overlay(roi_name)

        # Destroy overlays for ROIs that no longer exist in the app's list
        # (e.g., deleted in the ROI tab)
        names_to_remove = set(self.overlays.keys()) - processed_roi_names
        for roi_name in names_to_remove:
            # print(f"update_overlays: Destroying overlay for removed ROI {roi_name}")
            self.destroy_overlay(roi_name)

    def clear_all_overlays(self):
        """Clears the text content of all managed overlay windows."""
        for overlay in self.overlays.values():
            overlay.update_text("") # Set text to empty

    def hide_all_overlays(self):
        """Hides all managed overlay windows by updating their visibility state."""
        # print("OverlayManager: Hiding all overlays")
        for overlay in self.overlays.values():
            if overlay.winfo_exists():
                overlay.withdraw() # Use withdraw for immediate hiding

    def show_all_overlays(self):
        """Shows all managed overlay windows based on their individual enabled state."""
        # print("OverlayManager: Showing all overlays (if enabled)")
        if not self.global_overlays_enabled:
            # print("OverlayManager: Global overlays disabled, not showing.")
            return
        for overlay in self.overlays.values():
            # Let the overlay decide if it should be visible based on its own config
            overlay._update_visibility()

    def destroy_overlay(self, roi_name):
        """Safely destroys a specific overlay window and removes it from management."""
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            # print(f"OverlayManager: Destroying overlay for {roi_name}")
            if overlay.winfo_exists():
                overlay.destroy_window()
            del self.overlays[roi_name]

    def destroy_all_overlays(self):
        """Destroys all managed overlay windows."""
        # print("OverlayManager: Destroying all overlays")
        names = list(self.overlays.keys())
        for name in names:
            self.destroy_overlay(name)
        self.overlays = {} # Ensure the dictionary is empty

    def rebuild_overlays(self):
        """Destroys all existing overlays and recreates them based on current ROIs."""
        # print("OverlayManager: Rebuilding overlays")
        self.destroy_all_overlays()
        if not hasattr(self.app, 'rois'):
            print("Warning: rebuild_overlays called but app.rois not available.")
            return
        for roi in self.app.rois:
            self.create_overlay_for_roi(roi) # Creates if enabled, handles visibility internally

    def update_overlay_config(self, roi_name, new_partial_config):
        """Saves a partial config update and applies it to the live overlay if it exists."""
        # Save the partial update first (merges with existing config)
        if save_overlay_config_for_roi(roi_name, new_partial_config):
            # print(f"OverlayManager: Saved config update for {roi_name}")
            # Get the full, updated config after saving
            live_config = self._get_roi_config(roi_name)

            if roi_name in self.overlays:
                # If overlay exists, update its config and visibility
                # print(f"OverlayManager: Applying live config update to {roi_name}")
                self.overlays[roi_name].update_config(live_config)
                # update_config calls _update_visibility internally if needed
            else:
                # If overlay doesn't exist, check if it *should* exist now
                is_enabled_now = live_config.get('enabled', True)
                if is_enabled_now and self.global_overlays_enabled:
                    # Find the ROI object and create the overlay
                    roi = next((r for r in self.app.rois if r.name == roi_name), None)
                    if roi:
                        # print(f"OverlayManager: Creating overlay for {roi_name} after config update (enabled).")
                        self.create_overlay_for_roi(roi)
        else:
            print(f"Error: Failed to save overlay settings for {roi_name}.")

    def set_global_overlays_enabled(self, enabled):
        """Sets the global enabled state for all overlays."""
        if enabled == self.global_overlays_enabled:
            return # No change

        print(f"OverlayManager: Setting global overlays enabled to: {enabled}")
        self.global_overlays_enabled = enabled

        if set_setting("global_overlays_enabled", enabled):
            # Update the visibility of all existing overlays
            for overlay in self.overlays.values():
                overlay._update_visibility()

            # Update UI elements in other tabs (thread-safe checks)
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
                    # Reload the config view which implicitly updates widget states
                    if hasattr(self.app.overlay_tab, 'load_roi_config'):
                        self.app.overlay_tab.load_roi_config()

            except Exception as e:
                print(f"Error updating overlay tab global checkbox state: {e}")
        else:
            print("Error saving global overlay enabled state.")
            # Revert state if saving failed
            self.global_overlays_enabled = not enabled
            # Attempt to revert visibility
            for overlay in self.overlays.values():
                overlay._update_visibility()


    def save_specific_overlay_config(self, roi_name, config_dict):
        """Allows FloatingOverlayWindow to save its config via the manager."""
        # This is primarily for saving geometry changes initiated by the window itself
        if save_overlay_config_for_roi(roi_name, config_dict):
            # print(f"OverlayManager: Saved specific config (e.g., geometry) for {roi_name}")
            pass
        else:
            print(f"Error saving specific overlay config for {roi_name} via manager.")

    def reset_overlay_geometry(self, roi_name):
        """Resets the geometry for a specific overlay by saving None."""
        # Save None to the config to trigger default positioning on next load/update
        if save_overlay_config_for_roi(roi_name, {'geometry': None}):
            # print(f"OverlayManager: Saved geometry reset for {roi_name}")
            if roi_name in self.overlays:
                # Trigger a config update on the live overlay to apply the reset
                live_config = self._get_roi_config(roi_name) # Gets config with geometry=None
                self.overlays[roi_name].update_config(live_config) # This will call _load_geometry
                self.overlays[roi_name].lift() # Bring to front after reset
            return True
        else:
            print(f"Error saving geometry reset for {roi_name}.")
            return False