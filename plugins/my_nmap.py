"""My Nmap - Advanced Port Scan for Igris"""

import subprocess
from plugin_execution_logger import run as log_plugin_run

def run():
    log_plugin_run("my_nmap")
    try:
        ipaddress = input("Enter IP address: ")
        command = [
            "nmap",
            "-O", "-sV", "-p2048", "-T4", "-n",
            "-oN", "scan_output.txt", ipaddress
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return "Scan successful:\\n" + result.stdout
        else:
            return "Scan failed:\\n" + result.stderr
    except Exception as e:
        return f"Error: {e}"
