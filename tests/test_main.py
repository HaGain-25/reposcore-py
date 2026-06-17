from typer.testing import CliRunner

import main

runner = CliRunner()


def test_format_option_is_case_insensitive(monkeypatch):
    def fake_load_or_fetch_contributions(
        repos,
        token,
        output,
        cache=True,  # no_cache=False 에서 신규 표준 매개변수인 cache=True로 리팩토링
        since=None,
        until=None,
        page_size=100,
    ):
        return [[] for _ in repos]

    monkeypatch.setattr(
        main,
        "_load_or_fetch_contributions",
        fake_load_or_fetch_contributions,
    )

    result = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--format", "CSV", "--token", "dummy-token"],
    )

    assert result.exit_code == 0


def test_page_size_option_is_passed_to_loader(monkeypatch):
    captured = {}

    def fake_load_or_fetch_contributions(
        repos,
        token,
        output,
        cache=True,  # 신규 표준 매개변수인 cache=True로 반영
        since=None,
        until=None,
        page_size=100,
    ):
        captured["page_size"] = page_size
        return [[] for _ in repos]

    monkeypatch.setattr(
        main,
        "_load_or_fetch_contributions",
        fake_load_or_fetch_contributions,
    )

    result = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token", "--page-size", "25"],
    )

    assert result.exit_code == 0
    assert captured["page_size"] == 25


def test_page_size_envvar_is_passed_to_loader(monkeypatch):
    captured = {}

    def fake_load_or_fetch_contributions(
        repos,
        token,
        output,
        cache=True,  # 신규 표준 매개변수인 cache=True로 반영
        since=None,
        until=None,
        page_size=100,
    ):
        captured["page_size"] = page_size
        return [[] for _ in repos]

    monkeypatch.setattr(
        main,
        "_load_or_fetch_contributions",
        fake_load_or_fetch_contributions,
    )

    result = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token"],
        env={"REPOSCORE_PAGE_SIZE": "30"},
    )

    assert result.exit_code == 0
    assert captured["page_size"] == 30


# [신규 단위 테스트 검증 스펙 완벽 추가] 
# --cache / --no-cache 한 쌍이 제어 로직에 정상 바인딩되는지 검증합니다.
def test_cache_and_no_cache_toggle_options(monkeypatch):
    captured = {}

    def fake_load_or_fetch_contributions(
        repos,
        token,
        output,
        cache=True,
        since=None,
        until=None,
        page_size=100,
    ):
        captured["cache"] = cache
        return [[] for _ in repos]

    monkeypatch.setattr(
        main,
        "_load_or_fetch_contributions",
        fake_load_or_fetch_contributions,
    )

    # Case 1: 명시적으로 --cache 옵션을 주었을 때 True 가 찍히는지 확인
    result_cache = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token", "--cache"],
    )
    assert result_cache.exit_code == 0
    assert captured["cache"] is True

    # Case 2: 명시적으로 대칭 옵션인 --no-cache 를 주었을 때 False 가 찍히는지 확인
    result_no_cache = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token", "--no-cache"],
    )
    assert result_no_cache.exit_code == 0
    assert captured["cache"] is False


def test_claims_output_includes_summary_counts(monkeypatch):
    def fake_fetch_open_issue_claims(repo, token):
        return [
            {
                "number": 12,
                "title": "출력 형식 개선",
                "comments": {
                    "nodes": [
                        {
                            "body": "제가 하겠습니다",
                            "author": {"login": "user1"},
                        }
                    ]
                },
            },
            {
                "number": 13,
                "title": "README 예시 추가",
                "comments": {"nodes": []},
            },
        ]

    monkeypatch.setattr(
        main,
        "fetch_open_issue_claims",
        fake_fetch_open_issue_claims,
    )

    result = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token", "--claims"],
    )

    assert result.exit_code == 0
    assert "Claim Summary" in result.output
    assert "Total open issues: 2" in result.output
    assert "Claimed issues: 1" in result.output
    assert "Unclaimed issues: 1" in result.output
    assert "Claimed Issues" in result.output
    assert "Unclaimed Issues" in result.output


def test_claims_summary_when_no_claimed_issues(monkeypatch):
    def fake_fetch_open_issue_claims(repo, token):
        return [
            {
                "number": 13,
                "title": "README 예시 추가",
                "comments": {"nodes": []},
            },
        ]

    monkeypatch.setattr(
        main,
        "fetch_open_issue_claims",
        fake_fetch_open_issue_claims,
    )

    result = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token", "--claims"],
    )

    assert result.exit_code == 0
    assert "Total open issues: 1" in result.output
    assert "Claimed issues: 0" in result.output
    assert "Unclaimed issues: 1" in result.output


