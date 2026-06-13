from __future__ import annotations

import pytest
from gql.transport.exceptions import TransportQueryError, TransportServerError
from typer.testing import CliRunner

from main import app

runner = CliRunner()

BASE_ARGS = ["oss2026hnu/reposcore-py", "--token", "dummy"]


def _patch_loader(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """_load_or_fetch_contributions가 지정한 예외만 던지도록 교체합니다."""

    def _raise(*args, **kwargs):
        raise error

    monkeypatch.setattr("main._load_or_fetch_contributions", _raise)


def _server_error(code: int) -> TransportServerError:
    return TransportServerError("server error", code)


def _combined_output(result) -> str:
    output = result.output or ""
    try:
        output += result.stderr or ""
    except (ValueError, AttributeError):
        pass
    return output


def test_transport_query_error_exits_3(monkeypatch: pytest.MonkeyPatch):
    _patch_loader(monkeypatch, TransportQueryError("repo not found"))
    result = runner.invoke(app, BASE_ARGS)
    assert result.exit_code == 3
    assert "저장소를 찾을 수 없습니다" in _combined_output(result)


def test_transport_server_error_403_exits_2(monkeypatch: pytest.MonkeyPatch):
    _patch_loader(monkeypatch, _server_error(403))
    result = runner.invoke(app, BASE_ARGS)
    assert result.exit_code == 2
    assert "Rate Limit" in _combined_output(result)


def test_transport_server_error_429_exits_2(monkeypatch: pytest.MonkeyPatch):
    _patch_loader(monkeypatch, _server_error(429))
    result = runner.invoke(app, BASE_ARGS)
    assert result.exit_code == 2
    assert "Rate Limit" in _combined_output(result)


def test_transport_server_error_401_exits_4(monkeypatch: pytest.MonkeyPatch):
    _patch_loader(monkeypatch, _server_error(401))
    result = runner.invoke(app, BASE_ARGS)
    assert result.exit_code == 4
    assert "인증에 실패" in _combined_output(result)


def test_transport_server_error_500_exits_1(monkeypatch: pytest.MonkeyPatch):
    _patch_loader(monkeypatch, _server_error(500))
    result = runner.invoke(app, BASE_ARGS)
    assert result.exit_code == 1
    assert "HTTP 오류" in _combined_output(result)


def test_generic_exception_exits_1(monkeypatch: pytest.MonkeyPatch):
    _patch_loader(monkeypatch, RuntimeError("unexpected"))
    result = runner.invoke(app, BASE_ARGS)
    assert result.exit_code == 1
    assert "오류" in _combined_output(result)
