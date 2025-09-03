#!/usr/bin/env python3
"""
list_tasks_by_tag.py

Utility to show Igris tasks grouped by tag.
"""
import json
from pathlib import Path
import argparse

def load_intents(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def list_tags(tasks):
    tags = set()
    for task in tasks:
        tags.update(task.get("tags", []))
    return sorted(tags)

def list_tasks_by_tag(tasks, selected_tag):
    matched = [t for t in tasks if selected_tag in t.get("tags", [])]
    if not matched:
        print(f"No tasks found under tag '{selected_tag}'.")
        return
    print(f"Tasks under '{selected_tag}':")
    for t in matched:
        name = t.get("task")
        phrases = ", ".join(t.get("phrases", []))
        print(f" - {name}")
        {phrases}

def main():
    parser = argparse.ArgumentParser(description="List tasks by tag from Igris OS")
    parser.add_argument("--config", type=Path, default=Path("task_intents.json"))
    parser.add_argument("--list-tags", action="store_true", help="List all tag categories")
    parser.add_argument("--tag", type=str, help="Show tasks for specific tag (e.g. --tag Network)")
    args = parser.parse_args()

    data = load_intents(args.config)
    tasks = data.get("tasks", [])

    if args.list_tags:
        tags = list_tags(tasks)
        print("Available Tags:")
        for tag in tags:
            print(f" - {tag}")
    elif args.tag:
        list_tasks_by_tag(tasks, args.tag)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
