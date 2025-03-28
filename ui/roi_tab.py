# --- START OF FILE ui/roi_tab.py ---

import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import BaseTab
from utils.config import save_rois
from utils.settings import get_overlay_config_for_roi, update_settings, get_setting, set_setting
from ui.overlay_tab import SNIP_ROI_NAME # Import the special name
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
        self.roi_name_entry.insert(0, "dialogue")
        self.create_roi_btn = ttk.Button(create_frame, text="Define ROI", command=self.app.toggle_roi_selection)
        self.create_roi_btn.pack(side=tk.LEFT, padx=(5, 0), pady=(5,0))
        ttk.Label(roi_frame, text="Click 'Define ROI', then click and drag on the image preview.",
                  font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))

        # --- ROI List and Management ---
        list_manage_frame = ttk.Frame(roi_frame)
        list_manage_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        list_frame = ttk.Frame(list_manage_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        ttk.Label(list_frame, text="Current Game ROIs (Select to manage):").pack(anchor=tk.W)
        roi_scrollbar = ttk.Scrollbar(list_frame)
        roi_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.roi_listbox = tk.Listbox(list_frame, height=6, selectmode=tk.SINGLE, exportselection=False, yscrollcommand=roi_scrollbar.set)
        self.roi_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roi_scrollbar.config(command=self.roi_listbox.yview)
        self.roi_listbox.bind("<<ListboxSelect>>", self.on_roi_selected)

        # --- Management Buttons ---
        manage_btn_frame = ttk.Frame(list_manage_frame)
        manage_btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5,0))
        self.move_up_btn = ttk.Button(manage_btn_frame, text="▲ Up", width=8, command=self.move_roi_up, state=tk.DISABLED)
        self.move_up_btn.pack(pady=2, anchor=tk.N)
        self.move_down_btn = ttk.Button(manage_btn_frame, text="▼ Down", width=8, command=self.move_roi_down, state=tk.DISABLED)
        self.move_down_btn.pack(pady=2, anchor=tk.N)
        self.delete_roi_btn = ttk.Button(manage_btn_frame, text="Delete", width=8, command=self.delete_selected_roi, state=tk.DISABLED)
        self.delete_roi_btn.pack(pady=(10, 2), anchor=tk.N)
        self.config_overlay_btn = ttk.Button(manage_btn_frame, text="Overlay...", width=8, command=self.configure_selected_overlay, state=tk.DISABLED)
        self.config_overlay_btn.pack(pady=(5, 2), anchor=tk.N)

        # --- Save Button ---
        file_btn_frame = ttk.Frame(roi_frame)
        file_btn_frame.pack(fill=tk.X, pady=(10, 0))
        self.save_rois_btn = ttk.Button(file_btn_frame, text="Save ROIs for Current Game", command=self.save_rois_for_current_game)
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)

        # Load initial list (if any ROIs loaded automatically)
        self.update_roi_list()


    def on_roi_selected(self, event=None):
        """Enable/disable management buttons based on selection."""
        selection = self.roi_listbox.curselection()
        has_selection = bool(selection)
        num_items = self.roi_listbox.size()
        idx = selection[0] if has_selection else -1

        self.move_up_btn.config(state=tk.NORMAL if has_selection and idx > 0 else tk.DISABLED)
        self.move_down_btn.config(state=tk.NORMAL if has_selection and idx < num_items - 1 else tk.DISABLED)
        self.delete_roi_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)
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
        """Update the ROI listbox (excluding special names) and the Overlay tab's combo."""
        current_selection_index = self.roi_listbox.curselection()
        selected_text = self.roi_listbox.get(current_selection_index[0]) if current_selection_index else None

        self.roi_listbox.delete(0, tk.END)
        display_rois = [] # ROIs to show in this listbox
        for roi in self.app.rois:
            # --- Filter out special names like SNIP_ROI_NAME ---
            if roi.name == SNIP_ROI_NAME:
                continue # Skip adding to this listbox

            display_rois.append(roi) # Add valid game ROIs
            config = get_overlay_config_for_roi(roi.name)
            is_overlay_enabled = config.get('enabled', False)
            prefix = "[O] " if is_overlay_enabled else "[ ] "
            self.roi_listbox.insert(tk.END, f"{prefix}{roi.name}")

        # Try to re-select based on stored text
        new_idx_to_select = -1
        if selected_text:
            try:
                # Find the index of the previously selected text in the new list
                new_idx_to_select = self.roi_listbox.get(0, tk.END).index(selected_text)
            except ValueError:
                pass # Not found

        if new_idx_to_select != -1:
            self.roi_listbox.select_set(new_idx_to_select)
            self.roi_listbox.activate(new_idx_to_select)
        elif self.roi_listbox.size() > 0:
            # Optionally select the first item if previous selection is gone
            # self.roi_listbox.select_set(0); self.roi_listbox.activate(0)
            pass # Or keep no selection

        # Update the ROI list in the Overlay Tab (which *includes* the snip option)
        if hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists():
            self.app.overlay_tab.update_roi_list()

        self.on_roi_selected() # Update button states based on listbox selection


    def save_rois_for_current_game(self):
        """Save ROIs for the currently selected game window."""
        if not self.app.selected_hwnd:
            messagebox.showwarning("Save ROIs", "No game window selected.", parent=self.app.master); return
        # Filter out the special snip name if it somehow got into self.app.rois
        rois_to_save = [roi for roi in self.app.rois if roi.name != SNIP_ROI_NAME]
        if not rois_to_save:
            messagebox.showwarning("Save ROIs", "No actual game ROIs defined to save.", parent=self.app.master); return

        saved_path = save_rois(rois_to_save, self.app.selected_hwnd)
        if saved_path:
            self.app.config_file = saved_path
            self.app.update_status(f"Saved {len(rois_to_save)} ROIs for current game.")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(saved_path)}")
        else:
            self.app.update_status("Failed to save ROIs for current game.")

    def move_roi_up(self):
        """Move the selected ROI up in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0: return
        idx_in_listbox = selection[0]

        # Find the corresponding ROI object in the main app list
        listbox_text = self.roi_listbox.get(idx_in_listbox)
        roi_name = listbox_text.split("]", 1)[-1].strip()
        try:
            # Find index in the potentially longer self.app.rois list
            idx_in_app_list = next(i for i, r in enumerate(self.app.rois) if r.name == roi_name)
            # Find the previous *actual game ROI* index in the app list
            prev_app_idx = idx_in_app_list - 1
            while prev_app_idx >= 0 and self.app.rois[prev_app_idx].name == SNIP_ROI_NAME:
                prev_app_idx -= 1
            if prev_app_idx < 0: return # Already the first game ROI

            # Swap in the main app list
            self.app.rois[idx_in_app_list], self.app.rois[prev_app_idx] = \
                self.app.rois[prev_app_idx], self.app.rois[idx_in_app_list]

            self.update_roi_list() # This redraws the listbox correctly
            # Re-select based on the moved item's text
            try:
                new_idx_in_listbox = self.roi_listbox.get(0, tk.END).index(listbox_text)
                self.roi_listbox.select_set(new_idx_in_listbox)
                self.roi_listbox.activate(new_idx_in_listbox)
            except ValueError: pass # Should be found
            self.on_roi_selected()
        except (StopIteration, ValueError) as e:
            print(f"Error finding ROI for move up: {e}")


    def move_roi_down(self):
        """Move the selected ROI down in the list."""
        selection = self.roi_listbox.curselection()
        if not selection: return
        idx_in_listbox = selection[0]
        # Check if it's the last item *in the listbox*
        if idx_in_listbox >= self.roi_listbox.size() - 1: return

        listbox_text = self.roi_listbox.get(idx_in_listbox)
        roi_name = listbox_text.split("]", 1)[-1].strip()
        try:
            idx_in_app_list = next(i for i, r in enumerate(self.app.rois) if r.name == roi_name)
            # Find the next *actual game ROI* index
            next_app_idx = idx_in_app_list + 1
            while next_app_idx < len(self.app.rois) and self.app.rois[next_app_idx].name == SNIP_ROI_NAME:
                next_app_idx += 1
            if next_app_idx >= len(self.app.rois): return # Already the last game ROI

            # Swap
            self.app.rois[idx_in_app_list], self.app.rois[next_app_idx] = \
                self.app.rois[next_app_idx], self.app.rois[idx_in_app_list]

            self.update_roi_list()
            # Re-select
            try:
                new_idx_in_listbox = self.roi_listbox.get(0, tk.END).index(listbox_text)
                self.roi_listbox.select_set(new_idx_in_listbox)
                self.roi_listbox.activate(new_idx_in_listbox)
            except ValueError: pass
            self.on_roi_selected()
        except (StopIteration, ValueError) as e:
            print(f"Error finding ROI for move down: {e}")


    def delete_selected_roi(self):
        """Delete the selected ROI."""
        selection = self.roi_listbox.curselection()
        if not selection: return
        idx_in_listbox = selection[0]
        listbox_text = self.roi_listbox.get(idx_in_listbox)
        roi_name = listbox_text.split("]", 1)[-1].strip()

        # Double check it's not the special name
        if roi_name == SNIP_ROI_NAME: return

        confirm = messagebox.askyesno("Delete ROI", f"Delete ROI '{roi_name}'?", parent=self.app.master)
        if not confirm: return

        # Remove from app's main list
        roi_to_delete = next((roi for roi in self.app.rois if roi.name == roi_name), None)
        if roi_to_delete: self.app.rois.remove(roi_to_delete)

        # Remove associated overlay settings
        all_settings = get_setting("overlay_settings", {})
        if roi_name in all_settings:
            del all_settings[roi_name]
            update_settings({"overlay_settings": all_settings})

        # Destroy overlay window
        if hasattr(self.app, 'overlay_manager'): self.app.overlay_manager.destroy_overlay(roi_name)

        # Remove from text history/stable text
        if roi_name in self.app.text_history: del self.app.text_history[roi_name]
        if roi_name in self.app.stable_texts: del self.app.stable_texts[roi_name]
        # Refresh relevant displays
        def safe_update(widget_name, update_method, data):
            widget = getattr(self.app, widget_name, None)
            if widget and widget.frame.winfo_exists():
                try: update_method(data)
                except tk.TclError: pass
        safe_update('text_tab', self.app.text_tab.update_text, self.app.text_history)
        safe_update('stable_text_tab', self.app.stable_text_tab.update_text, self.app.stable_texts)

        self.update_roi_list() # Updates listbox and overlay tab combo
        self.app.update_status(f"ROI '{roi_name}' deleted.")
        # Consider auto-saving


    def configure_selected_overlay(self):
        """Switch to the Overlay tab and select the corresponding ROI."""
        selection = self.roi_listbox.curselection()
        if not selection: return
        listbox_text = self.roi_listbox.get(selection[0])
        roi_name = listbox_text.split("]", 1)[-1].strip()

        if not hasattr(self.app, 'overlay_tab') or not self.app.overlay_tab.frame.winfo_exists():
            messagebox.showerror("Error", "Overlay tab not available.", parent=self.app.master); return

        try:
            overlay_tab_widget = self.app.overlay_tab.frame
            notebook_widget = overlay_tab_widget.master
            if not isinstance(notebook_widget, ttk.Notebook): raise tk.TclError("Parent not Notebook")
            notebook_widget.select(overlay_tab_widget)

            # Set the selected ROI in the Overlay tab's combobox (it includes SNIP name)
            if hasattr(self.app.overlay_tab, 'roi_names_for_combo') and roi_name in self.app.overlay_tab.roi_names_for_combo:
                self.app.overlay_tab.selected_roi_var.set(roi_name)
                self.app.overlay_tab.load_roi_config() # Load config for display
            else: print(f"ROI '{roi_name}' not found in Overlay Tab combo after switch.")
        except (tk.TclError, AttributeError) as e:
            print(f"Error switching to overlay tab: {e}")
            messagebox.showerror("Error", "Could not switch to Overlay tab.", parent=self.app.master)
        except Exception as e: print(f"Unexpected error configuring overlay: {e}")

# --- END OF FILE ui/roi_tab.py ---