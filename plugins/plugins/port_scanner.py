"""
Port Scanner Plugin
Scans ports 20-1024 on a target IP.
"""
import socket

def run():
    target = input("Enter target IP to scan: ")
    open_ports = []
    for port in range(20, 1025):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((target, port)) == 0:
                open_ports.append(port)
    return f"Open ports on {target}: " + ", ".join(map(str, open_ports))
