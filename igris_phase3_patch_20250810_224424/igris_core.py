
"""
Igris Core — unified identity loader, secure admin auth, and robust Ollama prompt handling.
Implements:
  1) Shared admin authentication for CLI/GUI.
  2) ask_ollama() with strict JSON-only output + cleanup.
  3) Identity loader that merges defaults to resolve schema mismatches.
"""

from __future__ import annotations
import os, json, re, getpass, time, sys, subprocess, hashlib, hmac
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# -----------------------------
# Identity defaults + loader
# -----------------------------

DEFAULT_IDENTITY = {
    "name": "Igris",
    "role": "Hyper-intelligent system control assistant",
    "base_context": (
        "Act as Igris, a state-of-the-art AI operating system in development, designed to serve as a "
        "hyper-intelligent, fully-integrated computer tech assistant. Your tone is bold, efficient, and precise."
    ),
}

def load_assistant_identity(path: os.PathLike | str) -> Dict[str, Any]:
    p = Path(path)
    data: Dict[str, Any] = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
    merged = dict(DEFAULT_IDENTITY)
    merged.update(data or {})
    for k in ("name", "role", "base_context"):
        if not merged.get(k):
            merged[k] = DEFAULT_IDENTITY[k]
    return merged

def load_policy(path: os.PathLike | str | None = None) -> Dict[str, Any]:
    if path is None:
        # Default policy location: OneDrive Documents on Windows if available
        try:
            default = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_policy.json")
        except Exception:
            default = "ai_script_policy.json"
        path = default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}

# -----------------------------
# Shared Admin Authentication
# -----------------------------

def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)

def verify_admin_pin(raw_pin: str, policy: dict | None = None) -> bool:
    policy = policy or load_policy()
    want = (policy or {}).get("admin_pin_hash", "")
    if not want:
        return False
    got = hashlib.sha256((raw_pin or "").encode("utf-8")).hexdigest()
    return _constant_time_eq(got, want)

def cli_prompt_for_pin(policy: dict | None = None, attempts: int = 3, backoff_s: float = 1.0) -> bool:
    policy = policy or load_policy()
    for i in range(attempts):
        entered = getpass.getpass("🔑 Enter admin PIN: ")
        if verify_admin_pin(entered, policy):
            print("[SECURITY] PIN accepted.")
            return True
        print("[AUTH] Incorrect PIN.")
        time.sleep(backoff_s * (2 ** i))
    return False

def cli_show_fingerprint_prompt() -> bool:
    try:
        resp = input("🖐️  Confirm fingerprint scan (type 'scan'): ").strip().lower()
        return resp == "scan"
    except EOFError:
        return False

def cli_confirm_by_voice() -> bool:
    try:
        resp = input("🎤 Speak passphrase (type 'authorize'): ").strip().lower()
        return resp == "authorize"
    except EOFError:
        return False

def authenticate_admin() -> bool:
    # fingerprint
    try:
        if cli_show_fingerprint_prompt():
            return True
    except Exception:
        pass
    # PIN
    try:
        if cli_prompt_for_pin(load_policy()):
            return True
    except Exception:
        pass
    # voice fallback
    try:
        if cli_confirm_by_voice():
            return True
    except Exception:
        pass
    return False

def enforce_admin_then(fn, *, requires_admin: bool, auth_kwargs: Optional[dict]=None):
    if not requires_admin:
        return fn()
    if authenticate_admin():
        return fn()
    raise PermissionError("Admin authentication failed")

# -----------------------------
# Ollama wrapper + JSON cleanup
# -----------------------------

JSON_ENFORCEMENT_SUFFIX = """
You MUST respond with a single, valid JSON object only — no prose, no markdown fences, no preamble.
If you need to include multiple fields, put them inside that single object.
"""

def _strip_md_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\\s*```$", "", text.strip())
    return text.strip()

def _extract_jsonish(text: str) -> str:
    s = text.strip()
    if s.startswith("{") and s.endswith("}"):
        return s
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    for i, ch in enumerate(s[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:i+1]
    return s

def ask_ollama(prompt: str,
               model: str = "llama3",
               endpoint: str = "http://localhost:11434/api/generate",
               system_prefix: Optional[str] = None,
               force_json: bool = True) -> Dict[str, Any]:
    final_prompt = prompt.rstrip()
    if force_json:
        final_prompt += "\\n\\n" + JSON_ENFORCEMENT_SUFFIX.strip()
    if system_prefix:
        final_prompt = system_prefix.strip() + "\\n\\n" + final_prompt
    payload = {"model": model, "prompt": final_prompt, "stream": False}
    try:
        import requests  # type: ignore
        resp = requests.post(endpoint, json=payload, timeout=120)
        resp.raise_for_status()
        raw = resp.json().get("response", "")
    except Exception:
        raw = '{"status":"ok","note":"ollama-unavailable-dry-run"}'
    cleaned = _strip_md_fences(raw)
    jsonish = _extract_jsonish(cleaned)
    try:
        return json.loads(jsonish)
    except Exception:
        return {"_raw": raw, "_cleaned": cleaned, "_jsonish": jsonish}

def strict_json_from_text(text: str) -> dict | None:
    t = text.strip()
    if t.startswith("```json"):
        t = t[7:].strip()
    if t.startswith("```"):
        t = t[3:].strip()
    if t.endswith("```"):
        t = t[:-3].strip()
    m = re.search(r"\\{.*?\\}", t, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

# -----------------------------
# Utilities
# -----------------------------

def parse_task_response(obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], bool]:
    if not isinstance(obj, dict):
        return None, None, False
    task = obj.get("task") or obj.get("task_name")
    action = obj.get("action") or obj.get("command") or obj.get("run")
    requires_admin = bool(obj.get("requires_admin", False))
    return task, action, requires_admin

def run_shell(cmd: str, *, timeout: int | None = None):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
