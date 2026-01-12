"""
LAN Topology Scanner Plugin

Scans local subnet using ping and optional nmap (if installed).
Collects IPs, MACs, hostnames and prints device summary.
"""
import shlex
import re
import subprocess
import socket
from shutil import which

try:
    from core.secure_execution import safe_run_command
    from core.input_validation import InputValidator
    SECURE_MODULES = True
except ImportError:
    SECURE_MODULES = False

def get_local_subnet():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
    return subnet

def validate_subnet(subnet: str) -> tuple[bool, str]:
    """Validate subnet/IP range format."""
    # Allow: 192.168.1.0/24, 10.0.0.1-254, single IP
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2}|-\d{1,3})?$'
    if not re.match(ip_pattern, subnet):
        return False, "Invalid subnet format"
    # Validate octets are 0-255
    octets = re.findall(r'\d+', subnet.split('/')[0].split('-')[0])
    if any(int(o) > 255 for o in octets[:4]):
        return False, "Invalid IP octet (must be 0-255)"
    return True, "OK"

SAFE_NMAP_FLAGS = ['-sn', '-sP', '-sL', '-T1', '-T2', '-T3', '--open', '-oN', '-oX', '-oG']

def run(subnet: str = None, flags: list = None):
    """Run nmap scan securely."""
    if not which("nmap"):
        return "[ERROR] 'nmap' is required. Install it and try again."
        
    if subnet is None:
        # Auto-detect subnet logic here
        subnet = get_local_subnet()

    is_valid, error = validate_subnet(subnet)
    if not is_valid:
        return f"[BLOCKED] {error}"

    cmd_parts = ["nmap"]
    if flags:
        for flag in flags:
            if flag not in SAFE_NMAP_FLAGS and not flag.startswith('-o'):
                return f"[BLOCKED] Unsafe nmap flag: {flag}"
            cmd_parts.append(flag)
    else:
        cmd_parts.append("-sn")  # Default: ping scan only
    cmd_parts.append(subnet)

    if SECURE_MODULES:
        try:
            result = safe_run_command(cmd_parts, timeout=120)
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"[ERROR] {e}"
    else:
        import subprocess
        proc = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=120)
        return proc.stdout if proc.returncode == 0 else proc.stderr
