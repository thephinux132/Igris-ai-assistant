import tkinter as tk
import psutil

class SystemStatsWidget(tk.Frame):
    """
    A widget to display CPU and RAM usage.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, bg="#222", **kwargs)  # Dark background
        self.cpu_label = tk.Label(self, text="CPU: --%", fg="white", bg="#222", font=("Segoe UI", 10))
        self.cpu_label.pack(pady=(5, 2), padx=10, anchor=tk.W)  # Align left

        self.ram_label = tk.Label(self, text="RAM: --%", fg="white", bg="#222", font=("Segoe UI", 10))
        self.ram_label.pack(pady=(2, 5), padx=10, anchor=tk.W)  # Align left

        self.update_stats()

    def update_stats(self):
        """
        Updates the CPU and RAM usage statistics.
        """
        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_usage = ram.percent

        self.cpu_label.config(text=f"CPU: {cpu_usage:.1f}%")
        self.ram_label.config(text=f"RAM: {ram_usage:.1f}%")

        # Schedule the update after 1 second
        self.after(1000, self.update_stats)

    def destroy(self):
        """
        Override destroy method to prevent resource leaks
        """
        super().destroy()

if __name__ == '__main__':
    # Basic test
    root = tk.Tk()
    root.configure(bg="#333")
    widget = SystemStatsWidget(root)
    widget.pack()

    # Make the main window visible
    root.mainloop()