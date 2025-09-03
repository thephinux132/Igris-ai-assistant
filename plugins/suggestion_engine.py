"""
Suggestion Engine (Phase 5)
- Takes the last executed plugin as input.
- Queries the pattern_analyzer to find the most likely next plugin.
- Formulates a user-facing suggestion.
"""

try:
    # Import the analysis functions from our other new plugin
    from plugins.pattern_analyzer import find_command_sequences, load_plugin_history
except ImportError:
    # Provide dummy functions if pattern_analyzer is not available for isolated testing
    def find_command_sequences(history):
        # Simulate a known pattern for testing
        return {('run_security_audit', 'encrypt_audit_output'): 2}

    def load_plugin_history():
        print("[WARN] suggestion_engine using simulated history.")
        return [
            {'plugin_name': 'run_security_audit', 'timestamp': '...'},
            {'plugin_name': 'encrypt_audit_output', 'timestamp': '...'},
            {'plugin_name': 'run_security_audit', 'timestamp': '...'},
            {'plugin_name': 'encrypt_audit_output', 'timestamp': '...'},
        ]

# --- Configuration ---
# How many times a sequence must occur to be considered a suggestion-worthy pattern.
MINIMUM_OCCURRENCE_THRESHOLD = 2

def get_suggestion(last_plugin_run: str):
    """
    Analyzes history to suggest the next command.

    Args:
        last_plugin_run (str): The name of the plugin that just finished executing.

    Returns:
        dict: A dictionary containing the suggested plugin and a formatted
              suggestion string, or None if no suggestion is found.
              e.g., {'suggestion': "Run 'encrypt_audit_output' next?", 'plugin_name': 'encrypt_audit_output'}
    """
    history = load_plugin_history()
    if not history:
        return None

    sequences = find_command_sequences(history)
    if not sequences:
        return None

    # Find the most common plugin that follows the last_plugin_run
    most_likely_next_plugin = None
    highest_count = 0

    for (p1, p2), count in sequences.items():
        if p1 == last_plugin_run and count >= MINIMUM_OCCURRENCE_THRESHOLD:
            if count > highest_count:
                highest_count = count
                most_likely_next_plugin = p2

    if most_likely_next_plugin:
        # Format the suggestion for the user
        suggestion_text = f"You often run '{most_likely_next_plugin}' after this. Run it now?"
        return {
            "suggestion": suggestion_text,
            "plugin_name": most_likely_next_plugin
        }

    return None

def run():
    """A simple test harness for the suggestion engine."""
    last_command = "run_security_audit"
    print(f"[TEST] Simulating run of: '{last_command}'")
    suggestion = get_suggestion(last_command)
    if suggestion:
        return (f"Suggestion found:\n"
                f"  - Text: {suggestion['suggestion']}\n"
                f"  - Action: plugin:{suggestion['plugin_name']}")
    else:
        return "No suggestion found for the last command."

if __name__ == "__main__":
    print(run())