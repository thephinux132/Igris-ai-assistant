import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import subprocess
import shlex
try:
    from core.secure_execution import safe_run_command
    from core.input_validation import InputValidator
    SECURE_MODULES = True
except ImportError:
    SECURE_MODULES = False

def run_cmd(cmd: str) -> tuple[int, str, str]:
    """Execute command securely."""
    if SECURE_MODULES:
        validator = InputValidator(strict_mode=True)
        is_valid, error = validator.validate_user_input(cmd)
        if not is_valid:
            return 1, "", f"[BLOCKED] {error}"
        try:
            cmd_parts = shlex.split(cmd)
            result = safe_run_command(cmd_parts, timeout=30)
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, "", f"[ERROR] {e}"
    else:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return result.returncode, result.stdout, result.stderr

def build_command(name, command, schedule, time, modifier=None, days=None):
    base = f'schtasks /Create /TN "{name}" /TR "{command}" /ST {time} /F'

    if schedule == "Daily":
        return f"{base} /SC DAILY"
    elif schedule == "Weekly":
        days_flag = f"/D {','.join(days)}" if days else ""
        return f"{base} /SC WEEKLY {days_flag}"
    elif schedule == "Minutes" or schedule == "Hours":
        unit = "MINUTE" if schedule == "Minutes" else "HOURLY"
        return f"{base} /SC {unit} /MO {modifier}"
    else:
        return None

def run():
    root = tk.Toplevel()
    root.title("Visual Task Scheduler")
    root.geometry("600x500")

    tk.Label(root, text="Task Name:").pack(pady=3)
    task_name = tk.Entry(root)
    task_name.pack(fill=tk.X, padx=10)

    tk.Label(root, text="Command / Script:").pack(pady=3)
    path_frame = tk.Frame(root)
    path_frame.pack(fill=tk.X, padx=10)
    task_path = tk.Entry(path_frame)
    task_path.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Button(path_frame, text="Browse", command=lambda: task_path.insert(0, filedialog.askopenfilename())).pack(side=tk.LEFT, padx=5)

    tk.Label(root, text="Start Time (HH:MM):").pack(pady=3)
    start_time = tk.Entry(root)
    start_time.insert(0, "02:00")
    start_time.pack(fill=tk.X, padx=10)

    tk.Label(root, text="Frequency:").pack(pady=3)
    freq_var = tk.StringVar(value="Daily")
    freq_menu = ttk.Combobox(root, textvariable=freq_var, values=["Daily", "Weekly", "Minutes", "Hours"], state="readonly")
    freq_menu.pack(fill=tk.X, padx=10)

    modifier_frame = tk.Frame(root)
    modifier_var = tk.IntVar(value=5)
    tk.Label(modifier_frame, text="Every:").pack(side=tk.LEFT)
    tk.Spinbox(modifier_frame, from_=1, to=1440, textvariable=modifier_var, width=5).pack(side=tk.LEFT)
    modifier_frame.pack(fill=tk.X, padx=10, pady=5)
    modifier_frame.pack_forget()

    days_frame = tk.Frame(root)
    days_vars = {}
    for day in ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]:
        var = tk.BooleanVar()
        days_vars[day] = var
        tk.Checkbutton(days_frame, text=day, variable=var).pack(side=tk.LEFT)
    days_frame.pack(fill=tk.X, padx=10)
    days_frame.pack_forget()

    def update_fields(*args):
        freq = freq_var.get()
        modifier_frame.pack_forget()
        days_frame.pack_forget()
        if freq in ["Minutes", "Hours"]:
            modifier_frame.pack(fill=tk.X, padx=10, pady=5)
        elif freq == "Weekly":
            days_frame.pack(fill=tk.X, padx=10, pady=5)

    freq_var.trace_add("write", update_fields)

    def create_task():
        name = task_name.get().strip()
        cmd = task_path.get().strip()
        time_val = start_time.get().strip()
        freq = freq_var.get()
        modifier = modifier_var.get()
        selected_days = [day for day, var in days_vars.items() if var.get()]

        if not (name and cmd and time_val):
            messagebox.showerror("Missing Info", "Task name, command, and time are required.")
            return

        sch_cmd = build_command(name, cmd, freq, time_val, modifier, selected_days)
        if sch_cmd:
            returncode, stdout, stderr = run_cmd(sch_cmd)
            result = stdout if returncode == 0 else stderr
            messagebox.showinfo("Result", result)
        else:
            messagebox.showerror("Invalid", "Could not build scheduling command.")

    tk.Button(root, text="Create Task", command=create_task).pack(pady=10)
    return "Visual Task Scheduler launched."