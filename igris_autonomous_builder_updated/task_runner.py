import json
import os

TASK_FILE = "task_list.json"
MODULE_DIR = "modules"

def load_tasks():
    with open(TASK_FILE, "r") as f:
        return json.load(f)

def save_tasks(tasks):
    with open(TASK_FILE, "w") as f:
        json.dump(tasks, f, indent=4)

def mock_ai_response(prompt):
    # Simulated AI generation
    return f"# Code generated for: {prompt}\nprint(\"{prompt}\")"

def run_tasks():
    tasks = load_tasks()
    for task in tasks:
        if not task["done"]:
            print(f"Running: {task['name']}")
            code = mock_ai_response(task["prompt"])
            module_path = os.path.join(MODULE_DIR, f"{task['name']}.py")
            with open(module_path, "w") as f:
                f.write(code)
            task["done"] = True
    save_tasks(tasks)
    print("All tasks completed.")

if __name__ == "__main__":
    run_tasks()
