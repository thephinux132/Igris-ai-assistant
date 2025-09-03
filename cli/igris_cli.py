#!/usr/bin/env python3
"""
Igris CLI — path‑safe, model‑aware, offline‑capable.

Usage examples (Windows):
  python -m cli.igris_cli --identity .\\assistant_identity.json "open notepad"
  python .\\cli\\igris_cli.py "open settings"

This docstring uses double backslashes to avoid invalid escape-sequence warnings
on Windows paths when the module is imported.  Without escaping, sequences
like ``\c`` may trigger a ``SyntaxWarning: invalid escape sequence`` at runtime.
"""

from __future__ import annotations
import argparse, json, os, shlex, subprocess, sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from igris_core import run_shell

# ──────────────────────────────────────────────────────────────────────────────
# 0) PATH PATCH so `import igris_core` works no matter where you call this.
#    (handles: repo root, cli/, core/, cwd)
THIS   = Path(__file__).resolve()
CWD    = Path.cwd().resolve()
CANDIDATE_PATHS: Iterable[Path] = (
    THIS.parent,                 # ./cli
    THIS.parents[1],             # repo root
    THIS.parents[1] / "core",    # repo/core
    CWD,                         # current working dir
    CWD / "core",                # ./core from CWD
)
for p in CANDIDATE_PATHS:
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# ──────────────────────────────────────────────────────────────────────────────
# 1) IMPORT CORE (with fallback shims if missing)
try:
    # Preferred: flat file at repo root
    from igris_core import (
        load_policy,
        load_assistant_identity,
        ask_ollama,
        enforce_admin_then,
        parse_task_response,
    )
except Exception:
    try:
        # Alternate layout: core/igris_core.py
        from core.igris_core import (
            load_policy,
            load_assistant_identity,
            ask_ollama,
            enforce_admin_then,
            parse_task_response,
        )
    except Exception:
        # Nuclear option: tiny local shims so offline mode still works.
        import json as _json
        import hmac as _hmac, hashlib as _hashlib, getpass as _getpass, re as _re, time as _time

        def load_policy() -> dict:
            # SHA-256("1234") by default; change this in a proper policy file later.
            return {"admin_pin_hash": "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"}

        def load_assistant_identity(path: os.PathLike | str) -> dict:
            p = Path(path)
            data = {}
            if p.is_file():
                try:
                    data = _json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            # merge defaults
            base = {
                "name": "Igris",
                "role": "Hyper-intelligent system control assistant",
                "base_context": ("Act as Igris, a state-of-the-art AI operating system in development. "
                                 "Your tone is bold, efficient, and precise.")
            }
            base.update(data or {})
            return base

        def _ct(a: str, b: str) -> bool: return _hmac.compare_digest(a, b)

        def _validate_pin(pin: str) -> bool:
            return bool(_re.fullmatch(r"\d{4,8}", pin or ""))

        def _authenticate_admin() -> bool:
            print("[SECURITY] This action requires admin approval.")
            if input("Confirm fingerprint scan (type 'scan'): ").strip().lower() != "scan":
                print("[SECURITY] Fingerprint verification failed."); return False
            pin = _getpass.getpass("Enter admin PIN: ")
            want = load_policy().get("admin_pin_hash", "")
            got  = _hashlib.sha256(pin.encode("utf-8")).hexdigest()
            if not (want and _ct(want, got)) or not _validate_pin(pin):
                print("[SECURITY] PIN invalid."); return False
            if input("Speak passphrase (type 'authorize'): ").strip().lower() != "authorize":
                print("[SECURITY] Voice verification failed."); return False
            print("[SECURITY] Admin authentication successful."); return True

        def enforce_admin_then(fn, *, requires_admin: bool, auth_kwargs: Optional[dict]=None):
            if not requires_admin:
                return fn()
            if _authenticate_admin():
                return fn()
            raise PermissionError("Admin authentication failed")

        def ask_ollama(prompt: str, model: str="llama3",
                       endpoint: str="http://localhost:11434/api/generate",
                       system_prefix: Optional[str]=None, force_json: bool=True) -> dict:
            # Minimal offline-friendly stub: pretend model is down.
            return {"status": "error", "note": "ollama-unavailable"}

        def parse_task_response(obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], bool]:
            if not isinstance(obj, dict): return (None, None, False)
            task = obj.get("task") or obj.get("task_name")
            action = obj.get("action") or obj.get("command") or obj.get("run")
            return task, action, bool(obj.get("requires_admin", False))

# ──────────────────────────────────────────────────────────────────────────────
# 2) UTIL: model + identity + intents
def _first_existing(*paths: Path) -> Optional[Path]:
    for p in paths:
        if p and p.exists():
            return p
    return None

def load_identity_any(where: Path) -> dict:
    # look in CWD, repo/ai_assistant_config, alongside this file
    candidates = [
        where / "assistant_identity.json",
        where / "ai_assistant_config" / "assistant_identity.json",
        THIS.parents[1] / "assistant_identity.json",
        THIS.parents[1] / "ai_assistant_config" / "assistant_identity.json",
    ]
    p = _first_existing(*candidates)
    return load_assistant_identity(p or where / "assistant_identity.json")

