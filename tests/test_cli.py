import shlex
import pytest

from igris_core import run_cmd

def test_run_shortcut_executes(monkeypatch):
    # simulate subprocess.run for a known command
    fake = pytest.MonkeyPatch()
    class Result: returncode=0; stdout="OK\n"; stderr=""
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Result())
    # now actually call run_cmd
    rc = run_cmd(shlex.split("echo hi"))
    assert rc == "OK"

def test_run_shortcut_perm_denied(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "Access is denied"
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Result())
