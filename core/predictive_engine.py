#!/usr/bin/env python3
"""
Predictive Task Engine for Igris
Learns user patterns and suggests actions.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class ActionRecord:
    action: str
    target: str
    timestamp: str
    day_of_week: int  # 0=Monday
    hour: int
    success: bool = True

@dataclass
class Suggestion:
    action: str
    target: str
    confidence: float
    reason: str

class PatternStore:
    """Persistent storage for user patterns."""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or Path(__file__).parent.parent / "data" / "user_patterns.json"
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        """Load patterns from disk."""
        if self.data_path.exists():
            try:
                return json.loads(self.data_path.read_text())
            except Exception as e:
                logger.error(f"Failed to load patterns: {e}")

        return {
            "actions": [],
            "frequencies": {},
            "time_patterns": {},
            "sequences": [],
            "last_updated": None
        }

    def save(self):
        """Save patterns to disk."""
        with self.lock:
            self.data["last_updated"] = datetime.now().isoformat()
            try:
                self.data_path.write_text(json.dumps(self.data, indent=2))
            except Exception as e:
                logger.error(f"Failed to save patterns: {e}")

    def add_action(self, record: ActionRecord):
        """Record an action."""
        with self.lock:
            # Store recent actions (keep last 1000)
            self.data["actions"].append(asdict(record))
            if len(self.data["actions"]) > 1000:
                self.data["actions"] = self.data["actions"][-1000:]

            # Update frequency counts
            key = f"{record.action}:{record.target}"
            self.data["frequencies"][key] = self.data["frequencies"].get(key, 0) + 1

            # Update time patterns
            time_key = f"{record.day_of_week}:{record.hour}"
            if time_key not in self.data["time_patterns"]:
                self.data["time_patterns"][time_key] = {}
            self.data["time_patterns"][time_key][key] = \
                self.data["time_patterns"][time_key].get(key, 0) + 1

        # Save periodically (every 10 actions)
        if len(self.data["actions"]) % 10 == 0:
            self.save()

class PredictiveEngine:
    """Predicts and suggests user actions based on patterns."""

    def __init__(self, store: Optional[PatternStore] = None):
        self.store = store or PatternStore()
        self.min_confidence = 0.3
        self.recent_actions: List[str] = []  # For sequence tracking

    def record_action(
        self,
        action: str,
        target: str,
        success: bool = True
    ):
        """
        Record a user action for learning.

        Args:
            action: Action type (open, query, system, etc.)
            target: Action target
            success: Whether action succeeded
        """
        now = datetime.now()
        record = ActionRecord(
            action=action,
            target=target,
            timestamp=now.isoformat(),
            day_of_week=now.weekday(),
            hour=now.hour,
            success=success
        )

        self.store.add_action(record)

        # Track recent sequence
        key = f"{action}:{target}"
        self.recent_actions.append(key)
        if len(self.recent_actions) > 5:
            self.recent_actions.pop(0)

        logger.debug(f"Recorded action: {action} {target}")

    def get_suggestions(self, limit: int = 3) -> List[Suggestion]:
        """
        Get suggested actions based on current context.

        Args:
            limit: Maximum suggestions to return

        Returns:
            List of Suggestion objects
        """
        suggestions = []

        # Time-based suggestions
        time_suggestions = self._suggest_by_time()
        suggestions.extend(time_suggestions)

        # Frequency-based suggestions
        freq_suggestions = self._suggest_by_frequency()
        suggestions.extend(freq_suggestions)

        # Sequence-based suggestions
        seq_suggestions = self._suggest_by_sequence()
        suggestions.extend(seq_suggestions)

        # Deduplicate and sort by confidence
        seen = set()
        unique = []
        for s in sorted(suggestions, key=lambda x: x.confidence, reverse=True):
            key = f"{s.action}:{s.target}"
            if key not in seen:
                seen.add(key)
                unique.append(s)

        return unique[:limit]

    def _suggest_by_time(self) -> List[Suggestion]:
        """Suggest based on time patterns."""
        now = datetime.now()
        time_key = f"{now.weekday()}:{now.hour}"

        suggestions = []
        patterns = self.store.data.get("time_patterns", {}).get(time_key, {})

        if patterns:
            # Get top actions for this time
            sorted_actions = sorted(
                patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]

            total = sum(patterns.values())
            for action_key, count in sorted_actions:
                action, target = action_key.split(":", 1)
                confidence = min(count / total, 0.9)

                if confidence >= self.min_confidence:
                    suggestions.append(Suggestion(
                        action=action,
                        target=target,
                        confidence=confidence,
                        reason=f"Usually done at this time ({count} times)"
                    ))

        return suggestions

    def _suggest_by_frequency(self) -> List[Suggestion]:
        """Suggest most frequent actions."""
        suggestions = []
        frequencies = self.store.data.get("frequencies", {})

        if frequencies:
            total = sum(frequencies.values())
            sorted_actions = sorted(
                frequencies.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            for action_key, count in sorted_actions:
                action, target = action_key.split(":", 1)
                confidence = min((count / total) * 2, 0.7)  # Cap at 0.7

                if confidence >= self.min_confidence:
                    suggestions.append(Suggestion(
                        action=action,
                        target=target,
                        confidence=confidence,
                        reason=f"Frequently used ({count} times)"
                    ))

        return suggestions

    def _suggest_by_sequence(self) -> List[Suggestion]:
        """Suggest based on action sequences."""
        suggestions = []

        if len(self.recent_actions) < 2:
            return suggestions

        # Look for patterns in stored actions
        actions = self.store.data.get("actions", [])
        if len(actions) < 10:
            return suggestions

        # Find what typically follows recent actions
        last_action = self.recent_actions[-1]
        following = defaultdict(int)

        for i, record in enumerate(actions[:-1]):
            key = f"{record['action']}:{record['target']}"
            if key == last_action:
                next_record = actions[i + 1]
                next_key = f"{next_record['action']}:{next_record['target']}"
                following[next_key] += 1

        if following:
            total = sum(following.values())
            for action_key, count in sorted(following.items(), key=lambda x: x[1], reverse=True)[:2]:
                action, target = action_key.split(":", 1)
                confidence = min(count / total, 0.8)

                if confidence >= self.min_confidence:
                    suggestions.append(Suggestion(
                        action=action,
                        target=target,
                        confidence=confidence,
                        reason=f"Often follows your last action"
                    ))

        return suggestions

    def get_stats(self) -> Dict[str, Any]:
        """Get learning statistics."""
        data = self.store.data
        return {
            "total_actions": len(data.get("actions", [])),
            "unique_actions": len(data.get("frequencies", {})),
            "time_patterns": len(data.get("time_patterns", {})),
            "last_updated": data.get("last_updated")
        }


# Convenience functions
_engine = None

def get_engine() -> PredictiveEngine:
    global _engine
    if _engine is None:
        _engine = PredictiveEngine()
    return _engine

def record(action: str, target: str, success: bool = True):
    """Record an action."""
    get_engine().record_action(action, target, success)

def suggest(limit: int = 3) -> List[Suggestion]:
    """Get suggestions."""
    return get_engine().get_suggestions(limit)


# Self-test
if __name__ == "__main__":
    print("Predictive Engine Test")
    print("=" * 50)

    engine = PredictiveEngine()

    # Simulate some usage patterns
    print("\nSimulating user actions...")

    test_actions = [
        ("open", "notepad"),
        ("open", "chrome"),
        ("query", "time"),
        ("open", "notepad"),
        ("open", "vscode"),
        ("open", "chrome"),
        ("query", "status"),
        ("open", "notepad"),
        ("open", "chrome"),
        ("open", "notepad"),
    ]

    for action, target in test_actions:
        engine.record_action(action, target)

    print(f"Recorded {len(test_actions)} actions")

    # Get statistics
    stats = engine.get_stats()
    print(f"\nStatistics:")
    print(f"  Total actions: {stats['total_actions']}")
    print(f"  Unique actions: {stats['unique_actions']}")

    # Get suggestions
    print("\nSuggestions:")
    suggestions = engine.get_suggestions(limit=5)
    for s in suggestions:
        print(f"  [{s.confidence:.2f}] {s.action} {s.target}")
        print(f"         {s.reason}")

    # Save data
    engine.store.save()
    print(f"\nPatterns saved to: {engine.store.data_path}")
