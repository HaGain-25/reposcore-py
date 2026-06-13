from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from main import app, split_repository

runner = CliRunner()


def test_split_repository_valid():
    assert split_repository("oss2026hnu/reposcore-py") == ("oss2026hnu", "reposcore-py")


@pytest.mark.parametrize(
    "value",
    ["invalid-repo", "/repo", "owner/", "owner/repo/extra", ""],
)
def test_split_repository_invalid(value):
    with pytest.raises(ValueError):
        split_repository(value)


def test_invalid_repo_skips_github_api():
    # 잘못된 저장소 인자면 fetch_contributions 가 호출되지 않아야 함
    with patch("main.fetch_contributions") as mock_fetch:
        result = runner.invoke(app, ["invalid-repo", "--token", "dummy-token"])

    assert result.exit_code != 0
    mock_fetch.assert_not_called()