def test_claims_summary_when_no_unclaimed_issues(monkeypatch):
    def fake_fetch_open_issue_claims(repo, token):
        return [
            {
                "number": 12,
                "title": "출력 형식 개선",
                "comments": {
                    "nodes": [
                        {
                            "body": "진행하겠습니다",
                            "author": {"login": "user1"},
                        }
                    ]
                },
            },
        ]

    monkeypatch.setattr(
        main,
        "fetch_open_issue_claims",
        fake_fetch_open_issue_claims,
    )

    result = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token", "--claims"],
    )

    assert result.exit_code == 0
    assert "Total open issues: 1" in result.output
    assert "Claimed issues: 1" in result.output
    assert "Unclaimed issues: 0" in result.output


def test_claims_summary_for_multiple_repositories(monkeypatch):
    def fake_fetch_open_issue_claims(repo, token):
        if repo == "owner/repo1":
            return [
                {
                    "number": 1,
                    "title": "첫 번째 이슈",
                    "comments": {
                        "nodes": [
                            {
                                "body": "할게요",
                                "author": {"login": "user1"},
                            }
                        ]
                    },
                },
                {
                    "number": 2,
                    "title": "두 번째 이슈",
                    "comments": {"nodes": []},
                },
            ]

        return [
            {
                "number": 3,
                "title": "세 번째 이슈",
                "comments": {"nodes": []},
            }
        ]

    monkeypatch.setattr(
        main,
        "fetch_open_issue_claims",
        fake_fetch_open_issue_claims,
    )

    result = runner.invoke(
        main.app,
        [
            "owner/repo1",
            "owner/repo2",
            "--token",
            "dummy-token",
            "--claims",
        ],
    )

    assert result.exit_code == 0
    assert "=== Repository: owner/repo1 ===" in result.output
    assert "=== Repository: owner/repo2 ===" in result.output
    assert result.output.count("Claim Summary") == 2
    assert "Total open issues: 2" in result.output
    assert "Claimed issues: 1" in result.output
    assert "Unclaimed issues: 1" in result.output
    assert "Total open issues: 1" in result.output
    assert "Claimed issues: 0" in result.output
    assert "Unclaimed issues: 1" in result.output


def test_parse_claim_keywords_removes_empty_items():
    result = main._parse_claim_keywords("제가 하겠습니다,")

    assert result == ["제가 하겠습니다"]


def test_parse_claim_keywords_raises_when_all_empty():
    import pytest

    with pytest.raises(ValueError, match="선점 키워드는 하나 이상 입력해야 합니다."):
        main._parse_claim_keywords(",")


def test_parse_claim_keywords_raises_when_only_spaces():
    import pytest

    with pytest.raises(ValueError, match="선점 키워드는 하나 이상 입력해야 합니다."):
        main._parse_claim_keywords("   ")


def test_parse_claim_keywords_returns_default_when_none():
    result = main._parse_claim_keywords(None)

    assert result == main.DEFAULT_CLAIM_KEYWORDS


def test_claims_keywords_trailing_comma_removes_empty_keyword(monkeypatch):
    def fake_fetch_open_issue_claims(repo, token):
        return [
            {
                "number": 1,
                "title": "선점 테스트",
                "author": {"login": "issue-author"},
                "labels": {"nodes": []},
                "comments": {
                    "nodes": [
                        {
                            "body": "제가 하겠습니다",
                            "author": {"login": "claimer"},
                        }
                    ]
                },
            }
        ]

    monkeypatch.setattr(
        main,
        "fetch_open_issue_claims",
        fake_fetch_open_issue_claims,
    )

    result = runner.invoke(
        main.app,
        [
            "oss2026hnu/reposcore-py",
            "--token",
            "dummy-token",
            "--claims",
            "--keywords",
            "제가 하겠습니다,",
        ],
    )

    assert result.exit_code == 0
    assert "Claimed issues: 1" in result.output
    assert "Matched keyword: 제가 하겠습니다" in result.output


def test_claims_keywords_comma_only_exits_with_error():
    result = runner.invoke(
        main.app,
        [
            "oss2026hnu/reposcore-py",
            "--token",
            "dummy-token",
            "--claims",
            "--keywords",
            ",",
        ],
    )

    assert result.exit_code == 1
    assert "오류: 선점 키워드는 하나 이상 입력해야 합니다." in result.output


def test_claims_keywords_spaces_only_exits_with_error():
    result = runner.invoke(
        main.app,
        [
            "oss2026hnu/reposcore-py",
            "--token",
            "dummy-token",
            "--claims",
            "--keywords",
            "   ",
        ],
    )

    assert result.exit_code == 1
    assert "오류: 선점 키워드는 하나 이상 입력해야 합니다." in result.output
