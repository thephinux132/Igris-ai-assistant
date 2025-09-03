"""Igris CLI (patched)"""
import json, argparse, subprocess, sys
from pathlib import Path
from igris_core import load_assistant_identity, ask_ollama, enforce_admin_then, parse_task_response

def run_shell(cmd: str) -> int:
    print(f"[RUN] {cmd}")
    try:
        return subprocess.call(cmd, shell=True)
    except KeyboardInterrupt:
        return 130

def handle_intent(obj: dict) -> int:
    task, action, requires_admin = parse_task_response(obj)
    if not action:
        print("[WARN] No actionable 'action' found in response.")
        return 2

    def _do():
        return run_shell(action)

    try:
        return enforce_admin_then(_do, requires_admin=requires_admin)
    except PermissionError as e:
        print(f"[SECURITY] {e}")
        return 3

def main():
    p = argparse.ArgumentParser(description="Igris CLI (patched)")
    p.add_argument("prompt", nargs="*", help="Freeform request")
    args = p.parse_args()
    user_req = " ".join(args.prompt).strip()
    if not user_req:
        print("Example: igris_cli.py \"Open notepad\"")
        sys.exit(1)
    obj = ask_ollama(prompt=user_req, force_json=True)
    rc = handle_intent(obj)
    sys.exit(int(rc or 0))

if __name__ == "__main__":
    main()
