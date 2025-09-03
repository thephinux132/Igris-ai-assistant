import os
import sys
import json
import time
import argparse
import psutil
import subprocess
from memory_manager import retrieve_relevant, add_memory

# Constants
OLLAMA_MODEL = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"  # Ollama model
POLL_INTERVAL = 3600               # Seconds between checks
MEMORY_FILE = os.path.expanduser(r"~\OneDrive\Documents\ai_memory.json")

# Helper Functions
def run_cmd(cmd):
    """
    Run a CLI command and return its stdout or an error string.
    """
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False
        )
    except FileNotFoundError:
        return f"[ERROR] command not found: {cmd[0]}"

    out = proc.stdout.decode('utf-8', errors='replace').strip()
    err = proc.stderr.decode('utf-8', errors='replace').strip()

    if proc.returncode != 0:
        return f"[ERROR] {' '.join(cmd)} returned {proc.returncode}: {err}"
    return out

def ask_ollama(prompt_text):
    """
    Run `ollama run <MODEL>` feeding the prompt via stdin.
    """
    try:
        proc = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt_text.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except FileNotFoundError:
        sys.exit("[FATAL] `ollama` CLI not found. Is it on your PATH?")

    out = proc.stdout.decode('utf-8', errors='replace').strip()
    err = proc.stderr.decode('utf-8', errors='replace').strip()

    if proc.returncode != 0:
        sys.exit(f"[FATAL] Ollama returned {proc.returncode}: {err}")

    return out

def collect_performance_metrics():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")

    # Top 3 processes by CPU
    procs = sorted(
        psutil.process_iter(['name','cpu_percent']),
        key=lambda p: p.info['cpu_percent'], reverse=True
    )[:3]
    top = "\n".join(f"{p.info['name']} – {p.info['cpu_percent']}%" for p in procs)

    return {
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_used_mb": mem.used // (1024**2),
        "memory_total_mb": mem.total // (1024**2),
        "disk_percent_used": disk.percent,
        "disk_free_gb": disk.free // (1024**3),
        "disk_total_gb": disk.total // (1024**3),
        "top_processes": top
    }

def collect_security_metrics():
    fw = run_cmd(["netsh", "advfirewall", "show", "allprofiles"])
    try:
        svc = psutil.win_service_get("WinDefend")
        defender = f"WinDefend service is {svc.status()}"
    except Exception as e:
        defender = f"[ERROR] Could not query Defender service: {e}"
    bl_raw = run_cmd(["manage-bde", "-status", "C:"])
    if bl_raw.startswith("[ERROR]"):
        bitlocker = "C: is not encrypted (BitLocker disabled or not accessible)"
    else:
        bitlocker = bl_raw
    hotfixes = run_cmd(["wmic", "qfe", "get", "HotFixID"])
    lines = [l for l in hotfixes.splitlines() if l.strip()]
    hotfix_count = max(len(lines) - 1, 0)
    return {
        "firewall": fw,
        "defender": defender,
        "bitlocker": bitlocker,
        "hotfix_count": hotfix_count
    }

def format_summary(perf, sec):
    return (
        "=== Performance Metrics ===\n"
        f"CPU load: {perf['cpu_percent']}%\n"
        f"Memory: {perf['memory_percent']}% used ({perf['memory_used_mb']}MB/{perf['memory_total_mb']}MB)\n"
        f"Disk C:\\ used: {perf['disk_percent_used']}% ({perf['disk_free_gb']}GB free of {perf['disk_total_gb']}GB)\n"
        f"Top CPU processes:\n{perf['top_processes']}\n\n"
        "=== Security Metrics ===\n"
        f"Firewall status:\n{sec['firewall']}\n\n"
        f"{sec['defender']}\n\n"
        f"BitLocker (C:):\n{sec['bitlocker']}\n\n"
        f"Installed hotfixes: {sec['hotfix_count']}\n"
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="System Status AI with custom requests")
    parser.add_argument(
        '-r', '--request',
        action='append',
        help='Additional free-form request to include in the AI prompt'
    )
    args = parser.parse_args()
    additional_requests = args.request or []

    while True:
        perf = collect_performance_metrics()
        sec = collect_security_metrics()
        raw_summary = format_summary(perf, sec)

        # Retrieve relevant past memories
        mems = retrieve_relevant(raw_summary)
        mem_block = ""
        if mems:
            mem_block = "### Past memories relevant to this report:\n"
            for m in mems:
                mem_block += f"- [{m['timestamp']}] {m['entry']}\n"
            mem_block += "\n"

        # Include any additional user requests
        req_block = ""
        if additional_requests:
            req_block = "### Additional requests:\n"
            for req in additional_requests:
                req_block += f"- {req}\n"
            req_block += "\n"

        # Construct full prompt
        prompt = (
            "System status report (Windows 11):\n\n"
            f"{mem_block}"
            f"{raw_summary}\n"
            f"{req_block}"
            "Please give me prioritized, concrete steps to:\n"
            "1. Improve performance (CPU, RAM, disk)\n"
            "2. Harden security (patching, firewall, malware protection, encryption)\n"
        )

        # Send to Ollama and print advice
        print("→ Sending prompt to Ollama…")
        advice = ask_ollama(prompt)
        print(f"\n[{time.ctime()}] AI advice:\n{advice}\n{'='*60}\n")

        # Store the first line of advice into memory
        first_line = advice.splitlines()[0] if advice else ""
        if first_line:
            add_memory(f"Followed advice: {first_line}")

        time.sleep(POLL_INTERVAL)
