
"""
Patch the Igris System Control GUI to ensure the Tools menu is visible and working.
Adds a "Run Plugin..." option to launch any plugin inside the /plugins directory.
"""

import tkinter as tk
from tkinter import messagebox, ttk
import importlib.util
from pathlib import Path

def run():
    try:
        from igris_control_gui_final import App
    except ImportError:
        return "[ERROR] Could not import App from igris_control_gui_final."

    def show_plugin_menu_patch(self):
        plugins = self.load_plugins()
        if not plugins:
            messagebox.showinfo("Plugins", "No plugins found in the plugins directory.")
            return

        top = tk.Toplevel(self)
        top.title("Run Plugin")
        tree = ttk.Treeview(top, columns=("Description",), show="headings")
        tree.heading("#1", text="Description")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        for plugin in plugins:
            tree.insert("", tk.END, iid=plugin['name'], text=plugin['name'], values=(plugin['description'],))

        def run_plugin_wrapper():
            selected_item = tree.focus()
            if selected_item:
                plugin = next((p for p in plugins if p['name'] == selected_item), None)
                if plugin:
                    import threading
                    threading.Thread(target=self.run_plugin, args=(plugin['module'],), daemon=True).start()
            top.destroy()

        btn = tk.Button(top, text="Run Selected", command=run_plugin_wrapper)
        btn.pack(pady=10)

    # Patch the App class
    setattr(App, "show_plugin_menu", show_plugin_menu_patch)

    return "[SUCCESS] Tools menu functionality has been patched. Restart the app to see the menu restored."
