from __future__ import annotations

import pytest

from gh_service import fetch_contributions


def make_issue_response(
    nodes: list[dict],
    has_next: bool = False,
    end_cursor: str | None = None,
) -> dict:
    return {
        "repository": {
            "issues": {
                "pageInfo": {
                    "hasNextPage": has_next,
                    "endCursor": end_cursor,
                },
                "nodes": nodes,
            }
        }
    }


def make_pr_response(
    nodes: list[dict],
    has_next: bool = False,
    end_cursor: str | None = None,
) -> dict:
    return {
        "repository": {
            "pullRequests": {
                "pageInfo": {
                    "hasNextPage": has_next,
                    "endCursor": end_cursor,
                },
                "nodes": nodes,
            }
        }
    }


def make_node(login: str | None, labels: list[str]) -> dict:
    author = {"login": login} if login else None
    return {
        "author": author,
        "labels": {
            "nodes": [{"name": label} for label in labels]
        },
    }


class DummySession:
    def __init__(self, execute_handler):
        self.execute = execute_handler


class DummyClient:
    def __init__(self, execute_handler):
        self.session = DummySession(execute_handler)

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_issue_label_classification(monkeypatch: pytest.MonkeyPatch):
    def mock_execute(query, variable_values):
        query_str = str(query)
        if "issues(" in query_str:
            return make_issue_response([
                make_node("user1", ["documentation"]),
                make_node("user1", ["bug"]),
                make_node("user1", ["enhancement"]),
                make_node("user1", ["unknown"]),
                make_node("user1", []),
            ])
        if "pullRequests(" in query_str:
            return make_pr_response([])
        return {}

    monkeypatch.setattr(
        "gh_service.create_client",
        lambda token: DummyClient(mock_execute),
    )

    contribs = fetch_contributions("owner/repo", "dummy_token")
    assert len(contribs) == 1
    assert contribs[0].user == "user1"
    assert contribs[0].doc_issue_count == 1
    assert contribs[0].feature_bug_issue_count == 2


def test_pr_label_classification(monkeypatch: pytest.MonkeyPatch):
    def mock_execute(query, variable_values):
        query_str = str(query)
        if "issues(" in query_str:
            return make_issue_response([])
        if "pullRequests(" in query_str:
            return make_pr_response([
                make_node("user1", ["documentation"]),
                make_node("user1", ["typo"]),
                make_node("user1", ["bug"]),
                make_node("user1", ["enhancement"]),
                make_node("user1", ["unknown"]),
                make_node("user1", []),
            ])
        return {}

    monkeypatch.setattr(
        "gh_service.create_client",
        lambda token: DummyClient(mock_execute),
    )

    contribs = fetch_contributions("owner/repo", "dummy_token")
    assert len(contribs) == 1
    assert contribs[0].user == "user1"
    assert contribs[0].doc_pr_count == 1
    assert contribs[0].typo_pr_count == 1
    assert contribs[0].feature_bug_pr_count == 2


def test_missing_author_is_ignored(monkeypatch: pytest.MonkeyPatch):
    def mock_execute(query, variable_values):
        query_str = str(query)
        if "issues(" in query_str:
            return make_issue_response([
                make_node(None, ["bug"]),
            ])
        if "pullRequests(" in query_str:
            return make_pr_response([
                make_node(None, ["typo"]),
            ])
        return {}

    monkeypatch.setattr(
        "gh_service.create_client",
        lambda token: DummyClient(mock_execute),
    )

    contribs = fetch_contributions("owner/repo", "dummy_token")
    assert len(contribs) == 0


def test_same_user_counts_accumulate(monkeypatch: pytest.MonkeyPatch):
    def mock_execute(query, variable_values):
        query_str = str(query)
        if "issues(" in query_str:
            return make_issue_response([
                make_node("user1", ["bug"]),
                make_node("user1", ["documentation"]),
            ])
        if "pullRequests(" in query_str:
            return make_pr_response([
                make_node("user1", ["typo"]),
                make_node("user1", ["enhancement"]),
                make_node("user1", ["documentation"]),
            ])
        return {}

    monkeypatch.setattr(
        "gh_service.create_client",
        lambda token: DummyClient(mock_execute),
    )

    contribs = fetch_contributions("owner/repo", "dummy_token")
    assert len(contribs) == 1

    user_contrib = contribs[0]
    assert user_contrib.user == "user1"
    assert user_contrib.feature_bug_issue_count == 1
    assert user_contrib.doc_issue_count == 1
    assert user_contrib.feature_bug_pr_count == 1
    assert user_contrib.doc_pr_count == 1
    assert user_contrib.typo_pr_count == 1


def test_multiple_users_are_separated(monkeypatch: pytest.MonkeyPatch):
    def mock_execute(query, variable_values):
        query_str = str(query)
        if "issues(" in query_str:
            return make_issue_response([
                make_node("user1", ["bug"]),
                make_node("user2", ["documentation"]),
            ])
        if "pullRequests(" in query_str:
            return make_pr_response([
                make_node("user2", ["typo"]),
                make_node("user3", ["enhancement"]),
            ])
        return {}

    monkeypatch.setattr(
        "gh_service.create_client",
        lambda token: DummyClient(mock_execute),
    )

    contribs = fetch_contributions("owner/repo", "dummy_token")
    assert len(contribs) == 3

    contribs_by_user = {c.user: c for c in contribs}

    assert contribs_by_user["user1"].feature_bug_issue_count == 1
    assert contribs_by_user["user1"].doc_issue_count == 0

    assert contribs_by_user["user2"].doc_issue_count == 1
    assert contribs_by_user["user2"].typo_pr_count == 1

    assert contribs_by_user["user3"].feature_bug_pr_count == 1


def test_pagination(monkeypatch: pytest.MonkeyPatch):
    issue_call_count = 0
    pr_call_count = 0

    def mock_execute(query, variable_values):
        nonlocal issue_call_count, pr_call_count
        query_str = str(query)

        if "issues(" in query_str:
            issue_call_count += 1
            if variable_values.get("after") is None:
                return make_issue_response(
                    [make_node("user1", ["bug"])],
                    has_next=True,
                    end_cursor="cursor_issue_1",
                )
            elif variable_values.get("after") == "cursor_issue_1":
                return make_issue_response(
                    [make_node("user1", ["documentation"])],
                    has_next=False,
                )

        if "pullRequests(" in query_str:
            pr_call_count += 1
            if variable_values.get("after") is None:
                return make_pr_response(
                    [make_node("user1", ["typo"])],
                    has_next=True,
                    end_cursor="cursor_pr_1",
                )
            elif variable_values.get("after") == "cursor_pr_1":
                return make_pr_response(
                    [make_node("user2", ["enhancement"])],
                    has_next=False,
                )
        return {}

    monkeypatch.setattr(
        "gh_service.create_client",
        lambda token: DummyClient(mock_execute),
    )

    contribs = fetch_contributions("owner/repo", "dummy_token")
    assert issue_call_count == 2
    assert pr_call_count == 2

    contribs_by_user = {c.user: c for c in contribs}

    assert len(contribs_by_user) == 2
    assert contribs_by_user["user1"].feature_bug_issue_count == 1
    assert contribs_by_user["user1"].doc_issue_count == 1
    assert contribs_by_user["user1"].typo_pr_count == 1

    assert contribs_by_user["user2"].feature_bug_pr_count == 1