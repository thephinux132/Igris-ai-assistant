"""Plugin Execution Logger with Profile Integration"""
import json
from datetime import datetime
from pathlib import Path

# Log to the central memory file to be used by the suggestion engine
MEMORY_FILE = Path.home() / "OneDrive" / "Documents" / "ai_memory.json"

def run(plugin_name="unknown_plugin"):
    now = datetime.now().isoformat()
    log_entry = {"plugin_name": plugin_name, "timestamp": now}

    try:
        if MEMORY_FILE.exists():
            with MEMORY_FILE.open("r", encoding="utf-8") as f:
                memory = json.load(f)
        else:
            memory = {}
    except (json.JSONDecodeError, FileNotFoundError):
        memory = {} # Initialize if file is empty, not found, or corrupt

    # Ensure 'plugin_history' key exists and is a list
    if "plugin_history" not in memory or not isinstance(memory.get("plugin_history"), list):
        memory["plugin_history"] = []

    memory["plugin_history"].append(log_entry)

    with MEMORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)

    return f"Logged execution of {plugin_name} to ai_memory.json"
