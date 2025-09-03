
"""
Phase 1 Finalizer Plugin for Igris OS
- Restores Tools → Run Plugin menu
- Reloads patched task_intents.json into ai_assistant_config
- Displays a confirmation dialog
"""

import tkinter as tk
from tkinter import messagebox, ttk
import importlib.util
import shutil
from pathlib import Path

def run():
    try:
        from igris_control_gui_final import App
    except ImportError:
        return "[ERROR] Could not import App from Igris GUI."

    # === Patch Tools Menu ===
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

    setattr(App, "show_plugin_menu", show_plugin_menu_patch)

    # === Reload task_intents.json from patched version ===
    patched = Path("/mnt/data/task_intents_patched.json")
    target = Path("ai_assistant_config/task_intents.json")

    if not patched.exists():
        return "[ERROR] Missing task_intents_patched.json file."

    try:
        shutil.copyfile(patched, target)
    except Exception as e:
        return f"[ERROR] Failed to copy patched file: {e}"

    # === Final GUI Confirmation ===
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Phase 1 Complete", "✔️ Task system and Tools menu are now fully restored.")
    root.destroy()

    return "[SUCCESS] Phase 1 patch complete. GUI patched and tasks reloaded."
