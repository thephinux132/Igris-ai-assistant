"""
Phase 4 Diagnostic (thread-safe)
"""
from __future__ import annotations
import importlib.util, os, sys, threading, traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

ROOT = Path(__file__).resolve().parent.parent   # ai_stuff/
PLUGINS_DIR = ROOT / "plugins"

def _load_plugin_module(name: str):
    plugin_path = PLUGINS_DIR / f"{name}.py"
    if not plugin_path.exists():
        raise FileNotFoundError(f"Plugin not found: {plugin_path}")
    spec = importlib.util.spec_from_file_location(name, plugin_path)
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load spec for {plugin_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod

class Phase4Diag(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Phase 4 Diagnostic")
        self.geometry("720x460")

        self.out = tk.Text(self, height=18, wrap=tk.WORD)
        self.out.pack(fill="both", expand=True, padx=10, pady=10)

        btns = tk.Frame(self); btns.pack(pady=4)
        tk.Button(btns, text="Run Network Scanner", width=22,
                  command=self.run_scan_clicked).pack(side=tk.LEFT, padx=6)

        self.status = tk.Label(self, text="Ready.", anchor="w")
        self.status.pack(fill="x", padx=10, pady=(0,8))

    def run_scan_clicked(self):
        self.status.config(text="Running…")
        self.out.delete("1.0", "end")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            # Ensure child prints won’t explode on Windows cp1252 consoles
            os.environ.setdefault("PYTHONIOENCODING", "utf-8")
            result = self._do_heavy_work()   # long work; NO Tk calls here
            if self.winfo_exists():
                self.after(0, self._post_result, result)
        except Exception:
            err = traceback.format_exc(limit=8)
            if self.winfo_exists():
                self.after(0, lambda: self._post_result(err))
                self.after(0, lambda: messagebox.showerror("Error", err))
                self.after(0, lambda: self.status.config(text="Failed"))

    def _post_result(self, text: str):
        self.out.insert("end", text if isinstance(text, str) else str(text))
        self.out.see("end")
        self.status.config(text="Done")

    def _do_heavy_work(self) -> str:
        # Example: call the existing network_scanner plugin
        mod = _load_plugin_module("network_scanner")
        return mod.run()  # must return a string

def run():
    app = Phase4Diag()
    app.mainloop()
    return "Phase 4 diagnostic closed."