def resolve_model(identity: dict, cli_model: Optional[str]) -> str:
    """
    Determine which Ollama model to use based on precedence:

    1. The ``--model`` CLI argument explicitly provided by the user.
    2. A ``default_model`` key in the assistant identity.
    3. An ``IGRIS_DEFAULT_MODEL`` environment variable.
    4. A hard‑coded fallback.

    This function has been updated to use the smaller 1B Llama‑3.2 model
    from HuggingFace as the final fallback.  This ensures that, in the
    absence of any other configuration, we default to a locally available
    model that is compatible with resource‑constrained environments.
    """
    if cli_model:
        # Explicit CLI argument always wins
        return cli_model
    # identity may store either top-level default_model or under model_settings.default_model
    im = identity.get("default_model")
    if not im:
        im = (identity.get("model_settings") or {}).get("default_model")
    env = os.environ.get("IGRIS_DEFAULT_MODEL")
    # Hard-coded fallback uses the 1B parameter GGUF model from Bartowski on HuggingFace
    fallback_model = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"
    return (im or env or fallback_model)

def load_task_intents(where: Path) -> dict:
    # search order prefers GUI‑tags variant
    candidates = [
        where / "task_intents_gui_tags.json",
        where / "task_intents.json",
        where / "ai_assistant_config" / "task_intents_gui_tags.json",
        where / "ai_assistant_config" / "task_intents.json",
        THIS.parents[1] / "ai_assistant_config" / "task_intents_gui_tags.json",
        THIS.parents[1] / "ai_assistant_config" / "task_intents.json",
    ]
    p = _first_existing(*candidates)
    if not p:
        return {"tasks": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": []}

def local_match_action(user_req: str, intents: dict) -> Optional[dict]:
    """Exact phrase wins; otherwise first partial phrase hit."""
    q = (user_req or "").strip().lower()
    best = None
    for t in intents.get("tasks", []):
        task = t.get("task", "")
        action = t.get("action")
        requires_admin = bool(t.get("requires_admin", False))
        for ph in (t.get("phrases") or []):
            p = (ph or "").lower()
            if not p: 
                continue
            if q == p:
                return {
                    "task_name": task, "action": action,
                    "requires_admin": requires_admin, "reasoning": "Exact local match"
                }
            if (p in q) and best is None:
                best = {
                    "task_name": task, "action": action,
                    "requires_admin": requires_admin, "reasoning": "Partial local match"
                }
    return best

# ──────────────────────────────────────────────────────────────────────────────

def handle_intent(obj: dict) -> int:
    task, action, requires_admin = parse_task_response(obj)
    if not action:
        print("[WARN] No actionable 'action' found in response.")
        return 2

    def _do():
        return run_shell(action)

    try:
        policy = load_policy()
        return int(enforce_admin_then(_do, requires_admin=requires_admin, auth_kwargs={"policy": policy}) or 0)
    except PermissionError as e:
        print(f"[SECURITY] {e}")
        return 3

# ──────────────────────────────────────────────────────────────────────────────
# 4) MAIN
def main() -> None:
    p = argparse.ArgumentParser(description="Igris CLI (path‑safe, model‑aware, offline‑capable)")
    p.add_argument("--identity", type=Path, default=Path("assistant_identity.json"))
    p.add_argument("--model", default=None, help="Override model tag (else identity → $IGRIS_DEFAULT_MODEL → llama3)")
    p.add_argument("--system", default=None, help="Optional system prefix to send with the prompt")
    p.add_argument("prompt", nargs="*", help="Freeform request, e.g., 'open notepad'")
    args = p.parse_args()

    identity = load_identity_any(CWD)
    model = resolve_model(identity, args.model)
    user_req = " ".join(args.prompt).strip()

    if not user_req:
        print('Example:\n  python -m cli.igris_cli --identity .\\assistant_identity.json "open notepad"')
        sys.exit(1)

    # 1) Try offline intents first (fast path)
    intents = load_task_intents(CWD)
    lm = local_match_action(user_req, intents)
    if lm:
        print(f"[OFFLINE] {lm['reasoning']}: {lm['task_name']} → {lm['action']}")
        try:
            sys.exit(handle_intent(lm))
        except Exception as e:
            print(f"[ERROR] Failed to execute offline task: {e}")
            sys.exit(1)

    # 2) Call Ollama (if up). If it returns junk or is down, we fall back to offline again.
    print("[INFO] No exact local match. Querying model...")
    system_prefix = args.system or f"{identity.get('role','Assistant')}. {identity.get('base_context','')}"
    obj = ask_ollama(prompt=user_req, model=model, system_prefix=system_prefix, force_json=True)

    # If the call clearly failed, try one more offline pass before giving up.
    if isinstance(obj, dict) and obj.get("status") == "error":
        print("[WARN] Ollama unavailable or returned an error. Attempting offline fallback.")
        lm2 = local_match_action(user_req, intents)
        if lm2:
            print(f"[OFFLINE] {lm2['reasoning']}: {lm2['task_name']} → {lm2['action']}")
            try:
                sys.exit(handle_intent(lm2))
            except Exception as e:
                print(f"[ERROR] Failed to execute offline fallback task: {e}")
                sys.exit(1)
        else:
            print("[ERROR] Ollama unavailable and no suitable offline task found.")
            sys.exit(4)

    # 3) Normal path: parse model’s JSON and execute
    try:
        rc = handle_intent(obj if isinstance(obj, dict) else {})
        sys.exit(rc)
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during task execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
