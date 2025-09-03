"""
automation_scheduler_setup.py

A GUI utility to list, add, and delete scheduled tasks using Windows Task Scheduler.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import subprocess


def run_schtasks_command(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return proc.stdout.strip() if proc.returncode == 0 else proc.stderr.strip()
    except Exception as e:
        return f"[ERROR] {str(e)}"

def list_tasks():
    return run_schtasks_command("schtasks /Query /FO LIST /V")

def add_task(task_name, time, command):
    return run_schtasks_command(
        f'schtasks /Create /SC DAILY /TN "{task_name}" /TR "{command}" /ST {time} /F'
    )

def delete_task(task_name):
    return run_schtasks_command(f'schtasks /Delete /TN "{task_name}" /F')

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
