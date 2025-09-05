"""
Handles different LLM implementations for Igris.

The purpose of this module is to provide a swappable backend for the AI models used
in the Igris project. This way the application can use different models easily.
"""

from abc import ABC, abstractmethod
from pathlib import Path
import json

try:
    # Optional imports; keep GUI resilient if modules are missing
    from ai.router import AIRouter
    from ai.policy_defaults import AIRouterPolicy
except Exception:
    AIRouter = None  # type: ignore
    AIRouterPolicy = None  # type: ignore

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
        return core_ask(prompt)


class RoutedLLMHandler(LLMHandler):
    """
    Policy-driven LLM router that can choose between local and remote backends.

    Falls back to local-only if routing modules are unavailable.
    """

    def __init__(self, remote_llm_fn=None):
        # Local LLM via existing core implementation
        from igris_core import ask_ollama as core_ask

        self._use_router = AIRouter is not None

        # If no remote is provided, default to local callable (acts as pass-through)
        self._remote = remote_llm_fn or core_ask
        self._local = core_ask

        if self._use_router:
            # Load policy (optional)
            policy_path = Path('ai_assistant_config/policy.json')
            policy_dict = {}
            try:
                if policy_path.exists():
                    policy_dict = json.loads(policy_path.read_text(encoding='utf-8'))
            except Exception:
                policy_dict = {}

            router_policy = None
            if AIRouterPolicy is not None and isinstance(policy_dict.get('ai_router'), dict):
                try:
                    # Construct policy via loader in ai.policy_defaults
                    from ai.policy_defaults import load_policy_from_dict
                    router_policy = load_policy_from_dict(policy_dict['ai_router'])
                except Exception:
                    router_policy = None

            self._router = AIRouter(
                local_llm=self._local,
                remote_llm=self._remote,
                policy=router_policy,
            )
        else:
            self._router = None

    def ask_ollama(self, prompt: str) -> str:
        if self._router is None:
            # Router not available; use local LLM
            return self._local(prompt)
        return self._router.ask(prompt)
