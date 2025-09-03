"""
Igris Suggestion Engine (Phase 6)

This engine provides context-aware suggestions for the next action to take.
It analyzes the user's plugin history and prioritizes suggestions based on
the current context (e.g., 'CODING', 'BROWSING') as determined by the
proactive_context_agent.
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta

# This path should be consistent with where your other modules (like the logger)
# are saving the memory file.
MEMORY_FILE = Path.home() / "OneDrive" / "Documents" / "ai_memory.json"

# How far back/forward to look for a context when associating with a plugin event.
CONTEXT_WINDOW_MINUTES = 5

def get_suggestion(last_plugin_name: str):
    """
    Suggests the next plugin to run based on historical patterns and current context.

    1. Determines the user's current context from memory.
    2. Analyzes plugin execution history to find which plugin most frequently
       follows `last_plugin_name`.
    3. Prioritizes suggestions relevant to the current context.
    4. Falls back to non-contextual suggestions if no specific pattern is found.

    Returns:
        A dictionary with suggestion details, or None.
    """
    if not MEMORY_FILE.exists():
        return None

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as f:
            memory = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    plugin_history = memory.get("plugin_history", [])
    # The proactive agent logs to 'general_memory' via memory_manager.
    # We assume it logs entries like {"timestamp": "...", "entry": "CONTEXT_UPDATE: ..."}
    general_memory = memory.get("general_memory", [])

    if not plugin_history or len(plugin_history) < 2:
        return None  # Not enough data to find a pattern

    # 1. Determine Current Context
    current_context = "IDLE"  # Default context
    context_updates = [
        item for item in general_memory
        if isinstance(item, dict) and "entry" in item and item["entry"].startswith("CONTEXT_UPDATE:")
    ]

    if context_updates:
        latest_update = max(context_updates, key=lambda x: x.get("timestamp", ""))
        current_context = latest_update["entry"].split(":", 1)[1].strip()

    # 2. Build a Context-Aware Transition Model: (context, prev_plugin) -> Counter of next_plugins
    transitions = defaultdict(Counter)
    sorted_contexts = sorted(
        [(datetime.fromisoformat(c["timestamp"]), c["entry"].split(":", 1)[1].strip())
         for c in context_updates if "timestamp" in c],
        key=lambda x: x[0]
    )

    def get_context_for_timestamp(ts: datetime) -> str:
        active_context = "IDLE"
        for context_ts, context_name in reversed(sorted_contexts):
            if context_ts <= ts:
                if (ts - context_ts) < timedelta(minutes=CONTEXT_WINDOW_MINUTES):
                    return context_name
                break
        return active_context

    for i in range(len(plugin_history) - 1):
        prev_item, next_item = plugin_history[i], plugin_history[i+1]
        prev_plugin, next_plugin, ts_str = prev_item.get("plugin_name"), next_item.get("plugin_name"), prev_item.get("timestamp")

        if not all([prev_plugin, next_plugin, ts_str]): continue

        try:
            context = get_context_for_timestamp(datetime.fromisoformat(ts_str))
            transitions[(context, prev_plugin)][next_plugin] += 1
        except (ValueError, TypeError): continue

    # 3. Generate a Suggestion
    # Priority 1: A frequent follower in the CURRENT context
    contextual_key = (current_context, last_plugin_name)
    if contextual_key in transitions and transitions[contextual_key]:
        suggestion, count = transitions[contextual_key].most_common(1)[0]
        if suggestion != last_plugin_name:
            return {"plugin_name": suggestion, "suggestion": f"In '{current_context}' mode, run '{suggestion}'?", "reason": f"It followed '{last_plugin_name}' {count} time(s) in this context."}

    # Priority 2: A frequent follower in ANY context
    all_context_transitions = Counter()
    for (ctx, prev), next_counts in transitions.items():
        if prev == last_plugin_name: all_context_transitions.update(next_counts)

    if all_context_transitions:
        suggestion, count = all_context_transitions.most_common(1)[0]
        if suggestion != last_plugin_name:
            return {"plugin_name": suggestion, "suggestion": f"Run '{suggestion}' next?", "reason": f"It often follows '{last_plugin_name}' ({count} time(s) across all contexts)."}

    return None