import json
import pytest
from igris_cli import handle_request

ADMIN_CFG = {
    "tasks": [
        {"task": "secret", "action": "echo top_secret", "requires_admin": True}
    ]
}

def test_admin_gate_blocks(monkeypatch):
    monkeypatch.setattr("igris_core.authenticate_admin", lambda: False)
    out = handle_request("secret", ADMIN_CFG, policy={}, debug=False)
    assert "Admin authentication failed" in out

def test_admin_gate_allows(monkeypatch):
    monkeypatch.setattr("igris_core.authenticate_admin", lambda: True)
    # Now the direct-run shortcut path:
    out = handle_request("run echo top_secret", ADMIN_CFG, policy={}, debug=False)
    assert "▶ Running: echo top_secret" in out
    assert "top_secret" in out
