from __future__ import annotations

from datetime import date

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from pydantic import BaseModel

from calc_score import UserContributionCounts

DEFAULT_PAGE_SIZE = 100


# ── Pydantic 모델 정의 ──────────────────────────────────────────
class Author(BaseModel):
    login: str


class Label(BaseModel):
    name: str


class LabelConnection(BaseModel):
    nodes: list[Label]


class PageInfo(BaseModel):
    hasNextPage: bool
    endCursor: str | None


class Node(BaseModel):
    author: Author | None
    labels: LabelConnection
    createdAt: str | None = None
    mergedAt: str | None = None


class Connection(BaseModel):
    pageInfo: PageInfo
    nodes: list[Node]


class IssueRepository(BaseModel):
    issues: Connection


class PRRepository(BaseModel):
    pullRequests: Connection


class IssueResponse(BaseModel):
    repository: IssueRepository


class PRResponse(BaseModel):
    repository: PRRepository


# ── 클라이언트 생성 ──────────────────────────────────────────────
def create_client(token: str) -> Client:
    transport = RequestsHTTPTransport(
        url="https://api.github.com/graphql",
        headers={"Authorization": f"Bearer {token}"},
        verify=True,
        retries=3,
    )
    return Client(transport=transport, fetch_schema_from_transport=False)


# ── 날짜 필터링 유틸리티 ─────────────────────────────────────────
def _is_in_date_range(
    date_str: str | None,
    since: date | None,
    until: date | None,
) -> bool:
    if date_str is None:
        return True

    try:
        item_date = date.fromisoformat(date_str[:10])
    except ValueError:
        return True

    if since is not None and item_date < since:
        return False
    if until is not None and item_date > until:
        return False

    return True


# ── 공통 기여 집계 유틸리티 ─────────────────────────────────────
def _split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/")

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("저장소는 owner/repo 형식이어야 합니다.")

    return parts[0], parts[1]


def _get_contribution(
    contributions: dict[str, UserContributionCounts],
    user: str,
) -> UserContributionCounts:
    if user not in contributions:
        contributions[user] = UserContributionCounts(user=user)

    return contributions[user]


def _add_issue_contribution(
    contributions: dict[str, UserContributionCounts],
    node: Node,
    since: date | None = None,
    until: date | None = None,
) -> None:
    if node.author is None:
        return

    if not _is_in_date_range(node.createdAt, since, until):
        return

    contribution = _get_contribution(contributions, node.author.login)
    labels = [label.name.lower() for label in node.labels.nodes]

    if "documentation" in labels:
        contribution.doc_issue_count += 1
    elif "bug" in labels or "enhancement" in labels:
        contribution.feature_bug_issue_count += 1


def _add_pr_contribution(
    contributions: dict[str, UserContributionCounts],
    node: Node,
    since: date | None = None,
    until: date | None = None,
) -> None:
    if node.author is None:
        return

    if not _is_in_date_range(node.mergedAt, since, until):
        return

    contribution = _get_contribution(contributions, node.author.login)
    labels = [label.name.lower() for label in node.labels.nodes]

    if "documentation" in labels:
        contribution.doc_pr_count += 1
    elif "typo" in labels:
        contribution.typo_pr_count += 1
    elif "bug" in labels or "enhancement" in labels:
        contribution.feature_bug_pr_count += 1


def _build_issue_alias_query(indexes: list[int]):
    variable_definitions: list[str] = ["$pageSize: Int!"]
    repository_blocks: list[str] = []

    for index in indexes:
        variable_definitions.extend(
            [
                f"$owner{index}: String!",
                f"$name{index}: String!",
                f"$after{index}: String",
            ]
        )
        repository_blocks.append(
            f"""
            repo{index}: repository(owner: $owner{index}, name: $name{index}) {{
                issues(first: $pageSize, after: $after{index}, states: [OPEN, CLOSED]) {{
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                    nodes {{
                        author {{ login }}
                        createdAt
                        labels(first: 10) {{
                            nodes {{ name }}
                        }}
                    }}
                }}
            }}
            """
        )

    return gql(
        f"""
        query({", ".join(variable_definitions)}) {{
            {"".join(repository_blocks)}
        }}
        """
    )


def _build_pr_alias_query(indexes: list[int]):
    variable_definitions: list[str] = ["$pageSize: Int!"]
    repository_blocks: list[str] = []

    for index in indexes:
        variable_definitions.extend(
            [
                f"$owner{index}: String!",
                f"$name{index}: String!",
                f"$after{index}: String",
            ]
        )
        repository_blocks.append(
            f"""
            repo{index}: repository(owner: $owner{index}, name: $name{index}) {{
                pullRequests(first: $pageSize, after: $after{index}, states: [MERGED]) {{
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                    nodes {{
                        author {{ login }}
                        mergedAt
                        labels(first: 10) {{
                            nodes {{ name }}
                        }}
                    }}
                }}
            }}
            """
        )

    return gql(
        f"""
        query({", ".join(variable_definitions)}) {{
            {"".join(repository_blocks)}
        }}
        """
    )


