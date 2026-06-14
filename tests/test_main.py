from typer.testing import CliRunner

import main

runner = CliRunner()


def test_format_option_is_case_insensitive(monkeypatch):
    def fake_load_or_fetch_contributions(
        repos,
        token,
        output,
        no_cache=False,
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
        no_cache=False,
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
        no_cache=False,
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
