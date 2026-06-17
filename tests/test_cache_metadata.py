from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from typer.testing import CliRunner

from cache_manager import load_cache, save_cache
from calc_score import UserContributionCounts
from main import CACHE_TTL_SECONDS, app

runner = CliRunner()


def _generated_at(seconds_ago: int = 0) -> str:
    return (
        (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def test_cache_includes_metadata(tmp_path):
    fake = [UserContributionCounts(user="alice", feature_bug_pr_count=1)]
    with patch("main.fetch_contributions", return_value=fake):
        result = runner.invoke(
            app,
            ["oss2026hnu/reposcore-py", "--token", "dummy", "--output", str(tmp_path)],
        )
    assert result.exit_code == 0

    data = json.loads(
        (tmp_path / "oss2026hnu_reposcore-py" / "cache.json").read_text("utf-8")
    )
    meta = data["metadata"]
    assert meta["repository"] == "oss2026hnu/reposcore-py"
    assert meta["owner"] == "oss2026hnu"
    assert meta["name"] == "reposcore-py"
    assert meta["schemaVersion"] == 1
    assert "generatedAt" in meta
    assert "contributions" in data


def test_load_cache_without_metadata(tmp_path):
    p = tmp_path / "cache.json"
    save_cache(p, {"contributions": [{"user": "bob"}]})
    loaded = load_cache(p)
    assert "metadata" not in loaded
    assert loaded["contributions"][0]["user"] == "bob"


def test_cached_metadata_reused_skips_fetch(tmp_path):
    cache_file = tmp_path / "oss2026hnu_reposcore-py" / "cache.json"
    save_cache(
        cache_file,
        {
            "metadata": {
                "repository": "oss2026hnu/reposcore-py",
                "owner": "oss2026hnu",
                "name": "reposcore-py",
                "schemaVersion": 1,
                "generatedAt": _generated_at(),
            },
            "contributions": [{"user": "carol", "feature_bug_pr_count": 2}],
        },
    )

    with patch("main.fetch_contributions") as mock_fetch:
        result = runner.invoke(
            app,
            ["oss2026hnu/reposcore-py", "--token", "dummy", "--output", str(tmp_path)],
        )

    assert result.exit_code == 0
    mock_fetch.assert_not_called()


def test_expired_cache_metadata_refetches_contributions(tmp_path):
    cache_file = tmp_path / "oss2026hnu_reposcore-py" / "cache.json"
    cached = [{"user": "carol", "feature_bug_pr_count": 2}]
    fetched = [UserContributionCounts(user="dave", feature_bug_pr_count=3)]
    save_cache(
        cache_file,
        {
            "metadata": {
                "repository": "oss2026hnu/reposcore-py",
                "owner": "oss2026hnu",
                "name": "reposcore-py",
                "schemaVersion": 1,
                "generatedAt": _generated_at(
                    seconds_ago=CACHE_TTL_SECONDS + 1,
                ),
            },
            "contributions": cached,
        },
    )

    with patch("main.fetch_contributions", return_value=fetched) as mock_fetch:
        result = runner.invoke(
            app,
            ["oss2026hnu/reposcore-py", "--token", "dummy", "--output", str(tmp_path)],
        )

    assert result.exit_code == 0
    mock_fetch.assert_called_once()
    data = json.loads(cache_file.read_text("utf-8"))
    assert data["contributions"][0]["user"] == "dave"
