"""
Phase 4 Launcher (hardened)
- Loads plugins from absolute path (.../ai_stuff/plugins).
- Runs plugins on a worker thread to keep UI responsive.
- Marshals UI updates back to the Tk main thread with .after(0, ...).
"""
from __future__ import annotations
import importlib.util, os, sys, threading, traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

ROOT = Path(__file__).resolve().parent.parent           # .../ai_stuff
PLUGINS_DIR = (ROOT / "plugins").resolve()

def _load_plugin_module(name: str):
    plugin_path = (PLUGINS_DIR / f"{name}.py").resolve()
    if not plugin_path.exists():
        raise FileNotFoundError(f"Plugin not found: {plugin_path}")
    spec = importlib.util.spec_from_file_location(name, plugin_path)
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load spec for {plugin_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod

class Phase4GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Phase 4 Toolkit")
        self.geometry("700x460")
        self._build_ui()

    def _build_ui(self):
        self.result_box = tk.Text(self, height=18, wrap=tk.WORD)
        self.result_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_frame = tk.Frame(self); btn_frame.pack(pady=4)
        buttons = {
            "Ping Sweep": "ping_sweep",
            "Who is Connected": "who_is_connected",
            "Port Scanner": "port_scanner",
            "Phase 4 Diagnostic": "phase4_diagnostic",
            "Network Scanner": "network_scanner",
        }
        for label, plugin in buttons.items():
            tk.Button(btn_frame, text=label, width=20,
                      command=lambda p=plugin: self.run_plugin_async(p)).pack(side=tk.LEFT, padx=5)

        self.status = tk.Label(self, text=f"Ready. Plugins → {PLUGINS_DIR}", anchor="w")
        self.status.pack(fill=tk.X, padx=10, pady=(0,8))

    def run_plugin_async(self, name: str):
        self.status.config(text=f"Running {name}…")
        self.result_box.delete("1.0", tk.END)
        threading.Thread(target=self._worker, args=(name,), daemon=True).start()

    def _worker(self, name: str):
        try:
            os.environ.setdefault("PYTHONIOENCODING", "utf-8")
            mod = _load_plugin_module(name)
            if not hasattr(mod, "run"):
                raise AttributeError(f"{name}.py has no run()")
            out = mod.run()
            if not isinstance(out, str):
                out = str(out)
            if self.winfo_exists():
                self.after(0, self._post_result, out, f"{name} ✓")
        except Exception:
            err = traceback.format_exc(limit=8)
            if self.winfo_exists():
                self.after(0, self._post_result, err, f"{name} ✗")
                self.after(0, lambda: messagebox.showerror("Plugin Error", err))

    def _post_result(self, text: str, status: str):
        self.result_box.insert(tk.END, text)
        self.result_box.see(tk.END)
        self.status.config(text=status)

def run():
    app = Phase4GUI()
    app.mainloop()
    return "Phase 4 GUI opened."
