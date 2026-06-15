from __future__ import annotations

from datetime import date
from typing import Any

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
    stateReason: str | None = None


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
    """주어진 GitHub 토큰을 사용하여 GraphQL API 요청을 위한 클라이언트 인스턴스를 생성합니다."""
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
    """주어진 날짜 문자열이 since와 until 범위 안에 포함되는지 확인합니다."""
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
    """'owner/repo' 형식의 저장소 문자열을 소유자와 저장소 이름으로 분리하여 반환합니다."""
    parts = repository.split("/")

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("저장소는 owner/repo 형식이어야 합니다.")

    return parts[0], parts[1]


def _get_contribution(
    contributions: dict[str, UserContributionCounts],
    user: str,
) -> UserContributionCounts:
    """사용자의 기여 데이터 객체를 반환하거나, 없다면 새로 생성하여 사전에 추가한 뒤 반환합니다."""
    if user not in contributions:
        contributions[user] = UserContributionCounts(user=user)

    return contributions[user]


def _add_issue_contribution(
    contributions: dict[str, UserContributionCounts],
    node: Node,
    since: date | None = None,
    until: date | None = None,
) -> None:
    """이슈 노드 정보를 바탕으로 라벨 및 닫힘 사유, 날짜 범위를 확인하여 사용자의 이슈 기여 개수를 추가합니다."""
    if node.author is None:
        return

    # 중복 또는 계획되지 않음으로 닫힌 이슈는 제외
    if node.stateReason in ["DUPLICATE", "NOT_PLANNED"]:
        return

    if not _is_in_date_range(node.createdAt, since, until):
        return

    labels = [label.name.lower() for label in node.labels.nodes]

    if "documentation" in labels:
        contribution = _get_contribution(contributions, node.author.login)
        contribution.doc_issue_count += 1
    elif "bug" in labels or "enhancement" in labels:
        contribution = _get_contribution(contributions, node.author.login)
        contribution.feature_bug_issue_count += 1


def _add_pr_contribution(
    contributions: dict[str, UserContributionCounts],
    node: Node,
    since: date | None = None,
    until: date | None = None,
) -> None:
    """PR 노드 정보를 바탕으로 라벨 및 병합 날짜 범위를 확인하여 사용자의 PR 기여 개수를 추가합니다."""
    if node.author is None:
        return

    if not _is_in_date_range(node.mergedAt, since, until):
        return

    labels = [label.name.lower() for label in node.labels.nodes]

    if "documentation" in labels:
        contribution = _get_contribution(contributions, node.author.login)
        contribution.doc_pr_count += 1
    elif "typo" in labels:
        contribution = _get_contribution(contributions, node.author.login)
        contribution.typo_pr_count += 1
    elif "bug" in labels or "enhancement" in labels:
        contribution = _get_contribution(contributions, node.author.login)
        contribution.feature_bug_pr_count += 1


def _build_issue_alias_query(indexes: list[int]):
    """여러 저장소의 이슈를 한 번에 조회하기 위해 GraphQL repository alias를 적용한 쿼리를 생성합니다."""
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
                issues(
                    first: $pageSize,
                    after: $after{index},
                    states: [OPEN, CLOSED],
                ) {{
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                    nodes {{
                        author {{ login }}
                        createdAt
                        stateReason
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
    """여러 저장소의 병합된 PR을 한 번에 조회하기 위해 GraphQL repository alias를 적용한 쿼리를 생성합니다."""
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
                pullRequests(
                    first: $pageSize,
                    after: $after{index},
                    states: [MERGED],
                ) {{
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
    """단일 저장소에서 GraphQL API를 사용해 기여자별 활동 데이터를 수집하고 분류하여 반환합니다."""
    owner, name = _split_repository(repository)
    client = create_client(token)
    contributions: dict[str, UserContributionCounts] = {}

    combined_query = gql("""
    query(
        $owner: String!,
        $name: String!,
        $pageSize: Int!,
        $fetchIssues: Boolean!,
        $issueCursor: String,
        $fetchPRs: Boolean!,
        $prCursor: String
    ) {
        repository(owner: $owner, name: $name) {
            issues(first: $pageSize, after: $issueCursor, states: [OPEN, CLOSED]) @include(if: $fetchIssues) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    author { login }
                    createdAt
                    stateReason
                    labels(first: 10) {
                        nodes { name }
                    }
                }
            }
            pullRequests(first: $pageSize, after: $prCursor, states: [MERGED]) @include(if: $fetchPRs) {
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

    issue_cursor = None
    pr_cursor = None
    has_next_issue = True
    has_next_pr = True

    with client as session:
        while has_next_issue or has_next_pr:
            result = session.execute(
                combined_query,
                variable_values={
                    "owner": owner,
                    "name": name,
                    "pageSize": page_size,
                    "fetchIssues": has_next_issue,
                    "issueCursor": issue_cursor,
                    "fetchPRs": has_next_pr,
                    "prCursor": pr_cursor,
                },
            )

            repo_data = result.get("repository", {})

            if has_next_issue and "issues" in repo_data:
                issues = Connection.model_validate(repo_data["issues"])
                for node in issues.nodes:
                    _add_issue_contribution(contributions, node, since, until)

                has_next_issue = issues.pageInfo.hasNextPage
                issue_cursor = issues.pageInfo.endCursor

            if has_next_pr and "pullRequests" in repo_data:
                prs = Connection.model_validate(repo_data["pullRequests"])
                for node in prs.nodes:
                    _add_pr_contribution(contributions, node, since, until)

                has_next_pr = prs.pageInfo.hasNextPage
                pr_cursor = prs.pageInfo.endCursor

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

            variables: dict[str, str | int | None] = {"pageSize": page_size}
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

            variables: dict[str, str | int | None] = {"pageSize": page_size}
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


# ── 이슈 선점 데이터 수집 ──────────────────────────────────────────
def fetch_open_issue_claims(repository: str, token: str) -> list[dict[str, Any]]:
    """GitHub GraphQL API를 조회하여 열린 이슈 정보 및 가장 최근 댓글 명세를 수집합니다."""
    owner, name = _split_repository(repository)
    client = create_client(token)

    # GraphQL query에 after cursor 및 pageInfo 연동 보강
    query = gql("""
    query($owner: String!, $name: String!, $after: String) {
        repository(owner: $owner, name: $name) {
            issues(
                states: OPEN,
                first: 100,
                after: $after,
                orderBy: {field: CREATED_AT, direction: DESC}
            ) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    number
                    title
                    url
                    author {
                        login
                    }
                    labels(first: 10) {
                        nodes {
                            name
                        }
                    }
                    comments(last: 1) {
                        nodes {
                            author {
                                login
                            }
                            body
                            createdAt
                        }
                    }
                }
            }
        }
    }
    """)

    all_issues = []
    cursor = None
    has_next_page = True

    # pageInfo.hasNextPage와 endCursor를 활용한 전체 열린 이슈 페이지네이션 반복 루프
    with client as session:
        while has_next_page:
            result = session.execute(
                query,
                variable_values={
                    "owner": owner,
                    "name": name,
                    "after": cursor,
                },
            )

            issues_data = result.get("repository", {}).get("issues", {})
            all_issues.extend(issues_data.get("nodes", []))

            page_info = issues_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

    return all_issues