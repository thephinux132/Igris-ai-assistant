
"""
IGRIS OS - PHASE 2.5 INTEGRATED PATCH
Features:
1. /learn command for dynamic task training
2. Fallback to local task intent match if LLM fails
3. GUI Task Intent Manager for full control
"""

import tkinter as tk
from tkinter import simpledialog, messagebox, Toplevel, ttk
import difflib
import json
from pathlib import Path

TASK_INTENTS_FILE = Path("ai_assistant_config/task_intents.json")

def load_task_intents():
    try:
        return json.loads(TASK_INTENTS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {"tasks": []}

def save_task_intents(data):
    with open(TASK_INTENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def find_best_local_match(user_input, task_data):
    from difflib import SequenceMatcher
    best = None
    highest = 0.5  # Only match if similarity > 50%
    for task in task_data.get("tasks", []):
        for phrase in task.get("phrases", []):
            score = SequenceMatcher(None, user_input.lower(), phrase.lower()).ratio()
            if score > highest:
                highest = score
                best = task
    return best

def learn_new_task_gui(root):
    data = load_task_intents()

    phrase = simpledialog.askstring("Learn New Command", "Enter the phrase you want Igris to recognize:", parent=root)
    if not phrase:
        return

    action = simpledialog.askstring("Command Action", "Enter the command to execute for this phrase:", parent=root)
    if not action:
        return

    admin = messagebox.askyesno("Admin Rights", "Does this command require admin privileges?")

    # Check if this task exists
    existing = None
    for task in data["tasks"]:
        if action == task["action"]:
            existing = task
            break

    if existing:
        if phrase not in existing["phrases"]:
            existing["phrases"].append(phrase)
    else:
        data["tasks"].append({
            "task": phrase.strip().lower(),
            "phrases": [phrase],
            "action": action,
            "requires_admin": admin
        })

    save_task_intents(data)
    messagebox.showinfo("Success", f"Phrase '{phrase}' has been saved and will now be recognized.")

def show_task_intent_manager(root):
    data = load_task_intents()

    top = Toplevel(root)
    top.title("Task Intent Manager")
    top.geometry("700x400")
    tree = ttk.Treeview(top, columns=("Task", "Phrases", "Action", "Admin"), show="headings")
    tree.heading("Task", text="Task")
    tree.heading("Phrases", text="Phrases")
    tree.heading("Action", text="Action")
    tree.heading("Admin", text="Admin")
    tree.pack(fill=tk.BOTH, expand=True)

    def refresh_tree():
        for row in tree.get_children():
            tree.delete(row)
        for task in data["tasks"]:
            tree.insert("", tk.END, values=(task["task"], ", ".join(task["phrases"]), task["action"], str(task["requires_admin"])))

    def delete_selected():
        selected = tree.focus()
        if not selected:
            return
        item = tree.item(selected)
        task_name = item["values"][0]
        data["tasks"] = [t for t in data["tasks"] if t["task"] != task_name]
        save_task_intents(data)
        refresh_tree()

    def add_task():
        learn_new_task_gui(top)
        refresh_tree()

    refresh_tree()
    btns = tk.Frame(top)
    btns.pack()
    tk.Button(btns, text="Add Task", command=add_task).pack(side=tk.LEFT, padx=5)
    tk.Button(btns, text="Delete Task", command=delete_selected).pack(side=tk.LEFT, padx=5)
    tk.Button(btns, text="Close", command=top.destroy).pack(side=tk.RIGHT, padx=5)
