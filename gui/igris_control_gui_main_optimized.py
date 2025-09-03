import os
import sys
import json
import threading
import re
import shlex
import shutil
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import subprocess
from datetime import datetime, timedelta
from pathlib import Path 
from memory_manager import add_memory, add_conversation_memory, retrieve_conversation_memory, get_all_conversation_history
import psutil
import speech_recognition as sr
import pyttsx3
import importlib.util
import time
from concurrent.futures import ThreadPoolExecutor

from igris_phase2_5_patch_integrated import learn_new_task_gui, find_best_local_match, show_task_intent_manager

# === Configuration ===
OLLAMA_MODEL = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"
MEMORY_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_memory.json")
LOG_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_log.txt")
HISTORY_DIR = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_history")
POLICY_FILE = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_policy.json")
ASSISTANT_IDENTITY_FILE = Path("ai_assistant_config/assistant_identity.json")
CONFIG_DIR = Path("ai_assistant_config")
PLUGINS_DIR = Path("plugins")

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

# === Text-to-Speech ===
engine = pyttsx3.init()
engine.setProperty('rate', 150) # Adjust speaking speed here

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
    engine.say(text)
    engine.runAndWait()

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
        # Hardcoded task map for matching
        intent_prompt = """
You are Igris, an AI trained to match user requests to known Windows tasks.

Match the user input to one of the tasks below and return a response like:
{ "task_name": "...", "action": "...", "requires_admin": true }

Tasks:
- task: delete system files
  action: del /f /q C:\\Windows\\System32\\*.*
  requires_admin: true

- task: empty recycle bin
  action: PowerShell -Command "$shell = New-Object -ComObject Shell.Application; $shell.NameSpace(0xA).Items() | %%{$_.InvokeVerb('delete')}"
  requires_admin: true

- task: open word
  action: cmd /c start winword
  requires_admin: false

User request: {}
""".format(prompt.strip())

        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=intent_prompt,
            capture_output=True,
            text=True,
            timeout=30,
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
    top = tk.Toplevel()
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
        self.command_history = []
        self.history_index = None
        
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
        self.apply_theme(policy.get("theme", "Dark"))
        
    def handle_response(self, resp, user_req):
        """Handles AI responses, extracting actions, and managing fallback behaviors."""
        try:
            print("[LLM RAW OUTPUT]", repr(resp))  # Debug: show full raw AI response
            data = self._extract_json_from_response(resp, user_req)  # Parses AI response into JSON
            if data is None:
                return  # fallback message was already used

            
            if data is None:
                self.chat_area.insert(tk.END, "AI: Sorry, I couldn't match that request to any known task.")
                self._log_message("Fallback", "No matching task found.")
                return

            if "action" in data and "task_name" in data:
                self._handle_matched_task(data, user_req)
                return

        except json.JSONDecodeError:
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
        self.chat_area.insert(tk.END, "[INTENT] Task: {} | Action: {} | Admin: {}\n".format(task_name, action, requires_admin))
        self._log_message("Matched Task", f"Task: {task_name}, Action: {action}, Reasoning: {reasoning}")

 # Check if the task requires admin rights or is in the enforced list.
        if requires_admin or task_name in enforce_on_tasks: # This line was unindented
                self.chat_area.insert(tk.END, "[SECURITY] This task requires admin confirmation.\n")
                self._log_message("Security", f"Admin confirmation required for task: {task_name}")

        if policy.get("fingerprint_required", True):
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
            self.chat_area.insert(tk.END, "[SECURITY] Fingerprint not required.\n")
            self.chat_area.insert(tk.END, "[SECURITY] Confirmation failed. Task cancelled.\n\n")
            self._log_message("Security", f"Admin confirmation failed for task: {task_name}")
            return
            self.chat_area.insert(tk.END, "[SECURITY] Confirmation successful.\n")
            self._log_message("Security", f"Admin confirmation successful for task: {task_name}")

        # Execute the task if auto-execution is enabled.
        if self.auto_execute.get():
            THREAD_POOL.submit(self._execute_task, action)
        else:
            self.chat_area.insert(tk.END, "[INFO] Auto-execute is off. Command not run.\n\n")

    def _execute_task(self, cmd_action):
        """Helper method to execute a command and update status."""
        self.update_status(f"Executing: {cmd_action[:30]}...")
        result = run_cmd(shlex.split(cmd_action))
        self.after(0, lambda: self.chat_area.insert(tk.END, f"Result: {result}\n\n"))
        self.after(0, self.update_status)

    def _add_ai_response(self, text):
        """Helper method to safely add AI response to chat area."""
        self.after(0, lambda: self.chat_area.insert(tk.END, f"AI: {text}\n\n"))
        self.after(0, self.chat_area.see, tk.END)
        if self.tts_enabled_var.get():
            speak(text)

    def run_plugin(self, plugin_module):
        """Runs a plugin's 'run' function, updating the GUI safely."""
        plugin_name = plugin_module.__name__
        try:
            if hasattr(plugin_module, "run"):
                self.update_status(f"Running plugin: {plugin_name}...")
                result = plugin_module.run()
                self._add_ai_response(f"[Plugin: {plugin_name}] Result:\n{result}")
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
        tree = ttk.Treeview(top, columns=("Description",), show="headings")
        tree.heading("#1", text="Description")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        for plugin in plugins:
            tree.insert("", tk.END, iid=plugin['name'], text=plugin['name'], values=(plugin['description'],))

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
        options_menu = tk.Menu(menu_bar, tearoff=0, bg=THEMES[policy.get("theme", "Dark")]["bg"])
        menu_bar.add_cascade(label="Tools", menu=tools_menu)
        menu_bar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_checkbutton(label="Auto-Execute Matched Tasks", variable=self.auto_execute, command=self.save_policy)
        options_menu.add_checkbutton(label="Enable Text-to-Speech", variable=self.tts_enabled_var)

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
        if theme:
            policy["theme"] = theme
        Path(POLICY_FILE).write_text(json.dumps(policy, indent=2), encoding='utf-8')
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
                    "Respond ONLY with a raw JSON object. DO NOT include code blocks, markdown, triple backticks, or explanation text.\n"
                    "Just output something like this:\n\n"
                    '{\n'
                    '  "task_name": "...",\n'
                    '  "action": "...",\n'
                    '  "requires_admin": false,\n'
                    '  "reasoning": "User wants to open the calculator app." \n'
                    '}\n'
                    "No extra commentary, headers, or markdown blocks."
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
        else:
            self.chat_area.insert(tk.END, f"[INFO] Unknown command: {command}. Available commands: /history, /clear\n\n")
        self.chat_area.see(tk.END)

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
        log_to_file(f"DAILY CHECKUP:\n{report}")
    
    def _extract_json_from_response(self, resp, user_req):
        """Extracts and loads JSON from AI response, handling markdown code blocks and fallback logic."""
        try:
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