# ── 기여 데이터 수집 ──────────────────────────────────────────────
def fetch_contributions(
    repository: str,
    token: str,
    since: date | None = None,
    until: date | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[UserContributionCounts]:
    owner, name = _split_repository(repository)
    client = create_client(token)
    contributions: dict[str, UserContributionCounts] = {}

    # 이슈 수집
    issue_query = gql("""
    query($owner: String!, $name: String!, $after: String, $pageSize: Int!) {
        repository(owner: $owner, name: $name) {
            issues(first: $pageSize, after: $after, states: [OPEN, CLOSED]) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    author { login }
                    createdAt
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
            result = session.execute(
                issue_query,
                variable_values={
                    "owner": owner,
                    "name": name,
                    "after": cursor,
                    "pageSize": page_size,
                },
            )

        issues = Connection.model_validate(result["repository"]["issues"])

        for node in issues.nodes:
            _add_issue_contribution(contributions, node, since, until)

        if not issues.pageInfo.hasNextPage:
            break
        cursor = issues.pageInfo.endCursor

    # PR 수집
    pr_query = gql("""
    query($owner: String!, $name: String!, $after: String, $pageSize: Int!) {
        repository(owner: $owner, name: $name) {
            pullRequests(first: $pageSize, after: $after, states: [MERGED]) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    author { login }
                    mergedAt
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
            result = session.execute(
                pr_query,
                variable_values={
                    "owner": owner,
                    "name": name,
                    "after": cursor,
                    "pageSize": page_size,
                },
            )

        prs = Connection.model_validate(result["repository"]["pullRequests"])

        for node in prs.nodes:
            _add_pr_contribution(contributions, node, since, until)

        if not prs.pageInfo.hasNextPage:
            break
        cursor = prs.pageInfo.endCursor

    return list(contributions.values())


def fetch_multiple_contributions(
    repositories: list[str],
    token: str,
    since: date | None = None,
    until: date | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[list[UserContributionCounts]]:
    """여러 저장소의 기여 데이터를 GraphQL repository alias를 사용해 조회합니다."""

    if len(repositories) == 0:
        return []

    repository_parts = [_split_repository(repository) for repository in repositories]
    client = create_client(token)

    contributions_by_repository: list[dict[str, UserContributionCounts]] = [
        {} for _ in repositories
    ]

    issue_cursors: list[str | None] = [None for _ in repositories]
    issue_active = [True for _ in repositories]

    pr_cursors: list[str | None] = [None for _ in repositories]
    pr_active = [True for _ in repositories]

    with client as session:
        while any(issue_active):
            active_indexes = [
                index for index, active in enumerate(issue_active) if active
            ]

            variables = {"pageSize": page_size}
            for index in active_indexes:
                owner, name = repository_parts[index]
                variables[f"owner{index}"] = owner
                variables[f"name{index}"] = name
                variables[f"after{index}"] = issue_cursors[index]

            result = session.execute(
                _build_issue_alias_query(active_indexes),
                variable_values=variables,
            )

            for index in active_indexes:
                issues = Connection.model_validate(result[f"repo{index}"]["issues"])

                for node in issues.nodes:
                    _add_issue_contribution(
                        contributions_by_repository[index],
                        node,
                        since,
                        until,
                    )

                if issues.pageInfo.hasNextPage:
                    issue_cursors[index] = issues.pageInfo.endCursor
                else:
                    issue_active[index] = False

        while any(pr_active):
            active_indexes = [index for index, active in enumerate(pr_active) if active]

            variables = {"pageSize": page_size}
            for index in active_indexes:
                owner, name = repository_parts[index]
                variables[f"owner{index}"] = owner
                variables[f"name{index}"] = name
                variables[f"after{index}"] = pr_cursors[index]

            result = session.execute(
                _build_pr_alias_query(active_indexes),
                variable_values=variables,
            )

            for index in active_indexes:
                prs = Connection.model_validate(result[f"repo{index}"]["pullRequests"])

                for node in prs.nodes:
                    _add_pr_contribution(
                        contributions_by_repository[index],
                        node,
                        since,
                        until,
                    )

                if prs.pageInfo.hasNextPage:
                    pr_cursors[index] = prs.pageInfo.endCursor
                else:
                    pr_active[index] = False

    return [
        list(contributions.values()) for contributions in contributions_by_repository
    ]
