
import json
from pathlib import Path

def run():
    path = Path(__file__).parent.parent / "config" / "task_intents_gui_tags.json"

    if not path.exists():
        return "[ERROR] task_intents_gui_tags.json not found."

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    all_tags = set()
    for task in data:
        for tag in task.get("tags", []):
            all_tags.add(tag.strip())

    if not all_tags:
        return "[INFO] No tags found."

    return "[✓] Available Tags:\n" + "\n".join(sorted(all_tags))
