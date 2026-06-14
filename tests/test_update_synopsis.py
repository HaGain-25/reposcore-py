from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "tools" / "update-synopsis.py"
spec = importlib.util.spec_from_file_location("update_synopsis", SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None

update_synopsis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_synopsis)


def test_capture_cli_help_reports_all_failed_candidates(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run(command, **kwargs):
        if command[0] == sys.executable:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="ModuleNotFoundError: No module named 'typer'\n",
            )

        raise FileNotFoundError("No such file or directory: 'reposcore'")

    monkeypatch.setattr(update_synopsis.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        update_synopsis.capture_cli_help()

    message = str(exc_info.value)

    assert "CLI 도움말을 생성하지 못했습니다" in message
    assert "main.py --help" in message
    assert "ModuleNotFoundError: No module named 'typer'" in message
    assert "reposcore --help" in message
    assert "No such file or directory: 'reposcore'" in message
