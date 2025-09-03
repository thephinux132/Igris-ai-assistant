
"""
Registers /reload_tasks to hot-patch task_intents.json and reload the configuration into Igris.
"""

from pathlib import Path
import shutil
import json

def run():
    try:
        from igris_control_gui_final import App, load_config, CONFIG_DIR
    except ImportError:
        return "[ERROR] Could not import Igris internals."

    # Step 1: Replace the old task_intents.json with the patched one
    patched = Path("/mnt/data/task_intents_patched.json")
    target = CONFIG_DIR / "task_intents.json"

    if not patched.exists():
        return "[ERROR] Missing task_intents_patched.json file."

    try:
        shutil.copyfile(patched, target)
    except Exception as e:
        return f"[ERROR] Failed to copy file: {e}"

    # Step 2: Reload into memory
    try:
        new_data = load_config("task_intents.json")
        if not new_data.get("tasks"):
            return "[ERROR] No tasks found after reload. File may be malformed."

        return "[SUCCESS] Task intents reloaded from patched file. Use commands normally."
    except Exception as e:
        return f"[ERROR] Failed to reload configuration: {e}"
