"""
tag-management plugin
Lists all unique tags from the current task intents file.
"""

import json
from pathlib import Path

def run():
    root = Path(__file__).resolve().parent.parent
    intents_files = [
        root / "task_intents_gui_tags.json",
        root / "task_intents.json",
        root / "ai_assistant_config" / "task_intents_gui_tags.json",
        root / "ai_assistant_config" / "task_intents.json",
    ]
    tags = set()
    for f in intents_files:
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for t in data.get("tasks", []):
                for tag in t.get("tags", []):
                    tags.add(tag)
        except Exception:
            pass
    return sorted(tags) if tags else ["No tags found"]
