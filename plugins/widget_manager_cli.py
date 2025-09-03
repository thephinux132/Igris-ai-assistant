"""
Plugin to manage Igris Desktop widgets via the command line.
- Sends commands to the running Igris Shell to list or remove widgets.
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
import threading

# --- Paths ---
# This needs to be robust enough to find the config from the plugins dir
try:
    from core.igris_core import ROOT_DIR
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = ROOT_DIR / "ai_assistant_config"
DESKTOP_COMMAND_QUEUE_FILE = CONFIG_DIR / "desktop_command_queue.json"
DESKTOP_COMMAND_LOCK = threading.Lock()

def send_desktop_command(action, params=None):
    """A helper to send a command to the Igris Shell via the file queue."""
    if params is None:
        params = {}

    command = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "params": params
    }

    with DESKTOP_COMMAND_LOCK:
        try:
            queue = json.loads(DESKTOP_COMMAND_QUEUE_FILE.read_text(encoding="utf-8")) if DESKTOP_COMMAND_QUEUE_FILE.exists() else []
            if not isinstance(queue, list):
                queue = []
        except (json.JSONDecodeError, IOError):
            queue = []

        queue.append(command)

        try:
            DESKTOP_COMMAND_QUEUE_FILE.write_text(json.dumps(queue, indent=2), encoding="utf-8")
            return f"[Desktop] Sent command: '{action}' with params {params}"
        except IOError as e:
            return f"[ERROR] Failed to write to desktop command queue: {e}"

def run():
    """An interactive CLI to manage desktop widgets."""
    parser = argparse.ArgumentParser(description="Manage Igris Desktop widgets.", add_help=False)
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("list", help="List all active widgets.")
    remove_parser = subparsers.add_parser("remove", help="Remove a widget by name.")
    remove_parser.add_argument("name", type=str, help="The name of the widget to remove (e.g., 'system_stats').")

    print("\n--- Desktop Widget Manager ---")
    print("Enter 'list' to see active widgets, 'remove <name>' to delete one, or 'quit' to exit.")

    while True:
        try:
            user_input = input("widget-manager> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ['quit', 'exit']:
                return "Widget manager session ended."

            args = user_input.split()
            if args[0] == "list":
                return send_desktop_command("desktop:list_widgets")
            elif args[0] == "remove" and len(args) > 1:
                return send_desktop_command("desktop:remove_widget", {"name": args[1]})
            else:
                print("Invalid command. Use 'list' or 'remove <name>'.")
        except Exception as e:
            return f"[ERROR] An unexpected error occurred: {e}"