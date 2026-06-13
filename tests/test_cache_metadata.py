from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from cache_manager import load_cache, save_cache
from calc_score import UserContributionCounts
from main import app

runner = CliRunner()


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
                "generatedAt": "2026-06-12T00:00:00Z",
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
