"""
Generate Live Topology Map Plugin
- Integrates the network_scanner with the visual_topology_gui.
- Scans the local network for live hosts.
- Passes the discovered hosts to the GUI to be drawn on a live map.
"""
import tkinter as tk
import random
import matplotlib.pyplot as plt
# --- Import dependent plugins ---
try:
    # Use the real network scanner
    from plugins.network_scanner import scan_subnet
except ImportError:
    # Fallback for standalone testing or if scanner is missing
    def scan_subnet(*args, **kwargs):
        print("[WARN] network_scanner not found. Using simulated data.")
        return [
            {'ip': '192.168.1.1', 'hostname': 'Gateway'},
            {'ip': '192.168.1.101', 'hostname': 'Aarons-PC'},
            {'ip': '192.168.1.152', 'hostname': 'smart-tv.local'},
        ]

class TopologyMapWidget(tk.Frame):
    def __init__(self, parent, hosts, *args, **kwargs):
        super().__init__(parent, *args, bg="#1e1e1e", **kwargs)
        self.hosts = hosts
        self.canvas = tk.Canvas(self, width=400, height=300, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(expand=True, fill=tk.BOTH)
        self.draw_topology()
    
    def draw_topology(self):
        """Renders the network topology map on the canvas."""
        self.canvas.delete("all")  # Clear previous drawing

        # Simple star topology layout: router in the center, devices around it
        center_x, center_y = self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2
        radius = min(center_x, center_y) * 0.7

        # Assume the first host is the gateway/router
        gateway = self.hosts[0] if self.hosts else {'ip': '?.?.?.?', 'hostname': 'Center'}
        devices = self.hosts[1:] if len(self.hosts) > 1 else self.hosts

        # Draw center node (gateway)
        self.canvas.create_oval(center_x-25, center_y-25, center_x+25, center_y+25, fill="gold", outline="white")
        self.canvas.create_text(center_x, center_y, text=f"{gateway['hostname']}\n({gateway['ip']})", fill="black", font=("Segoe UI", 8, "bold"))

        # Draw device nodes around the center
        angle_step = 360 / len(devices) if devices else 0
        for i, device in enumerate(devices):
            angle = i * angle_step
            rad = (angle * 3.14159) / 180
        x = center_x + radius * random.uniform(0.8, 1.2) * (1 if i % 2 == 0 else -1) * (i/len(devices))
        y = center_y + radius * random.uniform(0.8, 1.2) * (1 if i % 2 != 0 else -1) * (i/len(devices))
        
        canvas.create_line(center_x, center_y, x, y, fill="gray50", dash=(2, 2))
        canvas.create_oval(x-20, y-20, x+20, y+20, fill="skyblue", outline="white")
        canvas.create_text(x, y, text=f"{device['hostname']}\n({device['ip']})", fill="black", font=("Segoe UI", 8))

def run():
    print("[INFO] Scanning network to generate live topology map...")
    hosts = scan_subnet()
    if not hosts:
        return "No hosts found on the network. Cannot generate map."

    return {
        "widget_type": "TopologyMapWidget",
        "hosts": hosts
    }

if __name__ == "__main__":
    run()