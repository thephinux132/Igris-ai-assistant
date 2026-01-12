"""
automation_scheduler_setup.py

A GUI utility to list, add, and delete scheduled tasks using Windows Task Scheduler.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import subprocess
import shlex
try:
    from core.secure_execution import safe_run_command
    from core.input_validation import InputValidator
    SECURE_MODULES = True
except ImportError:
    SECURE_MODULES = False


def run_schtasks_command(cmd: str) -> tuple[int, str, str]:
    """Execute schtasks command securely."""
    if SECURE_MODULES:
        validator = InputValidator(strict_mode=True)
        is_valid, error = validator.validate_user_input(cmd)
        if not is_valid:
            return 1, "", f"[BLOCKED] {error}"
        try:
            cmd_parts = shlex.split(cmd)
            if cmd_parts and cmd_parts[0].lower() != "schtasks":
                return 1, "", "[BLOCKED] Only schtasks commands allowed"
            result = safe_run_command(cmd_parts, timeout=30)
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, "", f"[ERROR] {e}"
    else:
        # Fallback
        proc = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return proc.returncode, proc.stdout, proc.stderr

def list_tasks():
    returncode, stdout, stderr = run_schtasks_command("schtasks /Query /FO LIST /V")
    return stdout if returncode == 0 else stderr

def add_task(task_name, time, command):
    returncode, stdout, stderr = run_schtasks_command(
        f'schtasks /Create /SC DAILY /TN "{task_name}" /TR "{command}" /ST {time} /F'
    )
    return stdout if returncode == 0 else stderr

def delete_task(task_name):
    returncode, stdout, stderr = run_schtasks_command(f'schtasks /Delete /TN "{task_name}" /F')
    return stdout if returncode == 0 else stderr

def run():
    root = tk.Toplevel()
    root.title("Task Scheduler Control")
    root.geometry("700x600")

    output = tk.Text(root, wrap=tk.WORD, font=("Consolas", 10))
    output.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

    def refresh_tasks():
        output.delete("1.0", tk.END)
        output.insert(tk.END, list_tasks())

    def create_task():
        name = simpledialog.askstring("Task Name", "Enter task name:", parent=root)
        time = simpledialog.askstring("Start Time", "Enter time (HH:MM):", parent=root)
        command = simpledialog.askstring("Command", "Enter full command or script:", parent=root)
        if name and time and command:
            result = add_task(name, time, command)
            messagebox.showinfo("Result", result)
            refresh_tasks()

    def remove_task():
        name = simpledialog.askstring("Delete Task", "Enter exact task name to delete:", parent=root)
        if name:
            result = delete_task(name)
            messagebox.showinfo("Result", result)
            refresh_tasks()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=5)

    tk.Button(btn_frame, text="Refresh Task List", command=refresh_tasks).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Create New Task", command=create_task).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Delete Task", command=remove_task).pack(side=tk.LEFT, padx=5)

    refresh_tasks()
    return "Task Scheduler GUI launched."
