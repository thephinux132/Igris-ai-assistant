#!/usr/bin/env python3
"""
Igris Preflight — validate project layout, intents, and plugins.

Checks:
  - ROOT/PLUGINS/identity exist
  - task_intents*.json loads cleanly
  - every action points to a valid plugin/command
  - optional dry-run to catch encoding/runtime issues

Usage:
  python preflight.py
  python preflight.py --list
  python preflight.py --dry-run
  python preflight.py --dry-run --timeout 3
"""

import argparse, json, os, shlex, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLUGINS = ROOT / "plugins"
IDENTITY = ROOT / "assistant_identity.json"
INTENTS = [
    ROOT / "task_intents_gui_tags.json",
    ROOT / "task_intents.json",
    ROOT / "ai_assistant_config" / "task_intents_gui_tags.json",
    ROOT / "ai_assistant_config" / "task_intents.json",
]

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": str(e)}

def collect_actions():
    actions = []
    for p in INTENTS:
        if not p.exists(): continue
        data = load_json(p)
        for t in data.get("tasks", []):
            if isinstance(t, dict) and t.get("action"):
                actions.append((t.get("task","unknown"), t["action"]))
    return actions

def resolve_cmd(action: str):
    if action.startswith("plugin:"):
        name = action.split("plugin:",1)[1].strip()
        return [sys.executable, str((PLUGINS/f"{name}.py").resolve())]
    if action.lower().startswith("python "):
        parts = shlex.split(action)[1:]
        script = Path(parts[0])
        if not script.is_absolute():
            script = (ROOT/script).resolve()
        return [sys.executable, str(script), *parts[1:]]
    return shlex.split(action)

def dry_run(argv, timeout: int):
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING","utf-8")
    try:
        p = subprocess.run(argv, cwd=str(ROOT),
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout, env=env)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return 999,"",str(e)

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=int, default=2)
    args = ap.parse_args(argv)

    print(f"== Igris Preflight ==")
    print(f"ROOT     : {ROOT}")
    print(f"PLUGINS  : {PLUGINS.exists()}")
    print(f"IDENTITY : {IDENTITY.exists()}")

    actions = collect_actions()
    print(f"Intents  : {len(actions)} actions found")

    if args.list:
        for t,a in actions: print(f"- {t:25s} :: {a}")
        return 0

    missing, fails = 0, 0
    for t,a in actions:
        argv = resolve_cmd(a)
        target = Path(argv[1]) if len(argv)>1 and argv[1].endswith(".py") else None
        if target and not target.exists():
            print(f" ✗ MISSING {t} → {target}")
            missing += 1
        else:
            print(f" ✓ PATH OK {t}")

        if args.dry_run and argv[0].endswith("python"):
            rc,out,err = dry_run(argv,args.timeout)
            if rc!=0:
                print(f"   [Dry-run FAIL rc={rc}] {err or out}")
                fails += 1

    print(f"\nSummary: missing={missing}, dry-run-fails={fails}")
    return 0 if not missing and not fails else 1

if __name__=="__main__":
    sys.exit(main(sys.argv[1:]))
