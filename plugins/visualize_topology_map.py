
""" 
visualize_topology_map.py

Scans local network and draws a simple network topology map using matplotlib.
Requires `nmap` and `matplotlib` installed.
"""

import subprocess
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None
import re

def run():
    if not plt:
        return "[ERROR] The 'matplotlib' library is not installed. Please run: pip install matplotlib"
    try:
        result = subprocess.run(["nmap", "-sn", "192.168.1.0/24"], capture_output=True, text=True, timeout=30)
        output = result.stdout
        hosts = re.findall(r"Nmap scan report for (.+)", output)

        if not hosts:
            return "No devices found during scan."

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.set_title("Igris Network Topology Map")
        ax.set_xlim(0, 10)
        ax.set_ylim(0, len(hosts) + 1)

        for i, host in enumerate(hosts):
            ax.plot(5, len(hosts) - i, 'bo')
            ax.text(5.2, len(hosts) - i, host, fontsize=10)

        ax.axis('off')
        plt.tight_layout()
        plt.show()
        return f"{len(hosts)} hosts visualized on map."
    except Exception as e:
        return f"[ERROR] Failed to visualize network: {e}"
