import os, sys, json, threading, re, shlex, shutil, subprocess, time, io, contextlib
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, simpledialog, ttk
from concurrent.futures import ThreadPoolExecutor
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

import importlib.util

from authentication import show_fingerprint_prompt, prompt_for_pin, confirm_by_voice
# --- Igris paths (MUST run before importing igris_core) ---
ROOT = Path(__file__).resolve().parents[1]  # project root
CONFIG_DIR = ROOT / "ai_assistant_config"
PLUGINS_DIR = ROOT / "plugins"


def _prepend_once(p):
    p = str(Path(p).resolve())
    if p not in sys.path:
        sys.path.insert(0, p)

_prepend_once(ROOT)           # allow flat modules at repo root (igris_core.py, memory_manager.py)
_prepend_once(ROOT / "core")  # allow imports like core.memory_manager
_prepend_once(PLUGINS_DIR)    # plugins folder for dynamic loading

PLUGINS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT))          # prefer flat modules
sys.path.insert(0, str((ROOT / "core").resolve()))  # fallback to core/ if present
sys.path.append(str(PLUGINS_DIR.resolve()))


# --- Memory manager (flat first, core/ fallback, then stubs) ---
try:
    from memory_manager import (
        add_memory, add_conversation_memory,
        retrieve_conversation_memory, get_all_conversation_history
    )
    from memory_manager_gui import open_memory_manager
except ModuleNotFoundError:
    try:
        from core.memory_manager import (
            add_memory, add_conversation_memory,
            retrieve_conversation_memory, get_all_conversation_history
        )
        from core.memory_manager_gui import open_memory_manager
    except ModuleNotFoundError:
        # Safe stubs so the GUI doesn't crash if memory modules are missing
        # We need to define the functions so they can be called without error.
        # The functions will do nothing if the module is not found.
        # This is a good practice for optional dependencies.
        # The functions are defined with the same signature as the real ones.
        # This is important for the GUI to work correctly.
        # The functions will be called when the user clicks on the corresponding menu items.
        # The user will see a message box if the module is not found.
        def add_memory(*a, **k): pass
        def add_conversation_memory(*a, **k): pass
        def retrieve_conversation_memory(*a, **k): return []
        def get_all_conversation_history(*a, **k): return []
        def open_memory_manager(*a, **k):
            import tkinter as tk
            from tkinter import messagebox
            try:
                # only show if we have a Tk context
                messagebox.showinfo("Memory", "Memory manager is not available.")
            except Exception:
                print("[WARN] Memory manager not available.")


try:
    from igris_core import strict_json_from_text, ask_ollama as core_ask, verify_admin_pin, ask_ollama_with_image
except ModuleNotFoundError:
    from core.igris_core import strict_json_from_text, ask_ollama as core_ask, verify_admin_pin, ask_ollama_with_image
 
# Optional routed handler
try:
    from gui.llm_handler import RoutedLLMHandler  # type: ignore
except Exception:
    RoutedLLMHandler = None  # type: ignore

# --- Optional deps (don’t crash if missing) ---
try:
    import psutil
except Exception: psutil = None
try:
    import speech_recognition as sr
except Exception: sr = None
try:
    import pyttsx3
except Exception: pyttsx3 = None

# --- Phase 2.5 helpers (guarded import) ---
try:
    from igris_phase2_5_patch_integrated import (
        learn_new_task_gui,
        find_best_local_match,
        show_task_intent_manager,
    )
except Exception:
    # Not fatal; features will be disabled
    learn_new_task_gui = find_best_local_match = show_task_intent_manager = None

# --- Phase 5 Anticipatory Engine ---
try:
    from suggestion_engine import get_suggestion
except (ImportError, ModuleNotFoundError):
    def get_suggestion(*a, **k):
        print("[WARN] suggestion_engine.py not found. Suggestions disabled.")
        return None

# --- Phase 4/5 Integration: Plugin Execution Logger ---
try:
    import plugin_execution_logger as _pel
except (ImportError, ModuleNotFoundError):
    _pel = None
    print("[WARN] plugin_execution_logger.py not found. Execution logging disabled.")


# Debug: verify core import path at startup
try:
    import igris_core as _ic
    print("[core] using:", _ic.__file__)
except Exception:
    try:
        import core.igris_core as _ic
        print("[core] using:", _ic.__file__)
    except Exception as e:
        print("[core] FAILED:", repr(e))


# === Configuration ===
OLLAMA_MODEL = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"
MEMORY_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_memory.json")
LOG_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_log.txt")
HISTORY_DIR = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_history")
POLICY_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_policy.json")
# --- Desktop IPC (as per desktop_ipc_design.md) ---
DESKTOP_COMMAND_QUEUE_FILE = CONFIG_DIR / "desktop_command_queue.json"
ASSISTANT_IDENTITY_FILE = CONFIG_DIR / "assistant_identity.json"

# === Additional Configuration ===
# File where user-defined aliases will be stored.  Aliases allow the user to
# map short commands to full phrases (e.g. '/alias reboot="restart computer"').
ALIASES_FILE = CONFIG_DIR / "aliases.json"

