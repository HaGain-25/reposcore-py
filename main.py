from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
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
# RepositoryAccessError 임포트 추가
from gh_service import (
    RepositoryAccessError,
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
CACHE_TTL_SECONDS = 60 * 60


def version_callback(value: bool) -> None:
    if value:
        try:
            ver = version("reposcore-py")
        except PackageNotFoundError:
            ver = "unknown"
        typer.echo(ver)
        raise typer.Exit()


AVAILABLE_FORMATS = ("csv", "txt", "html")


def parse_output_formats(raw: str) -> list[str]:
    """--format 입력을 검증해 출력 형식 목록으로 변환합니다."""
    tokens = [token.strip().lower() for token in raw.split(",")]

    if any(token == "" for token in tokens):
        raise ValueError("형식이 비어 있습니다. 사용 가능한 형식: csv, txt, html")

    invalid = [token for token in tokens if token not in AVAILABLE_FORMATS]
    if invalid:
        raise ValueError(
            f"유효하지 않은 형식: {', '.join(invalid)}. "
            "사용 가능한 형식: csv, txt, html"
        )

    deduped: list[str] = []
    for token in tokens:
        if token not in deduped:
            deduped.append(token)
    return deduped


def split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/")

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"저장소 형식이 올바르지 않습니다: '{repository}' "
            "— owner/repo 형식으로 입력하세요."
        )

    return parts[0], parts[1]


def _validate_unique_repositories(repos: list[str]) -> None:
    """입력된 저장소 목록 중 중복된 저장소가 있는지 유효성을 검증합니다."""
    seen = set()
    for repo in repos:
        split_repository(repo)
        repo_lower = repo.lower()
        if repo_lower in seen:
            raise ValueError(f"같은 저장소가 중복 입력되었습니다: {repo}")
        seen.add(repo_lower)
        
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


def _parse_generated_at(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None

    try:
        generated_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    return generated_at.astimezone(timezone.utc)


def _is_cache_fresh(metadata: dict[str, object]) -> bool:
    generated_at = _parse_generated_at(metadata.get("generatedAt"))
    if generated_at is None:
        return False

    age_seconds = (datetime.now(timezone.utc) - generated_at).total_seconds()
    return age_seconds <= CACHE_TTL_SECONDS


def _is_cache_valid(
    cached_data: object,
    since: date | None = None,
    until: date | None = None,
) -> bool:
    if not isinstance(cached_data, dict):
        return False

    metadata = cached_data.get("metadata")
    if not isinstance(metadata, dict):
        return False

    if metadata.get("schemaVersion") != 1:
        return False

    if not _is_cache_fresh(metadata):
        return False

    contributions = cached_data.get("contributions")
    if not isinstance(contributions, list):
        return False

    for contribution in contributions:
        if not isinstance(contribution, dict):
            return False
        try:
            UserContributionCounts(**contribution)
        except Exception:
            return False

    return True


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

        if _is_cache_valid(cached_data, since, until):
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
        str | None,
        typer.Option(
            "--format",
            "-f",
            help=(
                "출력 형식을 쉼표로 구분해 지정합니다. "
                "사용 가능: csv, txt, html (예: csv,html). "
                "생략하면 모든 형식을 출력합니다."
            ),
        ),
    ] = None,
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

    # 중복 저장소 입력 검증 단계를 토큰 확인 및 API 진입 전 최상단에 배치
    try:
        _validate_unique_repositories(repos)
    except ValueError as error:
        print(f"오류: {error}", file=sys.stderr)
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
                        for comment in reversed(comments_nodes):
                            body = comment.get("body", "")

                            for kw in claim_keywords:
                                if kw in body:
                                    matched_kw = kw
                                    claimant = (
                                        comment.get("author", {}).get("login")
                                        if comment.get("author")
                                        else "알 수 없음"
                                    )
                                    break

                            if matched_kw:
                                break

                    if matched_kw:
                        claimed_issues.append(
                            {
                                "number": issue["number"],
                                "title": issue["title"],
                                "url": issue.get("url"),
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
                                "url": issue.get("url"),
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
                    if ci.get("url"):
                        print(f"  URL: {ci['url']}")
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
                    if ui.get("url"):
                        print(f"  URL: {ui['url']}")
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

    if format is None:
        selected_formats = list(AVAILABLE_FORMATS)
    else:
        try:
            selected_formats = parse_output_formats(format)
        except ValueError as error:
            print(f"오류: {error}", file=sys.stderr)
            raise typer.Exit(1) from error

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

    # gh_service가 던지는 실제 미발견 저장소 추적 예외 분기 추가
    except RepositoryAccessError as error:
        repos_str = ", ".join(error.failed_repositories)
        print(
            "오류: 다음 저장소를 찾을 수 없거나 접근할 수 없습니다"
            f"(오타·권한 확인): {repos_str}",
            file=sys.stderr,
        )
        raise typer.Exit(3) from error

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

        for output_format in selected_formats:
            content = build_output(scores, output_format)
            write_output(content, output, output_format)

    except Exception as error:
        print(f"출력 오류: {error}", file=sys.stderr)
        raise typer.Exit(1) from error


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()