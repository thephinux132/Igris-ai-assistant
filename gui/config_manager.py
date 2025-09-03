import os
import json
from pathlib import Path

# Configuration-related constants and functions

class ConfigManager:
    """
    Handles loading and managing configuration files.
    """
    def __init__(self, root_dir: Path, config_filename: str = "ai_assistant_config"):
        self.root_dir = root_dir
        self.config_dir = root_dir / config_filename
        self.task_intents_file = self.config_dir / "task_intents.json"
        self.aliases_file = self.config_dir / "aliases.json"
        self.assistant_identity_file = self.config_dir / "assistant_identity.json"
        self.policy_file = os.path.expanduser(r"~\\OneDrive\\Documents\\ai_script_policy.json")

    def load_config(self, path: Path) -> dict:
        """Load a JSON configuration file."""
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def load_aliases(self) -> dict:
        """Load user-defined command aliases from a JSON file."""
        try:
            data = json.loads(self.aliases_file.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except FileNotFoundError:
            return {} # It's okay if the file doesn't exist yet
        except json.JSONDecodeError as e:
            print(f"[WARN] Could not parse aliases file {self.aliases_file}: {e}")
        except Exception as e:
            # Catch other potential I/O errors
            print(f"[WARN] Failed to load aliases from {self.aliases_file}: {e}")
        return {}

    def save_aliases(self, aliases: dict) -> None:
        """Persist user-defined command aliases to disk."""
        try:
            self.aliases_file.parent.mkdir(parents=True, exist_ok=True)
            self.aliases_file.write_text(json.dumps(aliases, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"[WARN] Failed to save aliases: {e}")

    def load_identity_and_initialize(self) -> dict:
        if not self.assistant_identity_file.exists():
            return {}
        try:
            return json.loads(self.assistant_identity_file.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}