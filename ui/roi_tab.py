import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import BaseTab
from utils.config import save_rois
from utils.settings import get_overlay_config_for_roi, update_settings, get_setting
from ui.overlay_tab import SNIP_ROI_NAME
import os

class ROITab(BaseTab):
    def setup_ui(self):
        roi_frame = ttk.LabelFrame(self.frame, text="Regions of Interest (ROIs)", padding="10")
        roi_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        create_frame = ttk.Frame(roi_frame)
        create_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(create_frame, text="New ROI Name:").pack(side=tk.LEFT, anchor=tk.W, pady=(5, 0), padx=(0, 5))
        self.roi_name_entry = ttk.Entry(create_frame, width=15)
        self.roi_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(5, 0))
        self.roi_name_entry.insert(0, "dialogue")
        self.create_roi_btn = ttk.Button(create_frame, text="Define ROI", command=self.app.toggle_roi_selection)
        self.create_roi_btn.pack(side=tk.LEFT, padx=(5, 0), pady=(5, 0))
        ttk.Label(roi_frame, text="Click 'Define ROI', then click and drag on the image preview.", font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(0, 5))
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
        manage_btn_frame = ttk.Frame(list_manage_frame)
        manage_btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0))
        self.move_up_btn = ttk.Button(manage_btn_frame, text="▲ Up", width=8, command=self.move_roi_up, state=tk.DISABLED)
        self.move_up_btn.pack(pady=2, anchor=tk.N)
        self.move_down_btn = ttk.Button(manage_btn_frame, text="▼ Down", width=8, command=self.move_roi_down, state=tk.DISABLED)
        self.move_down_btn.pack(pady=2, anchor=tk.N)
        self.delete_roi_btn = ttk.Button(manage_btn_frame, text="Delete", width=8, command=self.delete_selected_roi, state=tk.DISABLED)
        self.delete_roi_btn.pack(pady=(10, 2), anchor=tk.N)
        self.config_overlay_btn = ttk.Button(manage_btn_frame, text="Overlay...", width=8, command=self.configure_selected_overlay, state=tk.DISABLED)
        self.config_overlay_btn.pack(pady=(5, 2), anchor=tk.N)
        file_btn_frame = ttk.Frame(roi_frame)
        file_btn_frame.pack(fill=tk.X, pady=(10, 0))
        self.save_rois_btn = ttk.Button(file_btn_frame, text="Save ROIs for Current Game", command=self.save_rois_for_current_game)
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)
        self.update_roi_list()

    def on_roi_selected(self, event=None):
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
        if active:
            self.create_roi_btn.config(text="Cancel Define")
            self.app.update_status("ROI selection active. Drag on preview.")
            self.app.master.config(cursor="crosshair")
        else:
            self.create_roi_btn.config(text="Define ROI")
            self.app.master.config(cursor="")

    def update_roi_list(self):
        current_selection_index = self.roi_listbox.curselection()
        selected_text = self.roi_listbox.get(current_selection_index[0]) if current_selection_index else None
        self.roi_listbox.delete(0, tk.END)
        for roi in self.app.rois:
            if roi.name == SNIP_ROI_NAME:
                continue
            config = get_overlay_config_for_roi(roi.name)
            is_overlay_enabled = config.get('enabled', False)
            prefix = "[O] " if is_overlay_enabled else "[ ] "
            self.roi_listbox.insert(tk.END, f"{prefix}{roi.name}")
        new_idx_to_select = -1
        if selected_text:
            try:
                new_idx_to_select = self.roi_listbox.get(0, tk.END).index(selected_text)
            except ValueError:
                pass
        if new_idx_to_select != -1:
            self.roi_listbox.select_set(new_idx_to_select)
            self.roi_listbox.activate(new_idx_to_select)
        if hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists():
            self.app.overlay_tab.update_roi_list()
        self.on_roi_selected()

    def save_rois_for_current_game(self):
        if not self.app.selected_hwnd:
            messagebox.showwarning("Save ROIs", "No game window selected.", parent=self.app.master)
            return
        rois_to_save = [roi for roi in self.app.rois if roi.name != SNIP_ROI_NAME]
        if not rois_to_save:
            messagebox.showwarning("Save ROIs", "No actual game ROIs defined to save.", parent=self.app.master)
            return
        saved_path = save_rois(rois_to_save, self.app.selected_hwnd)
        if saved_path:
            self.app.config_file = saved_path
            self.app.update_status(f"Saved {len(rois_to_save)} ROIs for current game.")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(saved_path)}")
        else:
            self.app.update_status("Failed to save ROIs for current game.")

    def move_roi_up(self):
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        idx_in_listbox = selection[0]
        listbox_text = self.roi_listbox.get(idx_in_listbox)
        roi_name = listbox_text.split("]", 1)[-1].strip()
        try:
            idx_in_app_list = next(i for i, r in enumerate(self.app.rois) if r.name == roi_name)
            prev_app_idx = idx_in_app_list - 1
            while prev_app_idx >= 0 and self.app.rois[prev_app_idx].name == SNIP_ROI_NAME:
                prev_app_idx -= 1
            if prev_app_idx < 0:
                return
            self.app.rois[idx_in_app_list], self.app.rois[prev_app_idx] = self.app.rois[prev_app_idx], self.app.rois[idx_in_app_list]
            self.update_roi_list()
            try:
                new_idx_in_listbox = self.roi_listbox.get(0, tk.END).index(listbox_text)
                self.roi_listbox.select_set(new_idx_in_listbox)
                self.roi_listbox.activate(new_idx_in_listbox)
            except ValueError:
                pass
            self.on_roi_selected()
        except (StopIteration, ValueError) as e:
            print(f"Error finding ROI for move up: {e}")

    def move_roi_down(self):
        selection = self.roi_listbox.curselection()
        if not selection:
            return
        idx_in_listbox = selection[0]
        if idx_in_listbox >= self.roi_listbox.size() - 1:
            return
        listbox_text = self.roi_listbox.get(idx_in_listbox)
        roi_name = listbox_text.split("]", 1)[-1].strip()
        try:
            idx_in_app_list = next(i for i, r in enumerate(self.app.rois) if r.name == roi_name)
            next_app_idx = idx_in_app_list + 1
            while next_app_idx < len(self.app.rois) and self.app.rois[next_app_idx].name == SNIP_ROI_NAME:
                next_app_idx += 1
            if next_app_idx >= len(self.app.rois):
                return
            self.app.rois[idx_in_app_list], self.app.rois[next_app_idx] = self.app.rois[next_app_idx], self.app.rois[idx_in_app_list]
            self.update_roi_list()
            try:
                new_idx_in_listbox = self.roi_listbox.get(0, tk.END).index(listbox_text)
                self.roi_listbox.select_set(new_idx_in_listbox)
                self.roi_listbox.activate(new_idx_in_listbox)
            except ValueError:
                pass
            self.on_roi_selected()
        except (StopIteration, ValueError) as e:
            print(f"Error finding ROI for move down: {e}")

    def delete_selected_roi(self):
        selection = self.roi_listbox.curselection()
        if not selection:
            return
        idx_in_listbox = selection[0]
        listbox_text = self.roi_listbox.get(idx_in_listbox)
        roi_name = listbox_text.split("]", 1)[-1].strip()
        if roi_name == SNIP_ROI_NAME:
            return
        confirm = messagebox.askyesno("Delete ROI", f"Delete ROI '{roi_name}'?", parent=self.app.master)
        if not confirm:
            return
        roi_to_delete = next((roi for roi in self.app.rois if roi.name == roi_name), None)
        if roi_to_delete:
            self.app.rois.remove(roi_to_delete)
        all_settings = get_setting("overlay_settings", {})
        if roi_name in all_settings:
            del all_settings[roi_name]
            update_settings({"overlay_settings": all_settings})
        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.destroy_overlay(roi_name)
        if roi_name in self.app.text_history:
            del self.app.text_history[roi_name]
        if roi_name in self.app.stable_texts:
            del self.app.stable_texts[roi_name]

        def safe_update(widget_name, update_method, data):
            widget = getattr(self.app, widget_name, None)
            if widget and widget.frame.winfo_exists():
                try:
                    update_method(data)
                except tk.TclError:
                    pass
        safe_update('text_tab', self.app.text_tab.update_text, self.app.text_history)
        safe_update('stable_text_tab', self.app.stable_text_tab.update_text, self.app.stable_texts)
        self.update_roi_list()
        self.app.update_status(f"ROI '{roi_name}' deleted.")

    def configure_selected_overlay(self):
        selection = self.roi_listbox.curselection()
        if not selection:
            return
        listbox_text = self.roi_listbox.get(selection[0])
        roi_name = listbox_text.split("]", 1)[-1].strip()
        if not hasattr(self.app, 'overlay_tab') or not self.app.overlay_tab.frame.winfo_exists():
            messagebox.showerror("Error", "Overlay tab not available.", parent=self.app.master)
            return
        try:
            overlay_tab_widget = self.app.overlay_tab.frame
            notebook_widget = overlay_tab_widget.master
            if not isinstance(notebook_widget, ttk.Notebook):
                raise tk.TclError("Parent not Notebook")
            notebook_widget.select(overlay_tab_widget)
            if hasattr(self.app.overlay_tab, 'roi_names_for_combo') and roi_name in self.app.overlay_tab.roi_names_for_combo:
                self.app.overlay_tab.selected_roi_var.set(roi_name)
                self.app.overlay_tab.load_roi_config()
            else:
                print(f"ROI '{roi_name}' not found in Overlay Tab combo after switch.")
        except (tk.TclError, AttributeError) as e:
            print(f"Error switching to overlay tab: {e}")
            messagebox.showerror("Error", "Could not switch to Overlay tab.", parent=self.app.master)
        except Exception as e:
            print(f"Unexpected error configuring overlay: {e}")
