"""
Who Is Connected Plugin
Lists active connections (IP and port) using psutil.
"""
import psutil

def run():
    connections = psutil.net_connections(kind="inet")
    lines = []
    for conn in connections:
        if conn.raddr:
            lines.append(f"{conn.laddr.ip}:{conn.laddr.port} → {conn.raddr.ip}:{conn.raddr.port} ({conn.status})")
    return "Active Connections:\n" + "\n".join(lines[:25])  # limit output
