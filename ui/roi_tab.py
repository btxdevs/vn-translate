import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import BaseTab
from utils.config import save_rois, load_rois
from utils.settings import update_settings # For removing overlay settings
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
        # Add tooltip later if needed

        ttk.Label(roi_frame, text="Click 'Define ROI', then click and drag on the image preview.",
                  font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))


        # --- ROI List and Management ---
        list_manage_frame = ttk.Frame(roi_frame)
        list_manage_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Listbox with Scrollbar
        list_frame = ttk.Frame(list_manage_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(list_frame, text="Current ROIs (Select to manage):").pack(anchor=tk.W)

        roi_scrollbar = ttk.Scrollbar(list_frame)
        roi_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.roi_listbox = tk.Listbox(list_frame, height=6, selectmode=tk.SINGLE,
                                      exportselection=False, # Prevent selection changing when focus moves
                                      yscrollcommand=roi_scrollbar.set)
        self.roi_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roi_scrollbar.config(command=self.roi_listbox.yview)
        self.roi_listbox.bind("<<ListboxSelect>>", self.on_roi_selected)


        # Management Buttons (Vertical)
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
        self.config_overlay_btn.pack(pady=(5, 2), anchor=tk.N) # Moved closer


        # --- Save/Load Buttons ---
        file_btn_frame = ttk.Frame(roi_frame)
        file_btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.save_rois_btn = ttk.Button(file_btn_frame, text="Save ROIs As...",
                                        command=self.save_rois)
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)

        self.load_rois_btn = ttk.Button(file_btn_frame, text="Load ROIs...",
                                        command=self.load_rois)
        self.load_rois_btn.pack(side=tk.LEFT, padx=5)


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
        can_config_overlay = has_selection and hasattr(self.app, 'overlay_tab')
        self.config_overlay_btn.config(state=tk.NORMAL if can_config_overlay else tk.DISABLED)


    def on_roi_selection_toggled(self, active):
        """Update UI when ROI selection mode is toggled."""
        if active:
            self.create_roi_btn.config(text="Cancel Define")
            self.app.update_status("ROI selection active. Drag on preview.")
            self.app.master.config(cursor="crosshair") # Change cursor
        else:
            self.create_roi_btn.config(text="Define ROI")
            # Status update handled by app.toggle_roi_selection completion/cancellation
            self.app.master.config(cursor="") # Restore default cursor


    def update_roi_list(self):
        """Update the ROI listbox with current ROIs."""
        # Store current selection index to try and restore it
        current_selection_index = self.roi_listbox.curselection()
        idx_to_select = current_selection_index[0] if current_selection_index else -1

        self.roi_listbox.delete(0, tk.END)
        for roi in self.app.rois:
            # Maybe add an indicator if overlay is enabled? [O] ?
            is_overlay_enabled = False
            if hasattr(self.app, 'overlay_manager'):
                config = self.app.overlay_manager._get_roi_config(roi.name)
                is_overlay_enabled = config.get('enabled', False)
            prefix = "[O] " if is_overlay_enabled else "[ ] "
            self.roi_listbox.insert(tk.END, f"{prefix}{roi.name}") # Show name with overlay indicator

        # Try to restore selection
        if 0 <= idx_to_select < self.roi_listbox.size():
            self.roi_listbox.select_set(idx_to_select)
            self.roi_listbox.activate(idx_to_select)
        elif self.roi_listbox.size() > 0:
            idx_to_select = -1 # Reset selection if previous index invalid


        # Update the ROI list in the Overlay Tab as well
        if hasattr(self.app, 'overlay_tab'):
            self.app.overlay_tab.update_roi_list()

        # Update button states based on new selection state
        self.on_roi_selected()


    def save_rois(self):
        """Save ROIs using the config utility."""
        if not self.app.rois:
            messagebox.showwarning("Save ROIs", "There are no ROIs defined to save.", parent=self.app.master)
            return

        new_config_file = save_rois(self.app.rois, self.app.config_file)
        if new_config_file and new_config_file != self.app.config_file:
            self.app.config_file = new_config_file
            self.app.update_status(f"Saved {len(self.app.rois)} ROIs to {os.path.basename(new_config_file)}")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(new_config_file)}") # Update title
        elif new_config_file:
            # Saved to the same file (or user cancelled but path was returned)
            self.app.update_status(f"Saved {len(self.app.rois)} ROIs to {os.path.basename(new_config_file)}")
        # else: User cancelled, no status update needed


    def load_rois(self):
        """Load ROIs using the config utility."""
        rois, loaded_config_file = load_rois(self.app.config_file) # Pass current as suggestion

        if loaded_config_file and rois is not None: # Check success (path returned, rois not None)
            self.app.rois = rois
            self.app.config_file = loaded_config_file
            self.update_roi_list()
            self.app.overlay_manager.rebuild_overlays() # Rebuild overlays for new ROIs
            self.app.update_status(f"Loaded {len(rois)} ROIs from {os.path.basename(loaded_config_file)}")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(loaded_config_file)}") # Update title
            # Clear stale text data associated with old ROIs
            self.app.text_history = {}
            self.app.stable_texts = {}
            self.app.text_tab.update_text({})
            self.app.stable_text_tab.update_text({})
            # Safely clear translation display if it exists
            if hasattr(self.app, 'translation_tab') and self.app.translation_tab.frame.winfo_exists():
                try:
                    self.app.translation_tab.translation_display.config(state=tk.NORMAL)
                    self.app.translation_tab.translation_display.delete(1.0, tk.END)
                    self.app.translation_tab.translation_display.config(state=tk.DISABLED)
                except tk.TclError: pass # Ignore if widget destroyed


        elif rois is None and loaded_config_file is None: # Explicit failure from load_rois
            self.app.update_status("ROI loading failed. See console or previous message.")
        else: # User cancelled (rois=[], loaded_config_file=None)
            self.app.update_status("ROI loading cancelled.")


    def move_roi_up(self):
        """Move the selected ROI up in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0: return
        idx = selection[0]

        self.app.rois[idx - 1], self.app.rois[idx] = self.app.rois[idx], self.app.rois[idx - 1]

        self.update_roi_list() # Redraws listbox and updates overlay tab list
        # Restore selection
        new_idx = idx - 1
        self.roi_listbox.select_set(new_idx)
        self.roi_listbox.activate(new_idx)
        self.on_roi_selected() # Update button states
        self.app.overlay_manager.rebuild_overlays() # Order might matter for some overlay logic


    def move_roi_down(self):
        """Move the selected ROI down in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == len(self.app.rois) - 1: return
        idx = selection[0]

        self.app.rois[idx], self.app.rois[idx + 1] = self.app.rois[idx + 1], self.app.rois[idx]

        self.update_roi_list() # Redraws listbox and updates overlay tab list
        # Restore selection
        new_idx = idx + 1
        self.roi_listbox.select_set(new_idx)
        self.roi_listbox.activate(new_idx)
        self.on_roi_selected() # Update button states
        self.app.overlay_manager.rebuild_overlays()


    def delete_selected_roi(self):
        """Delete the selected ROI."""
        selection = self.roi_listbox.curselection()
        if not selection: return # Button should be disabled anyway

        index = selection[0]
        # Get name from listbox item (includes prefix) and strip prefix
        listbox_text = self.roi_listbox.get(index)
        roi_name = listbox_text.split("]", 1)[-1].strip() # Get text after "[O] " or "[ ] "

        # Confirm deletion
        confirm = messagebox.askyesno("Delete ROI", f"Are you sure you want to delete ROI '{roi_name}'?", parent=self.app.master)
        if not confirm: return

        # Find the actual ROI object by name (safer than relying on index if list changes)
        roi_to_delete = next((roi for roi in self.app.rois if roi.name == roi_name), None)
        if not roi_to_delete:
            print(f"Error: Could not find ROI object for name '{roi_name}' to delete.")
            return

        # Remove from list
        self.app.rois.remove(roi_to_delete)

        # Remove associated overlay settings (needs access to overlay_manager instance)
        if hasattr(self.app, 'overlay_manager') and roi_name in self.app.overlay_manager.overlay_settings:
            del self.app.overlay_manager.overlay_settings[roi_name]
            update_settings({"overlay_settings": self.app.overlay_manager.overlay_settings}) # Save removal

        # Destroy the overlay window if it exists
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.destroy_overlay(roi_name)

        # Remove from text history and stable text
        if roi_name in self.app.text_history: del self.app.text_history[roi_name]
        if roi_name in self.app.stable_texts: del self.app.stable_texts[roi_name]
        # Refresh displays (which will use the updated self.app.rois)
        # Safely update text tabs if they exist
        if hasattr(self.app, 'text_tab') and self.app.text_tab.frame.winfo_exists():
            self.app.text_tab.update_text({}) # Update with empty dict or current?
        if hasattr(self.app, 'stable_text_tab') and self.app.stable_text_tab.frame.winfo_exists():
            self.app.stable_text_tab.update_text(self.app.stable_texts)


        self.update_roi_list() # Updates listbox and overlay tab's list
        self.app.update_status(f"ROI '{roi_name}' deleted.")


    def configure_selected_overlay(self):
        """Switch to the Overlay tab and select the corresponding ROI."""
        selection = self.roi_listbox.curselection()
        if not selection: return

        # Get name from listbox item (includes prefix) and strip prefix
        listbox_text = self.roi_listbox.get(selection[0])
        roi_name = listbox_text.split("]", 1)[-1].strip()

        # --- Corrected Check ---
        # Check if overlay tab and its frame widget exist
        if not hasattr(self.app, 'overlay_tab') or not hasattr(self.app.overlay_tab, 'frame') or not self.app.overlay_tab.frame.winfo_exists():
            messagebox.showerror("Error", "Overlay configuration tab is not available.", parent=self.app.master)
            return
        # --- End Correction ---

        # Find the index of the Overlay tab
        try:
            overlay_tab_widget = self.app.overlay_tab.frame
            # Find the notebook containing this frame (usually the direct master)
            notebook_widget = overlay_tab_widget.master
            if not isinstance(notebook_widget, ttk.Notebook):
                # If nested deeper, search upwards (less likely with current structure)
                curr = notebook_widget.master
                while curr and not isinstance(curr, ttk.Notebook):
                    curr = curr.master
                notebook_widget = curr

            if not notebook_widget or not isinstance(notebook_widget, ttk.Notebook):
                raise tk.TclError("Could not find parent Notebook widget.")

            # Select the tab using the widget itself
            notebook_widget.select(overlay_tab_widget)

            # Set the selected ROI in the Overlay tab's combobox
            if roi_name in self.app.overlay_tab.roi_names:
                self.app.overlay_tab.selected_roi_var.set(roi_name)
                # Load the config for this ROI in the overlay tab
                self.app.overlay_tab.load_roi_config()
            else:
                print(f"ROI '{roi_name}' not found in Overlay Tab's list.")


        except (tk.TclError, AttributeError) as e:
            print(f"Error switching to overlay config tab: {e}")
            messagebox.showerror("Error", "Could not switch to Overlay configuration tab.", parent=self.app.master)
        except Exception as e:
            print(f"Unexpected error configuring overlay: {e}")