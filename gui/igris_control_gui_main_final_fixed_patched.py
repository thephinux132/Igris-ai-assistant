import os, sys, json, threading, re, shlex, shutil, subprocess, time, io, contextlib
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
from concurrent.futures import ThreadPoolExecutor

# --- Igris paths ---
ROOT = Path(__file__).resolve().parents[1]  # project root
CONFIG_DIR = ROOT / "ai_assistant_config"
PLUGINS_DIR = ROOT / "plugins"
sys.path.insert(0, str(ROOT))          # prefer flat modules
sys.path.insert(0, str((ROOT / "core").resolve()))  # fallback to core/ if present
sys.path.append(str(PLUGINS_DIR.resolve()))

# --- Memory manager (flat first, core/ fallback) ---
try:
    from memory_manager import (
        add_memory, add_conversation_memory,
        retrieve_conversation_memory, get_all_conversation_history
    )
    from memory_manager_gui import open_memory_manager
except ImportError:
    from core.memory_manager import (
        add_memory, add_conversation_memory,
        retrieve_conversation_memory, get_all_conversation_history
    )
    from core.memory_manager_gui import open_memory_manager

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
        learn_new_task_gui, find_best_local_match, show_task_intent_manager
    )
except Exception:
    def learn_new_task_gui(*a, **k): return "learn_new_task_gui unavailable"
    def find_best_local_match(*a, **k): return None
    def show_task_intent_manager(*a, **k): return "task_intent_manager unavailable"


# === Configuration ===
OLLAMA_MODEL = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"
MEMORY_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_memory.json")
LOG_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_log.txt")
HISTORY_DIR = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_history")
POLICY_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_policy.json")
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

# === Load Configurations ===
def load_config(path):
    try:
        return json.loads((CONFIG_DIR / path).read_text(encoding='utf-8'))
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
    top.title("Fingerprint Required")
    tk.Label(top, text="🔒 Please scan your fingerprint to proceed with this task.", font=("Segoe UI", 11)).pack(pady=10)
    tk.Button(top, text="Simulate Fingerprint", command=accept).pack(pady=10)
    top.transient(root)
    top.grab_set()
    root.wait_window(top)
    if confirmed:
        return True
    return bool(confirmed)

def speak(text):
    if engine:
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass

def confirm_by_voice(chat_area, expected_phrase="yes allow this"):
    try:
        recognizer = sr.Recognizer()
    except Exception as e:
        return False
    mic = sr.Microphone()
    try:
        with mic as source:
            chat_area.insert(tk.END, "[Voice Auth] Listening for confirmation...\n")
            chat_area.see(tk.END)
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source, timeout=2, phrase_time_limit=3)
        spoken = recognizer.recognize_google(audio, language="en-US").lower()
        return expected_phrase in spoken
    except Exception as e:
        chat_area.insert(tk.END, f"[Voice Error] {str(e)}\n")
        return False


def prompt_for_pin(root, pin_hash):
    import hashlib
    confirmed = []
    def submit_pin():
        entered = pin_entry.get()
        hashed = hashlib.sha256(entered.encode('utf-8')).hexdigest()
        if hashed == pin_hash:
            confirmed.append(True)
            top.destroy()
        else:
            messagebox.showerror("Access Denied", "Incorrect PIN.")
            top.lift()
            pin_entry.delete(0, tk.END)

    top = tk.Toplevel(root)
    top.title("PIN Required")
    tk.Label(top, text="🔑 Enter your admin PIN to continue:", font=("Segoe UI", 11)).pack(pady=10)
    pin_entry = tk.Entry(top, show="*", width=20)
    pin_entry.pack(pady=5)
    pin_entry.focus()
    tk.Button(top, text="Submit", command=submit_pin).pack(pady=5)
    top.transient(root)
    top.grab_set()
    root.wait_window(top)
    return bool(confirmed)


