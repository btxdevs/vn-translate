# --- START OF FILE main.py ---

import tkinter as tk
import os # Import os
from app import VisualNovelTranslatorApp
from pathlib import Path # For user home directory
from utils.translation import CACHE_DIR # Import CACHE_DIR

if __name__ == "__main__":
    root = tk.Tk()
    # Title is set within the App class now based on config

    # --- Set app icon if available ---
    try:
        # Get the directory where main.py is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "icon.ico") # Assume icon is in the same folder
        if os.path.exists(icon_path):
            # Use platform-specific method if needed, iconbitmap works on Windows
            root.iconbitmap(default=icon_path)
            print(f"Icon loaded from {icon_path}")
        else:
            print(f"icon.ico not found at {icon_path}, using default Tk icon.")
    except Exception as e:
        print(f"Could not set application icon: {e}")

    # --- Ensure required directories exist ---
    # Cache directory (now defined relative to app in translation.py)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Cache directory ensured at: {CACHE_DIR}")
    except Exception as e:
        print(f"Warning: Could not create cache directory {CACHE_DIR}: {e}")

    # --- Run the App ---
    try:
        app = VisualNovelTranslatorApp(root)
        root.mainloop()
    except Exception as e:
        # Catch major errors during app initialization or main loop
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!      UNEXPECTED APPLICATION ERROR     !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        import traceback
        traceback.print_exc()
        # Show error in a simple Tkinter message box if possible
        try:
            from tkinter import messagebox
            messagebox.showerror("Fatal Error", f"An unexpected error occurred:\n\n{e}\n\nSee console for details.")
        except:
            pass # Ignore if even messagebox fails

# --- END OF FILE main.py ---