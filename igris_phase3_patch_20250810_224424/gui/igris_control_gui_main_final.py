import sys
from pathlib import Path
# Original large GUI omitted in this package stub; the robust import shim will be applied.
# --- Robust core import shim (added by patch) ---
try:
    from igris_core import strict_json_from_text, ask_ollama as core_ask
except Exception:
    import importlib.util
    from pathlib import Path as _P
    _ROOT = _P(__file__).resolve().parents[1]
    for candidate in [_ROOT / "igris_core.py", _ROOT / "core" / "igris_core.py", _P(__file__).with_name("igris_core.py")]:
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("igris_core", candidate)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            strict_json_from_text = mod.strict_json_from_text
            core_ask = mod.ask_ollama
            break
    else:
        raise ImportError("igris_core not found via shim")
