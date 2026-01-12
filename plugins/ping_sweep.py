"""
Ping Sweep Plugin
Pings a full /24 subnet to identify responsive hosts.
"""
import platform
import subprocess
import socket
import re

try:
    from core.secure_execution import safe_run_command
    SECURE_MODULES = True
except ImportError:
    SECURE_MODULES = False

def validate_ip(ip: str) -> tuple[bool, str]:
    """Validate IP address format."""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False, "Invalid IP format"
    octets = [int(o) for o in ip.split('.')]
    if any(o > 255 for o in octets):
        return False, "Invalid octet value"
    return True, "OK"

def ping(ip: str) -> bool:
    is_valid, error = validate_ip(ip)
    if not is_valid:
        print(f"[BLOCKED] {error}")
        return False

    cmd_parts = ["ping", "-n", "1", "-w", "300", ip] if platform.system() == "Windows" else ["ping", "-c", "1", "-W", "1", ip]

    if SECURE_MODULES:
        try:
            result = safe_run_command(cmd_parts, timeout=10)
            return result.returncode == 0
        except Exception:
            return False
    else:
        try:
            result = subprocess.run(cmd_parts, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            return result.returncode == 0
        except Exception:
            return False

def run():
    try:
        # Get local IP to determine subnet
        # This is safer than hardcoding but assumes simple network setup
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        base_ip = ".".join(local_ip.split(".")[:3])
    except Exception:
        base_ip = "192.168.1" # Fallback

    live = []
    # Limit range for faster execution in this example/test context if needed
    # but strictly following logic: scan 1-254
    for i in range(1, 255):
        ip = f"{base_ip}.{i}"
        if ping(ip):
            live.append(ip)
            
    return "Ping Sweep Results:\n" + "\n".join(live)