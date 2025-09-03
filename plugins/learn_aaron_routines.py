"""
Learns Aaron's Routines Plugin
- Analyzes plugin execution history from ai_memory.json.
- Identifies the most frequently used tools and suggests potential automations.
"""
import json
from pathlib import Path
from collections import Counter

# Unify the data source to be the same as the logger.
MEMORY_FILE = Path.home() / "OneDrive" / "Documents" / "ai_memory.json"
TOP_N_PLUGINS = 3

def run():
    if not MEMORY_FILE.exists():
        return "No AI memory file found. Cannot analyze routines yet."

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as f:
            memory = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return f"[ERROR] Could not read AI memory file: {e}"

    plugin_history = memory.get("plugin_history", [])
    if not plugin_history:
        return "No plugin usage history found to analyze."

    # Count the occurrences of each plugin
    plugin_counts = Counter(item['plugin_name'] for item in plugin_history if 'plugin_name' in item)

    # Sort plugins by execution count in descending order
    sorted_plugins = plugin_counts.most_common(TOP_N_PLUGINS)

    report = ["Analysis of Your Routines:"]
    
    if not sorted_plugins:
        return "No plugin usage data to analyze."

    # Report on the most used plugins
    report.append("\nYour most frequently used tools are:")
    for i, (plugin_name, count) in enumerate(sorted_plugins):
        report.append(f"  {i+1}. {plugin_name.replace('_', ' ')} (used {count} times)")

    # Suggest a potential automation (simulated for now)
    if len(sorted_plugins) > 0:
        most_used_plugin = sorted_plugins[0][0]
        report.append(f"\n[Suggestion] You use '{most_used_plugin.replace('_', ' ')}' often. "
                      "Would you like to create a shortcut or schedule it to run automatically?")

    return "\n".join(report)

if __name__ == "__main__":
    # For testing, let's create a dummy profile file
    dummy_memory = {
        "plugin_history": [
            {"plugin_name": "network_scanner", "timestamp": "2023-10-27T10:00:00Z"},
            {"plugin_name": "harden_os", "timestamp": "2023-10-26T15:30:00Z"},
            {"plugin_name": "run_security_audit", "timestamp": "2023-10-27T11:00:00Z"},
            {"plugin_name": "network_scanner", "timestamp": "2023-10-27T10:01:00Z"},
            {"plugin_name": "network_scanner", "timestamp": "2023-10-27T10:02:00Z"},
            {"plugin_name": "run_security_audit", "timestamp": "2023-10-27T11:01:00Z"},
        ]
    }
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(dummy_memory, f, indent=2)
    
    print(run())
    
    # Clean up the dummy file
    MEMORY_FILE.unlink()
