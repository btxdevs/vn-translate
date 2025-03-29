import tkinter as tk
import os
from app import VisualNovelTranslatorApp
from utils.translation import CACHE_DIR

if __name__ == "__main__":
    root = tk.Tk()
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(default=icon_path)
        else:
            print(f"icon.ico not found at {icon_path}, using default Tk icon.")
    except Exception as e:
        print(f"Could not set application icon: {e}")

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create cache directory {CACHE_DIR}: {e}")

    try:
        app = VisualNovelTranslatorApp(root)
        root.mainloop()
    except Exception as e:
        print("UNEXPECTED APPLICATION ERROR")
        import traceback

        traceback.print_exc()
        try:
            from tkinter import messagebox

            messagebox.showerror("Fatal Error", f"An unexpected error occurred:\n\n{e}\n\nSee console for details.")
        except Exception:
            pass