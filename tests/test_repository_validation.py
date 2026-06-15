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


# ── 중복 저장소 입력 유효성 검증 테스트 추가 ──────────────────────────

@patch("main.fetch_contributions")
@patch("main.fetch_multiple_contributions")
def test_unique_repositories_pass(mock_multiple, mock_single):
    """
    서로 다른 독립된 저장소 여러 개를 인자로 넘겼을 때,
    입력값 유효성 검증 단계를 정상 통과하는지 확인합니다.
    """
    result = runner.invoke(app, ["owner/repo1", "owner/repo2", "-t", "dummy-token"])
    assert result.exit_code == 0


@patch("main.fetch_contributions")
@patch("main.fetch_multiple_contributions")
def test_duplicate_repositories_fail(mock_multiple, mock_single):
    """
    일반 실행 모드에서 같은 저장소를 중복 입력했을 때, API 호출 없이
    명확한 에러 메시지와 함께 에러 코드 1번으로 비정상 종료되는지 검증합니다.
    """
    result = runner.invoke(
        app, ["oss2026hnu/reposcore-py", "oss2026hnu/reposcore-py", "-t", "dummy-token"]
    )
    
    # 에러 코드로 즉시 종료되었는지 확인
    assert result.exit_code == 1
    
    # 오류 출력 스트림에 명시된 에러 문구와 중복 저장소 명칭이 포함되어 있는지 확인
    assert "오류: 같은 저장소가 중복 입력되었습니다: oss2026hnu/reposcore-py" in result.stdout

    # GitHub 서버를 찌르는 데이터 조회 함수들이 절대 호출되지 않았는지 안전성 체크
    mock_single.assert_not_called()
    mock_multiple.assert_not_called()


@patch("main.fetch_contributions")
@patch("main.fetch_multiple_contributions")
def test_duplicate_repositories_with_aggregate_fail(mock_multiple, mock_single):
    """
    --aggregate 옵션이 켜져 있더라도 저장소가 중복 입력되면 이중 합산 방지를 위해
    조기에 실행을 취소하고 오류 처리를 수행하는지 검증합니다.
    """
    result = runner.invoke(
        app,
        [
            "oss2026hnu/reposcore-py",
            "oss2026hnu/reposcore-py",
            "--aggregate",
            "-t",
            "dummy-token",
        ],
    )
    
    assert result.exit_code == 1
    assert "oss2026hnu/reposcore-py" in result.stdout
    
    # 무조건 데이터 수집부 진입 전에 차단되어야 함
    mock_single.assert_not_called()
    mock_multiple.assert_not_called()