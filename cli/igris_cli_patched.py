#!/usr/bin/env python3
import argparse
import json
import re
import shlex
import sys
import os
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory

import igris_core
from igris_core import load_policy, respond_with_review, ask_ollama as _ask, run_cmd, match_intent

def get_user_name() -> str:
    profile_override = Path(__file__).resolve().parent.parent / "plugins" / "user_profile.local.json"
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

def parse_json_response(resp: str):
    match = re.search(r'\{.*?\}', resp, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

def handle_request(user_req: str, cfg: dict, policy: dict, debug: bool, auth_func=igris_core.authenticate_admin) -> str:
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
    
        res = run_cmd(shlex.split(action))
        return f"▶ Running: {action}\n{res}"

    local = match_intent(user_req, cfg)
    if local:
        if local.get("requires_admin", False):
            if not auth_func():
                return "[ERROR] Admin authentication failed. Aborting task."
        
        
        action = local["action"]
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



    resp = _ask(user_req) if debug else _ask(user_req)
    data = parse_json_response(resp) or {}
    return f"Matched LLM task → {data.get('action')}"

def main():
    parser = argparse.ArgumentParser(prog="igris_cli", description="Igris OS – your personal Windows control assistant")
    parser.add_argument("--config", "-c", type=Path, default=Path("task_intents.json"), help="Path to task_intents.json")
    parser.add_argument("--identity", "-i", type=Path, default=Path("assistant_identity.json"), help="Path to assistant_identity.json")
    parser.add_argument("--debug", action="store_true", help="Show full LLM prompts & responses for debugging")
    parser.add_argument("--version", action="store_true", help="Print Igris version and exit")
    args = parser.parse_args()

    if args.version:
        identity = load_identity(args.identity)
        print(f"Igris CLI version {identity.get('version','?')}")
        return

    identity = load_identity(args.identity)
    policy = load_policy()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))

    history_path = Path.home() / "OneDrive" / "Documents" / "ai_script_history"
    history_path.mkdir(parents=True, exist_ok=True)
    history_file = history_path / "cli_history.txt"
    completer = WordCompleter([t["task"] for t in cfg.get("tasks", [])])
    session = PromptSession(completer=completer, history=FileHistory(str(history_file)))

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

if __name__ == "__main__":
    main()
