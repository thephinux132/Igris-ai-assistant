"""
Pattern Analyzer Plugin (Phase 5)
- Analyzes plugin_history from ai_memory.json to find common command sequences.
- Identifies pairs of plugins executed within a short time window.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

# --- Configuration ---
# This path should be consistent with where plugin_execution_logger saves its data.
MEMORY_FILE = Path.home() / "OneDrive" / "Documents" / "ai_memory.json"
# Time window to consider two commands as a sequence (in seconds)
SEQUENCE_WINDOW_SECONDS = 120  # 2 minutes

def load_plugin_history():
    """Loads the plugin execution history from the memory file."""
    if not MEMORY_FILE.exists():
        return []
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        # The logger stores history under the 'plugin_history' key
        return data.get("plugin_history", [])
    except (json.JSONDecodeError, IOError) as e:
        print(f"[ERROR] Could not load or parse memory file: {e}")
        return []

def find_command_sequences(history):
    """
    Analyzes the plugin history to find pairs of commands executed
    sequentially within the defined time window.
    """
    sequences = []
    # Sort history by timestamp just in case it's not ordered
    try:
        # The logger uses ISO format strings for timestamps
        sorted_history = sorted(history, key=lambda x: datetime.fromisoformat(x['timestamp']))
    except (KeyError, TypeError):
        return Counter()

    for i in range(len(sorted_history) - 1):
        first_event = sorted_history[i]
        second_event = sorted_history[i+1]

        try:
            t1 = datetime.fromisoformat(first_event['timestamp'])
            t2 = datetime.fromisoformat(second_event['timestamp'])
            plugin1 = first_event['plugin_name']
            plugin2 = second_event['plugin_name']
        except (KeyError, TypeError):
            continue # Skip malformed entries

        if plugin1 == plugin2:
            continue

        if (t2 - t1) <= timedelta(seconds=SEQUENCE_WINDOW_SECONDS):
            sequences.append((plugin1, plugin2))

    return Counter(sequences)

def run():
    """Main entry point for the plugin."""
    print("[INFO] Analyzing plugin execution history for common patterns...")
    history = load_plugin_history()
    if not history or len(history) < 2:
        return "Not enough plugin history to analyze for patterns."

    sequences = find_command_sequences(history)
    if not sequences:
        return "No command sequences found within the time window."

    report = ["--- Common Command Sequences ---"]
    for (plugin1, plugin2), count in sequences.most_common(5):
        report.append(f"'{plugin1}' -> '{plugin2}' (occurred {count} times)")

    return "\n".join(report)

if __name__ == "__main__":
    print(run())