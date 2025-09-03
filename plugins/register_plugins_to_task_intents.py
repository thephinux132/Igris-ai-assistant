"""
Registers any new plugins from /plugins into task_intents_gui_tags.json.
Auto-generates action, phrases, and description from docstring.
"""

import json
import os
from pathlib import Path
import importlib.util

PLUGIN_DIR = Path("plugins")
CONFIG_PATH = Path("ai_assistant_config/task_intents_gui_tags.json")
DEFAULT_TAG = "Tools"

def load_task_intents():
    if not CONFIG_PATH.exists():
        return {"tasks": []}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_task_intents(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def plugin_to_task_entry(filename, description):
    name = filename.stem
    task = name.replace("_", " ")
    return {
        "task": task,
        "phrases": [f"run {task}", f"launch {task}"],
        "action": f"plugin:{name}",
        "requires_admin": False,
        "result": description.strip() if description else f"Auto-generated plugin for {name}",
        "tags": [DEFAULT_TAG]
    }

def run():
    existing = load_task_intents()
    existing_tasks = {t["action"] for t in existing["tasks"]}

    added = 0
    for file in PLUGIN_DIR.glob("*.py"):
        if f"plugin:{file.stem}" in existing_tasks:
            continue
        try:
            spec = importlib.util.spec_from_file_location(file.stem, file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            desc = mod.__doc__ or ""
            task_entry = plugin_to_task_entry(file, desc)
            existing["tasks"].append(task_entry)
            added += 1
        except Exception as e:
            print(f"[ERROR] Failed loading {file.name}: {e}")

    save_task_intents(existing)
    return f"[INFO] Plugin registration complete. {added} new task(s) added."
