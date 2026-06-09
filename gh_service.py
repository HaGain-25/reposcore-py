from __future__ import annotations

import os

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from calc_score import UserContributionCounts


def create_client(token: str) -> Client:
    transport = RequestsHTTPTransport(
        url="https://api.github.com/graphql",
        headers={"Authorization": f"Bearer {token}"},
        verify=True,
        retries=3,
    )
    return Client(transport=transport, fetch_schema_from_transport=False)


def fetch_contributions(repository: str, token: str) -> list[UserContributionCounts]:
    owner, name = repository.split("/", maxsplit=1)
    client = create_client(token)

    contributions: dict[str, UserContributionCounts] = {}

    # 이슈 수집
    issue_query = gql("""
    query($owner: String!, $name: String!, $after: String) {
        repository(owner: $owner, name: $name) {
            issues(first: 100, after: $after, states: [OPEN, CLOSED]) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    author { login }
                    labels(first: 10) {
                        nodes { name }
                    }
                }
            }
        }
    }
    """)

    cursor = None
    while True:
        with client as session:
            result = session.execute(issue_query, variable_values={
                "owner": owner,
                "name": name,
                "after": cursor,
            })

        issues = result["repository"]["issues"]
        for node in issues["nodes"]:
            if not node["author"]:
                continue
            user = node["author"]["login"]
            labels = [l["name"].lower() for l in node["labels"]["nodes"]]

            if user not in contributions:
                contributions[user] = UserContributionCounts(user=user)

            if "documentation" in labels:
                contributions[user].doc_issue_count += 1
            elif "bug" in labels or "enhancement" in labels:
                contributions[user].feature_bug_issue_count += 1

        if not issues["pageInfo"]["hasNextPage"]:
            break
        cursor = issues["pageInfo"]["endCursor"]

    # PR 수집
    pr_query = gql("""
    query($owner: String!, $name: String!, $after: String) {
        repository(owner: $owner, name: $name) {
            pullRequests(first: 100, after: $after, states: [MERGED]) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    author { login }
                    labels(first: 10) {
                        nodes { name }
                    }
                }
            }
        }
    }
    """)

    cursor = None
    while True:
        with client as session:
            result = session.execute(pr_query, variable_values={
                "owner": owner,
                "name": name,
                "after": cursor,
            })

        prs = result["repository"]["pullRequests"]
        for node in prs["nodes"]:
            if not node["author"]:
                continue
            user = node["author"]["login"]
            labels = [l["name"].lower() for l in node["labels"]["nodes"]]

            if user not in contributions:
                contributions[user] = UserContributionCounts(user=user)

            if "documentation" in labels:
                contributions[user].doc_pr_count += 1
            elif "typo" in labels:
                contributions[user].typo_pr_count += 1
            elif "bug" in labels or "enhancement" in labels:
                contributions[user].feature_bug_pr_count += 1

        if not prs["pageInfo"]["hasNextPage"]:
            break
        cursor = prs["pageInfo"]["endCursor"]

    return list(contributions.values())
