from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from gql.transport.exceptions import TransportQueryError, TransportServerError

from cache_manager import load_cache, save_cache
from calc_score import (
    UserContributionCounts,
    calculate_repository_scores,
    calculate_total_scores,
)
from gh_service import (
    fetch_contributions,
    fetch_multiple_contributions,
    fetch_open_issue_claims,
)
from output_writer import build_output, write_output

DEFAULT_CLAIM_KEYWORDS = [
    "제가 하겠습니다",
    "제가하겠습니다",
    "내가 하겠습니다",
    "내가하겠습니다",
    "진행하겠습니다",
    "진행 하겠습니다",
    "할게요",
    "하겠습니다",
    "I'll do this",
    "I will do this",
    "I'll take this",
    "I will take this",
    "Assign to me",
    "assign to me",
]

app = typer.Typer(help="reposcore-py CLI")


def version_callback(value: bool) -> None:
    if value:
        try:
            ver = version("reposcore-py")
        except PackageNotFoundError:
            ver = "unknown"
        typer.echo(ver)
        raise typer.Exit()


class OutputFormatOption(str, Enum):
    csv = "csv"
    txt = "txt"
    html = "html"


def split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/")

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("저장소는 owner/repo 형식이어야 합니다.")

    return parts[0], parts[1]


def _parse_claim_keywords(keywords: str | None) -> list[str]:
    if keywords is None:
        return DEFAULT_CLAIM_KEYWORDS

    parsed_keywords = [
        keyword.strip()
        for keyword in keywords.split(",")
        if keyword.strip()
    ]

    if not parsed_keywords:
        raise ValueError("선점 키워드는 하나 이상 입력해야 합니다.")

    return parsed_keywords


def _dump_contributions(
    contributions: list[UserContributionCounts],
) -> list[dict]:
    return [
        contribution.model_dump()
        if hasattr(contribution, "model_dump")
        else vars(contribution)
        for contribution in contributions
    ]


def _load_or_fetch_contributions(
    repos: list[str],
    token: str,
    output: str | None,
    no_cache: bool = False,
    since: date | None = None,
    until: date | None = None,
) -> list[list[UserContributionCounts]]:
    all_contributions: list[list[UserContributionCounts]] = [[] for _ in repos]
    cache_paths: list[Path | None] = []
    missing_indexes: list[int] = []
    missing_repos: list[str] = []

    for index, repo in enumerate(repos):
        owner, repo_name = split_repository(repo)
        cache_path = None

        if not no_cache and output:
            cache_path = Path(output) / f"{owner}_{repo_name}" / "cache.json"

        cache_paths.append(cache_path)
        cached_data = load_cache(cache_path) if cache_path else {}

        if "contributions" in cached_data:
            all_contributions[index] = [
                UserContributionCounts(**contribution)
                for contribution in cached_data["contributions"]
            ]
        else:
            missing_indexes.append(index)
            missing_repos.append(repo)

    if missing_repos:
        if len(missing_repos) == 1:
            fetched_contributions = [
                fetch_contributions(missing_repos[0], token, since, until)
            ]
        else:
            fetched_contributions = fetch_multiple_contributions(
                missing_repos,
                token,
                since,
                until,
            )

        for index, repo, contributions in zip(
            missing_indexes,
            missing_repos,
            fetched_contributions,
            strict=True,
        ):
            all_contributions[index] = contributions
            cache_path = cache_paths[index]

            if cache_path:
                owner, repo_name = split_repository(repo)
                save_cache(
                    cache_path,
                    {
                        "metadata": {
                            "repository": repo,
                            "owner": owner,
                            "name": repo_name,
                            "schemaVersion": 1,
                            "generatedAt": datetime.now(timezone.utc)
                            .isoformat(timespec="seconds")
                            .replace("+00:00", "Z"),
                        },
                        "contributions": _dump_contributions(contributions),
                    },
                )

    return all_contributions


