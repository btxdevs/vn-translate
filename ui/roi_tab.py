# --- START OF FILE ui/roi_tab.py ---

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from ui.base import BaseTab
from utils.capture import capture_window
from utils.config import save_rois
from utils.settings import get_overlay_config_for_roi, update_settings, get_setting
from utils.roi import ROI
from ui.overlay_tab import SNIP_ROI_NAME
from ui.preview_window import PreviewWindow
from ui.color_picker import ScreenColorPicker
import os
import cv2

class ROITab(BaseTab):
    def setup_ui(self):
        # --- Main ROI definition and list ---
        roi_frame = ttk.LabelFrame(self.frame, text="Regions of Interest (ROIs)", padding="10")
        roi_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        create_frame = ttk.Frame(roi_frame)
        create_frame.pack(fill=tk.X, pady=(0, 5))
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
        ttk.Label(list_frame, text="Current Game ROIs ([O]=Overlay, [C]=Color Filter):").pack(anchor=tk.W)
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

        # --- Color Filter Configuration ---
        self.color_filter_frame = ttk.LabelFrame(self.frame, text="Color Filtering (for selected ROI)", padding="10")
        self.color_filter_frame.pack(fill=tk.X, pady=(5, 5))
        self.color_widgets = {}

        # Enable Checkbox
        self.color_widgets['enabled_var'] = tk.BooleanVar(value=False)
        self.color_widgets['enabled_check'] = ttk.Checkbutton(
            self.color_filter_frame, text="Enable Color Filter", variable=self.color_widgets['enabled_var']
        )
        self.color_widgets['enabled_check'].grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 5))

        # Target Color
        ttk.Label(self.color_filter_frame, text="Target Color:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        self.color_widgets['target_color_var'] = tk.StringVar(value="#FFFFFF")
        self.color_widgets['target_color_label'] = ttk.Label(self.color_filter_frame, text="       ", background="#FFFFFF", relief=tk.SUNKEN, width=8)
        self.color_widgets['target_color_label'].grid(row=1, column=1, sticky=tk.W, pady=2)
        self.color_widgets['pick_target_btn'] = ttk.Button(self.color_filter_frame, text="Pick...", width=6, command=lambda: self.pick_color('target'))
        self.color_widgets['pick_target_btn'].grid(row=1, column=2, padx=(5, 2), pady=2)
        self.color_widgets['pick_screen_btn'] = ttk.Button(self.color_filter_frame, text="Screen", width=7, command=self.pick_color_from_screen)
        self.color_widgets['pick_screen_btn'].grid(row=1, column=3, padx=(2, 0), pady=2)

        # Replacement Color (NEW)
        ttk.Label(self.color_filter_frame, text="Replace With:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        default_replace_hex = ROI.rgb_to_hex(ROI.DEFAULT_REPLACEMENT_COLOR_RGB)
        self.color_widgets['replace_color_var'] = tk.StringVar(value=default_replace_hex)
        self.color_widgets['replace_color_label'] = ttk.Label(self.color_filter_frame, text="       ", background=default_replace_hex, relief=tk.SUNKEN, width=8)
        self.color_widgets['replace_color_label'].grid(row=2, column=1, sticky=tk.W, pady=2)
        self.color_widgets['pick_replace_btn'] = ttk.Button(self.color_filter_frame, text="Pick...", width=6, command=lambda: self.pick_color('replace'))
        self.color_widgets['pick_replace_btn'].grid(row=2, column=2, padx=(5, 2), pady=2)
        # No screen picker for replacement color for now, usually less critical

        # Threshold
        ttk.Label(self.color_filter_frame, text="Threshold:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        self.color_widgets['threshold_var'] = tk.IntVar(value=30)
        self.color_widgets['threshold_scale'] = ttk.Scale(
            self.color_filter_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.color_widgets['threshold_var'], length=150,
            command=lambda v: self.color_widgets['threshold_label_var'].set(f"{int(float(v))}")
        )
        self.color_widgets['threshold_scale'].grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=2)
        self.color_widgets['threshold_label_var'] = tk.StringVar(value="30")
        ttk.Label(self.color_filter_frame, textvariable=self.color_widgets['threshold_label_var'], width=4).grid(row=3, column=3, sticky=tk.W, padx=(5, 0), pady=2)

        # Apply & Preview Buttons
        color_btn_frame = ttk.Frame(self.color_filter_frame)
        color_btn_frame.grid(row=4, column=0, columnspan=4, pady=(10, 0)) # Incremented row
        self.color_widgets['apply_btn'] = ttk.Button(color_btn_frame, text="Apply Filter Settings", command=self.apply_color_filter_settings)
        self.color_widgets['apply_btn'].pack(side=tk.LEFT, padx=5)
        self.color_widgets['preview_orig_btn'] = ttk.Button(color_btn_frame, text="Preview Original", command=self.show_original_preview)
        self.color_widgets['preview_orig_btn'].pack(side=tk.LEFT, padx=5)
        self.color_widgets['preview_filter_btn'] = ttk.Button(color_btn_frame, text="Preview Filtered", command=self.show_filtered_preview)
        self.color_widgets['preview_filter_btn'].pack(side=tk.LEFT, padx=5)

        # --- Bottom part: Save All ROIs ---
        file_btn_frame = ttk.Frame(self.frame)
        file_btn_frame.pack(fill=tk.X, pady=(5, 10))
        self.save_rois_btn = ttk.Button(file_btn_frame, text="Save All ROI Settings for Current Game", command=self.save_rois_for_current_game)
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)

        # Initial state
        self.update_roi_list()
        self.set_color_filter_widgets_state(tk.DISABLED)

    def set_color_filter_widgets_state(self, state):
        """Enable or disable all widgets in the color filter frame."""
        if not hasattr(self, 'color_filter_frame') or not self.color_filter_frame.winfo_exists():
            return
        valid_states = (tk.NORMAL, tk.DISABLED)
        actual_state = state if state in valid_states else tk.DISABLED
        scale_state = tk.NORMAL if actual_state == tk.NORMAL else tk.DISABLED

        try:
            for widget in self.color_filter_frame.winfo_children():
                widget_class = widget.winfo_class()
                if isinstance(widget, (ttk.Frame, tk.Frame)):
                    for sub_widget in widget.winfo_children():
                        sub_widget_class = sub_widget.winfo_class()
                        try:
                            if sub_widget_class in ('TButton', 'TCheckbutton'):
                                sub_widget.configure(state=actual_state)
                        except tk.TclError: pass
                elif widget_class in ('TButton', 'TCheckbutton'):
                    widget.configure(state=actual_state)
                elif widget_class in ('Scale', 'TScale'):
                    widget.configure(state=scale_state)
        except tk.TclError:
            print("TclError setting color filter widget state (widgets might be closing).")
        except Exception as e:
            print(f"Error setting color filter widget state: {e}")


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

        if has_selection:
            roi = self.get_selected_roi_object()
            if roi:
                self.load_color_filter_settings(roi)
                self.set_color_filter_widgets_state(tk.NORMAL)
            else:
                self.set_color_filter_widgets_state(tk.DISABLED)
        else:
            self.set_color_filter_widgets_state(tk.DISABLED)

    def get_selected_roi_object(self):
        """Gets the ROI object corresponding to the listbox selection."""
        selection = self.roi_listbox.curselection()
        if not selection:
            return None
        try:
            listbox_text = self.roi_listbox.get(selection[0])
            roi_name = listbox_text.split("]")[-1].strip()
            return next((r for r in self.app.rois if r.name == roi_name), None)
        except (tk.TclError, IndexError, StopIteration):
            return None

    def load_color_filter_settings(self, roi):
        """Loads the color filter settings from the ROI object into the UI."""
        if not roi or not hasattr(self, 'color_widgets'):
            return
        try:
            self.color_widgets['enabled_var'].set(roi.color_filter_enabled)

            target_hex = ROI.rgb_to_hex(roi.target_color)
            self.color_widgets['target_color_var'].set(target_hex)
            self.color_widgets['target_color_label'].config(background=target_hex)

            replace_hex = ROI.rgb_to_hex(roi.replacement_color)
            self.color_widgets['replace_color_var'].set(replace_hex)
            self.color_widgets['replace_color_label'].config(background=replace_hex)

            self.color_widgets['threshold_var'].set(roi.color_threshold)
            self.color_widgets['threshold_label_var'].set(str(roi.color_threshold))
        except tk.TclError:
            print("TclError loading color filter settings (widget might be destroyed).")
        except Exception as e:
            print(f"Error loading color filter settings for {roi.name}: {e}")

    def apply_color_filter_settings(self):
        """Applies the UI settings to the selected in-memory ROI object."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "No ROI selected to apply settings to.", parent=self.app.master)
            return

        try:
            roi.color_filter_enabled = self.color_widgets['enabled_var'].get()

            target_hex = self.color_widgets['target_color_var'].get()
            roi.target_color = ROI.hex_to_rgb(target_hex)

            replace_hex = self.color_widgets['replace_color_var'].get()
            roi.replacement_color = ROI.hex_to_rgb(replace_hex)

            roi.color_threshold = self.color_widgets['threshold_var'].get()

            self.update_roi_list() # Update listbox display immediately

            self.app.update_status(f"Color filter settings updated for '{roi.name}'. (Save ROIs to persist)")
            print(f"Applied in-memory color settings for {roi.name}: enabled={roi.color_filter_enabled}, target={roi.target_color}, replace={roi.replacement_color}, thresh={roi.color_threshold}")

        except tk.TclError:
            messagebox.showerror("Error", "Could not read settings from UI (widgets might be destroyed).", parent=self.app.master)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply color filter settings: {e}", parent=self.app.master)

    def pick_color(self, color_type):
        """Opens a color chooser dialog. color_type is 'target' or 'replace'."""
        roi = self.get_selected_roi_object()
        if not roi: return

        if color_type == 'target':
            var = self.color_widgets['target_color_var']
            label = self.color_widgets['target_color_label']
            title = "Choose Target Color"
        elif color_type == 'replace':
            var = self.color_widgets['replace_color_var']
            label = self.color_widgets['replace_color_label']
            title = "Choose Replacement Color"
        else:
            return # Invalid type

        initial_color_hex = var.get()
        try:
            color_code = colorchooser.askcolor(title=title,
                                               initialcolor=initial_color_hex,
                                               parent=self.app.master)
            if color_code and color_code[1]:
                new_hex_color = color_code[1]
                var.set(new_hex_color)
                label.config(background=new_hex_color)
                # print(f"{color_type.capitalize()} color picked for {roi.name}: {new_hex_color}")
        except Exception as e:
            messagebox.showerror("Color Picker Error", f"Failed to open color picker: {e}", parent=self.app.master)

    def pick_color_from_screen(self):
        """Starts the screen color picking process (for target color)."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "Select an ROI first.", parent=self.app.master)
            return

        self.app.update_status("Screen Color Picker: Click anywhere on screen (Esc to cancel).")
        # Use the fixed ScreenColorPicker
        picker = ScreenColorPicker(self.app.master)
        picker.grab_color(self._on_screen_color_picked) # Pass callback

    def _on_screen_color_picked(self, color_rgb):
        """Callback function after screen color is picked (for target color)."""
        if color_rgb:
            roi = self.get_selected_roi_object()
            if roi:
                hex_color = ROI.rgb_to_hex(color_rgb)
                self.color_widgets['target_color_var'].set(hex_color)
                self.color_widgets['target_color_label'].config(background=hex_color)
                self.app.update_status(f"Screen color picked: {hex_color}. Apply settings if desired.")
                print(f"Screen color picked for {roi.name} target: {color_rgb} -> {hex_color}")
            else:
                self.app.update_status("Screen color picked, but no ROI selected.")
        else:
            self.app.update_status("Screen color picking cancelled.")

    def show_original_preview(self):
        """Shows a preview of the original selected ROI content."""
        self._show_preview(filtered=False)

    def show_filtered_preview(self):
        """Shows a preview of the selected ROI after color filtering."""
        roi = self.get_selected_roi_object()
        if roi and not self.color_widgets['enabled_var'].get(): # Check UI state for preview
            messagebox.showinfo("Info", "Color filtering is not currently enabled in UI.", parent=self.app.master)
            return
        self._show_preview(filtered=True)

    def _show_preview(self, filtered=False):
        """Helper function to generate and show ROI previews."""
        roi = self.get_selected_roi_object()
        if not roi:
            messagebox.showwarning("Warning", "No ROI selected.", parent=self.app.master)
            return

        source_frame = None
        if self.app.using_snapshot and self.app.snapshot_frame is not None:
            source_frame = self.app.snapshot_frame
        elif self.app.current_frame is not None:
            source_frame = self.app.current_frame
        elif self.app.selected_hwnd:
            self.app.update_status("Capturing frame for preview...")
            source_frame = capture_window(self.app.selected_hwnd) # Use app's capture method
            if source_frame is not None:
                self.app.current_frame = source_frame
                self.app.update_status("Frame captured for preview.")
            else:
                self.app.update_status("Failed to capture frame for preview.")

        if source_frame is None:
            messagebox.showerror("Error", "No frame available to generate preview.", parent=self.app.master)
            return

        roi_img = roi.extract_roi(source_frame)
        if roi_img is None:
            messagebox.showerror("Error", f"Could not extract ROI '{roi.name}' from frame.", parent=self.app.master)
            return

        preview_img = roi_img
        title_suffix = "Original"
        if filtered:
            # Apply the *current UI settings* for preview
            try:
                # Create a temporary ROI instance with current UI settings
                temp_roi = ROI("temp_preview", 0,0,1,1)
                temp_roi.color_filter_enabled = self.color_widgets['enabled_var'].get()
                temp_roi.target_color = ROI.hex_to_rgb(self.color_widgets['target_color_var'].get())
                temp_roi.replacement_color = ROI.hex_to_rgb(self.color_widgets['replace_color_var'].get()) # Use UI replacement color
                temp_roi.color_threshold = self.color_widgets['threshold_var'].get()

                preview_img = temp_roi.apply_color_filter(roi_img.copy())
                if preview_img is None:
                    messagebox.showerror("Error", "Failed to apply color filter for preview.", parent=self.app.master)
                    return

                target_hex = ROI.rgb_to_hex(temp_roi.target_color)
                replace_hex = ROI.rgb_to_hex(temp_roi.replacement_color)
                title_suffix = f"Filtered (Target:{target_hex}, Replace:{replace_hex}, Thresh:{temp_roi.color_threshold})"

            except Exception as e:
                messagebox.showerror("Error", f"Error applying filter for preview: {e}", parent=self.app.master)
                return

        try:
            preview_img_rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
        except cv2.error as e:
            messagebox.showerror("Preview Error", f"Failed to convert image for display: {e}", parent=self.app.master)
            return

        PreviewWindow(self.app.master, f"ROI Preview: {roi.name} - {title_suffix}", preview_img_rgb)


    # --- Other methods (on_roi_selection_toggled, update_roi_list, save_rois, move, delete, configure_overlay) ---
    # These methods remain largely the same as in the previous version, but ensure update_roi_list
    # correctly reflects the state after changes.

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
            if roi.name == SNIP_ROI_NAME: continue

            overlay_config = get_overlay_config_for_roi(roi.name)
            is_overlay_enabled = overlay_config.get('enabled', True) # Assume True if not set
            overlay_prefix = "[O]" if is_overlay_enabled else "[ ]"

            color_prefix = "[C]" if roi.color_filter_enabled else "[ ]"

            self.roi_listbox.insert(tk.END, f"{overlay_prefix}{color_prefix} {roi.name}")

        new_idx_to_select = -1
        if selected_text:
            selected_name = selected_text.split("]")[-1].strip()
            all_names_in_listbox = [item.split("]")[-1].strip() for item in self.roi_listbox.get(0, tk.END)]
            try:
                new_idx_to_select = all_names_in_listbox.index(selected_name)
            except ValueError: pass

        if new_idx_to_select != -1:
            self.roi_listbox.selection_clear(0, tk.END)
            self.roi_listbox.selection_set(new_idx_to_select)
            self.roi_listbox.activate(new_idx_to_select)
            self.roi_listbox.see(new_idx_to_select)

        if hasattr(self.app, 'overlay_tab') and self.app.overlay_tab.frame.winfo_exists():
            self.app.overlay_tab.update_roi_list()

        self.on_roi_selected() # Update button states and color filter UI

    def save_rois_for_current_game(self):
        if not self.app.selected_hwnd:
            messagebox.showwarning("Save ROIs", "No game window selected.", parent=self.app.master)
            return
        rois_to_save = [roi for roi in self.app.rois if roi.name != SNIP_ROI_NAME]

        saved_path = save_rois(rois_to_save, self.app.selected_hwnd)
        if saved_path is not None:
            self.app.config_file = saved_path
            self.app.update_status(f"Saved {len(rois_to_save)} ROIs for current game.")
            self.app.master.title(f"Visual Novel Translator - {os.path.basename(saved_path)}")
        else:
            self.app.update_status("Failed to save ROIs for current game.")

    def move_roi_up(self):
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0: return
        roi = self.get_selected_roi_object()
        if not roi: return

        try:
            idx_in_app_list = self.app.rois.index(roi)
            prev_app_idx = idx_in_app_list - 1
            while prev_app_idx >= 0 and self.app.rois[prev_app_idx].name == SNIP_ROI_NAME:
                prev_app_idx -= 1
            if prev_app_idx < 0: return

            self.app.rois[idx_in_app_list], self.app.rois[prev_app_idx] = self.app.rois[prev_app_idx], self.app.rois[idx_in_app_list]
            self.update_roi_list() # Rebuild and reselect
        except (ValueError, IndexError) as e:
            print(f"Error finding ROI for move up: {e}")

    def move_roi_down(self):
        selection = self.roi_listbox.curselection()
        if not selection: return
        idx_in_listbox = selection[0]
        if idx_in_listbox >= self.roi_listbox.size() - 1: return

        roi = self.get_selected_roi_object()
        if not roi: return

        try:
            idx_in_app_list = self.app.rois.index(roi)
            next_app_idx = idx_in_app_list + 1
            while next_app_idx < len(self.app.rois) and self.app.rois[next_app_idx].name == SNIP_ROI_NAME:
                next_app_idx += 1
            if next_app_idx >= len(self.app.rois): return

            self.app.rois[idx_in_app_list], self.app.rois[next_app_idx] = self.app.rois[next_app_idx], self.app.rois[idx_in_app_list]
            self.update_roi_list() # Rebuild and reselect
        except (ValueError, IndexError) as e:
            print(f"Error finding ROI for move down: {e}")

    def delete_selected_roi(self):
        roi = self.get_selected_roi_object()
        if not roi: return
        if roi.name == SNIP_ROI_NAME: return

        confirm = messagebox.askyesno("Delete ROI", f"Delete ROI '{roi.name}'?", parent=self.app.master)
        if not confirm: return

        self.app.rois.remove(roi)

        all_overlay_settings = get_setting("overlay_settings", {})
        if roi.name in all_overlay_settings:
            del all_overlay_settings[roi.name]
            update_settings({"overlay_settings": all_overlay_settings})

        if hasattr(self.app, 'overlay_manager'):
            self.app.overlay_manager.destroy_overlay(roi.name)

        if roi.name in self.app.text_history: del self.app.text_history[roi.name]
        if roi.name in self.app.stable_texts: del self.app.stable_texts[roi.name]

        def safe_update(widget_name, update_method, data):
            widget = getattr(self.app, widget_name, None)
            if widget and hasattr(widget, 'frame') and widget.frame.winfo_exists():
                try: update_method(data)
                except tk.TclError: pass
                except Exception as e: print(f"Error updating {widget_name} after delete: {e}")

        safe_update('text_tab', self.app.text_tab.update_text, self.app.text_history)
        safe_update('stable_text_tab', self.app.stable_text_tab.update_text, self.app.stable_texts)

        self.update_roi_list()
        self.app.update_status(f"ROI '{roi.name}' deleted. (Save ROIs to persist)")

    def configure_selected_overlay(self):
        roi = self.get_selected_roi_object()
        if not roi: return

        if not hasattr(self.app, 'overlay_tab') or not self.app.overlay_tab.frame.winfo_exists():
            messagebox.showerror("Error", "Overlay tab not available.", parent=self.app.master)
            return

        try:
            overlay_tab_widget = self.app.overlay_tab.frame
            notebook_widget = overlay_tab_widget.master
            if not isinstance(notebook_widget, ttk.Notebook):
                raise tk.TclError("Parent not Notebook")

            notebook_widget.select(overlay_tab_widget)

            if hasattr(self.app.overlay_tab, 'roi_names_for_combo') and roi.name in self.app.overlay_tab.roi_names_for_combo:
                self.app.overlay_tab.selected_roi_var.set(roi.name)
                self.app.overlay_tab.load_roi_config()
            else:
                print(f"ROI '{roi.name}' not found in Overlay Tab combo after switch.")

        except (tk.TclError, AttributeError) as e:
            print(f"Error switching to overlay tab: {e}")
            messagebox.showerror("Error", "Could not switch to Overlay tab.", parent=self.app.master)
        except Exception as e:
            print(f"Unexpected error configuring overlay: {e}")

# --- END OF FILE ui/roi_tab.py ---