def load_aliases():
    """Load user-defined command aliases from a JSON file."""
    try:
        data = json.loads(ALIASES_FILE.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def save_aliases(aliases: dict) -> None:
    """Persist user-defined command aliases to disk."""
    try:
        ALIASES_FILE.parent.mkdir(parents=True, exist_ok=True)
        ALIASES_FILE.write_text(json.dumps(aliases, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"[WARN] Failed to save aliases: {e}")

os.makedirs(HISTORY_DIR, exist_ok=True)
PLUGINS_DIR.mkdir(exist_ok=True)

THREAD_POOL = ThreadPoolExecutor(max_workers=6)
DESKTOP_COMMAND_LOCK = threading.Lock()

# === Load Configurations ===
def load_config(path):
    try:
        p = (CONFIG_DIR / path)
        if not p.exists() and path == "task_intents.json":
            # prefer the tags variant if present
            alt = CONFIG_DIR / "task_intents_gui_tags.json"
            if alt.exists():
                p = alt
        return json.loads(p.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_identity_and_initialize():
    if not ASSISTANT_IDENTITY_FILE.exists():
        return {}
    try:
        return json.loads(ASSISTANT_IDENTITY_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def load_policy():
    try:
        return json.loads(Path(POLICY_FILE).read_text(encoding='utf-8'))
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

policy = load_policy()
identity = load_identity_and_initialize()

# Check for required fields in identity
if not all(key in identity for key in ["name", "role", "base_context"]):
    default_identity = {"name": "Assistant", "role": "AI Assistant", "base_context": "You are a helpful assistant."}
    identity = {**default_identity, **identity}  # Merge with defaults, keeping existing values
    print("Warning: `assistant_identity.json` is missing required fields. Using default values.")


base_context_template = identity.get("base_context", "")
task_intents = load_config("task_intents.json")
review_templates = load_config("review_templates.json")

# Format the task list to be injected into the AI's context
task_list_str = "\n--- START TASK LIST ---\n"
for task in task_intents.get("tasks", []):
    task_list_str += f"- Task: {task.get('task')}, Action: `{task.get('action')}`, Phrases: {task.get('phrases')}\n"
task_list_str += "--- END TASK LIST ---\n"

# Combine the identity template with the list of tasks
base_context = base_context_template + task_list_str

# === Text-to-Speech (safe) ===
engine = None
if 'pyttsx3' in globals() and pyttsx3:
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
    except Exception:
        engine = None

def log_to_file(content):
    if policy.get("logging_enabled", True):
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}]\n{content}\n\n")

def save_to_history(script):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(HISTORY_DIR, f"script_{timestamp}.py")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(script)
    return path

def run_cmd(cmd_list):
    """Executes a command list in a shell."""
    command_str = " ".join(cmd_list)
    try:
        # Using shell=True is necessary for many Windows-specific commands like 'start'
        # However, this introduces a command injection vulnerability if cmd_list contains untrusted data.
        # Consider sanitizing user inputs.
        # Note: The below fix is not complete, you should sanitize the input before passing it to subprocess.
        #       instead of just disabling shell=True.
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
        else:
            return f"[ERROR] Command '{command_str}' failed with return code {e.returncode}: {e.stderr or e.stdout}"
    except OSError as e:
        return f"[ERROR] OS error executing '{command_str}': {e}"
    except Exception as e:
        return f"[ERROR] Unexpected error executing '{command_str}': {e}"
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if proc.returncode != 0:
        return f"[ERROR] Command '{command_str}' returned {proc.returncode}: {err or out}"
    return out if out else "Command executed."

def get_system_status_report():
    """Collects and formats a system status report."""
    if psutil is None:
        return "psutil not available: system metrics unavailable."
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    return (
        f"CPU Load: {cpu}%\n"
        f"Memory Usage: {mem.percent}% ({mem.used // (1024 ** 2)} MB / {mem.total // (1024 ** 2)} MB)\n"
        f"Disk Usage (C:\\): {disk.percent}% ({disk.free // (1024 ** 3)} GB free / {disk.total // (1024 ** 3)} GB total)"
        f"\nUptime: {get_system_uptime()}"

    )

def respond_with_review(user_input):
    """Handles local system status queries without calling the LLM."""
    user_input_lower = user_input.lower()
    # If psutil is unavailable, only uptime queries are supported
    if psutil is None:
        if "uptime" in user_input_lower:
            return get_system_uptime()
        return "psutil not available: system metrics unavailable."

    # General system status query
    if "system" in user_input_lower and ("status" in user_input_lower or "stats" in user_input_lower):
        return get_system_status_report()
    # Specific CPU/Memory query
    if "cpu" in user_input_lower and "status" in user_input_lower:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        return review_templates.get("reviews", {}).get("cpu_memory", "").format(
            cpu_load=cpu,
            mem_percent=mem.percent,
            mem_used=round(mem.used / (1024 ** 3), 1),
            mem_total=round(mem.total / (1024 ** 3), 1)
        )
    # Uptime query
    if "uptime" in user_input_lower:
        return get_system_uptime()
    if "disk space" in user_input_lower or "disk usage" in user_input_lower:
        disk = psutil.disk_usage("C:\\")
        return f"Disk Usage (C:\\): {disk.percent}% ({disk.free // (1024 ** 3)} GB free / {disk.total // (1024 ** 3)} GB total)"
    return None

def show_policy_editor(root):
    top = tk.Toplevel(root)
    top.title("Edit Policy File")
    editor = scrolledtext.ScrolledText(top, wrap=tk.WORD)
    editor.pack(fill=tk.BOTH, expand=True)
    try:
        editor.insert(tk.END, Path(POLICY_FILE).read_text())
    except:
        editor.insert(tk.END, "{}")
    def save():
        try:
            json.loads(editor.get("1.0", tk.END))
            with open(POLICY_FILE, 'w', encoding='utf-8') as f:
                f.write(editor.get("1.0", tk.END))
            top.destroy()
        except:
            messagebox.showerror("Invalid JSON", "The policy file is not valid JSON.")
    tk.Button(top, text="Save", command=save).pack()

def show_fingerprint_prompt(root):
    confirmed = []
    def accept():
        confirmed.append(True)
        top.destroy()
    top = tk.Toplevel(root)
    top.title("Admin Authentication Required")
    tk.Label(top, text="🔒 Please scan your fingerprint to proceed with this task.", font=("Segoe UI", 11)).pack(pady=10)
    tk.Button(top, text="Simulate Fingerprint", command=accept).pack(pady=10)
    top.transient(root)
    top.grab_set()
    root.wait_window(top)
    if confirmed:
        return True
    return bool(confirmed)
_ROUTER = None
if RoutedLLMHandler is not None:
    def _local_llm(prompt: str) -> str:
        # Read live identity each call
        model = identity.get("default_model", OLLAMA_MODEL)
        return core_ask(prompt, model=model)
    try:
        _ROUTER = RoutedLLMHandler(local_llm_fn=_local_llm)
    except Exception:
        _ROUTER = None

def ask_ollama(prompt):
    # Delegate to router if available; otherwise direct core call
    if _ROUTER is not None:
        return _ROUTER.ask_ollama(prompt)
    model = identity.get("default_model", OLLAMA_MODEL)
    return core_ask(prompt, model=model)


    
    
def clean_ai_response(response):
    """
    Cleans the AI's response by removing preliminary "thinking" or reasoning steps.
    It assumes the final, intended answer is the last block of text.
    """
    # Split the response into blocks separated by one or more empty lines.
    blocks = re.split(r'\n\s*\n', response.strip())

    # Filter out any empty blocks that might result from splitting.
    non_empty_blocks = [b.strip() for b in blocks if b.strip()]

    if not non_empty_blocks:
        return ""

    # Return the last non-empty block, which is assumed to be the final answer.
    return non_empty_blocks[-1]

def prompt_username(root):
    top = tk.Toplevel(root)
    top.title("Login")
    tk.Label(top, text="Enter username:").pack(padx=10, pady=5)
    username_var = tk.StringVar()
    entry_user = tk.Entry(top, textvariable=username_var)
    entry_user.pack(padx=10, pady=5)
    def submit():
        if username_var.get().strip():
            top.destroy()
    tk.Button(top, text="Login", command=submit).pack(pady=5)
    top.transient(root)
    top.grab_set()
    root.wait_window(top)
    return username_var.get().strip()

def verify_plugin_signature(plugin_path: Path) -> bool:
    """
    Verifies a plugin file against its .sig file using the public key.
    Returns True if the signature is valid, False otherwise.
    """
    public_key_path = CONFIG_DIR / "public_key.pem"
    signature_path = plugin_path.with_suffix(plugin_path.suffix + ".sig")

    if not public_key_path.exists():
        # If no public key, we can't verify. Fail open or closed?
        # For security, we should fail closed: no key means no verification is possible.
        print(f"[SECURITY] Public key not found at {public_key_path}. Cannot verify plugins.")
        return False
    if not signature_path.exists():
        print(f"[SECURITY] Signature file not found for {plugin_path.name}. Plugin will not be loaded.")
        return False

    try:
        with open(public_key_path, "rb") as f:
            public_key = serialization.load_pem_public_key(f.read())

        plugin_data = plugin_path.read_bytes()
        signature = signature_path.read_bytes()

        public_key.verify(
            signature,
            plugin_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False

def local_match_action(user_req: str) -> dict | None:
    """Check task_intents.json for a matching task."""
    conf = load_config("task_intents.json") or {}
    q = user_req.strip().lower()
    best = None

    for t in conf.get("tasks", []):
        task = t.get("task", "")
        action = t.get("action")
        requires_admin = bool(t.get("requires_admin", False))
        for p in (t.get("phrases") or []):
            pl = (p or "").lower()
            if not pl:
                continue
            if q == pl:
                return {
                    "task_name": task,
                    "action": action,
                    "requires_admin": requires_admin,
                    "reasoning": "Exact local match"
                }
            if pl in q and best is None:
                best = {
                    "task_name": task,
                    "action": action,
                    "requires_admin": requires_admin,
                    "reasoning": "Partial local match"
                }
    return best


THEMES = {
    "Dark": {"fg": "white", "bg": "#1e1e1e", "entry_bg": "#252525"},
    "Light": {"fg": "black", "bg": "white", "entry_bg": "#f0f0f0"},
    "Solarized": {"fg": "#657b83", "bg": "#fdf6e3", "entry_bg": "#eee8d5"},
    "Monokai": {"fg": "#f8f8f2", "bg": "#272822", "entry_bg": "#3e3d32"},
}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        # History for command recall
        self.command_history = []
        self.history_index = None
        self.plugins = []
        # Suggestion engine state
        self.current_suggestion = None
        # Load persisted aliases.  These map short keywords to full commands.
        self.aliases = load_aliases()
        # Variable to control whether admin authentication is enforced for privileged tasks
        self.admin_enforce_var = tk.BooleanVar(value=policy.get("fingerprint_required", True))
        self.tts_enabled_var = tk.BooleanVar(value=identity.get("voice_enabled", False))
        self.auto_execute = tk.BooleanVar(value=policy.get("auto_execute_default", True))

    def run_async(self, worker_func, *args, on_complete=None, **kwargs):
        """
        A robust, centralized method for running tasks in the background thread pool.
        It handles exceptions and ensures the on_complete callback is safely executed
        on the main Tkinter thread. This prevents context-related errors.

        :param worker_func: The function to execute in the background. It will be
                            called with *args and **kwargs.
        :param on_complete: Optional. A function to call on the main thread when the
                            worker is complete. It will receive two arguments:
                            `result` and `exception`. One of them will be None.
        """
        self.update_status("Working...")

        def worker_wrapper():
            """Wraps the target function to catch exceptions."""
            try:
                result = worker_func(*args, **kwargs)
                return result, None
            except Exception as e:
                import traceback
                error_details = f"Error in worker thread: {e}\n{traceback.format_exc()}"
                print(error_details)
                return None, e

        def _on_done_main_thread(future):
            """This function is executed on the main thread via self.after."""
            try:
                result, exception = future.result()
                if on_complete:
                    on_complete(result, exception)
                elif exception:
                    self.report_error(f"Background task failed: {exception}")
            except Exception as e:
                self.report_error(f"Error in async task completion handler: {e}")
            finally:
                self.update_status()

    def set_window_alpha(self, alpha: float):
        """Apply window transparency with clamping and persist setting."""
        try:
            alpha = max(0.2, min(1.0, float(alpha)))
        except Exception:
            alpha = 1.0
        try:
            self.attributes('-alpha', alpha)
        except Exception:
            pass  # Not all platforms support this
        policy["window_alpha"] = alpha
        try:
            Path(POLICY_FILE).write_text(json.dumps(policy, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[WARN] Failed to save opacity: {e}")

    def open_opacity_dialog(self):
        """Open a modal slider dialog to control opacity in real time."""
        top = tk.Toplevel(self)
        top.title("Set Window Opacity")
        top.transient(self)
        top.resizable(False, False)
        ttk.Label(top, text="Window opacity (%)").pack(padx=12, pady=(12, 6), anchor=tk.W)
        try:
            current_alpha = float(policy.get("window_alpha", self.attributes('-alpha')))
        except Exception:
            current_alpha = float(policy.get("window_alpha", 1.0))
        var = tk.DoubleVar(value=current_alpha * 100.0)
        value_lbl = ttk.Label(top, text=f"{int(var.get())}%")
        value_lbl.pack(padx=12, anchor=tk.W)
        def on_change(val):
            try:
                pct = float(val)
            except Exception:
                pct = var.get()
            value_lbl.config(text=f"{int(pct)}%")
            self.set_window_alpha(pct / 100.0)
        scale = ttk.Scale(top, from_=20, to=100, orient=tk.HORIZONTAL, variable=var, command=on_change, length=280)
        scale.pack(padx=12, pady=6, fill=tk.X)
        btns = ttk.Frame(top); btns.pack(padx=12, pady=(6,12), fill=tk.X)
        ttk.Button(btns, text="Close", command=top.destroy).pack(side=tk.RIGHT)
        def _on_close():
            self.set_window_alpha(var.get()/100.0)
            top.destroy()
        top.protocol("WM_DELETE_WINDOW", _on_close)

    def run_startup_tasks(self):
        self.build_ui()
        self.plugins = self.load_plugins()
        username = prompt_username(self)
        if username:
             self.update_status(f"User: {username}")
             assistant_name = identity.get("name", "AI")
             greeting = f"Welcome back, {username}. I'm {assistant_name}, ready to assist."
             self.chat_area.insert(tk.END, f"--- {greeting} ---\n\n")
             if self.tts_enabled_var.get():
                speak(greeting)
             # Auto-run plugins on startup
             for plugin_name in policy.get("autorun_plugins", []):
                 try:
                     plugin_file = PLUGINS_DIR / f"{plugin_name}.py"
                     if plugin_file.exists():
                         spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                         mod = importlib.util.module_from_spec(spec)
                         spec.loader.exec_module(mod)
                         if hasattr(mod, "run"): # Pass self (the app instance) to the plugin
                             # run asynchronously to avoid blocking UI
                             THREAD_POOL.submit(self.run_plugin, mod, self)
                             if self.tts_enabled_var.get():
                                 speak(f"{plugin_name} launching.")
                     else:
                         self.chat_area.insert(tk.END, f"[Autorun Plugin Error] {plugin_name} not found.\n")
                 except Exception as e:
                     self.chat_area.insert(tk.END, f"[Autorun Error] Failed to run {plugin_name}: {e}\n")

             if policy.get("daily_checkup_enabled", False):
                 self.after(1000, self.run_daily_checkup)
        else:
            self.destroy()
            sys.exit("Username is required to proceed.")

        self.load_configs()
        self.set_window_alpha(policy.get("window_alpha", 1.0))
        
        
    def handle_response(self, resp, user_req):
        """Handles AI responses, extracting actions, and managing fallback behaviors."""
        try:
            print("[LLM RAW OUTPUT]", repr(resp))  # Debug: show full raw AI response
            # If core.ask_ollama() already returned a dict, skip parsing
            if isinstance(resp, dict):
                data = resp
            else:
                data = self._extract_json_from_response(resp, user_req)

            if data is None:
                return  # fallback message was already used

            if "action" in data and "task_name" in data:
                self._handle_matched_task(data, user_req)
                return

        except Exception:
            if not resp or resp.startswith("[FATAL]"):
                self.report_error(resp or "[AI Error] No response from model.")
                self.chat_area.insert(tk.END, f"[DEBUG - Raw AI Response]:\n{resp}\n\n")
                return

            cleaned = clean_ai_response(resp)
            self.chat_area.insert(tk.END, f"AI: {cleaned}\n\n")
            self.chat_area.insert(tk.END, f"[DEBUG - Full AI Response]:\n{resp}\n\n")
            if self.tts_enabled_var.get():
                speak(cleaned)
            add_conversation_memory(user_req, cleaned)

        self.chat_area.see(tk.END)
        print("[DEBUG] RAW AI RESPONSE:", repr(resp))

    def _handle_matched_task(self, data, user_req):
        """Handles actions for matched tasks."""
        action = data['action']
        task_name = data['task_name']
        reasoning = data.get('reasoning', "")
        requires_admin = data.get('requires_admin', False)
        # Pull enforced list from identity.admin_verification.enforce_on_tasks
        enforce_on_tasks = identity.get("admin_verification", {}).get("enforce_on_tasks", [])
        needs_admin = data.get('requires_admin', False) or (task_name in enforce_on_tasks)

        if needs_admin:
            self.chat_area.insert(tk.END, "[SECURITY] This task requires admin confirmation.\n")
            if self.admin_enforce_var.get():
                if show_fingerprint_prompt(self):
                    self.chat_area.insert(tk.END, "[SECURITY] Fingerprint accepted.\n")
                else:
                    self.chat_area.insert(tk.END, "[SECURITY] Fingerprint failed. Trying PIN...\n")
                    pin_hash = policy.get("admin_pin_hash", "")
                    if prompt_for_pin(self, pin_hash):
                        self.chat_area.insert(tk.END, "[SECURITY] PIN accepted.\n")
                    else:
                        self.chat_area.insert(tk.END, "[SECURITY] PIN failed. Trying voice...\n")
                        if confirm_by_voice(self.chat_area):
                            self.chat_area.insert(tk.END, "[SECURITY] Voice confirmation accepted.\n")
                        else:
                            self.chat_area.insert(tk.END, "[SECURITY] All authentication methods failed.\n")
                            self._log_message("Security", f"Authentication failed for task: {task_name}")
                            return
            else:
                self.chat_area.insert(tk.END, "[SECURITY] Admin enforcement OFF. Skipping authentication.\n")
        else:
            self.chat_area.insert(tk.END, "[SECURITY] No admin needed.\n")


        self.chat_area.insert(tk.END, f"AI Decision: Matched task '{task_name}'.\n")
        self.chat_area.insert(tk.END, f"AI Reasoning: {reasoning}\n")
        # Highlight the intent line using configured tags
        self.chat_area.insert(tk.END, "[INTENT] ", 'intent_label')
        self.chat_area.insert(tk.END, "Task: ", 'intent_label')
        self.chat_area.insert(tk.END, task_name, 'intent_task')
        self.chat_area.insert(tk.END, " | Action: ", 'intent_label')
        self.chat_area.insert(tk.END, action, 'intent_action')
        self.chat_area.insert(tk.END, " | Admin: ", 'intent_label')
        self.chat_area.insert(tk.END, str(requires_admin), 'intent_admin')
        self.chat_area.insert(tk.END, "\n")
        # Display tags associated with this task, if available
        tags = self._get_task_tags(task_name)
        if tags:
            self.chat_area.insert(tk.END, "[Tags] ", 'intent_label')
            for idx, tname in enumerate(tags):
                self.chat_area.insert(tk.END, tname, 'intent_tag')
                if idx < len(tags) - 1:
                    self.chat_area.insert(tk.END, ", ", 'intent_label')
            self.chat_area.insert(tk.END, "\n")
        self._log_message("Matched Task", f"Task: {task_name}, Action: {action}, Reasoning: {reasoning}, Admin: {needs_admin}")

    def _start_image_analysis_flow(self):
        """
        Handles the UI part of analyzing an image, then calls the plugin logic
        in a background thread using the robust `run_async` method.
        """
        image_path = filedialog.askopenfilename(
            title="Select an image to analyze",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")],
            parent=self
        )
        if not image_path:
            self.update_status("Image analysis cancelled.")
            return

        question = simpledialog.askstring(
            "Analyze Image",
            f"What do you want to know about this image?\n({Path(image_path).name})",
            parent=self
        )
        if not question:
            self.update_status("Image analysis cancelled.") # noqa: B018
            return

        def worker(img_path, q_text):
            plugins = self.load_plugins()
            plugin_module = next((p['module'] for p in plugins if p['name'] == 'image_analyzer'), None)
            if not plugin_module:
                raise FileNotFoundError("[ERROR] image_analyzer plugin not found.")
            # Be flexible with plugin signatures: try (self, img, q), then (img, q), then ()
            try:
                return plugin_module.run(self, img_path, q_text)
            except TypeError:
                try:
                    return plugin_module.run(img_path, q_text)
                except TypeError:
                    return plugin_module.run()

        self.run_async(
            worker, image_path, question,
            on_complete=lambda res, err: self._add_ai_response(res) if not err else self.report_error(f"Image analysis failed: {err}")
        )

    def _worker_analyze_screen(self):
        """Worker thread to handle the screen analysis workflow."""
        self.update_status("Capturing screen...")
        image_path = self.run_plugin_by_name("screen_capture", sync=True)
        if not image_path or "[ERROR]" in image_path:
            self.report_error(f"Screen capture failed: {image_path}")
            self.update_status()
            return
        self.after(0, self.chat_area.insert, tk.END, f"[INFO] Screenshot saved to {image_path}\n")
        self.update_status("Asking AI to analyze image...")
        prompt = "You are an expert system assistant. Describe this screenshot and identify any actionable items or text."
        response_data = ask_ollama_with_image(prompt, image_path)
        analysis = response_data.get("response", "[ERROR] AI returned no analysis.")
        self.after(0, self._add_ai_response, f"Screen Analysis:\n{analysis}")
        self.after(0, self.update_status)
        try:
            os.remove(image_path)
        except Exception as e:
            self.report_error(f"Could not remove temp screenshot {image_path}: {e}")

    def send_desktop_command(self, action, params=None):
        """Sends a command to the Igris Shell via the file queue."""
        if params is None:
            params = {}

        command = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "params": params
        }

        with DESKTOP_COMMAND_LOCK:
            try:
                if DESKTOP_COMMAND_QUEUE_FILE.exists():
                    queue = json.loads(DESKTOP_COMMAND_QUEUE_FILE.read_text(encoding="utf-8"))
                    if not isinstance(queue, list):
                        queue = []
                else:
                    queue = []
            except (json.JSONDecodeError, IOError):
                queue = []

            queue.append(command)

            try:
                DESKTOP_COMMAND_QUEUE_FILE.write_text(json.dumps(queue, indent=2), encoding="utf-8")
            except IOError as e:
                self.report_error(f"Failed to write to desktop command queue: {e}")

    def _get_task_tags(self, task_name: str):
        """Retrieve a list of tags associated with a task from the task_intents configuration."""
        try:
            tasks_conf = load_config("task_intents.json")
            for t in tasks_conf.get("tasks", []):
                if t.get("task") == task_name:
                    return t.get("tags", [])
        except Exception:
            pass
        return []

    def _add_ai_response(self, text):
        """Helper method to safely add AI response to chat area."""
        self.after(0, lambda: self.chat_area.insert(tk.END, f"AI: {text}\n\n"))
        self.after(0, self.chat_area.see, tk.END)
        if self.tts_enabled_var.get():
            speak(text)

    def run_plugin_by_name(self, plugin_name: str, *args, sync: bool = False):
        """
        Finds a plugin by its name and runs it.
        - By default (sync=False), runs in a background thread.
        - If sync=True, runs in the current thread and returns the result.
        """
        plugins = self.plugins
        plugin_module = next((p['module'] for p in plugins if p['name'] == plugin_name), None)

        if not plugin_module:
            error_msg = f"Plugin '{plugin_name}' not found."
            if sync:
                return f"[ERROR] {error_msg}"
            self.report_error(error_msg)
            return

        def worker():
            """The actual plugin execution logic, capturing output."""
            with io.StringIO() as buf, contextlib.redirect_stdout(buf): # Flexible run() calling
                try:
                    result = plugin_module.run(*args)
                except TypeError:
                    try:
                        result = plugin_module.run()
                    except TypeError:
                        result = plugin_module.run(self, *args)
                output = buf.getvalue()

            if _pel:
                try: _pel.run(plugin_name)
                except Exception as e: print(f"[Logger Error] {e}")

            final_result = result if result is not None else ""
            if output.strip():
                final_result = f"{final_result}\n[Plugin Output]\n{output.strip()}"
            return final_result.strip()

        if sync:
            return worker()
        
        self.run_async(worker, on_complete=lambda res, err: self._add_ai_response(f"[Plugin: {plugin_name}] Result:\n{res}") if not err else self.report_error(str(err)))

    def run_network_task(self, plugin_name):
        """Finds and runs a network plugin using run_async, directing its output to the dashboard."""
        plugins = self.plugins
        plugin_to_run = next((p['module'] for p in plugins if p['name'] == plugin_name), None)

        if not plugin_to_run:
            self.report_error(f"Network task failed: Plugin '{plugin_name}' not found.")
            return

        def worker():
            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                # Try with context, then no-arg
                try:
                    result = plugin_to_run.run(self)
                except TypeError:
                    result = plugin_to_run.run()
                output = buf.getvalue().strip()

            final_output = result if result is not None else output

            if _pel:
                try: _pel.run(plugin_name)
                except Exception as e: print(f"[Logger Error] {e}")

            return final_output

        self.run_async(worker, on_complete=lambda res, err: self._parse_and_populate_dashboard(plugin_name, res) if not err else self.report_error(f"Error running {plugin_name}: {err}"))

    def _parse_and_populate_dashboard(self, plugin_name, result):
        """Parses plugin output and updates the correct network dashboard widget."""
        if plugin_name == 'network_scanner':
            self.hosts_tree.delete(*self.hosts_tree.get_children())
            lines = [ln.strip() for ln in (result or "").splitlines() if ln.strip()]
            if len(lines) > 2:
                for line in lines[2:]:
                    parts = re.split(r'\s{2,}', line.strip())
                    if len(parts) >= 3:
                        ip, mac, hostname = parts[0], parts[1], " ".join(parts[2:])
                        self.hosts_tree.insert("", "end", values=(ip, mac, hostname))
        elif plugin_name == 'port_scanner':
            self.ports_tree.delete(*self.ports_tree.get_children())
            for line in (result or "").splitlines():
                if line.lower().strip().startswith("list:"):
                    ports = line.split(":", 1)[1].strip().split(',')
                    for port in ports:
                        if port.strip().isdigit():
                            self.ports_tree.insert("", "end", values=(port.strip(),))
                    break
        elif plugin_name == 'who_is_connected':
            self.connections_text.insert(tk.END, f"--- Active Connections ({datetime.now().strftime('%H:%M:%S')}) ---\n{result}\n\n")
            self.connections_text.see(tk.END)
        else:
            self.chat_area.insert(tk.END, f"Result from {plugin_name}:\n{result}\n\n")


    def run_plugin(self, plugin_module, *args):
        self.after(0, self.clear_suggestion)
        plugin_name = plugin_module.__name__
        try:
            if hasattr(plugin_module, "run"):
                self.update_status(f"Running plugin: {plugin_name}...")
                try:
                    # Redirect stdout to capture print statements from the plugin
                    with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                        # Try calling run() with provided args; if signature mismatch, fall back
                        try:
                            result = plugin_module.run(*args)
                        except TypeError:
                            try:
                                result = plugin_module.run()
                            except TypeError:
                                # As a last resort, try passing context explicitly
                                result = plugin_module.run(self, *args)
                        output = buf.getvalue()

                        self._add_ai_response(f"[Plugin: {plugin_name}] Result:\n{result}")
                        
                        if _pel:
                            try: _pel.run(plugin_name)
                            except Exception as _e: self.after(0, self.report_error, f"[Logger] {_e}")

                        # Display any captured print output from the plugin
                        if output and output.strip():
                            self.after(0, self.chat_area.insert, tk.END, f"[Plugin Output] {output.strip()}\n")
                    self.after(0, self.chat_area.see, tk.END)

                    # --- Suggestion Logic ---
                    suggestion = get_suggestion(plugin_name)
                    if suggestion:
                        self.after(0, self.display_suggestion, suggestion)
                except Exception as plugin_exc:
                    self.chat_area.insert(tk.END, f"[Plugin Error] {plugin_name}: {plugin_exc}\n")
            else:
                self.report_error(f"[Plugin Error: {plugin_name}] No 'run' function found.")
        finally:
            self.update_status()


    def load_plugins(self):
        """Loads plugins from the plugins directory, extracting metadata and handling errors."""
        plugins = []
        for file in PLUGINS_DIR.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(file.stem, file)
                if spec is None:
                    raise ImportError(f"Could not load module spec for {file}")

                # Before loading, check if the file has a valid signature or checksum, if required
                # if not verify_plugin_signature(file):
                #    raise SecurityException(f"Plugin {file} has an invalid signature")

                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # Ensure the module is fully loaded
                description = mod.__doc__.strip() if mod.__doc__ else "No description provided."

                plugins.append({'name': file.stem, 'module': mod, 'description': description})
            except Exception as e:
                self.report_error(f"[Plugin Load Error] {file.stem}: {e}")
        return plugins        





    def load_configs(self):
        global policy, identity, base_context, review_templates
        policy = load_policy()
        identity = load_identity_and_initialize()

        task_intents = load_config("task_intents.json")
        review_templates = load_config("review_templates.json")

        base_context_template = identity.get("base_context", "")

        task_list_str = "\n--- START TASK LIST ---\n"
        for task in task_intents.get("tasks", []):
            task_list_str += f"- Task: {task.get('task')}, Action: `{task.get('action')}`, Phrases: {task.get('phrases')}\n"
        task_list_str += "--- END TASK LIST ---\n"
        base_context = base_context_template + task_list_str
    
    def show_plugin_menu(self):
        plugins = self.plugins
        if not plugins:
            messagebox.showinfo("Plugins", "No plugins found in the plugins directory.")
            return

        top = tk.Toplevel(self)
        top.title("Run Plugin")

        # Group plugins by prefix (e.g. "net_scan_x" → "net")
        groups = sorted({p['name'].split('_')[0] for p in plugins})
        groups.insert(0, "All")  # add 'All' group
        group_var = tk.StringVar(value="All")

        # Group filter dropdown
        group_menu = ttk.Combobox(top, values=groups, state='readonly', textvariable=group_var)
        group_menu.pack(fill=tk.X, padx=10, pady=(10, 0))

        # Treeview for plugin list
        tree = ttk.Treeview(top, columns=("Description",), show="headings", selectmode="browse")
        tree.heading("#1", text="Description")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)

        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

         # Populate treeview
        def populate_tree(selected_group):
            tree.delete(*tree.get_children())
            for plugin in plugins:
                if selected_group == "All" or plugin['name'].startswith(selected_group):
                    tree.insert("", "end", iid=plugin['name'], values=(plugin['description'],))

        populate_tree("All")

        def on_group_change(event=None):
            populate_tree(group_var.get())

        group_menu.bind("<<ComboboxSelected>>", on_group_change)

        def on_double_click(event):
            item_id = tree.selection()
            if not item_id:
                return
            plugin_name = item_id[0]
            for p in plugins:
                if p['name'] == plugin_name:
                    try: # This is a simple case, so we don't need the full async wrapper
                        output = p['module'].run()
                        messagebox.showinfo("Plugin Output", str(output))
                    except Exception as e:
                        messagebox.showerror("Plugin Error", f"Error running plugin '{plugin_name}': {e}")
                    break
        tree.bind("<Double-1>", on_double_click)            

        def refresh_tree(*args):
            selected = group_var.get()
            tree.delete(*tree.get_children())
            for plugin in plugins:
                grp = plugin['name'].split('_')[0]
                if selected == "All" or grp == selected:
                    tree.insert("", tk.END, iid=plugin['name'], text=plugin['name'], values=(plugin['description'],))

        group_var.trace_add('write', lambda *a: refresh_tree())
        refresh_tree()

        def run_plugin_wrapper():
            selected_item = tree.focus()
            if selected_item:
                plugin = next((p for p in plugins if p['name'] == selected_item), None)
                if plugin:
                    THREAD_POOL.submit(self.run_plugin, plugin['module'], self)
            top.destroy()

        btn = tk.Button(top, text="Run Selected", command=run_plugin_wrapper)
        btn.pack(pady=10)

    def build_ui(self):
        self.title(f"{identity.get('name', 'AI')} System Control")
        self.geometry("1000x800")

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Loading...")  # Initialize with loading message
        self.status_bar = tk.Label(self, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.update_status("Ready")
        
        # --- Error Area ---
        self.error_area = scrolledtext.ScrolledText(self, height=4, fg="red", state='normal', wrap=tk.WORD)
        self.error_area.pack(fill=tk.X, padx=5, pady=(0,5))

        # --- Main Content Area (Notebook) ---
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Console Tab ---
        console_frame = ttk.Frame(notebook)
        notebook.add(console_frame, text="Console")
 
        # --- Network Tab ---
        network_frame = ttk.Frame(notebook)
        notebook.add(network_frame, text="Network Dashboard")
        self.build_network_tab(network_frame)
 
        # --- Bottom Frame for Suggestions and Input ---
        bottom_frame = tk.Frame(console_frame) # Parent is now console_frame
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=0)
 
        # --- Menu Bar ---
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=0, bg=THEMES[policy.get("theme", "Dark")]["bg"])
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Chat...", command=self.export_chat)
        file_menu.add_command(label="Import Chat...", command=self.import_chat)
        file_menu.add_separator() 
        file_menu.add_command(label="Exit", command=self.quit)

        tools_menu = tk.Menu(menu_bar, tearoff=0, bg=THEMES[policy.get("theme", "Dark")]["bg"])
        tools_menu.add_command(label="Run Plugin...", command=lambda: self.show_plugin_menu())
        tools_menu.add_command(label="Run Daily Checkup", command=self.run_daily_checkup)
        tools_menu.add_separator()
        tools_menu.add_command(label="Edit Policy File...", command=lambda: show_policy_editor(self))
        tools_menu.add_separator() # This separator was already here
        tools_menu.add_command(label="Analyze Image...", command=self._start_image_analysis_flow)
        # Memory Manager entry – view and manage stored conversation memory
        tools_menu.add_command(label="Memory Manager", command=self.show_memory_manager)
        options_menu = tk.Menu(menu_bar, tearoff=0, bg=THEMES[policy.get("theme", "Dark")]["bg"])
        menu_bar.add_cascade(label="Tools", menu=tools_menu)
        menu_bar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_checkbutton(label="Auto-Execute Matched Tasks", variable=self.auto_execute, command=self.save_policy)
        options_menu.add_checkbutton(label="Enable Text-to-Speech", variable=self.tts_enabled_var)
        # Checkbox to toggle enforcement of admin authentication (fingerprint/PIN/voice)
        options_menu.add_checkbutton(label="Enforce Admin Auth", variable=self.admin_enforce_var, command=self.save_policy)
        options_menu.add_command(label="Set Window Opacity…", command=self.open_opacity_dialog)

        # --- Docker Menu ---
        docker_menu = tk.Menu(menu_bar, tearoff=0, bg=THEMES[policy.get("theme", "Dark")]["bg"])
        menu_bar.add_cascade(label="Docker", menu=docker_menu)
        docker_menu.add_command(label="List Containers", command=lambda: self.run_plugin_by_name("app_manager_cli", "list"))
        docker_menu.add_command(label="Stop Container...", command=self._docker_stop_prompt)
        docker_menu.add_command(label="Remove Container...", command=self._docker_remove_prompt)

        # --- Theme Menu ---
        theme_menu = tk.Menu(options_menu, tearoff=0)
        options_menu.add_cascade(label="Theme", menu=theme_menu)
        self.theme_var = tk.StringVar(value=policy.get("theme", "Dark"))
        for theme_name in THEMES.keys():
            theme_menu.add_radiobutton(label=theme_name, variable=self.theme_var, command=lambda t=theme_name: self.set_theme(t))

        # --- Suggestion Bar (Packed before input frame) ---
        self.suggestion_frame = tk.Frame(bottom_frame)
        self.suggestion_label = tk.Label(self.suggestion_frame, text="", font=("Segoe UI", 9, "italic"))
        self.suggestion_label.pack(side=tk.LEFT, padx=(10, 5), pady=2)

        suggestion_btn = tk.Button(self.suggestion_frame, text="Run Suggestion", command=self.run_suggestion, relief=tk.FLAT, borderwidth=1)
        suggestion_btn.pack(side=tk.LEFT, padx=5, pady=2)

        dismiss_btn = tk.Button(self.suggestion_frame, text="Dismiss (X)", command=self.clear_suggestion, relief=tk.FLAT, borderwidth=1)
        dismiss_btn.pack(side=tk.LEFT, padx=5, pady=2)

        self.entry = tk.Entry(bottom_frame, font=("Consolas", 11), relief=tk.FLAT, borderwidth=4)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        mic_btn = tk.Button(bottom_frame, text="🎤", command=self.record_voice, relief=tk.FLAT)
        if sr is None:
            mic_btn.config(state="disabled")
        mic_btn.pack(side=tk.RIGHT, padx=(5, 0))
        CreateToolTip(mic_btn, "Record voice command")


        btn = tk.Button(bottom_frame, text="Send", command=self.send_request, relief=tk.FLAT)
        btn.pack(side=tk.RIGHT, padx=(5,0))

        self.entry.bind('<Return>', lambda e: self.send_request())
        self.entry.bind('<Up>', self.on_entry_key)
        self.entry.bind('<Down>', self.on_entry_key)

        # --- Chat Area (inside console_frame) ---
        self.chat_area = scrolledtext.ScrolledText(
            console_frame, state='normal', wrap=tk.WORD, font=("Consolas", 11),
            borderwidth=0, highlightthickness=0
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure tags for intent highlighting.
        self.chat_area.tag_configure('intent_label', foreground='#888888', font=("Consolas", 11, 'bold'))
        self.chat_area.tag_configure('intent_task', foreground='#1E90FF', font=("Consolas", 11, 'bold'))
        self.chat_area.tag_configure('intent_action', foreground='#00AA00', font=("Consolas", 11))
        self.chat_area.tag_configure('intent_admin', foreground='#FF6347', font=("Consolas", 11))
        self.chat_area.tag_configure('intent_tag', foreground='#8A2BE2', font=("Consolas", 11, 'italic'))

        self.tts_enabled_var.set(policy.get("tts_enabled", self.tts_enabled_var.get()))

        self.apply_theme(self.theme_var.get())  # Apply theme after widgets are created

    def build_network_tab(self, parent_frame):
        """Populates the Network Dashboard tab with its widgets."""
        button_bar = ttk.Frame(parent_frame, padding=5)
        button_bar.pack(side=tk.TOP, fill=tk.X)

        # Note: 'ping_sweep' is the intent name, but 'network_scanner' is the actual plugin file.
        ttk.Button(button_bar, text="Sweep LAN", command=lambda: self.run_network_task("network_scanner")).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_bar, text="Port Scan Target", command=lambda: self.run_network_task("port_scanner")).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_bar, text="Active Connections", command=lambda: self.run_network_task("who_is_connected")).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_bar, text="Generate Map", command=lambda: self.run_network_task("generate_live_topology_map")).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_bar, text="Manage Tunnels", command=lambda: self.run_network_task("ssh_tunnel_manager")).pack(side=tk.LEFT, padx=2)

        paned_window = ttk.PanedWindow(parent_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_pane = ttk.Frame(paned_window, padding=5)
        paned_window.add(left_pane, weight=2)

        ttk.Label(left_pane, text="Live Hosts", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.hosts_tree = ttk.Treeview(left_pane, columns=("ip", "mac", "hostname"), show="headings")
        self.hosts_tree.heading("ip", text="IP Address")
        self.hosts_tree.heading("mac", text="MAC Address")
        self.hosts_tree.heading("hostname", text="Hostname")
        self.hosts_tree.column("ip", width=120, anchor=tk.W)
        self.hosts_tree.column("mac", width=150, anchor=tk.W)
        self.hosts_tree.column("hostname", width=200, anchor=tk.W)
        self.hosts_tree.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(left_pane, text="Open Ports (on selected host)", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(10, 0))
        self.ports_tree = ttk.Treeview(left_pane, columns=("port",), show="headings")
        self.ports_tree.heading("port", text="Port")
        self.ports_tree.column("port", width=80, anchor=tk.W)
        self.ports_tree.pack(fill=tk.BOTH, expand=True, pady=(5,0))

        right_pane = ttk.Frame(paned_window, padding=5)
        paned_window.add(right_pane, weight=1)

        
        ttk.Label(right_pane, text="Active Connections Log", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.connections_text = scrolledtext.ScrolledText(right_pane, wrap=tk.WORD, font=("Consolas", 9))
        self.connections_text.pack(fill=tk.BOTH, expand=True)

    def _docker_stop_prompt(self):
        """Prompt user for container ID to stop."""
        # First, show the user the list of running containers
        self.chat_area.insert(tk.END, "Fetching container list...\n")
        self.run_plugin_by_name("app_manager_cli", "list")

        # Then, ask for the one to stop
        container_id = simpledialog.askstring("Stop Container", "Enter the Container ID or Name to stop:", parent=self)
        if container_id:
            self.run_plugin_by_name("app_manager_cli", "stop", container_id)

    def _docker_remove_prompt(self):
        """Prompt user for container ID to remove."""
        # First, show the user the list of running containers
        self.chat_area.insert(tk.END, "Fetching container list...\n")
        self.run_plugin_by_name("app_manager_cli", "list")

        # Then, ask for the one to remove
        container_id = simpledialog.askstring("Remove Container", "Enter the Container ID or Name to remove:", parent=self)
        if container_id:
            self.run_plugin_by_name("app_manager_cli", "remove", container_id)

    def export_chat(self): # This is the correct, single definition now
        file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        #Style configuration
        style = ttk.Style()
        style.configure("Treeview", rowheight=20)
        #Adjust Column Widths
        self.hosts_tree.column("ip", width=100, anchor=tk.W)

        if file:
            with open(file, 'w', encoding='utf-8') as f:
                f.write(self.chat_area.get("1.0", tk.END).strip()) # remove trailing newline

        self.update_status("Chat exported successfully.")
    
    def import_chat(self):
        file = filedialog.askopenfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if file:
            with open(file, 'r', encoding='utf-8') as f:
                chat_text = f.read()
            self.chat_area.insert(tk.END, f"\n[Imported Chat]\n{chat_text}\n\n")
            self.chat_area.see(tk.END)
            self.update_status("Chat imported successfully.")



    def update_status(self, text="Ready"):
        try:
            self.after(0, self.status_var.set, text)
        except Exception:
            self.status_var.set(text)


    def report_error(self, msg):
        self.after(0, self.error_area.insert, tk.END, f"{msg}\n")
        self.after(0, self.error_area.see, tk.END)

    def apply_theme(self, theme_name):
        theme = THEMES.get(theme_name, THEMES["Dark"])
        self.config(bg=theme["bg"])
        self.chat_area.config(fg=theme["fg"], bg=theme["bg"])
        self.error_area.config(fg="red", bg=theme["bg"])
        self.status_bar.config(fg=theme["fg"], bg=theme["bg"])
        self.entry.config(fg=theme["fg"], bg=theme["entry_bg"], insertbackground=theme["fg"])
        # Theme the suggestion bar
        self.suggestion_frame.config(bg=theme["bg"])
        self.suggestion_label.config(fg="#FFFF99", bg=theme["bg"])  # Light yellow for text
        for child in self.suggestion_frame.winfo_children():
            if isinstance(child, tk.Button):
                child.config(fg=theme["fg"], bg=theme["entry_bg"])


        # Save theme to policy

    def set_theme(self, theme_name):
        self.apply_theme(theme_name)
        self.save_policy(theme=theme_name)

    def save_policy(self, theme=None, alpha=None):
        policy["auto_execute_default"] = self.auto_execute.get()
        policy["tts_enabled"] = self.tts_enabled_var.get()
        # Persist admin enforcement flag as fingerprint_required.  When false, all admin
        # authentication will be bypassed.
        policy["fingerprint_required"] = self.admin_enforce_var.get()
        if theme:
            policy["theme"] = theme
        if alpha is not None:
            policy["window_alpha"] = float(alpha)
        try:
            Path(POLICY_FILE).write_text(json.dumps(policy, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[WARN] Failed to save policy: {e}")
    
    def on_entry_key(self, event):
        if event.keysym == "Up":
            if self.command_history:
                if self.history_index is None:
                    self.history_index = len(self.command_history) - 1
                elif self.history_index > 0:
                    self.history_index -= 1
                self.entry.delete(0, tk.END)
                self.entry.insert(0, self.command_history[self.history_index])
        elif event.keysym == "Down":
            if self.command_history and self.history_index is not None:
                if self.history_index < len(self.command_history) - 1:
                    self.history_index += 1
                    self.entry.delete(0, tk.END)
                    self.entry.insert(0, self.command_history[self.history_index])
                else:
                    self.entry.delete(0, tk.END)
                    self.history_index = None
    
    def show_opacity_dialog(self):
        top = tk.Toplevel(self)
        top.title("Window Opacity")
        top.geometry("280x100")
        top.transient(self)
        top.grab_set()

        try:
            current_alpha = self.wm_attributes("-alpha")
        except tk.TclError:
            current_alpha = 1.0 # Default if not supported

        alpha_var = tk.DoubleVar(value=current_alpha)

        label = tk.Label(top, text="Adjust window opacity\n(Requires a desktop compositor)")
        label.pack(pady=(10, 5))

        scale = ttk.Scale(top, from_=0.2, to=1.0, orient=tk.HORIZONTAL, variable=alpha_var, command=self.set_window_alpha)
        scale.pack(fill=tk.X, padx=15, pady=5)

        ok_button = ttk.Button(top, text="OK", command=lambda: [self.save_policy(alpha=alpha_var.get()), top.destroy()])
        ok_button.pack(pady=(0, 10))
        top.focus_set()

    def set_window_alpha(self, value_str):
        try:
            value = float(value_str)
            if 0.1 <= value <= 1.0:
                self.wm_attributes("-alpha", value)
        except (tk.TclError, ValueError):
            # Silently fail on platforms that don't support it or on invalid values.
            pass

    def on_entry_key(self, event):
        if event.keysym == "Up":
            if self.command_history:
                if self.history_index is None:
                    self.history_index = len(self.command_history) - 1
                elif self.history_index > 0:
                    self.history_index -= 1
                self.entry.delete(0, tk.END)
                self.entry.insert(0, self.command_history[self.history_index])
        elif event.keysym == "Down":
            if self.command_history and self.history_index is not None:
                if self.history_index < len(self.command_history) - 1:
                    self.history_index += 1
                    self.entry.delete(0, tk.END)
                    self.entry.insert(0, self.command_history[self.history_index])
                else:
                    self.entry.delete(0, tk.END)
                    self.history_index = None
    
    def send_request(self):
        try:
            user_req = self.entry.get().strip()
            if not user_req:
                return
            # Expand aliases if the first token matches a defined alias
            if not user_req.startswith('/'):
                parts = user_req.split(maxsplit=1)
                if parts:
                    alias_key = parts[0]
                    if alias_key in self.aliases:
                        expanded = self.aliases[alias_key]
                        rest = parts[1] if len(parts) > 1 else ""
                        user_req = (expanded + (" " + rest if rest else "")).strip()

            # Handle local slash commands first
            if user_req.startswith('/'):
                self.handle_slash_command(user_req)
                return

            self.update_status(f"Last input: {user_req[:30]}")
            self.command_history.append(user_req)
            self.history_index = None
            self.entry.delete(0, tk.END)
            self.chat_area.insert(tk.END, f"> {user_req}\n")
            self.chat_area.see(tk.END)
            log_to_file(f"USER: {user_req}")

            if self.tts_enabled_var.get():
                speak(f"You said: {user_req}")

            review = respond_with_review(user_req)
            if review:
                self.chat_area.insert(tk.END, f"System Review:\n{review}\n")
                return

            for phrase in policy.get("blocked_phrases", []):
                if phrase.lower() in user_req.lower():
                    self.chat_area.insert(tk.END, f"[SECURITY] This request is blocked by policy.\n")
                    return

            # 1) Try local intents first (offline fast‑path)
            lm = local_match_action(user_req)
            if lm:
                self._handle_matched_task(lm, user_req)
                return

            def worker(current_user_req):
                recent_conversation = retrieve_conversation_memory(current_user_req, top_n=3)
                context_str = ""
                if recent_conversation:
                    context_str = "\n--- RECENT CONVERSATION CONTEXT ---\n"
                    for mem in reversed(recent_conversation):
                        context_str += f"User: {mem['user']}\nAI: {mem['ai']}\n"
                    context_str += "--- END CONTEXT ---\n\n"

                prompt = (
                    f"{context_str}{base_context}\n\n"
                    f"User request: {current_user_req}\n\n"
                    "Respond ONLY with a raw JSON object. DO NOT include code blocks, markdown, triple backticks, or explanation text. Just return a JSON object like this:\n"
                    '{\n'
                    '  "task_name": "...",\n'
                    '  "action": "...",\n'
                    '  "requires_admin": false,\n'
                    '  "reasoning": "..." \n'
                    '}\n\n'
                    "Do not include help text, explanations, or introductions."
                )

                response = ask_ollama(prompt)

                return response

            def on_complete(result, exception):
                if exception:
                    self.report_error(f"AI request failed: {exception}")
                    return
                # --- DEBUG PATCH START ---
                print("[DEBUG] Raw LLM Output:\n", result)
                self.chat_area.insert(tk.END, f"\n[DEBUG] Raw AI Response:\n{result}\n\n")
                self.chat_area.see(tk.END)
                # --- DEBUG PATCH END ---
                self.handle_response(result, user_req)

            self.run_async(worker, user_req, on_complete=on_complete)
        except Exception as e:
            self.report_error(f"[Send Request Error] {str(e)}")

    def handle_slash_command(self, command):
        """Handles local client-side commands like /history."""
        self.command_history.append(command)
        self.history_index = None
        self.entry.delete(0, tk.END)
        self.chat_area.insert(tk.END, f"> {command}\n")

        if command == '/history':
            history = get_all_conversation_history(limit=15)
            if not history:
                self.chat_area.insert(tk.END, "[History] No conversation history found.\n\n")
            else:
                history_str = "--- Recent Conversation History ---\n"
                for mem in history:
                    ts = mem.get('timestamp', 'No date')
                    user = mem.get('user', 'N/A')
                    ai = mem.get('ai', 'N/A').replace('\n', '\n  ')
                    history_str += f"[{ts}]\n  You: {user}\n  AI: {ai}\n\n"
                self.chat_area.insert(tk.END, history_str)
        
        elif command == '/learn':
            learn_new_task_gui(self)
        elif command == '/intent':
            show_task_intent_manager(self)
        elif command == '/clear':
            self.chat_area.delete('1.0', tk.END)
        elif command.startswith('/alias'):
            # Syntax:
            #   /alias list
            #   /alias remove <name>
            #   /alias <name>="full command"
            alias_args = command[len('/alias'):].strip()
            if alias_args.lower() in ('', 'list'):
                # List aliases
                if not self.aliases:
                    self.chat_area.insert(tk.END, "[Alias] No aliases defined.\n\n")
                else:
                    self.chat_area.insert(tk.END, "[Alias List]\n")
                    for k, v in self.aliases.items():
                        self.chat_area.insert(tk.END, f"  {k} = \"{v}\"\n")
                    self.chat_area.insert(tk.END, "\n")
            elif alias_args.lower().startswith('remove '):
                name = alias_args[7:].strip()
                if name in self.aliases:
                    del self.aliases[name]
                    save_aliases(self.aliases)
                    self.chat_area.insert(tk.END, f"[Alias] Removed alias '{name}'.\n\n")
                else:
                    self.chat_area.insert(tk.END, f"[Alias] Alias '{name}' not found.\n\n")
            else:
                # Define new alias
                # Accept formats like foo="bar" or foo=bar
                match = re.match(r"(\S+?)\s*=\s*['\"]?(.*?)['\"]?$", alias_args)
                if match:
                    name, value = match.group(1), match.group(2)
                    if not name:
                        self.chat_area.insert(tk.END, "[Alias] Invalid alias name.\n\n")
                    else:
                        self.aliases[name] = value.strip()
                        save_aliases(self.aliases)
                        self.chat_area.insert(tk.END, f"[Alias] Set '{name}' = '{value.strip()}'.\n\n")
                else:
                    self.chat_area.insert(tk.END, "[Alias] Invalid syntax. Use /alias name=\"full command\".\n\n")
        else:
            self.chat_area.insert(tk.END, f"[INFO] Unknown command: {command}. Available commands: /history, /clear, /alias\n\n")
        self.chat_area.see(tk.END)

    def record_voice(self):
        """Record a short voice input using speech_recognition and populate the entry."""
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                self.update_status("Listening...")
                # Adjust noise threshold
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=5)
            try:
                spoken = recognizer.recognize_google(audio, language="en-US")
                self.entry.delete(0, tk.END)
                self.entry.insert(0, spoken)
                # Optionally auto-send after voice input
                self.send_request()
            except sr.UnknownValueError:
                self.chat_area.insert(tk.END, "[Voice Input] Unable to recognize speech.\n")
            except sr.RequestError as e:
                self.chat_area.insert(tk.END, f"[Voice Input] Recognition error: {e}\n")
        except Exception as e:
            self.chat_area.insert(tk.END, f"[Voice Input] Error: {e}\n")
        finally:
            self.update_status()

    def apply_initial_theme(self):
        self.apply_theme(self.theme_var.get())

    def run_daily_checkup(self):
        from datetime import time
        from concurrent.futures import ThreadPoolExecutor
        self.chat_area.insert(tk.END, "[Daily Checkup] Starting system health check...\n")
        report_body = get_system_status_report()
        report = f"[Daily Checkup]\n{report_body}\n"
        self.chat_area.insert(tk.END, report)
        if self.tts_enabled_var.get():
            speak("Daily checkup complete. Please review the system report.")
        add_memory(report)
        now = datetime.now()
        next_checkup_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if next_checkup_time <= now:
            next_checkup_time += timedelta(days=1)
        delay = (next_checkup_time - now).total_seconds()
        self.after(int(delay * 1000), self.run_daily_checkup)
        self.chat_area.insert(tk.END, f"[Daily Checkup] Next check scheduled for {next_checkup_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    def show_memory_manager(self):
        """Opens a window to browse and clear stored conversation memory."""
        try:
            # Fetch history via memory manager helper.  Limit None to fetch all.
            mem_entries = get_all_conversation_history(limit=None)
        except Exception as e:
            messagebox.showerror("Memory Error", f"Failed to load memory: {e}")
            return
        top = tk.Toplevel(self)
        top.title("Memory Manager")
        top.geometry("600x400")
        # Frame for list and buttons
        frame = tk.Frame(top)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Listbox showing each entry summary
        listbox = tk.Listbox(frame)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Populate listbox with timestamp and truncated user text
        for idx, mem in enumerate(mem_entries):
            ts = mem.get('timestamp', 'NoDate')
            user_text = mem.get('user', '')
            listbox.insert(tk.END, f"[{ts}] {user_text[:40]}")
        # Scrollbar
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.configure(yscrollcommand=scrollbar.set)
        # Text widget to display full details
        details = scrolledtext.ScrolledText(top, wrap=tk.WORD, height=10)
        details.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

        def on_select(event):
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                mem = mem_entries[idx]
                details.delete('1.0', tk.END)
                details.insert(tk.END, json.dumps(mem, indent=2))
        listbox.bind('<<ListboxSelect>>', on_select)

        def clear_selected():
            selection = listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            # Remove from memory manager
            # We remove by timestamp if available
            mem = mem_entries.pop(idx)
            # call memory_manager to delete?  We'll remove from in-memory only for now
            listbox.delete(idx)
            details.delete('1.0', tk.END)

        def clear_all():
            if messagebox.askyesno("Confirm", "Clear all memory entries?"):
                mem_entries.clear()
                listbox.delete(0, tk.END)
                details.delete('1.0', tk.END)

        btn_frame = tk.Frame(top)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(btn_frame, text="Delete Selected", command=clear_selected).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="Clear All", command=clear_all).pack(side=tk.LEFT, padx=(5,0))
        log_to_file("MEMORY VIEWER opened.")
    
    def _extract_json_from_response(self, resp, user_req):
        """
        Extract JSON object from model output.
        Now delegates parsing to core.strict_json_from_text()
        and skips if resp is already a dict.
        """

        # Safety: skip if already a dict
        if isinstance(resp, dict):
            return resp

        data = strict_json_from_text(resp or "")
        if data and all(k in data for k in ("task_name", "action", "requires_admin")):
            return data

        # If we get here, parsing failed — debug log
        self.chat_area.insert(tk.END, f"\n[DEBUG] Could not parse JSON from model.\n{resp}\n\n")
        self._log_message("AI Response Failure", f"Raw: {resp}")

        # Fallback message if configured
        fb = identity.get("fallback_behavior", {}).get("on_no_match")
        if fb:
            self.chat_area.insert(tk.END, f"AI: {fb}\n\n")
            return None

        # Try local intent match (only if helper is available)
        match = None
        if find_best_local_match is not None:
            local_tasks = load_config("task_intents.json")  # returns {"tasks":[...]} or {}
            match = find_best_local_match(user_req, local_tasks)

        if match:
            self._handle_matched_task({
                "task_name": match["task"],
                "action": match["action"],
                "requires_admin": bool(match.get("requires_admin", False)),
                "reasoning": "Matched locally from trained intents"
            }, user_req)
            return None

        return None



    def _log_message(self, tag, message):
        """Helper to log messages with AI's role for traceability."""
        full_message = f"[{identity.get('role', 'Assistant')} - {tag}] {message}"
        log_to_file(full_message)

    def display_suggestion(self, suggestion_data):
        """Makes the suggestion bar visible and populates it with the suggestion text."""
        self.current_suggestion = suggestion_data
        self.suggestion_label.config(text=suggestion_data.get('suggestion', ''))
        self.suggestion_frame.pack(side=tk.TOP, fill=tk.X, pady=(2, 2), before=self.entry)

    def clear_suggestion(self):
        """Hides the suggestion bar and clears the current suggestion."""
        self.current_suggestion = None
        self.suggestion_frame.pack_forget()

    def run_suggestion(self):
        if self.current_suggestion and "plugin_name" in self.current_suggestion:
            plugin_name = self.current_suggestion["plugin_name"]
            self.chat_area.insert(tk.END, f"> (Suggested) Run plugin: {plugin_name}\n")
            self.run_plugin_by_name(plugin_name)
            self.clear_suggestion()

class CreateToolTip:
    """
    Create a tooltip for a given widget.
    """
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.id = self.widget.after(500, self.show_tip)

    def leave(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
        if self.tw:
            self.tw.destroy()

    def show_tip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

def get_system_uptime():
    """Retrieves system uptime and formats it into a human-readable string."""
    try:
        if psutil is None:
            return "Uptime unavailable (psutil not installed)."
        uptime_seconds = time.time() - psutil.boot_time()
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        uptime_str = ""
        if days:
            uptime_str += f"{int(days)} day(s), "
        if hours:
            uptime_str += f"{int(hours)} hour(s), "
        if minutes:
            uptime_str += f"{int(minutes)} minute(s), "
        uptime_str += f"{int(seconds)} second(s)"

        return uptime_str.strip(", ")  # Remove trailing comma if present
    except Exception as e:
        return f"Could not retrieve uptime: {e}"

if __name__ == "__main__":
    app = App() # build GUI widgets first
    app.run_startup_tasks() # prompt login and launch    
    app.mainloop() # build GUI widgets first