def ask_ollama(prompt):
    import subprocess

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.strip(),
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
        # Load persisted aliases.  These map short keywords to full commands.
        self.aliases = load_aliases()
        # Variable to control whether admin authentication is enforced for privileged tasks
        self.admin_enforce_var = tk.BooleanVar(value=policy.get("fingerprint_required", True))
        self.tts_enabled_var = tk.BooleanVar(value=identity.get("voice_enabled", False))
    def run_startup_tasks(self):
        self.build_ui()
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
                         if hasattr(mod, "run"):
                             result = mod.run()
                             self.chat_area.insert(tk.END, f"[Autorun Plugin] {plugin_name} -> {result}\n")
                             if self.tts_enabled_var.get():
                                 speak(f"{plugin_name} launched.")
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
        
        
    def handle_response(self, resp, user_req):
        """Handles AI responses, extracting actions, and managing fallback behaviors."""
        try:
            print("[LLM RAW OUTPUT]", repr(resp))  # Debug: show full raw AI response
            data = self._extract_json_from_response(resp, user_req)  # Parses AI response into JSON
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
        enforce_on_tasks = identity.get("enforce_on_tasks", [])

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
        self._log_message("Matched Task", f"Task: {task_name}, Action: {action}, Reasoning: {reasoning}")

 # Check if the task requires admin rights or is in the enforced list.
        if requires_admin or task_name in enforce_on_tasks: # This line was unindented
                self.chat_area.insert(tk.END, "[SECURITY] This task requires admin confirmation.\n")
                self._log_message("Security", f"Admin confirmation required for task: {task_name}")

        # If admin enforcement is enabled, require fingerprint/PIN/voice confirmation.
        if self.admin_enforce_var.get():
            if not show_fingerprint_prompt(self):
                self.chat_area.insert(tk.END, "[SECURITY] Fingerprint failed. Trying PIN...\n")
                pin_hash = policy.get("admin_pin_hash", "")
                if not prompt_for_pin(self, pin_hash):
                    self.chat_area.insert(tk.END, "[SECURITY] PIN failed. Trying voice...\n")
                    if not confirm_by_voice(self.chat_area):
                        self.chat_area.insert(tk.END, "[SECURITY] All authentication methods failed.\n")
                        self._log_message("Security", f"Authentication failed for task: {task_name}")
                        return
                    else:
                        self.chat_area.insert(tk.END, "[SECURITY] Voice confirmation accepted.\n")
                else:
                    self.chat_area.insert(tk.END, "[SECURITY] PIN accepted.\n")
            else:
                self.chat_area.insert(tk.END, "[SECURITY] Fingerprint accepted.\n")
        else:
            # Admin enforcement disabled; skip security prompts entirely
            self.chat_area.insert(tk.END, "[SECURITY] Admin enforcement disabled. Proceeding without confirmation.\n")

        # Execute the task if auto-execution is enabled.
        if self.auto_execute.get():
            THREAD_POOL.submit(self._execute_task, action)
        else:
            self.chat_area.insert(tk.END, "[INFO] Auto-execute is off. Command not run.\n\n")

    def _execute_task(self, cmd_action):
        """Helper method to execute a command and update status."""
        self.update_status(f"Executing: {cmd_action[:30]}...")
        # Pass the full command string through to preserve quotes/escaping
        result = run_cmd([cmd_action])
        self.after(0, lambda: self.chat_area.insert(tk.END, f"Result: {result}\n\n"))
        self.after(0, self.update_status)

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



    def run_plugin(self, plugin_module):
        plugin_name = plugin_module.__name__
        try:
            if hasattr(plugin_module, "run"):
                self.update_status(f"Running plugin: {plugin_name}...")
                try:
                    with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                        result = plugin_module.run()
                        output = buf.getvalue()
                    self._add_ai_response(f"[Plugin: {plugin_name}] Result:\n{result}")
                    if output.strip():
                        self.chat_area.insert(tk.END, f"[Plugin Output] {output.strip()}\n")
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
        plugins = self.load_plugins()
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
                    try:
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
                    THREAD_POOL.submit(self.run_plugin, plugin['module'])
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

        # --- Chat Area ---
        self.chat_area = scrolledtext.ScrolledText(
            self, state='normal', wrap=tk.WORD, font=("Consolas", 11),
            borderwidth=0, highlightthickness=0
)
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure tags for intent highlighting.  These colour different parts of
        # the [INTENT] message, making it easier to distinguish the task name,
        # command action, admin requirement, and tags.
        self.chat_area.tag_configure('intent_label', foreground='#888888', font=("Consolas", 11, 'bold'))
        self.chat_area.tag_configure('intent_task', foreground='#1E90FF', font=("Consolas", 11, 'bold'))
        self.chat_area.tag_configure('intent_action', foreground='#00AA00', font=("Consolas", 11))
        self.chat_area.tag_configure('intent_admin', foreground='#FF6347', font=("Consolas", 11))
        self.chat_area.tag_configure('intent_tag', foreground='#8A2BE2', font=("Consolas", 11, 'italic'))

        # --- Menu Bar ---
        self.auto_execute = tk.BooleanVar(value=policy.get("auto_execute_default", True))
        self.tts_enabled_var = tk.BooleanVar(value=policy.get("tts_enabled", True))
        
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
        # Memory Manager entry – view and manage stored conversation memory
        tools_menu.add_command(label="Memory Manager", command=self.show_memory_manager)
        options_menu = tk.Menu(menu_bar, tearoff=0, bg=THEMES[policy.get("theme", "Dark")]["bg"])
        menu_bar.add_cascade(label="Tools", menu=tools_menu)
        menu_bar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_checkbutton(label="Auto-Execute Matched Tasks", variable=self.auto_execute, command=self.save_policy)
        options_menu.add_checkbutton(label="Enable Text-to-Speech", variable=self.tts_enabled_var)
        # Checkbox to toggle enforcement of admin authentication (fingerprint/PIN/voice)
        options_menu.add_checkbutton(label="Enforce Admin Auth", variable=self.admin_enforce_var, command=self.save_policy)

        theme_menu = tk.Menu(options_menu, tearoff=0)
        options_menu.add_cascade(label="Theme", menu=theme_menu)
        self.theme_var = tk.StringVar(value=policy.get("theme", "Dark"))
        for theme_name in THEMES.keys():
            theme_menu.add_radiobutton(label=theme_name, variable=self.theme_var, command=lambda t=theme_name: self.set_theme(t))
        
        # --- Bottom Input Frame ---
        frame = tk.Frame(self)
        frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.entry = tk.Entry(frame, font=("Consolas", 11), relief=tk.FLAT, borderwidth=4)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.entry.bind('<Return>', lambda e: self.send_request())
        self.entry.bind('<Up>', self.on_entry_key)
        self.entry.bind('<Down>', self.on_entry_key)
        
        # Microphone button for optional voice input.  When clicked, listens
        # for a brief voice command and populates the input field.
        mic_btn = tk.Button(frame, text="🎤", command=self.record_voice, relief=tk.FLAT)
        mic_btn.pack(side=tk.RIGHT, padx=(5, 0))
        btn = tk.Button(frame, text="Send", command=self.send_request, relief=tk.FLAT)
        btn.pack(side=tk.RIGHT, padx=(5,0))

        self.apply_theme(self.theme_var.get())  # Apply theme after widgets are created
    def export_chat(self): 
        file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
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
        self.status_var.set(text)

    def report_error(self, msg):
        self.error_area.insert(tk.END, f"{msg}\n")
        self.error_area.see(tk.END)

    def apply_theme(self, theme_name):
        theme = THEMES.get(theme_name, THEMES["Dark"])
        self.config(bg=theme["bg"])
        self.chat_area.config(fg=theme["fg"], bg=theme["bg"])
        self.error_area.config(fg="red", bg=theme["bg"])
        self.status_bar.config(fg=theme["fg"], bg=theme["bg"])
        self.entry.config(fg=theme["fg"], bg=theme["entry_bg"], insertbackground=theme["fg"])
        # Save theme to policy

    def set_theme(self, theme_name):
        self.apply_theme(theme_name)
        self.save_policy(theme=theme_name)

    def save_policy(self, theme=None):
        policy["auto_execute_default"] = self.auto_execute.get()
        policy["tts_enabled"] = self.tts_enabled_var.get()
        # Persist admin enforcement flag as fingerprint_required.  When false, all admin
        # authentication will be bypassed.
        policy["fingerprint_required"] = self.admin_enforce_var.get()
        if theme:
            policy["theme"] = theme
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

            def worker():
                recent_conversation = retrieve_conversation_memory(user_req, top_n=3)
                context_str = ""
                if recent_conversation:
                    context_str = "\n--- RECENT CONVERSATION CONTEXT ---\n"
                    for mem in reversed(recent_conversation):
                        context_str += f"User: {mem['user']}\nAI: {mem['ai']}\n"
                    context_str += "--- END CONTEXT ---\n\n"

                prompt = (
                    f"{context_str}{base_context}\n\n"
                    f"User request: {user_req}\n\n"
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

                # --- DEBUG PATCH START ---
                print("[DEBUG] Raw LLM Output:\n", response)
                self.chat_area.insert(tk.END, f"\n[DEBUG] Raw AI Response:\n{response}\n\n")
                # --- DEBUG PATCH END ---

                self.after(0, self.handle_response, response, user_req)


            THREAD_POOL.submit(worker)
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
        """Extracts and loads JSON from AI response, handling markdown code blocks and fallback logic."""
        try:
            resp = resp.strip()
            if resp.startswith("```json"):
                resp = resp.replace("```json", "").strip()
            elif resp.startswith("```"):
                resp = resp.replace("```", "").strip()
            if resp.endswith("```"):
                resp = resp[:-3].strip()
            print("[FINAL CLEANED RESPONSE]", repr(resp))  # Debug
            resp = resp.strip()


            # STEP 1: Remove triple backtick wrappers like ```json ... ```
            if resp.startswith("```json"):
                resp = resp.replace("```json", "").strip()
            elif resp.startswith("```"):
                resp = resp.replace("```", "").strip()

            # Remove trailing backticks if they exist
            if resp.endswith("```"):
                resp = resp[:-3].strip()

            # Optional: see what was cleaned
            print("[FINAL CLEANED RESPONSE]", repr(resp))

            # STEP 2: Extract JSON object using regex
            json_match = re.search(r'\{.*?\}', resp, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in model response")

            raw_json = json_match.group(0)
            parsed = json.loads(raw_json)

            # STEP 3: Ensure expected keys are present
            for key in ["task_name", "action", "requires_admin"]:
                if key not in parsed:
                    raise KeyError(f"Missing key: '{key}'")

            return parsed

        except Exception as e:
            self.chat_area.insert(tk.END, f"\n[DEBUG] Raw Response Error: {e}\n{resp}\n\n")
            self._log_message("AI Response Failure", f"{e} - Raw: {resp}")

            # STEP 4: Handle fallback behavior
            fallback_msg = identity.get("fallback_behavior", {}).get("on_no_match")
            if fallback_msg:
                self.chat_area.insert(tk.END, f"AI: {fallback_msg}\n\n")
                return None

            fallback = find_best_local_match(user_req, load_config("task_intents.json"))
            if fallback:
                self._handle_matched_task({
                    "task_name": fallback["task"],
                    "action": fallback["action"],
                    "requires_admin": fallback.get("requires_admin", False),
                    "reasoning": "Matched locally from trained intents"
                }, user_req)
                return None

            raise

    def _log_message(self, tag, message):
        """Helper to log messages with AI's role for traceability."""
        full_message = f"[{identity.get('role', 'Assistant')} - {tag}] {message}"
        log_to_file(full_message)


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