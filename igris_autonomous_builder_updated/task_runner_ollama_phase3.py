import json
import os
import subprocess

TASK_FILE = "task_list.json"
MODULE_DIR = "modules"
OLLAMA_MODEL = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"  # Change to your model ID if different

def load_tasks():
    with open(TASK_FILE, "r") as f:
        return json.load(f)

def save_tasks(tasks):
    with open(TASK_FILE, "w") as f:
        json.dump(tasks, f, indent=4)

def call_ollama(prompt):
    try:
        full_prompt = f"Write a working Python script that does the following task. Do not include explanations or markdown.\n"
        f"Task: {prompt}"
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=60
            encoding='utf-8',           # ← Add this
            errors='replace'            # ← Add this to skip unreadable characters
        )
        if result.returncode != 0:
            return f"# Ollama error: {result.stderr.strip()}"
        return result.stdout.strip()
    except Exception as e:
        return f"# Exception occurred: {e}"

def run_tasks():
    tasks = load_tasks()
    for task in tasks:
        if not task["done"]:
            print(f"Running: {task['name']}")
            code = call_ollama(task["prompt"])
            module_path = os.path.join(MODULE_DIR, f"{task['name']}.py")
            with open(module_path, "w", encoding="utf-8") as f:
                f.write(code)
            task["done"] = True
    save_tasks(tasks)
    print("All tasks completed.")

if __name__ == "__main__":
    run_tasks()

# === BATCH: PHASE 3 COMPLETION PROMPTS ===

# 🔒 Encrypt audit output
# Prompt 1:
# Encrypt the output of run_security_audit.py using Fernet and save it to audit_results.enc.
# Add secure key generation, storage, and decryption instructions.

# 🔍 Convert scan_weak_services.py to plugin
# Prompt 2:
# Wrap scan_weak_services.py into a valid Igris plugin with a run() function and proper docstring.
# Return summary of weak services found.

# ⚠️ Anomaly Monitor Plugin
# Prompt 3:
# Create a plugin that scans for unsigned processes, suspicious startup entries, and known malware indicators.
# Output suspicious findings in a secure log.

# 🧠 Plugin Execution Logger
# Prompt 4:
# Write a plugin that logs every plugin execution (name, timestamp) to ai_memory.json for later analysis.

# 🔄 Plugin → Task Intent Registrar
# Prompt 5:
# Build a plugin that scans the /plugins directory for all .py files, extracts the plugin name and docstring,
# and appends entries to task_intents.json with default trigger phrases.