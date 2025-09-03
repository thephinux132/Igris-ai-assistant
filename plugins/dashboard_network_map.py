""" 
Network Dashboard GUI
Displays live results from ping_sweep and network_scanner plugins.
"""
import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import os

class NetworkDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Igris Network Dashboard")
        self.geometry("700x400")
        self.resizable(False, False)
        self.build_ui()

    def build_ui(self):
        self.tree = ttk.Treeview(self, columns=("IP", "MAC", "Host"), show="headings")
        for col in ("IP", "MAC", "Host"):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=200)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        refresh_btn = tk.Button(self, text="Scan LAN", command=self.run_scan)
        refresh_btn.pack(pady=(0, 10))

    def run_scan(self):
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self._scan_logic).start()

    def _scan_logic(self):
        try:
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "network_scanner.py"))
            result = subprocess.check_output(["python", script_path], text=True)
            lines = result.strip().split("\n")[1:]  # skip header
            for line in lines:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) == 3:
                    self.tree.insert("", "end", values=parts)
        except Exception as e:
            print("Scan failed:", e)

if __name__ == "__main__":
    app = NetworkDashboard()
    app.mainloop()