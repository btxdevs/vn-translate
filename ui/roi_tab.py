# --- START OF FILE ui/roi_tab.py ---

import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import BaseTab
from utils.config import save_rois # Removed load_rois import
# Import settings functions directly for getting config and saving removal
from utils.settings import get_overlay_config_for_roi, update_settings, get_setting, set_setting
import os

class ROITab(BaseTab):
    """Tab for ROI management."""

    def setup_ui(self):
        roi_frame = ttk.LabelFrame(self.frame, text="Regions of Interest (ROIs)", padding="10")
        roi_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # --- New ROI creation ---
        create_frame = ttk.Frame(roi_frame)
        create_frame.pack(fill=tk.X, pady=(0,10))

        ttk.Label(create_frame, text="New ROI Name:").pack(side=tk.LEFT, anchor=tk.W, pady=(5, 0), padx=(0,5))

        self.roi_name_entry = ttk.Entry(create_frame, width=15)
        self.roi_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(5, 0))
        self.roi_name_entry.insert(0, "dialogue") # Default name

        self.create_roi_btn = ttk.Button(create_frame, text="Define ROI",
                                         command=self.app.toggle_roi_selection)
        self.create_roi_btn.pack(side=tk.LEFT, padx=(5, 0), pady=(5,0))

        ttk.Label(roi_frame, text="Click 'Define ROI', then click and drag on the image preview.",
                  font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))


        # --- ROI List and Management ---
        list_manage_frame = ttk.Frame(roi_frame)
        list_manage_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        list_frame = ttk.Frame(list_manage_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(list_frame, text="Current ROIs (Select to manage):").pack(anchor=tk.W)

        roi_scrollbar = ttk.Scrollbar(list_frame)
        roi_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.roi_listbox = tk.Listbox(list_frame, height=6, selectmode=tk.SINGLE,
                                      exportselection=False,
                                      yscrollcommand=roi_scrollbar.set)
        self.roi_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roi_scrollbar.config(command=self.roi_listbox.yview)
        self.roi_listbox.bind("<<ListboxSelect>>", self.on_roi_selected)


        manage_btn_frame = ttk.Frame(list_manage_frame)
        manage_btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5,0))

        self.move_up_btn = ttk.Button(manage_btn_frame, text="▲ Up", width=8,
                                      command=self.move_roi_up, state=tk.DISABLED)
        self.move_up_btn.pack(pady=2, anchor=tk.N)

        self.move_down_btn = ttk.Button(manage_btn_frame, text="▼ Down", width=8,
                                        command=self.move_roi_down, state=tk.DISABLED)
        self.move_down_btn.pack(pady=2, anchor=tk.N)

        self.delete_roi_btn = ttk.Button(manage_btn_frame, text="Delete", width=8,
                                         command=self.delete_selected_roi, state=tk.DISABLED)
        self.delete_roi_btn.pack(pady=(10, 2), anchor=tk.N)

        self.config_overlay_btn = ttk.Button(manage_btn_frame, text="Overlay...", width=8,
                                             command=self.configure_selected_overlay, state=tk.DISABLED)
        self.config_overlay_btn.pack(pady=(5, 2), anchor=tk.N)


        # --- Save Button (Removed Load/Save As) ---
        file_btn_frame = ttk.Frame(roi_frame)
        file_btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.save_rois_btn = ttk.Button(file_btn_frame, text="Save ROIs for Current Game",
                                        command=self.save_rois_for_current_game) # Changed command
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)

        # self.load_rois_btn = ttk.Button(file_btn_frame, text="Load ROIs...",
        #                                 command=self.load_rois) # REMOVED
        # self.load_rois_btn.pack(side=tk.LEFT, padx=5) # REMOVED


    def on_roi_selected(self, event=None):
        """Enable/disable management buttons based on selection."""
        selection = self.roi_listbox.curselection()
        has_selection = bool(selection)
        num_items = self.roi_listbox.size()
        idx = selection[0] if has_selection else -1

        self.move_up_btn.config(state=tk.NORMAL if has_selection and idx > 0 else tk.DISABLED)
        self.move_down_btn.config(state=tk.NORMAL if has_selection and idx < num_items - 1 else tk.DISABLED)
        self.delete_roi_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        # Enable overlay config button only if overlay tab exists
        can_config_overlay = has_selection and hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists()
        self.config_overlay_btn.config(state=tk.NORMAL if can_config_overlay else tk.DISABLED)


    def on_roi_selection_toggled(self, active):
        """Update UI when ROI selection mode is toggled."""
        if active:
            self.create_roi_btn.config(text="Cancel Define")
            self.app.update_status("ROI selection active. Drag on preview.")
            self.app.master.config(cursor="crosshair")
        else:
            self.create_roi_btn.config(text="Define ROI")
            self.app.master.config(cursor="")
            # Status updated by calling functions


    def update_roi_list(self):
        """Update the ROI listbox with current ROIs."""
        current_selection_index = self.roi_listbox.curselection()
        idx_to_select = current_selection_index[0] if current_selection_index else -1

        self.roi_listbox.delete(0, tk.END)
        for roi in self.app.rois:
            # Get config for this ROI to check if overlay is enabled
            config = get_overlay_config_for_roi(roi.name) # Use settings utility
            is_overlay_enabled = config.get('enabled', False)
            prefix = "[O] " if is_overlay_enabled else "[ ] "
            self.roi_listbox.insert(tk.END, f"{prefix}{roi.name}")

        if 0 <= idx_to_select < self.roi_listbox.size():
            self.roi_listbox.select_set(idx_to_select)
            self.roi_listbox.activate(idx_to_select)
        elif self.roi_listbox.size() > 0:
            idx_to_select = -1 # No selection if index out of bounds

        # Update the ROI list in the Overlay Tab as well
        if hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists():
            self.app.overlay_tab.update_roi_list()

        self.on_roi_selected() # Update button states


    def save_rois_for_current_game(self):
        """Save ROIs for the currently selected game window."""
        if not self.app.selected_hwnd:
            messagebox.showwarning("Save ROIs", "No game window selected.", parent=self.app.master)
            return
        if not self.app.rois:
            messagebox.showwarning("Save ROIs", "There are no ROIs defined to save.", parent=self.app.master)
            return

        saved_path = save_rois(self.app.rois, self.app.selected_hwnd)
        if saved_path:
            self.app.config_file = saved_path # Update app's current config file path
            self.app.update_status(f"Saved {len(self.app.rois)} ROIs for current game.")
            # Update window title to reflect the saved file (optional, but consistent)
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(saved_path)}")
        else:
            # Error message shown by save_rois or already handled
            self.app.update_status("Failed to save ROIs for current game.")

    # def load_rois(self): # REMOVED - Loading is automatic on window selection now
    #     """Load ROIs using the config utility."""
    #     # Suggest last used file from settings
    #     initial_suggestion = get_setting("last_roi_config", self.app.config_file)
    #     rois, loaded_config_file = load_rois(initial_suggestion)
    #
    #     if loaded_config_file and rois is not None:
    #         self.app.rois = rois
    #         self.app.config_file = loaded_config_file
    #         # Important: Save the newly loaded path as the 'last_roi_config'
    #         set_setting("last_roi_config", loaded_config_file)
    #
    #         self.update_roi_list() # Updates own list and overlay tab's list
    #         if hasattr(self.app, 'overlay_manager'):
    #             self.app.overlay_manager.rebuild_overlays() # Rebuild based on new ROIs
    #
    #         self.app.update_status(f"Loaded {len(rois)} ROIs from {os.path.basename(loaded_config_file)}")
    #         self.app.master.title(f"Visual Novel Translator - {os.path.basename(loaded_config_file)}")
    #         # Clear stale data
    #         self.app.text_history = {}
    #         self.app.stable_texts = {}
    #         if hasattr(self.app, 'text_tab'): self.app.text_tab.update_text({})
    #         if hasattr(self.app, 'stable_text_tab'): self.app.stable_text_tab.update_text({})
    #         if hasattr(self.app, 'translation_tab'): self.app.translation_tab.translation_display.config(state=tk.NORMAL); self.app.translation_tab.translation_display.delete(1.0, tk.END); self.app.translation_tab.translation_display.config(state=tk.DISABLED)
    #
    #     elif rois is None and loaded_config_file is None:
    #         self.app.update_status("ROI loading failed. See console or previous message.")
    #     else:
    #         self.app.update_status("ROI loading cancelled.")


    def move_roi_up(self):
        """Move the selected ROI up in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0: return
        idx = selection[0]

        self.app.rois[idx - 1], self.app.rois[idx] = self.app.rois[idx], self.app.rois[idx - 1]

        self.update_roi_list()
        new_idx = idx - 1
        self.roi_listbox.select_set(new_idx)
        self.roi_listbox.activate(new_idx)
        self.on_roi_selected()
        # Order doesn't visually matter for floating overlays, no rebuild needed for move.


    def move_roi_down(self):
        """Move the selected ROI down in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == len(self.app.rois) - 1: return
        idx = selection[0]

        self.app.rois[idx], self.app.rois[idx + 1] = self.app.rois[idx + 1], self.app.rois[idx]

        self.update_roi_list()
        new_idx = idx + 1
        self.roi_listbox.select_set(new_idx)
        self.roi_listbox.activate(new_idx)
        self.on_roi_selected()
        # Order doesn't visually matter for floating overlays, no rebuild needed for move.


    def delete_selected_roi(self):
        """Delete the selected ROI."""
        selection = self.roi_listbox.curselection()
        if not selection: return

        index = selection[0]
        listbox_text = self.roi_listbox.get(index)
        roi_name = listbox_text.split("]", 1)[-1].strip()

        confirm = messagebox.askyesno("Delete ROI", f"Are you sure you want to delete ROI '{roi_name}'?", parent=self.app.master)
        if not confirm: return

        roi_to_delete = next((roi for roi in self.app.rois if roi.name == roi_name), None)
        if not roi_to_delete: return

        self.app.rois.remove(roi_to_delete)

        # Remove associated overlay settings
        all_overlay_settings = get_setting("overlay_settings", {})
        if roi_name in all_overlay_settings:
            del all_overlay_settings[roi_name]
            update_settings({"overlay_settings": all_overlay_settings}) # Save removal

        # Destroy the overlay window
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.destroy_overlay(roi_name)

        # Remove from text history/stable text
        if roi_name in self.app.text_history: del self.app.text_history[roi_name]
        if roi_name in self.app.stable_texts: del self.app.stable_texts[roi_name]
        # Refresh displays
        if hasattr(self.app, 'text_tab'): self.app.text_tab.update_text(self.app.text_history) # Update with current history
        if hasattr(self.app, 'stable_text_tab'): self.app.stable_text_tab.update_text(self.app.stable_texts)

        self.update_roi_list()
        self.app.update_status(f"ROI '{roi_name}' deleted.")
        # Consider triggering an auto-save here? Or rely on user pressing save button?
        # self.save_rois_for_current_game() # Optional: Auto-save after deletion


    def configure_selected_overlay(self):
        """Switch to the Overlay tab and select the corresponding ROI."""
        selection = self.roi_listbox.curselection()
        if not selection: return

        listbox_text = self.roi_listbox.get(selection[0])
        roi_name = listbox_text.split("]", 1)[-1].strip()

        if not hasattr(self.app, 'overlay_tab') or not self.app.overlay_tab.frame.winfo_exists():
            messagebox.showerror("Error", "Overlay configuration tab is not available.", parent=self.app.master)
            return

        try:
            overlay_tab_widget = self.app.overlay_tab.frame
            notebook_widget = overlay_tab_widget.master
            # Simplified: Assume direct parent is the notebook
            if not isinstance(notebook_widget, ttk.Notebook):
                raise tk.TclError("Parent is not Notebook widget.")

            notebook_widget.select(overlay_tab_widget)

            # Set the selected ROI in the Overlay tab's combobox
            if hasattr(self.app.overlay_tab, 'roi_names') and roi_name in self.app.overlay_tab.roi_names:
                self.app.overlay_tab.selected_roi_var.set(roi_name)
                self.app.overlay_tab.load_roi_config() # Load config for display
            else:
                print(f"ROI '{roi_name}' not found in Overlay Tab's list after switch.")


        except (tk.TclError, AttributeError) as e:
            print(f"Error switching to overlay config tab: {e}")
            messagebox.showerror("Error", "Could not switch to Overlay configuration tab.", parent=self.app.master)
        except Exception as e:
            print(f"Unexpected error configuring overlay: {e}")

# --- END OF FILE ui/roi_tab.py ---