"""
Application Manager (CLI)
- Provides a command-line interface to manage containerized applications.
- Uses the central AppLauncher module from the 'gui' directory.
"""
import sys
from pathlib import Path
import argparse

# Ensure the 'gui' directory is in the Python path to find app_launcher
try:
    from core.igris_core import ROOT_DIR
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

GUI_DIR = ROOT_DIR / "gui"
if str(GUI_DIR) not in sys.path:
    sys.path.insert(0, str(GUI_DIR))

try:
    from app_launcher import AppLauncher
except ImportError:
    AppLauncher = None

def get_app_launcher():
    """Initializes and returns an AppLauncher instance, handling errors."""
    if not AppLauncher:
        print("[ERROR] Could not import AppLauncher. Check python path and file existence.")
        return None

    app_launcher_instance = AppLauncher(None)

    if not app_launcher_instance.client:
        print("[ERROR] AppLauncher is not available. Is Docker running and the 'docker' library installed?")
        return None
    return app_launcher_instance

def list_apps(launcher):
    """Lists running containerized applications."""
    containers = launcher.list_running_containers()
    if not containers:
        return "No Docker containers are currently running."

    report = ["--- Running Applications ---"]
    for c in containers:
        image_tag = c.image.tags[0] if c.image.tags else 'N/A'
        report.append(f"ID: {c.short_id:<12} Name: {c.name:<25} Image: {image_tag}")
    return "\n".join(report)

def stop_app(launcher, name):
    """Stops a running container by name."""
    try:
        container = launcher.client.containers.get(name)
        container.stop()
        return f"Successfully stopped container '{name}'."
    except Exception as e:
        return f"[ERROR] Could not stop container '{name}': {e}"

def remove_app(launcher, name):
    """Removes a stopped container by name."""
    try:
        container = launcher.client.containers.get(name)
        if container.status == "running":
            return f"[ERROR] Cannot remove running container '{name}'. Please stop it first."
        container.remove()
        return f"Successfully removed container '{name}'."
    except Exception as e:
        return f"[ERROR] Could not remove container '{name}': {e}"

def run():
    """Provides a CLI to list, stop, or remove containerized applications."""
    parser = argparse.ArgumentParser(description="Manage containerized applications.")
    parser.add_argument("action", choices=['list', 'stop', 'remove'], help="The action to perform.")
    parser.add_argument("name", nargs='?', help="The name of the container for 'stop' or 'remove' actions.")
    args = parser.parse_args()

    launcher = get_app_launcher()
    if not launcher:
        return

    if args.action == 'list':
        return list_apps(launcher)
    elif args.action in ['stop', 'remove']:
        if not args.name:
            return f"[ERROR] The '{args.action}' action requires a container name."
        if args.action == 'stop':
            return stop_app(launcher, args.name)
        elif args.action == 'remove':
            return remove_app(launcher, args.name)