import json
import os
import subprocess

TASK_FILE = "task_list.json"
MODULE_DIR = "modules"
OLLAMA_MODEL = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"  # Adjust if you change your model

def load_tasks():
    if not os.path.exists(TASK_FILE):
        print(f"[ERROR] {TASK_FILE} not found.")
        return []
    with open(TASK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=4)

def call_ollama(prompt):
    try:
        full_prompt = f"Write a working Python script that does the following task. Do not include explanations or markdown.\nTask: {prompt}"
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=60
            encoding='utf-8', # <--- Force UTF-8 decoding
            errors='replace'  # <--- Replace unknown characters instead of crashing
        )
        if result.returncode != 0:
            return f"# Ollama error: {result.stderr.strip()}"
        return result.stdout.strip()
    except Exception as e:
        return f"# Exception occurred: {e}"

def run_tasks():
    tasks = load_tasks()
    os.makedirs(MODULE_DIR, exist_ok=True)

    for task in tasks:
        if not task.get("done", False):
            print(f"[+] Running: {task['name']}")
            script_code = call_ollama(task["prompt"])
            module_path = os.path.join(MODULE_DIR, f"{task['name']}.py")
            with open(module_path, "w", encoding="utf-8") as f:
                f.write(script_code)
            task["done"] = True
            print(f"[✓] Saved to: {module_path}")

    save_tasks(tasks)
    print("\n[✔] All tasks processed.")

if __name__ == "__main__":
    run_tasks()
