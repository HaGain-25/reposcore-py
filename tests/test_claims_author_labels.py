"""--claims 출력에 issue 작성자(author)와 라벨(labels) 정보가 포함되는지 검증합니다.

테스트 범위:
- claimed issue 출력에 issue 작성자가 포함된다.
- claimed issue 출력에 issue 라벨 목록이 포함된다.
- unclaimed issue 출력에 issue 작성자가 포함된다.
- unclaimed issue 출력에 issue 라벨 목록이 포함된다.
- 라벨이 없는 issue는 Labels: 없음으로 안전하게 출력된다.
- author가 없는 issue도 CLI가 중단되지 않는다.
- Claimed by와 Matched keyword 출력은 기존처럼 유지된다.
- --claims 모드에서 기존 점수 계산 흐름은 실행되지 않는다.
"""

from __future__ import annotations

from typer.testing import CliRunner

import main

runner = CliRunner()


def _invoke_claims(monkeypatch, fake_issues: list[dict]) -> object:
    """fake_issues로 fetch_open_issue_claims를 monkeypatch하고 --claims를 실행합니다."""

    def fake_fetch(repo, token):
        return fake_issues

    monkeypatch.setattr(main, "fetch_open_issue_claims", fake_fetch)

    return runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token", "--claims"],
    )


# ── claimed issue 작성자 포함 검증 ────────────────────────────


def test_claimed_issue_output_includes_author(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 12,
                "title": "출력 형식 개선",
                "author": {"login": "issue-author"},
                "labels": {"nodes": [{"name": "enhancement"}]},
                "comments": {
                    "nodes": [{"body": "제가 하겠습니다", "author": {"login": "user1"}}]
                },
            }
        ],
    )

    assert result.exit_code == 0
    assert "Author: issue-author" in result.output


# ── claimed issue 라벨 포함 검증 ─────────────────────────────


def test_claimed_issue_output_includes_labels(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 12,
                "title": "출력 형식 개선",
                "author": {"login": "issue-author"},
                "labels": {
                    "nodes": [{"name": "enhancement"}, {"name": "documentation"}]
                },
                "comments": {
                    "nodes": [{"body": "제가 하겠습니다", "author": {"login": "user1"}}]
                },
            }
        ],
    )

    assert result.exit_code == 0
    assert "Labels: enhancement, documentation" in result.output


# ── unclaimed issue 작성자 포함 검증 ─────────────────────────


def test_unclaimed_issue_output_includes_author(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 13,
                "title": "README 예시 추가",
                "author": {"login": "another-author"},
                "labels": {"nodes": [{"name": "documentation"}]},
                "comments": {"nodes": []},
            }
        ],
    )

    assert result.exit_code == 0
    assert "Author: another-author" in result.output


# ── unclaimed issue 라벨 포함 검증 ───────────────────────────


def test_unclaimed_issue_output_includes_labels(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 13,
                "title": "README 예시 추가",
                "author": {"login": "another-author"},
                "labels": {"nodes": [{"name": "documentation"}]},
                "comments": {"nodes": []},
            }
        ],
    )

    assert result.exit_code == 0
    assert "Labels: documentation" in result.output


# ── 라벨 없는 issue → Labels: 없음 ───────────────────────────


def test_issue_with_no_labels_outputs_none_label(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 14,
                "title": "라벨 없는 이슈",
                "author": {"login": "some-author"},
                "labels": {"nodes": []},
                "comments": {"nodes": []},
            }
        ],
    )

    assert result.exit_code == 0
    assert "Labels: 없음" in result.output


# ── author 없는 issue → CLI 중단 없이 처리 ───────────────────


def test_issue_with_no_author_does_not_crash(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 15,
                "title": "작성자 없는 이슈",
                "author": None,
                "labels": {"nodes": [{"name": "bug"}]},
                "comments": {"nodes": []},
            }
        ],
    )

    assert result.exit_code == 0
    assert "Author: 알 수 없음" in result.output


