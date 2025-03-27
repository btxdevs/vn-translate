from tkinter import ttk

class BaseTab:
    """Base class for application tabs."""

    def __init__(self, parent, app):
        """
        Initialize a tab.

        Args:
            parent: The parent widget (usually a ttk.Notebook)
            app: The main application instance
        """
        self.parent = parent
        self.app = app
        # Use frame directly for content
        self.frame = ttk.Frame(parent, padding="10")
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components. Should be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement setup_ui")

    def on_tab_selected(self):
        """Called when this tab is selected. Can be overridden by subclasses."""
        pass