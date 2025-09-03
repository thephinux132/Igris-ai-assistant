
"""
Minimal shim: example of how the GUI should import shared pieces from igris_core.
Keeps GUI aligned with CLI for auth + identity loading. Real GUI code should call:
  - load_assistant_identity(...)
  - authenticate_admin() via enforce_admin_then(...)
  - ask_ollama(...) for model calls
"""
from igris_core import load_assistant_identity, ask_ollama, enforce_admin_then
