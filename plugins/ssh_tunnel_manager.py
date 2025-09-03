"""
SSH Tunnel Manager Plugin
- Scans for running 'autossh' processes.
- Provides an interactive menu to list and terminate active SSH tunnels.
"""
import os
import signal
try:
    import psutil
except ImportError:
    psutil = None

def find_autossh_processes():
    """Finds all running processes that appear to be autossh tunnels."""
    if not psutil:
        return []
    tunnels = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if 'autossh' is in the process name or command line arguments
            cmdline = proc.info.get('cmdline') or []  # Ensure cmdline is always iterable
            # The original code had a potential NoneType error if cmdline was None.
            if 'autossh' in proc.info['name'].lower() or any('autossh' in arg.lower() for arg in cmdline):
                tunnels.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return tunnels

def terminate_tunnel(pid: int) -> str:
    """Terminates a process by its PID."""
    if not psutil:
        return "[ERROR] psutil library not installed."
    try:
        proc = psutil.Process(pid)
        proc.terminate()  # Graceful termination
        # Or use proc.kill() for forceful termination
        return f"[SUCCESS] Terminated tunnel with PID {pid}."
    except psutil.NoSuchProcess:
        return f"[ERROR] No process found with PID {pid}."
    except Exception as e:
        return f"[ERROR] Failed to terminate process {pid}: {e}"

def run():
    """Main plugin entry point with an interactive menu."""
    if not psutil:
        return "[ERROR] The 'psutil' library is not installed. Please run: pip install psutil"
    while True:
        tunnels = find_autossh_processes()
        print("\n--- SSH Tunnel Manager ---")

        if not tunnels:
            print("No active autossh tunnels found.")
            return "Exited: No tunnels to manage."

        for i, proc in enumerate(tunnels):
            cmd = ' '.join(proc.info['cmdline'])
            print(f"{i + 1}. PID: {proc.info['pid']} | Command: {cmd}")

        print("\nEnter the number of the tunnel to terminate, or 'q' to quit.")
        choice = input("Selection: ").strip().lower()

        if choice == 'q':
            return "SSH Tunnel Manager closed."

        try:
            index = int(choice) - 1
            if 0 <= index < len(tunnels):
                pid_to_terminate = tunnels[index].info['pid']
                print(terminate_tunnel(pid_to_terminate))
            else:
                print("[ERROR] Invalid selection. Please try again.")
        except ValueError:
            print("[ERROR] Invalid input. Please enter a number or 'q'.")

if __name__ == "__main__":
    run()