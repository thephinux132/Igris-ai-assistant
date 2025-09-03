#!/usr/bin/env python3
import json, sys
from pathlib import Path
from datetime import datetime

REQUIRED_ID_KEYS = ["name","role","base_context"]

def read_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"Missing file: {p}"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in {p}: {e}"

def main():
    root = Path(__file__).resolve().parent
    identity_p = root / "ai_assistant_config" / "assistant_identity.json"
    intents_p  = root / "ai_assistant_config" / "task_intents.json"
    ok = lambda: "\x1b[32mOK\x1b[0m"
    warn = lambda: "\x1b[33mWARN\x1b[0m"
    bad = lambda: "\x1b[31mFAIL\x1b[0m"

    print("=== Igris Preflight ===")
    print("Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    ident, e1 = read_json(identity_p)
    if e1:
        print("Identity:", bad(), identity_p); print("  -", e1); sys.exit(2)
    missing = [k for k in REQUIRED_ID_KEYS if not ident.get(k)]
    if missing:
        print("Identity:", warn(), identity_p); [print("  - Missing key:", k) for k in missing]
    else:
        print("Identity:", ok(), identity_p)

    intents, e2 = read_json(intents_p)
    if e2:
        print("Intents :", bad(), intents_p); print("  -", e2); sys.exit(2)
    tasks = intents.get("tasks", [])
    print("Intents :", ok() if tasks else warn(), intents_p)
    print("  - Tasks:", len(tasks))
    sys.exit(0)

if __name__ == "__main__":
    main()
