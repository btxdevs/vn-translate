import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import BaseTab
from utils.config import save_rois, load_rois

class ROITab(BaseTab):
    """Tab for ROI management."""

    def setup_ui(self):
        roi_frame = ttk.LabelFrame(self.frame, text="Regions of Interest", padding="10")
        roi_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # New ROI creation
        ttk.Label(roi_frame, text="Create a new ROI:").pack(anchor=tk.W)
        ttk.Label(roi_frame, text="Name:").pack(anchor=tk.W, pady=(5, 0))

        self.roi_name_entry = ttk.Entry(roi_frame)
        self.roi_name_entry.pack(fill=tk.X, pady=(0, 5))
        self.roi_name_entry.insert(0, "dialogue")

        ttk.Label(roi_frame, text="Click and drag on the image to define a region").pack(anchor=tk.W)

        # Buttons
        roi_btn_frame = ttk.Frame(roi_frame)
        roi_btn_frame.pack(fill=tk.X, pady=(5, 0))

        self.create_roi_btn = ttk.Button(roi_btn_frame, text="Enable ROI Selection",
                                         command=self.app.toggle_roi_selection)
        self.create_roi_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.save_rois_btn = ttk.Button(roi_btn_frame, text="Save ROIs",
                                        command=self.save_rois)
        self.save_rois_btn.pack(side=tk.LEFT, padx=5)

        self.load_rois_btn = ttk.Button(roi_btn_frame, text="Load ROIs",
                                        command=self.load_rois)
        self.load_rois_btn.pack(side=tk.LEFT, padx=5)

        # Reordering buttons
        reorder_frame = ttk.Frame(roi_frame)
        reorder_frame.pack(fill=tk.X, pady=5)

        self.move_up_btn = ttk.Button(reorder_frame, text="Move Up",
                                      command=self.move_roi_up)
        self.move_up_btn.pack(side=tk.LEFT, padx=5)

        self.move_down_btn = ttk.Button(reorder_frame, text="Move Down",
                                        command=self.move_roi_down)
        self.move_down_btn.pack(side=tk.LEFT, padx=5)

        # ROI list
        ttk.Label(roi_frame, text="Current ROIs:").pack(anchor=tk.W, pady=(10, 5))

        roi_list_frame = ttk.Frame(roi_frame)
        roi_list_frame.pack(fill=tk.BOTH, expand=True)

        roi_scrollbar = ttk.Scrollbar(roi_list_frame)
        roi_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.roi_listbox = tk.Listbox(roi_list_frame, height=5, selectmode=tk.SINGLE,
                                      yscrollcommand=roi_scrollbar.set)
        self.roi_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        roi_scrollbar.config(command=self.roi_listbox.yview)

        self.delete_roi_btn = ttk.Button(roi_frame, text="Delete Selected ROI",
                                         command=self.delete_selected_roi)
        self.delete_roi_btn.pack(anchor=tk.W, pady=(5, 0))

    def on_roi_selection_toggled(self, active):
        """Update UI when ROI selection is toggled."""
        if active:
            self.create_roi_btn.config(text="Cancel ROI Selection")
        else:
            self.create_roi_btn.config(text="Enable ROI Selection")

    def update_roi_list(self):
        """Update the ROI listbox with current ROIs."""
        self.roi_listbox.delete(0, tk.END)
        for roi in self.app.rois:
            self.roi_listbox.insert(tk.END, f"{roi.name} ({roi.x1},{roi.y1}) to ({roi.x2},{roi.y2})")

    def save_rois(self):
        """Save ROIs to a configuration file."""
        config_file = save_rois(self.app.rois, self.app.config_file)
        if config_file:
            self.app.config_file = config_file
            self.app.capture_tab.update_status(f"Saved {len(self.app.rois)} ROIs to {config_file}")

    def load_rois(self):
        """Load ROIs from a configuration file."""
        rois, config_file = load_rois()
        if rois:
            self.app.rois = rois
            if config_file:
                self.app.config_file = config_file
            self.update_roi_list()
            self.app.capture_tab.update_status(f"Loaded {len(rois)} ROIs from {config_file}")

    def move_roi_up(self):
        """Move the selected ROI up in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        idx = selection[0]
        self.app.rois[idx - 1], self.app.rois[idx] = self.app.rois[idx], self.app.rois[idx - 1]
        self.update_roi_list()
        self.roi_listbox.select_set(idx - 1)

    def move_roi_down(self):
        """Move the selected ROI down in the list."""
        selection = self.roi_listbox.curselection()
        if not selection or selection[0] == len(self.app.rois) - 1:
            return
        idx = selection[0]
        self.app.rois[idx], self.app.rois[idx + 1] = self.app.rois[idx + 1], self.app.rois[idx]
        self.update_roi_list()
        self.roi_listbox.select_set(idx + 1)

    def delete_selected_roi(self):
        """Delete the selected ROI."""
        selection = self.roi_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a ROI to delete.")
            return
        index = selection[0]
        roi_name = self.app.rois[index].name
        del self.app.rois[index]
        self.update_roi_list()
        self.app.capture_tab.update_status(f"ROI '{roi_name}' deleted.")