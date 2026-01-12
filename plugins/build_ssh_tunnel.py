"""
SSH Tunnel Builder Plugin

Builds an SSH tunnel securely, with parameter validation.
This plugin is now non-interactive.
"""

import shlex
import re
import subprocess

try:
    from core.secure_execution import safe_run_command
    from core.input_validation import InputValidator
    SECURE_MODULES = True
except ImportError:
    SECURE_MODULES = False

def validate_ssh_params(host: str, port: int, local_port: int, remote_port: int) -> tuple[bool, str]:
    """Validate SSH tunnel parameters."""
    # Host validation: alphanumeric, dots, hyphens only
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.\-]*$', host):
        return False, "Invalid hostname format"
    # Port validation: 1-65535
    for p, name in [(port, "SSH port"), (local_port, "local port"), (remote_port, "remote port")]:
        if not isinstance(p, int) or not (1 <= p <= 65535):
            return False, f"Invalid {name}: must be 1-65535"
    return True, "OK"

def run(host: str, port: int = 22, local_port: int = 8080, remote_port: int = 80, user: str = None, tunnel_type: str = "local"):
    """Build SSH tunnel securely."""
    is_valid, error = validate_ssh_params(host, port, int(local_port), int(remote_port))
    if not is_valid:
        return f"[BLOCKED] {error}"

    if tunnel_type == "reverse":
        cmd_parts = ["autossh", "-M", "0", "-f", "-N", "-R", f"{remote_port}:localhost:{local_port}"]
    else:
        cmd_parts = ["autossh", "-M", "0", "-f", "-N", "-L", f"{local_port}:localhost:{remote_port}"]

    if user:
        if not re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_\-]*$', user):
            return "[BLOCKED] Invalid username format"
        cmd_parts.extend([f"{user}@{host}"])

    cmd_parts.extend(["-p", str(port)])

    if SECURE_MODULES:
        try:
            # We are not using safe_run_command here because autossh needs to run in the background
            # and safe_run_command is designed for foreground processes.
            # The command is constructed from validated parts, so it's safer than the original.
            proc = subprocess.Popen(cmd_parts)
            return f"Tunnel established successfully. ({tunnel_type}) PID: {proc.pid}"
        except Exception as e:
            return f"[ERROR] {e}"
    else:
        # Fallback
        proc = subprocess.Popen(cmd_parts)
        return f"Tunnel established successfully. ({tunnel_type}) PID: {proc.pid}"
