from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import main as main_module
from gh_service import (
    Author,
    Label,
    LabelConnection,
    Node,
    _add_issue_contribution,
    _add_pr_contribution,
    _is_in_date_range,
)

runner = CliRunner()


def _make_node(
    *,
    login: str = "user1",
    labels: tuple[str, ...],
    created_at: str | None = None,
    merged_at: str | None = None,
    state_reason: str | None = None,
) -> Node:
    return Node(
        author=Author(login=login),
        labels=LabelConnection(nodes=[Label(name=label) for label in labels]),
        createdAt=created_at,
        mergedAt=merged_at,
        stateReason=state_reason,
    )


def _combined_output(result: Any) -> str:
    return f"{result.output}{getattr(result, 'stderr', '') or ''}"


@pytest.mark.parametrize(
    ("date_str", "since", "until", "expected"),
    [
        ("2026-06-10", None, None, True),
        (None, date(2026, 6, 1), date(2026, 6, 10), True),
        ("2026-06-01", date(2026, 6, 1), date(2026, 6, 10), True),
        ("2026-06-10", date(2026, 6, 1), date(2026, 6, 10), True),
        ("2026-05-31", date(2026, 6, 1), date(2026, 6, 10), False),
        ("2026-06-11", date(2026, 6, 1), date(2026, 6, 10), False),
        ("2026-06-05", date(2026, 6, 1), date(2026, 6, 10), True),
    ],
)
def test_is_in_date_range_boundaries(
    date_str: str | None,
    since: date | None,
    until: date | None,
    expected: bool,
) -> None:
    assert _is_in_date_range(date_str, since, until) is expected


def test_is_in_date_range_uses_date_part_of_iso_datetime() -> None:
    assert (
        _is_in_date_range(
            "2026-06-10T12:34:56Z",
            date(2026, 6, 10),
            date(2026, 6, 10),
        )
        is True
    )


def test_is_in_date_range_keeps_existing_behavior_for_invalid_date_string() -> None:
    assert (
        _is_in_date_range(
            "invalid-date",
            date(2026, 6, 1),
            date(2026, 6, 10),
        )
        is True
    )


def test_add_issue_contribution_includes_created_at_inside_range() -> None:
    contributions = {}
    node = _make_node(
        labels=("documentation",),
        created_at="2026-06-10T00:00:00Z",
    )

    _add_issue_contribution(
        contributions,
        node,
        since=date(2026, 6, 1),
        until=date(2026, 6, 10),
    )

    assert contributions["user1"].doc_issue_count == 1


@pytest.mark.parametrize(
    "created_at",
    [
        "2026-05-31T23:59:59Z",
        "2026-06-11T00:00:00Z",
    ],
)
def test_add_issue_contribution_excludes_created_at_outside_range(
    created_at: str,
) -> None:
    contributions = {}
    node = _make_node(
        labels=("documentation",),
        created_at=created_at,
    )

    _add_issue_contribution(
        contributions,
        node,
        since=date(2026, 6, 1),
        until=date(2026, 6, 10),
    )

    assert contributions == {}


def test_add_issue_contribution_includes_when_created_at_is_none() -> None:
    contributions = {}
    node = _make_node(
        labels=("documentation",),
        created_at=None,
    )

    _add_issue_contribution(
        contributions,
        node,
        since=date(2026, 6, 1),
        until=date(2026, 6, 10),
    )

    assert contributions["user1"].doc_issue_count == 1


def test_add_issue_contribution_filters_by_created_at_not_merged_at() -> None:
    contributions = {}
    node = _make_node(
        labels=("documentation",),
        created_at="2026-06-10T00:00:00Z",
        merged_at="2026-06-11T00:00:00Z",
    )

    _add_issue_contribution(
        contributions,
        node,
        since=date(2026, 6, 1),
        until=date(2026, 6, 10),
    )

    assert contributions["user1"].doc_issue_count == 1


def test_add_pr_contribution_includes_merged_at_inside_range() -> None:
    contributions = {}
    node = _make_node(
        labels=("enhancement",),
        merged_at="2026-06-10T00:00:00Z",
    )

    _add_pr_contribution(
        contributions,
        node,
        since=date(2026, 6, 1),
        until=date(2026, 6, 10),
    )

    assert contributions["user1"].feature_bug_pr_count == 1


