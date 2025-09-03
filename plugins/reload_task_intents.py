
"""
Plugin to hot-replace task_intents.json with the patched version and reload it into Igris memory.
"""

import shutil
from pathlib import Path

def run():
    source = Path("/mnt/data/task_intents_patched.json")
    destination = Path("ai_assistant_config/task_intents.json")

    if not source.exists():
        return "[ERROR] Patched task_intents_patched.json not found."

    try:
        shutil.copyfile(source, destination)
        return "[SUCCESS] task_intents.json has been hot-reloaded with the patched version."
    except Exception as e:
        return f"[ERROR] Failed to reload task_intents.json: {e}"
