"""My Nmap - Advanced Port Scan for Igris"""

import re
import subprocess
from plugin_execution_logger import run as log_plugin_run

try:
    from core.secure_execution import safe_run_command
    from core.input_validation import InputValidator
    SECURE_MODULES = True
except ImportError:
    SECURE_MODULES = False

def validate_target(target: str) -> tuple[bool, str]:
    """Validate nmap target (IP, hostname, or CIDR)."""
    # IP or CIDR
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$' 
    # Hostname (simple alphanumeric + dots/hyphens)
    hostname_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9.\-]*$'
    
    if re.match(ip_pattern, target) or re.match(hostname_pattern, target):
        return True, "OK"
    return False, "Invalid target format"

def run(ipaddress: str = None):
    log_plugin_run("my_nmap")
    
    if not ipaddress:
        # Fallback to input if not provided (for CLI usage)
        try:
            ipaddress = input("Enter IP address: ").strip()
        except EOFError:
            return "[ERROR] No input provided"

    # 1. Validate Input
    is_valid, error = validate_target(ipaddress)
    if not is_valid:
        return f"[BLOCKED] {error}"

    # 2. Build Command safely as list
    # Fixed flags for this specific plugin task
    command = [
        "nmap",
        "-O", "-sV", "-p2048", "-T4", "-n",
        "-oN", "scan_output.txt", ipaddress
    ]

    try:
        if SECURE_MODULES:
            # Use secure execution wrapper
            result = safe_run_command(command, timeout=300) # Increased timeout for O/sV scans
            if result.returncode == 0:
                return "Scan successful:\n" + result.stdout
            else:
                return "Scan failed:\n" + result.stderr
        else:
            # Legacy fallback - still safer because shell=False (default for list)
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                return "Scan successful:\n" + result.stdout
            else:
                return "Scan failed:\n" + result.stderr

    except Exception as e:
        return f"Error: {e}"