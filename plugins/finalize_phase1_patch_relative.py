
"""
Phase 1 Finalizer Plugin for Igris OS (Relative Path Version)
Works from ./mnt/data/task_intents_patched.json instead of /mnt/data
"""

import tkinter as tk
from tkinter import messagebox, ttk
import shutil
from pathlib import Path

def run():
    try:
        from igris_control_gui_final import App
    except ImportError:
        return "[ERROR] Could not import App from GUI."

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

    # === Patch task_intents.json ===
    patched = Path("mnt/data/task_intents_patched.json")
    target = Path("ai_assistant_config/task_intents.json")

    if not patched.exists():
        return "[ERROR] Missing patched task_intents_patched.json file at ./mnt/data"

    try:
        shutil.copyfile(patched, target)
    except Exception as e:
        return f"[ERROR] Failed to patch task_intents.json: {e}"

    # === Confirmation ===
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Phase 1 Complete", "✔️ System Control Core is patched and Tools menu is restored.")
    root.destroy()

    return "[SUCCESS] Phase 1 patch finalized and confirmed."
