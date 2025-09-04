#!/usr/bin/env python3
"""
igris_cli.py

A command-line interface to interact with Igris from your terminal, with history & tab-completion.
"""
import argparse
import json
import re
import shlex
import sys
import os
from pathlib import Path

# Resolve core path safely for all environments
try:
    base_dir = Path(__file__).resolve().parent.parent
except NameError:
    base_dir = Path.cwd().parent

igris_core_path = base_dir / "igris_core.py"
if not igris_core_path.exists():
    print("[ERROR] Cannot locate igris_core module. Please ensure 'igris_core.py' is in the project directory.")
    sys.exit(1)

sys.path.insert(0, str(base_dir))
import igris_core
from igris_core import load_policy, respond_with_review, ask_ollama as _ask, run_cmd, match_intent, authenticate_admin

def get_user_name() -> str:
    profile_override = base_dir / "plugins" / "user_profile.local.json"
    if profile_override.exists():
        try:
            with profile_override.open(encoding="utf-8") as f:
                return json.load(f).get("name", "User")
        except Exception:
            pass
    return os.getenv("IGRIS_USER_NAME", "User")

USER_NAME = get_user_name()

DEFAULT_IDENTITY = {
    "intro_message": f"Welcome back, {USER_NAME}. I'm Igris – your personal Windows control assistant. Ready to assist.",
    "fallback_behavior": {"on_no_match": "I'm not sure how to do that yet, but I'm learning."},
    "base_context": "You are Igris, an AI trained to match user requests to known Windows tasks.",
    "version": "unknown"
}

def load_identity(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[WARN] identity file not found at {path}, using defaults.")
        return DEFAULT_IDENTITY
    except json.JSONDecodeError as e:
        sys.exit(f"[ERROR] Failed parsing identity JSON: {e}")
    for key, val in DEFAULT_IDENTITY.items():
        data.setdefault(key, val)
    return data

def parse_json_response(resp: str) -> dict | None:
    """
    Extract and parse a JSON object from an AI response string.
    Cleans markdown, trims whitespace, and verifies required keys.
    """
    try:
        resp = resp.strip()

        # Strip common markdown wrappers
        if resp.startswith("```json"):
            resp = resp.replace("```json", "").strip()
        elif resp.startswith("```"):
            resp = resp.replace("```", "").strip()
        if resp.endswith("```"):
            resp = resp[:-3].strip()

        # Extract JSON object using regex (non-greedy match)
        json_match = re.search(r'\{.*?\}', resp, re.DOTALL)
        if not json_match:
            return None

        parsed = json.loads(json_match.group(0))

        # Confirm it contains the expected fields
        if not all(k in parsed for k in ("task_name", "action", "requires_admin")):
            return None

        return parsed
    except Exception as e:
        print(f"[ERROR] Failed to parse AI response: {e}")
        return None

def build_prompt_with_tasks(user_req: str, cfg: dict) -> str:
    task_block = ""
    for task in cfg.get("tasks", []):
        task_block += f'''- task: {task.get("task")}
  action: {task.get("action")}
  requires_admin: {str(task.get("requires_admin", False)).lower()}

'''

    system = f"""You are Igris, an AI trained to match user requests to known Windows tasks.
Match the user request to one of the tasks below and return ONLY a JSON object like this:

{{ "task_name": "...", "action": "...", "requires_admin": true }}

Here are the available tasks:
{task_block}
Now match this user request: {user_req}
Only return the JSON. No explanation, no markdown, no intro text."""
    
    return system


def handle_request(user_req: str, cfg: dict, policy: dict, debug: bool, auth_func=authenticate_admin) -> str:
    review = respond_with_review(user_req)
    if review:
        return review

    if user_req.lower().startswith("run "):
        action = user_req[4:].strip()
        intent = match_intent(user_req, cfg)
        if intent and intent.get("requires_admin", False):
            if not auth_func():
                return "[ERROR] Admin authentication failed. Aborting task."
        if action.startswith("plugin:"):
            plugin_name = action.split(":", 1)[1]
            plugin_file = Path("plugins") / f"{plugin_name}.py"
            if plugin_file.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "run"):
                    result = mod.run()
                    return f"[Plugin: {plugin_name}] {result}"
                else:
                    return f"[ERROR] Plugin '{plugin_name}' has no run() function."
            else:
                return f"[ERROR] Plugin '{plugin_name}' not found."
        else:
            res = run_cmd(shlex.split(action))
            return f"▶ Running: {action}\n{res}"

    local = match_intent(user_req, cfg)
    if local:
        if local.get("requires_admin", False):
            if not auth_func():
                return "[ERROR] Admin authentication failed. Aborting task."
        return f"Matched local task → {local['action']}"

    prompt = build_prompt_with_tasks(user_req, cfg)
    resp = _ask(prompt)
    if debug:
        print("\n[DEBUG] Full Prompt Sent to Ollama:\n", prompt)
        print("\n[DEBUG] Raw Ollama Response:\n", resp)
    data = parse_json_response(resp) or {}
    return f"Matched LLM task → {data.get('action')}"

