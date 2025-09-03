
import argparse
import json
import re
from pathlib import Path

def load_intents(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def list_tags(data):
    tags = set()
    for task in data:
        tags.update(task.get("tags", []))
    print("Available Tags:")
    for tag in sorted(tags):
        print(f" - {tag}")

def list_by_tag(data, tag):
    matched = [t["name"] for t in data if tag in t.get("tags", [])]
    if not matched:
        print(f"No tasks found under tag '{tag}'.")
        return
    print(f"Tasks under '{tag}':")
    for name in matched:
        print(f" - {name}")

def parse_natural_language(input_str):
    match = re.search(r"(list|show) (tools|tasks) (in|under) (.+)", input_str, re.IGNORECASE)
    if match:
        return match.group(4).strip()
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to task_intents file")
    parser.add_argument("--list-tags", action="store_true", help="List available tags")
    parser.add_argument("--tag", type=str, help="Filter by specific tag")
    parser.add_argument("--ask", type=str, help="Natural language input")
    args = parser.parse_args()

    data = load_intents(args.config)

    if args.list_tags:
        list_tags(data)
    elif args.tag:
        list_by_tag(data, args.tag)
    elif args.ask:
        tag = parse_natural_language(args.ask)
        if tag:
            list_by_tag(data, tag)
        else:
            print("Could not understand your request.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
