import tkinter as tk

from app import VisualNovelTranslatorApp

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Visual Novel Translator")

    # Set app icon if available
    try:
        root.iconbitmap("icon.ico")
    except:
        pass

    app = VisualNovelTranslatorApp(root)
    root.mainloop()