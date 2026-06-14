from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cache_manager import save_cache
from calc_score import UserContributionCounts
from main import _is_cache_valid, app

runner = CliRunner()


def _fresh_metadata() -> dict:
    generated_at = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    return {
        "repository": "oss2026hnu/reposcore-py",
        "owner": "oss2026hnu",
        "name": "reposcore-py",
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "since": None,
        "until": None,
    }


@pytest.mark.parametrize("value", [0, None, [], "invalid cache", 1.5, True])
def test_is_cache_valid_rejects_non_dict_root(value):
    assert _is_cache_valid(value, None, None) is False


@pytest.mark.parametrize(
    "contributions",
    [5, "oops", {"user": "a"}, [1, 2], [{"user": "a"}, 3]],
)
def test_is_cache_valid_rejects_bad_contributions(contributions):
    data = {"metadata": _fresh_metadata(), "contributions": contributions}
    assert _is_cache_valid(data, None, None) is False


def test_is_cache_valid_accepts_well_formed_cache():
    data = {
        "metadata": _fresh_metadata(),
        "contributions": [{"user": "a", "feature_bug_pr_count": 1}],
    }
    assert _is_cache_valid(data, None, None) is True


def _write_cache(tmp_path: Path, raw: str) -> None:
    cache_file = tmp_path / "oss2026hnu_reposcore-py" / "cache.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text(raw, encoding="utf-8")


@pytest.mark.parametrize(
    "raw",
    [
        "0",
        "null",
        "[]",
        '"invalid cache"',
        '{"metadata": {}, "contributions": 5}',
        '{"metadata": {}, "contributions": "oops"}',
        '{"metadata": {}, "contributions": {"user": "a"}}',
        '{"metadata": {}, "contributions": [1, 2]}',
    ],
)
def test_malformed_cache_refetches_without_crash(tmp_path, raw):
    _write_cache(tmp_path, raw)
    fake = [UserContributionCounts(user="carol", feature_bug_pr_count=2)]
    with patch("main.fetch_contributions", return_value=fake) as mock_fetch:
        result = runner.invoke(
            app,
            ["oss2026hnu/reposcore-py", "--token", "dummy", "--output", str(tmp_path)],
        )
    assert result.exit_code == 0
    mock_fetch.assert_called_once()


def test_valid_metadata_with_bad_contribution_refetches(tmp_path):
    # 구조(list[dict])는 통과하지만 user 누락으로 Pydantic 검증 실패 → 재조회
    cache_file = tmp_path / "oss2026hnu_reposcore-py" / "cache.json"
    save_cache(
        cache_file,
        {"metadata": _fresh_metadata(), "contributions": [{"feature_bug_pr_count": 1}]},
    )
    fake = [UserContributionCounts(user="carol", feature_bug_pr_count=2)]
    with patch("main.fetch_contributions", return_value=fake) as mock_fetch:
        result = runner.invoke(
            app,
            ["oss2026hnu/reposcore-py", "--token", "dummy", "--output", str(tmp_path)],
        )
    assert result.exit_code == 0
    mock_fetch.assert_called_once()
