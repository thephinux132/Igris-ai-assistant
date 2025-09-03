import os
import shutil
from pathlib import Path

ROOT = Path.cwd()  # Run from inside ai_stuff
print(f"[INFO] Working in: {ROOT}")

folders = {
    "cli": ["igris_cli.py", "igris_cli_patched.py", "igris_cli_merged_with_tag_patch.py"],
    "gui": [f for f in os.listdir() if f.startswith("igris_control_gui") and f.endswith(".py")],
    "core": ["igris_core.py", "memory_manager.py", "system_status_ai.py"],
    "config": [
        "assistant_identity.json", "task_intents.json", "task_intents_gui_tags.json",
        "task_intents_phase4_patched.json", "review_templates.json", "user_phrases.json"
    ],
    "plugins": []  # already a folder
}

# Create new folders
for name in folders:
    new_dir = ROOT / name
    new_dir.mkdir(exist_ok=True)
    (new_dir / "__init__.py").touch()

# Move files
for folder, files in folders.items():
    for file in files:
        src = ROOT / file
        dest = ROOT / folder / file
        if src.exists():
            print(f"[MOVE] {file} → {folder}/")
            shutil.move(str(src), str(dest))

# Delete duplicates if they exist
backup_dir = ROOT / "backup_duplicates"
backup_dir.mkdir(exist_ok=True)
for dup in ["assistant_identity.json", "task_intents.json"]:
    for path in ROOT.rglob(dup):
        if "config" not in str(path):
            print(f"[BACKUP+REMOVE] {path}")
            shutil.move(str(path), str(backup_dir / path.name))

print("\n✅ Igris project reorganized successfully.")