def main():
    parser = argparse.ArgumentParser(prog="igris_cli", description="Igris OS – your personal Windows control assistant")
    parser.add_argument("--config", "-c", type=Path, required=True, help="Path to task_intents.json")
    parser.add_argument("--identity", "-i", type=Path, default=Path.home() / ".igris_identity.json", help="Path to your assistant_identity.json")
    parser.add_argument("--debug", action="store_true", help="Show full LLM prompts & responses for debugging")
    parser.add_argument("--version", action="store_true", help="Print Igris version and exit")
    parser.add_argument("--list-tags", action="store_true", help="List all tag categories")
    parser.add_argument("--tag", type=str, help="Show tasks for specific tag")
    parser.add_argument("--ask", type=str, help="Natural language query to infer tag")
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))

    if args.list_tags:
        tags = {tag for task in cfg["tasks"] for tag in task.get("tags", [])}
        print("Available Tags:")
        for tag in sorted(tags):
            print(f" - {tag}")
        return

    if args.tag:
        matched = [t for t in cfg["tasks"] if args.tag in t.get("tags", [])]
        print(f"Tasks under '{args.tag}':")
        for t in matched:
            print(f" - {t['task']}")
        return

    if args.ask:
        match = re.search(r"(list|show) (tools|tasks) (in|under) (.+)", args.ask, re.IGNORECASE)
        if match:
            tag = match.group(4).strip()
            matched = [t for t in cfg["tasks"] if tag in t.get("tags", [])]
            print(f"Tasks under '{tag}':")
            for t in matched:
                print(f" - {t['task']}")
        else:
            print("Could not understand your request.")
        return

    identity = load_identity(args.identity)
    policy = load_policy()

    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory

        completer = WordCompleter([t["task"] for t in cfg.get("tasks", [])])
        history_path = Path.home() / "OneDrive" / "Documents" / "ai_script_history" / "cli_history.txt"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        session = PromptSession(completer=completer, history=FileHistory(str(history_path)))

        print(identity["intro_message"])
        print("Type 'exit' or 'quit' to leave.\n")

        while True:
            try:
                raw = session.prompt("Igris> ")
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break

            user_req = raw.strip()
            if not user_req:
                continue
            if user_req.lower() in ("exit", "quit"):
                print("Goodbye.")
                break

            output = handle_request(user_req, cfg, policy, args.debug)
            print(output + "\n")

    except ModuleNotFoundError:
        print(identity["intro_message"])
        print("[WARN] prompt_toolkit not found. Falling back to basic input mode.\n")
        while True:
            try:
                raw = input("Igris> ")
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break

            user_req = raw.strip()
            if not user_req:
                continue
            if user_req.lower() in ("exit", "quit"):
                print("Goodbye.")
                break

            output = handle_request(user_req, cfg, policy, args.debug)
            print(output + "\n")

if __name__ == "__main__":
    main()



# === Tag Patch Logic Injected ===

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
