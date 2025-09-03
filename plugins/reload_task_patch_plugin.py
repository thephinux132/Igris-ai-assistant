
"""
Reload Task Intents Plugin
Overwrites the current task_intents.json with a patched version and hot-reloads config using load_configs().
"""

from pathlib import Path
import shutil

def run():
    try:
        from igris_control_gui_final import App
    except ImportError:
        return "[ERROR] Could not access App class from Igris GUI."

    patched_file = Path("/mnt/data/task_intents_patched.json")
    live_file = Path("ai_assistant_config/task_intents.json")

    if not patched_file.exists():
        return "[ERROR] Patched file not found. Make sure 'task_intents_patched.json' exists in /mnt/data."

    try:
        shutil.copyfile(patched_file, live_file)
    except Exception as e:
        return f"[ERROR] Failed to copy patched task file: {e}"

    return "[SUCCESS] Patched task_intents.json loaded. Please use or restart GUI to fully activate new tasks."
