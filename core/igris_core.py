import json
import subprocess
import re
import hashlib
import getpass
import base64
from pathlib import Path
import psutil

def match_intent(user_input: str, intents: dict) -> dict | None:
    """
    Normalize both the user's text and each intent key by stripping out
    all non-alphanumeric characters, then match via substring lookup.
    """
    # Strip everything except letters+digits, lowercase
    clean_in = re.sub(r"\W+", "", user_input).lower()

    for intent in intents.get("tasks", []):
        key = intent.get("task") or intent.get("task_name")
        if not key:
            continue

        clean_key = re.sub(r"\W+", "", key).lower()
        if clean_key in clean_in:
            return intent

    return None


# Default Ollama model if not overridden
default_ollama_model = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"


def load_policy(policy_path: Path = None) -> dict:
    """
    Load the policy JSON from the given path or a default location.
    """
    if policy_path is None:
        policy_path = Path(__file__).parent / 'ai_script_policy.json'
    try:
        return json.loads(policy_path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run_cmd(cmd_list: list) -> str:
    """
    Execute a command list in a shell, returning stdout or a formatted error.
    """
    command_str = " ".join(cmd_list)
    try:
        proc = subprocess.run(
            command_str,
            capture_output=True,
            text=True,
            shell=True,
            check=False,
            encoding='utf-8',
            errors='replace'
        )
    except FileNotFoundError:
        return f"[ERROR] Command not found: '{cmd_list[0]}'"
    except subprocess.CalledProcessError as e:
        if e.returncode == 1 and "Access is denied" in (e.stderr or e.stdout):
            return f"[ERROR] Permission denied: '{command_str}'. Ensure you have necessary privileges."
        return f"[ERROR] Command '{command_str}' failed (code {e.returncode}): {e.stderr or e.stdout}"
    except OSError as e:
        return f"[ERROR] OS error executing '{command_str}': {e}"
    except Exception as e:
        return f"[ERROR] Unexpected error executing '{command_str}': {e}"

    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if proc.returncode != 0:
        return f"[ERROR] Command '{command_str}' returned {proc.returncode}: {err or out}"
    return out if out else "Command executed."


def run_shell(cmd: str, *, timeout: int | None = None):
    """
    Execute a shell command string. Returns (returncode, stdout, stderr).
    Compatible with plugins expecting a tuple.
    """
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',
            check=False,
        )
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except Exception as e:
        return 1, "", f"[ERROR] run_shell exception: {e}"


def ask_ollama(prompt: str, model: str = None) -> str:
    """
    Call Ollama with the given prompt and return its raw response.
    """
    if model is None:
        model = default_ollama_model
    intent_prompt = prompt
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=intent_prompt,
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8'
        )
        if result.returncode != 0:
            return f"[FATAL] Ollama error: {result.stderr.strip()}"
        return result.stdout.strip()
    except Exception as e:
        return f"[FATAL] Exception: {e}"


def respond_with_review(user_input: str) -> str:
    """
    Handle basic system status queries locally, without LLM.
    """
    ui = user_input.lower()
    if "system" in ui and ("status" in ui or "stats" in ui):
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        return (
            f"CPU Load: {cpu}%\n"
            f"Memory Usage: {mem.percent}% ({mem.used // (1024 ** 2)} MB / {mem.total // (1024 ** 2)} MB)\n"
            f"Disk Usage (C:\\): {disk.percent}% ({disk.free // (1024 ** 3)} GB free / {disk.total // (1024 ** 3)} GB total)\n"
            f"Uptime: {psutil.boot_time()}"
        )
    if "cpu" in ui and "status" in ui:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        return f"CPU: {cpu}%, Memory: {mem.percent}%"
    if "uptime" in ui:
        return f"Uptime: {psutil.boot_time()}"
    if "disk" in ui:
        disk = psutil.disk_usage("C:\\")
        return f"Disk Usage: {disk.percent}%"
    return None


def cli_show_fingerprint_prompt() -> bool:
    """
    Console prompt to simulate fingerprint scan.
    """
    try:
        input("🔒 Please scan your fingerprint and press Enter to simulate: ")
        return True
    except KeyboardInterrupt:
        return False


def cli_prompt_for_pin(pin_hash: str) -> bool:
    """
    Prompt user for PIN, hash it, and compare to stored hash.
    """
    entered = getpass.getpass("🔑 Enter admin PIN: ")
    hashed = hashlib.sha256(entered.encode('utf-8')).hexdigest()
    return hashed == pin_hash


def cli_confirm_by_voice(expected_phrase: str = "yes allow this") -> bool:
    """
    Console-based fallback for voice confirmation via typed phrase.
    """
    resp = input(f"[Voice Auth] Please type '{expected_phrase}' to confirm: ")
    return expected_phrase in resp.lower()



def authenticate_admin() -> bool:
    """
    Try fingerprint first, then PIN, then voice confirmation.
    Returns True if any succeed.
    """
    try:
        if cli_show_fingerprint_prompt():
            return True
    except Exception:
        pass

    try:
        if cli_prompt_for_pin():
            return True
    except Exception:
        pass

    try:
        if cli_confirm_by_voice():
            return True
    except Exception:
        pass

    return False


# --- Compatibility helpers expected by GUI/CLI variants ---
def verify_admin_pin(raw_pin: str, policy: dict | None = None) -> bool:
    """Constant-time check of a user-entered PIN against policy hash."""
    try:
        p = policy or load_policy()
        want = (p or {}).get("admin_pin_hash", "")
        if not want:
            return False
        got = hashlib.sha256((raw_pin or "").encode('utf-8')).hexdigest()
        import hmac
        return hmac.compare_digest(got, want)
    except Exception:
        return False


def strict_json_from_text(text: str) -> dict | None:
    """Extract the first JSON object from arbitrary text or fenced code."""
    t = (text or "").strip()
    if t.startswith("```json"):
        t = t[7:].strip()
    if t.startswith("```"):
        t = t[3:].strip()
    if t.endswith("```"):
        t = t[:-3].strip()
    m = re.search(r"\{.*?\}", t, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def ask_ollama_with_image(prompt: str, image_path: str, model: str | None = None, endpoint: str | None = None) -> dict:
    """
    Send an image + prompt to an Ollama HTTP endpoint if available.
    Returns a dict with at least a 'response' key. Falls back to stub.
    """
    try:
        import requests  # type: ignore
    except Exception:
        return {"response": "[ERROR] requests not available for image requests."}

    ep = endpoint or "http://localhost:11434/api/generate"
    mdl = model or default_ollama_model
    try:
        img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode('ascii')
    except Exception as e:
        return {"response": f"[ERROR] could not read image: {e}"}

    payload = {
        "model": mdl,
        "prompt": prompt,
        "stream": False,
        "images": [img_b64],
    }
    try:
        resp = requests.post(ep, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json() if resp.headers.get('content-type','').startswith('application/json') else {}
        out = data.get("response") if isinstance(data, dict) else None
        return {"response": out or ""}
    except Exception as e:
        return {"response": f"[ERROR] ollama image call failed: {e}"}