@app.command()
def main(
    repos: Annotated[
        list[str],
        typer.Argument(
            help="조회할 GitHub 저장소 경로입니다. 예: owner/repo1 owner/repo2"
        ),
    ],
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="현재 버전을 출력하고 종료합니다.",
            is_eager=True,
            callback=version_callback,
        ),
    ] = False,
    format: Annotated[
        OutputFormatOption,
        typer.Option(
            "--format", "-f", help="출력 파일 형식을 지정합니다. (csv | txt | html)"
        ),
    ] = OutputFormatOption.txt,
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help=(
                "결과를 저장할 출력 디렉터리 경로입니다. "
                "생략하면 파일로 저장하지 않고 stdout에 출력합니다. 예: ./result"
            ),
        ),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option(
            "--token",
            "-t",
            help=(
                "GitHub Personal Access Token. "
                "미제공 시 GITHUB_TOKEN 환경 변수를 사용합니다."
            ),
        ),
    ] = None,
    aggregate: Annotated[
        bool,
        typer.Option(
            "--aggregate",
            help="여러 저장소의 결과를 하나로 합산하여 전체 기여 점수를 출력합니다.",
        ),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="캐시를 사용하지 않고 GitHub API에서 최신 데이터를 다시 조회합니다.",
        ),
    ] = False,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help=(
                "이 날짜 이후의 기여만 점수 계산에 포함합니다. "
                "예: 2026-06-01 (YYYY-MM-DD)"
            ),
        ),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option(
            "--until",
            help=(
                "이 날짜까지의 기여만 점수 계산에 포함합니다. "
                "예: 2026-06-10 (YYYY-MM-DD)"
            ),
        ),
    ] = None,
    claims: Annotated[
        bool,
        typer.Option(
            "--claims",
            help="열린 이슈의 선점 현황을 출력합니다. 점수 계산은 실행하지 않습니다.",
        ),
    ] = False,
    keywords: Annotated[
        str | None,
        typer.Option(
            "--keywords",
            help=(
                "선점 키워드를 쉼표로 구분하여 지정합니다. 예: '제가 하겠습니다,할게요'"
            ),
        ),
    ] = None,
) -> None:
    """Fetch basic repository counts from GitHub GraphQL API."""

    if len(repos) == 0:
        print("오류: 저장소를 하나 이상 입력해주세요.", file=sys.stderr)
        raise typer.Exit(1)

    resolved_token = token or os.environ.get("GITHUB_TOKEN")
    if not resolved_token:
        typer.echo(
            "오류: GITHUB_TOKEN 환경 변수 또는 --token 옵션이 필요합니다.", err=True
        )
        raise typer.Exit(1)

    # --claims 모드: 점수 계산 없이 선점 현황만 출력 후 종료
    if claims:
        try:
            claim_keywords = _parse_claim_keywords(keywords)
        except ValueError as error:
            print(f"오류: {error}", file=sys.stderr)
            raise typer.Exit(1) from error

        for repo in repos:
            try:
                open_issues = fetch_open_issue_claims(repo, resolved_token)

                claimed_issues = []
                unclaimed_issues = []

                for issue in open_issues:
                    # issue 작성자 추출
                    issue_author = (
                        issue.get("author", {}).get("login")
                        if issue.get("author")
                        else "알 수 없음"
                    )

                    # issue 라벨 목록 추출
                    labels = [
                        label.get("name")
                        for label in issue.get("labels", {}).get("nodes", [])
                        if label.get("name")
                    ]

                    matched_kw = None
                    claimant = None

                    comments_nodes = issue.get("comments", {}).get("nodes", [])
                    if comments_nodes:
                        latest_comment = comments_nodes[0]
                        body = latest_comment.get("body", "")

                        for kw in claim_keywords:
                            if kw in body:
                                matched_kw = kw
                                claimant = (
                                    latest_comment.get("author", {}).get("login")
                                    if latest_comment.get("author")
                                    else "알 수 없음"
                                )
                                break

                    if matched_kw:
                        claimed_issues.append(
                            {
                                "number": issue["number"],
                                "title": issue["title"],
                                "author": issue_author,
                                "labels": labels,
                                "claimant": claimant,
                                "keyword": matched_kw,
                            }
                        )
                    else:
                        unclaimed_issues.append(
                            {
                                "number": issue["number"],
                                "title": issue["title"],
                                "author": issue_author,
                                "labels": labels,
                            }
                        )

                if len(repos) > 1:
                    print(f"=== Repository: {repo} ===")
                    print()

                claimed_count = len(claimed_issues)
                unclaimed_count = len(unclaimed_issues)
                total_count = claimed_count + unclaimed_count

                print("Claim Summary\n")
                print(f"Total open issues: {total_count}")
                print(f"Claimed issues: {claimed_count}")
                print(f"Unclaimed issues: {unclaimed_count}")
                print()

                print("Claimed Issues\n")
                for ci in claimed_issues:
                    labels_str = ", ".join(ci["labels"]) if ci["labels"] else "없음"
                    print(f"- #{ci['number']} {ci['title']}")
                    print(f"  Author: {ci['author']}")
                    print(f"  Labels: {labels_str}")
                    print(f"  Claimed by: {ci['claimant']}")
                    print(f"  Matched keyword: {ci['keyword']}")
                if not claimed_issues:
                    print("(선점된 이슈가 없습니다.)\n")

                print("\nUnclaimed Issues\n")
                for ui in unclaimed_issues:
                    labels_str = ", ".join(ui["labels"]) if ui["labels"] else "없음"
                    print(f"- #{ui['number']} {ui['title']}")
                    print(f"  Author: {ui['author']}")
                    print(f"  Labels: {labels_str}")
                if not unclaimed_issues:
                    print("(미선점된 이슈가 없습니다.)\n")
                print()

            except Exception as error:
                print(f"오류 ({repo}): {error}", file=sys.stderr)
                raise typer.Exit(1) from error
        raise typer.Exit(0)

    parsed_since: date | None = None
    parsed_until: date | None = None

    if since is not None:
        try:
            parsed_since = date.fromisoformat(since)
        except ValueError:
            print(
                f"오류: --since 날짜 형식이 잘못되었습니다. "
                f"YYYY-MM-DD 형식으로 입력하세요. (입력값: {since})",
                file=sys.stderr,
            )
            raise typer.Exit(1)

    if until is not None:
        try:
            parsed_until = date.fromisoformat(until)
        except ValueError:
            print(
                f"오류: --until 날짜 형식이 잘못되었습니다. "
                f"YYYY-MM-DD 형식으로 입력하세요. (입력값: {until})",
                file=sys.stderr,
            )
            raise typer.Exit(1)

    if (
        parsed_since is not None
        and parsed_until is not None
        and parsed_since > parsed_until
    ):
        print("오류: --since 날짜가 --until 날짜보다 늦습니다.", file=sys.stderr)
        raise typer.Exit(1)

    try:
        all_contributions = _load_or_fetch_contributions(
            repos,
            resolved_token,
            output,
            no_cache,
            parsed_since,
            parsed_until,
        )

    except ValueError as error:
        print(f"오류: {error}", file=sys.stderr)
        raise typer.Exit(1) from error

    except TransportQueryError as error:
        print(
            "오류: 저장소를 찾을 수 없습니다. 존재 여부와 권한을 확인하세요. "
            f"(Detail: {error})",
            file=sys.stderr,
        )
        raise typer.Exit(3) from error

    except TransportServerError as error:
        status_code = getattr(error, "code", None)

        if status_code in [403, 429]:
            print(
                "오류: GitHub API 호출 한도(Rate Limit)를 초과했습니다. "
                f"잠시 후 다시 시도하세요. (Status: {status_code})",
                file=sys.stderr,
            )
            raise typer.Exit(2) from error
        if status_code == 401:
            print(
                "오류: GitHub API 인증에 실패했습니다. "
                f"GITHUB_TOKEN을 확인하세요. (Status: {status_code})",
                file=sys.stderr,
            )
            raise typer.Exit(4) from error

        print(
            "오류: GitHub 서버 통신 중 HTTP 오류가 발생했습니다. "
            f"(Status: {status_code})",
            file=sys.stderr,
        )
        raise typer.Exit(1) from error

    except Exception as error:
        print(f"오류: {error}", file=sys.stderr)
        raise typer.Exit(1) from error

    format_value = format.value

    try:
        if aggregate:
            scores = calculate_total_scores(all_contributions)
        else:
            flat_contributions = [
                contrib
                for repo_contribs in all_contributions
                for contrib in repo_contribs
            ]
            scores = calculate_repository_scores(flat_contributions)

        content = build_output(scores, format_value)
        write_output(content, output, format_value)

    except Exception as error:
        print(f"출력 오류: {error}", file=sys.stderr)
        raise typer.Exit(1) from error


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
