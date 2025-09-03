import psutil
import json, hashlib
import pytest
from igris_core import run_cmd, respond_with_review

def test_run_cmd_success(mocker):
    fake = mocker.Mock(returncode=0, stdout="OK\n", stderr="")
    mocker.patch("subprocess.run", return_value=fake)
    assert run_cmd(["echo","hi"]) == "OK"

def test_run_cmd_perm_denied(mocker):
    fake = mocker.Mock(returncode=1, stdout="", stderr="Access is denied")
    mocker.patch("subprocess.run", return_value=fake)
    out = run_cmd(["locked_file"])
    assert "Access is denied" in out


def test_respond_with_review_cpu(monkeypatch):
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval: 12.3)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: FakeMem(percent=45))
    monkeypatch.setattr(psutil, "disk_usage", lambda path: FakeDisk(percent=55.5, free=2*(1024**3), total=10*(1024**3)))

