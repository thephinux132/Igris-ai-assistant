"""
Handles different LLM implementations for Igris.

The purpose of this module is to provide a swappable backend for the AI models used
in the Igris project. This way the application can use different models easily.
"""

from abc import ABC, abstractmethod

class LLMHandler(ABC):
    """
    Abstract base class for language model handlers.
    """
    @abstractmethod
    def ask_ollama(self, prompt: str) -> str:
        """
        Abstract method to prompt the LLM model.

        Args:
            prompt (str): The prompt to send to the model.

        Returns:
            str: The response from the model.
        """
        pass

class CoreLLMHandler(LLMHandler):
    """Implementation using igris_core or core.igris_core."""
    def ask_ollama(self, prompt: str) -> str:
        from igris_core import ask_ollama as core_ask