""" 
alert_on_new_hosts.py

Scans for new hosts on the local network using the robust network_scanner plugin.
Logs timestamped alerts to ai_script_log.txt and notifies via popup + voice.
"""

import json
import os
from pathlib import Path
from tkinter import messagebox, Tk
try:
    import pyttsx3
except ImportError:
    pyttsx3 = None
from datetime import datetime
import time

# Import the superior scanning function from our existing plugin
try:
    from plugins.network_scanner import scan_subnet
except ImportError:
    # Provide a dummy function if network_scanner can't be imported,
    # so this plugin doesn't crash the whole system.
    def scan_subnet(*args, **kwargs):
        print("[ERROR] Could not import network_scanner.py. Host detection is disabled.")
        return []

KNOWN_HOSTS_FILE = Path("ai_assistant_config/known_hosts.json")
LOG_FILE = Path(os.path.expanduser("~")) / "OneDrive" / "Documents" / "ai_script_log.txt"

def get_current_hosts():
    """Uses the network_scanner plugin to get a reliable list of hosts."""
    try:
        # scan_subnet returns a list of dicts, e.g., [{'ip': ..., 'mac': ...}]
        # We only care about the MAC addresses for identifying unique devices.
        return {host['mac'] for host in scan_subnet()}
    except Exception as e:
        print(f"[alert_on_new_hosts] Error during network scan: {e}")
        return set()

def load_known_hosts():
    """Loads known MAC addresses from the JSON file."""
    try:
        if KNOWN_HOSTS_FILE.exists():
            return set(json.loads(KNOWN_HOSTS_FILE.read_text(encoding='utf-8')))
    except Exception:
        return set()

def save_known_hosts(hosts):
    """Saves a set of MAC addresses to the JSON file."""
    try:
        KNOWN_HOSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        KNOWN_HOSTS_FILE.write_text(json.dumps(sorted(list(hosts)), indent=2), encoding='utf-8')
    except Exception as e:
        print(f"[alert_on_new_hosts] Error saving known hosts: {e}")

def speak(msg):
    try:
        engine = pyttsx3.init() if pyttsx3 else None
        if not engine: return
        engine.say(msg)
        engine.runAndWait()
    except:
        pass

def popup(msg):
    try:
        root = Tk()
        root.withdraw()
        messagebox.showinfo("Igris Alert", msg)
        root.destroy()
    except:
        pass

def log_event(entry):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [NEW_HOST_ALERT] {entry}\n"
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_msg)
    except:
        pass

def run_once():
    known_macs = load_known_hosts()
    current_macs = get_current_hosts()
    
    new_macs = current_macs - known_macs
    
    if new_macs:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_msg = f"⚠️ New device(s) detected @ {ts}:\n" + "\n".join(new_macs)
        speak("Warning, a new device has been detected on your network.")
        popup(alert_msg)
        # Add the new devices to our known list and save it
        save_known_hosts(known_macs.union(new_macs))
        log_event(f"New MACs: {', '.join(new_macs)}")
        return alert_msg
    else:
        return "No new devices detected on the network."

def run():
    # For persistent mode, loop every 2 minutes. Otherwise just run once.
    PERSISTENT = False  # Change to True if background task manager will launch this
    if not PERSISTENT:
        return run_once()
    while True:
        run_once()
        time.sleep(120)  # 2 min delay
