"""
Ping Sweep Plugin
Pings a full /24 subnet to identify responsive hosts.
"""
import platform
import subprocess
import socket

def run():
    base_ip = ".".join(socket.gethostbyname(socket.gethostname()).split(".")[:3])
    live = []
    for i in range(1, 255):
        ip = f"{base_ip}.{i}"
        cmd = ["ping", "-n", "1", "-w", "300", ip] if platform.system() == "Windows" else ["ping", "-c", "1", ip]
        if subprocess.run(cmd, stdout=subprocess.DEVNULL).returncode == 0:
            live.append(ip)
    return "Ping Sweep Results:\n" + "\n".join(live)
