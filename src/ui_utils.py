"""
ui_utils.py

Small UI helpers shared across the Streamlit pages (GTFS_Static_Explorer.py and pages/*.py).
"""


def pick_folder() -> str:
    """Open a native OS folder-picker dialog and return the selected path (or '')."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)   # bring dialog to front
        path = filedialog.askdirectory(title="Select folder")
        root.destroy()
        return path or ""
    except Exception:
        return ""
