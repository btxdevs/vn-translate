from tkinter import ttk

class BaseTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.frame = ttk.Frame(parent, padding="10")
        self.setup_ui()

    def setup_ui(self):
        raise NotImplementedError("Subclasses must implement setup_ui")

    def on_tab_selected(self):
        pass
