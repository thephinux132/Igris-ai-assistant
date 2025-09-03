"""
A Tkinter widget to display network status using psutil.
"""
import tkinter as tk
import psutil
import socket

class NetworkStatsWidget(tk.Frame):
    """
    A widget to display network interface, IP address, and I/O statistics.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, bg="#222", **kwargs)
        self.config(borderwidth=1, relief=tk.SOLID)

        self.interface_label = tk.Label(self, text="Interface: N/A", fg="white", bg="#222", font=("Segoe UI", 10))
        self.interface_label.pack(pady=(5, 2), padx=10, anchor=tk.W)

        self.ip_label = tk.Label(self, text="IP: N/A", fg="white", bg="#222", font=("Segoe UI", 10))
        self.ip_label.pack(pady=2, padx=10, anchor=tk.W)

        self.sent_label = tk.Label(self, text="Sent: 0.0 MB", fg="white", bg="#222", font=("Segoe UI", 10))
        self.sent_label.pack(pady=2, padx=10, anchor=tk.W)

        self.recv_label = tk.Label(self, text="Recv: 0.0 MB", fg="white", bg="#222", font=("Segoe UI", 10))
        self.recv_label.pack(pady=(2, 5), padx=10, anchor=tk.W)

        self.update_stats()

    def get_primary_interface_info(self):
        """Finds the most likely primary network interface and its IPv4 address."""
        try:
            # A common method is to check which interface is used to connect to an external address.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(1)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]

            addrs = psutil.net_if_addrs()
            for intf, intf_addrs in addrs.items():
                for addr in intf_addrs:
                    if addr.address == local_ip:
                        return intf, local_ip
        except (socket.error, OSError):
            # Fallback if the above method fails (e.g., no internet)
            pass
        return "N/A", "N/A"

    def update_stats(self):
        """Updates the network statistics display."""
        try:
            interface_name, ip_address = self.get_primary_interface_info()
            net_io = psutil.net_io_counters()

            self.interface_label.config(text=f"Interface: {interface_name}")
            self.ip_label.config(text=f"IP: {ip_address}")
            self.sent_label.config(text=f"Sent: {net_io.bytes_sent / (1024*1024):.2f} MB")
            self.recv_label.config(text=f"Recv: {net_io.bytes_recv / (1024*1024):.2f} MB")
        except Exception as e:
            self.ip_label.config(text=f"Error: {type(e).__name__}")

        # Schedule the next update
        self.after(2000, self.update_stats)