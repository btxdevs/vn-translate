import tkinter as tk
from ui.overlay import OverlayWindow
from utils.settings import get_setting, set_setting, update_settings
import win32gui # To check game window validity

class OverlayManager:
    """Manages multiple OverlayWindow instances."""

    # Default configuration applied if no specific setting exists for an ROI
    DEFAULT_OVERLAY_CONFIG = {
        "enabled": True,
        "font_family": "Segoe UI", # Default modern font
        "font_size": 14,
        "font_color": "white",
        "bg_color": "#222222", # Dark grey background
        "alpha": 0.85, # Transparency level (used by OverlayWindow if applicable)
        "position": "bottom_roi", # Default position relative to ROI
        "wraplength": 450, # Max width in pixels before text wraps
        "justify": "left" # Text alignment (left, center, right)
    }

    def __init__(self, master, app_ref):
        self.master = master
        self.app = app_ref # Reference to the main application
        self.overlays = {}  # roi_name: OverlayWindow instance
        # Load global enabled state and individual ROI settings from persistent storage
        self.global_overlays_enabled = get_setting("global_overlays_enabled", True)
        self.overlay_settings = get_setting("overlay_settings", {}) # roi_name: config_dict

    def _get_roi_config(self, roi_name):
        """Gets the specific config for an ROI, merging with defaults."""
        # Start with a copy of the defaults
        config = self.DEFAULT_OVERLAY_CONFIG.copy()
        # Get ROI-specific saved settings
        roi_specific = self.overlay_settings.get(roi_name, {})
        # Update the defaults with any specific settings found
        config.update(roi_specific)
        return config

    def create_overlay_for_roi(self, roi):
        """Creates or recreates an overlay window for a given ROI object."""
        roi_name = roi.name
        if roi_name in self.overlays:
            # If already exists, maybe just update its config/position?
            # For simplicity now, destroy and recreate if needed.
            self.destroy_overlay(roi_name)

        # Check if game window is valid before creating
        if not self.app.selected_hwnd or not win32gui.IsWindow(self.app.selected_hwnd):
            # print(f"Cannot create overlay for {roi_name}: Invalid game window.")
            return # Silently fail if no valid game window

        config = self._get_roi_config(roi_name)

        # Only create if globally enabled AND this specific ROI is enabled in its config
        if self.global_overlays_enabled and config.get("enabled", True):
            try:
                overlay = OverlayWindow(self.master, roi_name, config, self.app.selected_hwnd)
                self.overlays[roi_name] = overlay
                print(f"Created overlay for ROI: {roi_name}")
                # It starts hidden, will be shown on update_text if needed
            except Exception as e:
                print(f"Error creating overlay window for {roi_name}: {e}")
        else:
            # Don't print spam if intentionally disabled
            # print(f"Overlay creation skipped for {roi_name} (Globally Enabled: {self.global_overlays_enabled}, ROI Enabled: {config.get('enabled', True)})")
            pass


    def update_overlay(self, roi_name, text):
        """Updates the text and position of a specific overlay."""
        if roi_name in self.overlays:
            overlay = self.overlays[roi_name]
            # Find the corresponding ROI object to get its coordinates
            roi = next((r for r in self.app.rois if r.name == roi_name), None)
            if roi:
                # Pass ROI coordinates relative to the game window's client area origin
                # Assuming roi.x1, roi.y1 etc. are relative to the captured frame origin
                # which should correspond to the game window client area origin.
                roi_rect = (roi.x1, roi.y1, roi.x2, roi.y2)
                # Update text first, which handles showing/hiding based on content & enabled state
                overlay.update_text(text)
                # Position update is handled within update_text -> update_position_if_needed
                # overlay.update_position_if_needed(roi_rect_in_game_coords=roi_rect) # Pass coords here
            else:
                # If ROI object not found (e.g., deleted but overlay not yet destroyed?), just update text
                overlay.update_text(text)
                # Cannot update position accurately without ROI coords
                overlay.update_position_if_needed() # Use fallback position


    def update_overlays(self, translated_segments):
        """Updates all relevant overlays based on the translation results dictionary."""
        if not self.global_overlays_enabled:
            self.hide_all_overlays() # Ensure all are hidden if globally disabled
            return

        # Get all current ROI names
        all_roi_names = {roi.name for roi in self.app.rois}
        # Get names of ROIs that received a translation
        translated_roi_names = set(translated_segments.keys())

        # Iterate through all known ROIs
        for roi_name in all_roi_names:
            # Check if an overlay exists or should exist
            overlay_exists = roi_name in self.overlays
            roi = next((r for r in self.app.rois if r.name == roi_name), None)
            config = self._get_roi_config(roi_name)
            is_roi_enabled = config.get("enabled", True)

            # Get the translated text, default to empty string if none provided
            text_to_display = translated_segments.get(roi_name, "")

            if roi and is_roi_enabled: # If the ROI exists and should be displayed
                if not overlay_exists:
                    # Create overlay if it's missing but should be shown
                    print(f"Recreating missing overlay for enabled ROI: {roi_name}")
                    self.create_overlay_for_roi(roi) # Create it
                    overlay_exists = roi_name in self.overlays # Check again

                if overlay_exists:
                    # Update the overlay with text (handles show/hide internally)
                    self.update_overlay(roi_name, text_to_display)

            elif overlay_exists:
                # If ROI is disabled or deleted, ensure overlay is hidden/destroyed
                print(f"Hiding/Destroying overlay for disabled/deleted ROI: {roi_name}")
                self.destroy_overlay(roi_name) # Destroy might be cleaner


    def clear_all_overlays(self):
        """Clears text from all managed overlays (hides them)."""
        for overlay in self.overlays.values():
            overlay.update_text("")

    def hide_all_overlays(self):
        """Hides all managed overlay windows."""
        for overlay in self.overlays.values():
            overlay.withdraw()

    def show_all_overlays(self):
        """Shows all managed overlay windows *if* they have text and are enabled."""
        if not self.global_overlays_enabled:
            return
        print("Attempting to show all enabled overlays with text...")
        for roi_name, overlay in self.overlays.items():
            config = self._get_roi_config(roi_name)
            # Show only if globally enabled, ROI enabled, and has text
            if config.get("enabled", True) and overlay.label_var.get():
                # Find ROI for position update
                roi = next((r for r in self.app.rois if r.name == roi_name), None)
                roi_rect = (roi.x1, roi.y1, roi.x2, roi.y2) if roi else None
                overlay.update_position_if_needed(roi_rect) # Recalc position
                overlay.deiconify()
                overlay.lift()


    def destroy_overlay(self, roi_name):
        """Destroys a specific overlay window."""
        if roi_name in self.overlays:
            try:
                self.overlays[roi_name].destroy_window()
            except Exception as e:
                print(f"Error destroying overlay {roi_name}: {e}")
            del self.overlays[roi_name]
            print(f"Destroyed overlay for ROI: {roi_name}")


    def destroy_all_overlays(self):
        """Destroys all managed overlay windows."""
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
        for roi in self.app.rois:
            self.create_overlay_for_roi(roi) # Creates only if enabled

    def update_overlay_config(self, roi_name, new_partial_config):
        """Updates the config for a specific overlay and saves it."""
        # Ensure the roi_name entry exists in settings
        if roi_name not in self.overlay_settings:
            self.overlay_settings[roi_name] = {}

        # Update the specific settings for this ROI
        self.overlay_settings[roi_name].update(new_partial_config)

        # Save updated settings persistently
        if update_settings({"overlay_settings": self.overlay_settings}):
            print(f"Overlay settings saved for {roi_name}.")
        else:
            print(f"Error saving overlay settings for {roi_name}.")

        # Apply changes to the live overlay if it exists
        if roi_name in self.overlays:
            # Get the fully merged config (defaults + specific) to apply
            live_config = self._get_roi_config(roi_name)
            self.overlays[roi_name].update_config(live_config)
        elif new_partial_config.get('enabled', False) and self.global_overlays_enabled:
            # If overlay was disabled but now enabled, try to create it
            roi = next((r for r in self.app.rois if r.name == roi_name), None)
            if roi:
                print(f"Creating overlay for {roi_name} as it was enabled.")
                self.create_overlay_for_roi(roi)


    def set_global_overlays_enabled(self, enabled):
        """Sets the global enable state, saves it, and shows/hides overlays."""
        if enabled == self.global_overlays_enabled:
            return # No change

        self.global_overlays_enabled = enabled
        set_setting("global_overlays_enabled", enabled) # Save setting

        if enabled:
            print("Global overlays enabled. Rebuilding...")
            self.rebuild_overlays() # Recreate overlays respecting individual configs
            # Optionally restore last text? Needs storing last text per overlay.
        else:
            print("Global overlays disabled. Hiding all.")
            self.hide_all_overlays()

        # Update floating controls state if they exist
        if self.app.floating_controls and self.app.floating_controls.winfo_exists():
            self.app.floating_controls.overlay_var.set(enabled)