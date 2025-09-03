"""
SSH Tunnel Builder Plugin

Prompts user for remote IP, SSH username, port, and direction (local/reverse).
Generates an SSH tunnel command and optionally runs it in background using autossh.
"""

def run():
    import subprocess

    print("=== SSH Tunnel Builder ===")
    remote = input("Remote Host (e.g. 192.168.1.10): ").strip()
    user = input("SSH Username: ").strip()
    port = input("Remote SSH Port [22]: ").strip() or "22"
    tunnel_type = input("Tunnel Type (local/reverse) [local]: ").strip().lower() or "local"
    local_port = input("Local Port to Forward (e.g. 8080): ").strip()
    remote_port = input("Remote Target Port (e.g. 80): ").strip()

    if tunnel_type == "reverse":
        cmd = f"autossh -M 0 -f -N -R {remote_port}:localhost:{local_port} {user}@{remote} -p {port}"
    else:
        cmd = f"autossh -M 0 -f -N -L {local_port}:localhost:{remote_port} {user}@{remote} -p {port}"

    print(f"[INFO] Running: {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True)
        return f"Tunnel established successfully. ({tunnel_type})"
    except subprocess.CalledProcessError as e:
        return f"[ERROR] Failed to create tunnel: {e}"