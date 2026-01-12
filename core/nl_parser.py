#!/usr/bin/env python3
"""
Natural Language Parser for Igris
Uses local LLM (Ollama) for intent parsing.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import subprocess

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

@dataclass
class ParsedIntent:
    action: str
    target: str
    args: List[str]
    confidence: float
    requires_approval: bool
    raw_response: str = ""

class OllamaClient:
    """Client for Ollama local LLM API."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if Ollama is running."""
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return resp.status_code == 200
        except:
            return False

    def generate(
        self,
        prompt: str,
        model: str = "llama3.2:3b",
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 150,
        timeout: int = 10
    ) -> Optional[str]:
        """Generate completion from Ollama."""
        if not self.available:
            return None

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=timeout
            )

            if resp.status_code == 200:
                return resp.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")

        return None

    def list_models(self) -> List[str]:
        """List available models."""
        if not self.available:
            return []

        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return [m.get("name", "") for m in models]
        except:
            pass

        return []

class NLParser:
    """Natural language intent parser."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "nl_prompts.yaml"
        self.client = OllamaClient()
        self.system_prompt = ""
        self.examples = []
        self.settings = {}
        self._load_config()

        # Fallback patterns for when LLM unavailable
        self.fallback_patterns = self._build_fallback_patterns()

    def _load_config(self):
        """Load parser configuration."""
        if not YAML_AVAILABLE or not self.config_path.exists():
            self._load_defaults()
            return

        try:
            config = yaml.safe_load(self.config_path.read_text())
            self.system_prompt = config.get("system_prompt", "")
            self.examples = config.get("examples", [])
            self.settings = config.get("settings", {})
            logger.info("NL parser config loaded")
        except Exception as e:
            logger.error(f"Failed to load NL config: {e}")
            self._load_defaults()

    def _load_defaults(self):
        """Load default configuration."""
        self.system_prompt = "Parse user request into JSON with action, target, args."
        self.examples = []
        self.settings = {
            "model": "llama3.2:3b",
            "temperature": 0.1,
            "max_tokens": 150,
            "timeout": 10
        }

    def _build_fallback_patterns(self) -> List[tuple]:
        """Build regex patterns for fallback parsing."""
        return [
            # Open/launch apps
            (r"(?:open|launch|start|run)\s+(\w+)", "open", None, False),

            # System commands
            (r"(?:shut\s*down|power\s*off)", "system", "shutdown", True),
            (r"(?:restart|reboot)", "system", "restart", True),
            (r"(?:lock|lock\s*screen)", "system", "lock", False),
            (r"(?:sleep|hibernate)", "system", "sleep", False),

            # Queries
            (r"(?:what(?:'s| is) the )?time", "query", "time", False),
            (r"(?:battery|power)\s*(?:status|level)?", "query", "battery", False),
            (r"(?:disk|storage)\s*(?:space|usage)?", "query", "disk", False),
            (r"(?:memory|ram)\s*(?:usage)?", "query", "memory", False),
            (r"(?:system\s*)?status", "query", "status", False),

            # File operations
            (r"(?:list|show)\s+files?\s*(?:in\s+)?(\S+)?", "file", "list", False),
            (r"(?:create|make)\s+(?:folder|directory)\s+(\S+)", "file", "mkdir", False),
        ]

    def is_available(self) -> bool:
        """Check if LLM parsing is available."""
        return self.client.available

    def parse(self, user_input: str) -> ParsedIntent:
        """
        Parse natural language input into structured intent.

        Args:
            user_input: Natural language request

        Returns:
            ParsedIntent with action, target, args
        """
        user_input = user_input.strip()

        # Try LLM parsing first
        if self.client.available:
            result = self._parse_with_llm(user_input)
            if result and result.confidence > 0.5:
                return result

        # Fall back to pattern matching
        return self._parse_with_patterns(user_input)

    def _parse_with_llm(self, user_input: str) -> Optional[ParsedIntent]:
        """Parse using local LLM."""
        # Build few-shot prompt
        examples_text = "\n".join([
            f"Input: {ex['input']}\nOutput: {json.dumps(ex['output'])}"
            for ex in self.examples[:3]
        ])

        prompt = f"""Examples:
{examples_text}

Input: {user_input}
Output:"""

        response = self.client.generate(
            prompt=prompt,
            model=self.settings.get("model", "llama3.2:3b"),
            system=self.system_prompt,
            temperature=self.settings.get("temperature", 0.1),
            max_tokens=self.settings.get("max_tokens", 150),
            timeout=self.settings.get("timeout", 10)
        )

        if not response:
            return None

        # Parse JSON from response
        try:
            # Extract JSON from response
            json_match = re.search(r'\{{[^{{}}]+\}}', response)
            if json_match:
                data = json.loads(json_match.group())
                return ParsedIntent(
                    action=data.get("action", "unknown"),
                    target=data.get("target", ""),
                    args=data.get("args", []),
                    confidence=float(data.get("confidence", 0.8)),
                    requires_approval=data.get("requires_approval", False),
                    raw_response=response
                )
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse LLM response: {response}")

        return None

    def _parse_with_patterns(self, user_input: str) -> ParsedIntent:
        """Parse using regex patterns (fallback)."""
        user_lower = user_input.lower()

        for pattern, action, default_target, requires_approval in self.fallback_patterns:
            match = re.search(pattern, user_lower)
            if match:
                # Extract target from match group if available
                target = default_target
                if match.groups():
                    target = match.group(1) or default_target

                return ParsedIntent(
                    action=action,
                    target=target or "",
                    args=[],
                    confidence=0.7,  # Lower confidence for pattern match
                    requires_approval=requires_approval
                )

        # No match
        return ParsedIntent(
            action="unknown",
            target=user_input,
            args=[],
            confidence=0.0,
            requires_approval=False
        )

    def get_available_models(self) -> List[str]:
        """Get list of available Ollama models."""
        return self.client.list_models()


# Convenience functions
_parser = None

def get_parser() -> NLParser:
    global _parser
    if _parser is None:
        _parser = NLParser()
    return _parser

def parse(text: str) -> ParsedIntent:
    """Parse natural language text."""
    return get_parser().parse(text)


# Self-test
if __name__ == "__main__":
    print("Natural Language Parser Test")
    print("=" * 50)

    parser = NLParser()
    print(f"Ollama available: {parser.is_available()}")

    if parser.is_available():
        models = parser.get_available_models()
        print(f"Available models: {models}")

    test_inputs = [
        "open notepad",
        "what's the time",
        "restart the computer",
        "show me disk usage",
        "list files in downloads",
        "lock my computer",
        "do something weird",
    ]

    print("\nTest parsing:")
    print("-" * 50)

    for text in test_inputs:
        result = parser.parse(text)
        status = "LLM" if parser.is_available() and result.confidence > 0.7 else "Pattern"
        print(f"\n[{status}] \"{text}\" ")
        print(f"  Action: {result.action}")
        print(f"  Target: {result.target}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Approval: {result.requires_approval}")