# ── Claimed by / Matched keyword 기존 출력 유지 ───────────────


def test_claimed_issue_retains_claimant_and_keyword(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 12,
                "title": "출력 형식 개선",
                "author": {"login": "issue-author"},
                "labels": {"nodes": []},
                "comments": {
                    "nodes": [{"body": "제가 하겠습니다", "author": {"login": "user1"}}]
                },
            }
        ],
    )

    assert result.exit_code == 0
    assert "Claimed by: user1" in result.output
    assert "Matched keyword: 제가 하겠습니다" in result.output


# ── --claims 모드에서 점수 계산 흐름 미실행 확인 ──────────────


def test_claims_mode_does_not_run_score_calculation(monkeypatch):
    """--claims 모드에서는 fetch_contributions가 호출되지 않아야 합니다."""
    fetch_called = []

    def fake_fetch_open(repo, token):
        return []

    def fake_fetch_contributions(*args, **kwargs):
        fetch_called.append(True)
        return []

    monkeypatch.setattr(main, "fetch_open_issue_claims", fake_fetch_open)
    monkeypatch.setattr(main, "fetch_contributions", fake_fetch_contributions)
    monkeypatch.setattr(main, "fetch_multiple_contributions", fake_fetch_contributions)

    result = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "--token", "dummy-token", "--claims"],
    )

    assert result.exit_code == 0
    assert fetch_called == [], (
        "점수 계산용 fetch가 --claims 모드에서 호출되어서는 안 됩니다."
    )


# ── claimed/unclaimed 혼합 시나리오 ──────────────────────────


def test_mixed_claimed_and_unclaimed_with_author_labels(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 10,
                "title": "버그 수정",
                "author": {"login": "author-a"},
                "labels": {"nodes": [{"name": "bug"}]},
                "comments": {
                    "nodes": [{"body": "할게요", "author": {"login": "claimer-a"}}]
                },
            },
            {
                "number": 11,
                "title": "문서 개선",
                "author": {"login": "author-b"},
                "labels": {"nodes": [{"name": "documentation"}]},
                "comments": {"nodes": []},
            },
        ],
    )

    assert result.exit_code == 0
    # claimed issue
    assert "Author: author-a" in result.output
    assert "Labels: bug" in result.output
    assert "Claimed by: claimer-a" in result.output
    # unclaimed issue
    assert "Author: author-b" in result.output
    assert "Labels: documentation" in result.output


# ── issue URL 출력 검증 ──────────────────────────────────────


def test_claimed_issue_output_includes_url(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 12,
                "title": "출력 형식 개선",
                "url": "https://github.com/oss2026hnu/reposcore-py/issues/12",
                "author": {"login": "issue-author"},
                "labels": {"nodes": [{"name": "enhancement"}]},
                "comments": {
                    "nodes": [
                        {
                            "body": "제가 하겠습니다",
                            "author": {"login": "user1"},
                        }
                    ]
                },
            }
        ],
    )

    assert result.exit_code == 0
    assert "URL: https://github.com/oss2026hnu/reposcore-py/issues/12" in result.output


def test_unclaimed_issue_output_includes_url(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 13,
                "title": "README 예시 추가",
                "url": "https://github.com/oss2026hnu/reposcore-py/issues/13",
                "author": {"login": "another-author"},
                "labels": {"nodes": [{"name": "documentation"}]},
                "comments": {"nodes": []},
            }
        ],
    )

    assert result.exit_code == 0
    assert "URL: https://github.com/oss2026hnu/reposcore-py/issues/13" in result.output


def test_issue_without_url_does_not_crash(monkeypatch):
    result = _invoke_claims(
        monkeypatch,
        [
            {
                "number": 14,
                "title": "URL 없는 이슈",
                "author": {"login": "some-author"},
                "labels": {"nodes": []},
                "comments": {"nodes": []},
            }
        ],
    )

    assert result.exit_code == 0
    assert "URL 없는 이슈" in result.output
    assert "URL:" not in result.output
