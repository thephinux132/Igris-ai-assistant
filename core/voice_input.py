#!/usr/bin/env python3
"""
Voice Input Module for Igris
Provides speech recognition and voice command processing.
"""

import logging
import re
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
import queue

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    logger.info("speech_recognition not available - install SpeechRecognition")

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

class VoiceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    ERROR = "error"

@dataclass
class VoiceCommand:
    text: str
    confidence: float
    action: Optional[str] = None
    target: Optional[str] = None
    requires_approval: bool = False

@dataclass
class CommandMatch:
    action: str
    target: str
    requires_approval: bool
    matched_trigger: str
    similarity: float

class VoiceInputManager:
    """Manages voice input and command recognition."""

    def __init__(self, config_path: Optional[Path] = None):
        self.available = SR_AVAILABLE
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "voice_commands.yaml"
        self.state = VoiceState.IDLE
        self.recognizer = None
        self.microphone = None
        self.wake_words: List[str] = ["igris"]
        self.commands: List[dict] = []
        self.settings: dict = {}
        self.command_queue: queue.Queue = queue.Queue()
        self.callbacks: Dict[str, Callable] = {}
        self._listening_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        if self.available:
            self._init_recognizer()
        self._load_config()

    def _init_recognizer(self):
        """Initialize speech recognizer."""
        self.recognizer = sr.Recognizer()
        try:
            self.microphone = sr.Microphone()
            # Calibrate for ambient noise
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            logger.info("Microphone initialized")
        except Exception as e:
            logger.error(f"Microphone initialization failed: {e}")
            self.available = False

    def _load_config(self):
        """Load voice command configuration."""
        if not YAML_AVAILABLE or not self.config_path.exists():
            self._load_defaults()
            return

        try:
            config = yaml.safe_load(self.config_path.read_text())
            self.wake_words = config.get("wake_words", ["igris"])
            self.commands = config.get("commands", [])
            self.settings = config.get("settings", {})
            logger.info(f"Loaded {len(self.commands)} voice commands")
        except Exception as e:
            logger.error(f"Failed to load voice config: {e}")
            self._load_defaults()

    def _load_defaults(self):
        """Load default configuration."""
        self.wake_words = ["igris"]
        self.commands = [
            {"triggers": ["open notepad"], "action": "open", "target": "notepad"},
            {"triggers": ["system status"], "action": "query", "target": "status"},
        ]
        self.settings = {"timeout": 5, "confirmation_required": True}

    def is_available(self) -> bool:
        """Check if voice input is available."""
        return self.available and self.microphone is not None

    def listen_once(self, timeout: int = None) -> Optional[VoiceCommand]:
        """
        Listen for a single voice command.

        Args:
            timeout: Max seconds to listen (default from config)

        Returns:
            VoiceCommand if recognized, None otherwise
        """
        if not self.is_available():
            logger.warning("Voice input not available")
            return None

        timeout = timeout or self.settings.get("timeout", 5)
        self.state = VoiceState.LISTENING

        try:
            with self.microphone as source:
                logger.debug("Listening...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=10
                )

            self.state = VoiceState.PROCESSING

            # Try Google Speech Recognition (free, no API key)
            try:
                text = self.recognizer.recognize_google(
                    audio,
                    language=self.settings.get("language", "en-US")
                )
                logger.info(f"Recognized: {text}")

                # Parse command
                command = self._parse_command(text)
                self.state = VoiceState.IDLE
                return command

            except sr.UnknownValueError:
                logger.debug("Speech not understood")
            except sr.RequestError as e:
                logger.error(f"Recognition service error: {e}")

        except sr.WaitTimeoutError:
            logger.debug("Listen timeout")
        except Exception as e:
            logger.error(f"Listen error: {e}")
            self.state = VoiceState.ERROR

        self.state = VoiceState.IDLE
        return None

    def _parse_command(self, text: str) -> VoiceCommand:
        """Parse spoken text into a command."""
        text_lower = text.lower().strip()

        # Remove wake word if present
        for wake in self.wake_words:
            if text_lower.startswith(wake):
                text_lower = text_lower[len(wake):].strip()
                break

        # Find matching command
        match = self._find_command_match(text_lower)

        if match:
            return VoiceCommand(
                text=text,
                confidence=match.similarity,
                action=match.action,
                target=match.target,
                requires_approval=match.requires_approval
            )

        # No match - return raw text
        return VoiceCommand(text=text, confidence=0.0)

    def _find_command_match(self, text: str) -> Optional[CommandMatch]:
        """Find best matching command for text."""
        best_match = None
        best_score = 0.0

        for cmd in self.commands:
            for trigger in cmd.get("triggers", []):
                score = self._similarity(text, trigger.lower())
                if score > best_score and score > 0.6:  # 60% threshold
                    best_score = score
                    best_match = CommandMatch(
                        action=cmd.get("action", ""),
                        target=cmd.get("target", ""),
                        requires_approval=cmd.get("requires_approval", False),
                        matched_trigger=trigger,
                        similarity=score
                    )

        return best_match

    def _similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two strings."""
        # Simple word overlap scoring
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def listen_for_wake_word(self, callback: Callable[[VoiceCommand], None]):
        """
        Start background listening for wake word.

        Args:
            callback: Function to call when command recognized
        """
        if not self.is_available():
            logger.warning("Voice input not available")
            return

        self._stop_event.clear()
        self._listening_thread = threading.Thread(
            target=self._background_listen,
            args=(callback,),
            daemon=True
        )
        self._listening_thread.start()
        logger.info("Background listening started")

    def _background_listen(self, callback: Callable):
        """Background listening loop."""
        while not self._stop_event.is_set():
            command = self.listen_once(timeout=2)

            if command and command.text:
                text_lower = command.text.lower()

                # Check for wake word
                wake_detected = any(
                    wake in text_lower
                    for wake in self.wake_words
                )

                if wake_detected:
                    logger.info(f"Wake word detected: {command.text}")
                    callback(command)

    def stop_listening(self):
        """Stop background listening."""
        self._stop_event.set()
        if self._listening_thread:
            self._listening_thread.join(timeout=2)
        logger.info("Background listening stopped")

    def register_callback(self, action: str, callback: Callable):
        """Register callback for specific action type."""
        self.callbacks[action] = callback

    def execute_command(self, command: VoiceCommand) -> Tuple[bool, str]:
        """
        Execute a voice command.

        Returns:
            (success, message)
        """
        if not command.action:
            return False, "No action recognized"

        # Check approval
        if command.requires_approval:
            if self.settings.get("confirmation_required", True):
                print(f"\n⚠️  Command requires approval: {command.action} {command.target}")
                confirm = input("Approve? [y/N]: ").strip().lower()
                if confirm not in ('y', 'yes'):
                    return False, "Command not approved"

        # Find callback
        callback = self.callbacks.get(command.action)
        if callback:
            try:
                result = callback(command.target)
                return True, str(result)
            except Exception as e:
                return False, f"Execution error: {e}"

        return False, f"No handler for action: {command.action}"


# Convenience functions
_manager = None

def get_voice_manager() -> VoiceInputManager:
    global _manager
    if _manager is None:
        _manager = VoiceInputManager()
    return _manager

def listen() -> Optional[VoiceCommand]:
    """Listen for a voice command."""
    return get_voice_manager().listen_once()

def is_voice_available() -> bool:
    """Check if voice input is available."""
    return get_voice_manager().is_available()


# Self-test
if __name__ == "__main__":
    print("Voice Input Module Test")
    print("=" * 40)
    print(f"SpeechRecognition available: {SR_AVAILABLE}")

    manager = VoiceInputManager()
    print(f"Voice input available: {manager.is_available()}")
    print(f"Wake words: {manager.wake_words}")
    print(f"Commands loaded: {len(manager.commands)}")

    if manager.is_available():
        print("\nSay something (5 second timeout)...")
        command = manager.listen_once()
        if command:
            print(f"\nRecognized: {command.text}")
            print(f"Confidence: {command.confidence:.2f}")
            print(f"Action: {command.action}")
            print(f"Target: {command.target}")
        else:
            print("No speech detected")
    else:
        print("\nVoice input not available. Install:")
        print("  pip install SpeechRecognition pyaudio")
