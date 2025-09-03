"""
A simple file browser application for the Igris Desktop Shell.
"""
import tkinter as tk
import os
from tkinter import ttk
from pathlib import Path

# --- Icon mapping ---
# Using emojis as a simple, dependency-free way to represent icons.
ICON_MAP = {
    # Folders
    "__folder__": "📁",
    # Text & Code
    ".txt": "📄", ".md": "📄", ".log": "📄",
    ".py": "🐍", ".json": "📜", ".html": "🌐", ".css": "🎨", ".js": "📜",
    # Images
    ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️", ".gif": "🖼️", ".bmp": "🖼️", ".svg": "🖼️",
    # Archives
    ".zip": "📦", ".rar": "📦", ".gz": "📦", ".7z": "📦",
    # Executables & Installers
    ".exe": "⚙️", ".msi": "⚙️", ".bat": "⚙️",
    # Documents
    ".pdf": "📕", ".docx": "📘", ".xlsx": "📗", ".pptx": "📙",
    # Audio & Video
    ".mp3": "🎵", ".wav": "🎵", ".ogg": "🎵",
    ".mp4": "🎬", ".mov": "🎬", ".avi": "🎬",
    # Default
    "__default__": "📄",
}

def get_icon_for_path(path: Path) -> str:
    """Returns a text-based icon for a given file or folder path."""
    if path.is_dir():
        return ICON_MAP["__folder__"]
    return ICON_MAP.get(path.suffix.lower(), ICON_MAP["__default__"])

class FileBrowserApp(tk.Frame):
    """A simple file browser application for the Igris Desktop Shell."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.current_path = Path.home()

        self.configure(bg="#2c2c2c")
        self.pack(fill=tk.BOTH, expand=True)

        self.create_widgets()
        self.populate_tree()

    def create_widgets(self):
        # Top frame for path and up button
        top_frame = tk.Frame(self, bg="#3c3c3c")
        top_frame.pack(fill=tk.X, side=tk.TOP)

        self.up_button = tk.Button(top_frame, text="↑ Up", command=self.go_up, relief=tk.FLAT, bg="#555", fg="white")
        self.up_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.path_label = tk.Label(top_frame, text=str(self.current_path), anchor=tk.W, bg="#3c3c3c", fg="white")
        self.path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Treeview for file listing
        self.tree = ttk.Treeview(self, columns=("type", "size"), show="headings tree")
        self.tree.heading("#0", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="Size (KB)")

        self.tree.column("#0", width=300, anchor=tk.W)
        self.tree.column("type", width=80, anchor=tk.W)
        self.tree.column("size", width=100, anchor=tk.E)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5, padx=5)

        self.tree.bind("<Double-1>", self.on_double_click)

    def populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.path_label.config(text=str(self.current_path))

        try:
            # Use os.scandir for better performance by reducing system calls
            entries = []
            with os.scandir(self.current_path) as it:
                for entry in it:
                    entries.append(entry)
            
            # Sort entries: folders first, then by name
            entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))

            for entry in entries:
                try:
                    path_obj = Path(entry.path)
                    icon = get_icon_for_path(path_obj)
                    display_name = f"{icon} {entry.name}"
                    if entry.is_dir():
                        item_type = "Folder"
                        size_kb = ""
                    else:
                        item_type = "File"
                        size_kb = f"{entry.stat().st_size / 1024:.2f}"
                    self.tree.insert("", tk.END, text=display_name, values=(item_type, size_kb), iid=str(path_obj))
                except (OSError, PermissionError):
                    # Skip individual files we can't access
                    continue
        except (OSError, PermissionError) as e:
            # Give the error node a specific iid to avoid issues on double-click
            self.tree.insert("", tk.END, text=f"Error: {e}", values=("Error", ""), iid="<error>")

    def on_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id or item_id == "<error>": return
        
        new_path = Path(item_id)
        if new_path.is_dir():
            self.current_path = new_path.resolve()
            self.populate_tree()

    def go_up(self):
        self.current_path = self.current_path.parent
        self.populate_tree()