@pytest.mark.parametrize(
    "merged_at",
    [
        "2026-05-31T23:59:59Z",
        "2026-06-11T00:00:00Z",
    ],
)
def test_add_pr_contribution_excludes_merged_at_outside_range(
    merged_at: str,
) -> None:
    contributions = {}
    node = _make_node(
        labels=("enhancement",),
        merged_at=merged_at,
    )

    _add_pr_contribution(
        contributions,
        node,
        since=date(2026, 6, 1),
        until=date(2026, 6, 10),
    )

    assert contributions == {}


def test_add_pr_contribution_includes_when_merged_at_is_none() -> None:
    contributions = {}
    node = _make_node(
        labels=("enhancement",),
        merged_at=None,
    )

    _add_pr_contribution(
        contributions,
        node,
        since=date(2026, 6, 1),
        until=date(2026, 6, 10),
    )

    assert contributions["user1"].feature_bug_pr_count == 1


def test_add_pr_contribution_filters_by_merged_at_not_created_at() -> None:
    contributions = {}
    node = _make_node(
        labels=("enhancement",),
        created_at="2026-05-31T00:00:00Z",
        merged_at="2026-06-10T00:00:00Z",
    )

    _add_pr_contribution(
        contributions,
        node,
        since=date(2026, 6, 1),
        until=date(2026, 6, 10),
    )

    assert contributions["user1"].feature_bug_pr_count == 1


def _patch_cli_side_effects(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls = {}

    def fake_load_or_fetch_contributions(
        repos,
        token,
        output,
        cache=True,
        since=None,
        until=None,
        page_size=100,
    ):
        calls["repos"] = repos
        calls["token"] = token
        calls["output"] = output
        calls["cache"] = cache
        calls["since"] = since
        calls["until"] = until
        calls["page_size"] = page_size
        return [[] for _ in repos]

    monkeypatch.setattr(
        main_module,
        "_load_or_fetch_contributions",
        fake_load_or_fetch_contributions,
    )
    monkeypatch.setattr(main_module, "build_output", lambda results, format_value: "")
    monkeypatch.setattr(
        main_module,
        "write_output",
        lambda content, output, format_value: Path(output) / f"result.{format_value}",
    )

    return calls


@pytest.mark.parametrize(
    ("args", "expected_since", "expected_until"),
    [
        (
            ["--since", "2026-06-01"],
            date(2026, 6, 1),
            None,
        ),
        (
            ["--until", "2026-06-10"],
            None,
            date(2026, 6, 10),
        ),
        (
            ["--since", "2026-06-01", "--until", "2026-06-10"],
            date(2026, 6, 1),
            date(2026, 6, 10),
        ),
    ],
)
def test_cli_accepts_valid_since_until_dates(
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    expected_since: date | None,
    expected_until: date | None,
) -> None:
    calls = _patch_cli_side_effects(monkeypatch)

    result = runner.invoke(
        main_module.app,
        [
            "oss2026hnu/reposcore-py",
            "--token",
            "dummy-token",
            *args,
        ],
    )

    assert result.exit_code == 0
    assert calls["since"] == expected_since
    assert calls["until"] == expected_until


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (
            ["--since", "2026/06/01"],
            "--since 날짜 형식이 잘못되었습니다",
        ),
        (
            ["--until", "06-10-2026"],
            "--until 날짜 형식이 잘못되었습니다",
        ),
    ],
)
def test_cli_rejects_invalid_date_format(
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    expected_message: str,
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("GitHub API 흐름이 호출되면 안 됩니다.")

    monkeypatch.setattr(main_module, "_load_or_fetch_contributions", fail_if_called)

    result = runner.invoke(
        main_module.app,
        [
            "oss2026hnu/reposcore-py",
            "--token",
            "dummy-token",
            *args,
        ],
    )

    assert result.exit_code == 1
    assert expected_message in _combined_output(result)


def test_cli_rejects_since_later_than_until(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("GitHub API 흐름이 호출되면 안 됩니다.")

    monkeypatch.setattr(main_module, "_load_or_fetch_contributions", fail_if_called)

    result = runner.invoke(
        main_module.app,
        [
            "oss2026hnu/reposcore-py",
            "--token",
            "dummy-token",
            "--since",
            "2026-06-10",
            "--until",
            "2026-06-01",
        ],
    )

    assert result.exit_code == 1
    assert "--since 날짜가 --until 날짜보다 늦습니다" in _combined_output(result)
