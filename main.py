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
    UserScore,
    calculate_repository_scores,
    calculate_total_scores,
)

# fetch_open_issue_claims 함수 임포트 추가
from gh_service import (
    DEFAULT_PAGE_SIZE,
    fetch_contributions,
    fetch_multiple_contributions,
    fetch_open_issue_claims,
)
from output_writer import build_output, write_output

DEFAULT_REPOSITORY = "oss2026hnu/reposcore-py"

# 기본 선점 키워드 상수 추가
DEFAULT_CLAIM_KEYWORDS = [
    "제가 하겠습니다",
    "진행하겠습니다",
    "할게요",
    "I'll take this",
]

CACHE_SCHEMA_VERSION = 1
CACHE_TTL_SECONDS = 60 * 60

app = typer.Typer(help="reposcore-py CLI")


def version_callback(value: bool) -> None:
    if value:
        try:
            ver = version("reposcore-py")
        except PackageNotFoundError:
            ver = "unknown"
        typer.echo(ver)
        raise typer.Exit()


# --format 옵션을 csv, txt, html로 제한하기 위한 Enum 클래스 정의
class OutputFormatOption(str, Enum):
    csv = "csv"
    txt = "txt"
    html = "html"


def split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/")

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("저장소는 owner/repo 형식이어야 합니다.")

    return parts[0], parts[1]


def _format_cache_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _is_cache_valid(
    cached_data: dict,
    since: date | None,
    until: date | None,
) -> bool:
    if "contributions" not in cached_data:
        return False

    metadata = cached_data.get("metadata")
    if not isinstance(metadata, dict):
        return False

    if metadata.get("schemaVersion") != CACHE_SCHEMA_VERSION:
        return False

    if metadata.get("since") != _format_cache_date(since):
        return False

    if metadata.get("until") != _format_cache_date(until):
        return False

    generated_at = metadata.get("generatedAt")
    if not isinstance(generated_at, str):
        return False

    try:
        generated_datetime = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return False

    now = datetime.now(timezone.utc)

    if (now - generated_datetime).total_seconds() > CACHE_TTL_SECONDS:
        return False

    return True


def _dump_contributions(
    contributions: list[UserContributionCounts],
) -> list[dict]:
    return [
        contribution.model_dump()
        if hasattr(contribution, "model_dump")
        else vars(contribution)
        for contribution in contributions
    ]


def _score_to_result(score: UserScore) -> dict:
    """UserScore를 output_writer가 기대하는 dict 형태로 변환합니다."""
    contribution = score.contribution
    return {
        "nameWithOwner": contribution.user,
        "issues": {
            "totalCount": contribution.feature_bug_issue_count
            + contribution.doc_issue_count,
        },
        "pullRequests": {
            "totalCount": contribution.feature_bug_pr_count
            + contribution.doc_pr_count
            + contribution.typo_pr_count,
        },
        "totalScore": score.score,
    }


def _load_or_fetch_contributions(
    repos: list[str],
    token: str,
    output: str,
    no_cache: bool = False,
    since: date | None = None,
    until: date | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[list[UserContributionCounts]]:
    all_contributions: list[list[UserContributionCounts]] = [[] for _ in repos]
    cache_paths: list[Path | None] = []
    missing_indexes: list[int] = []
    missing_repos: list[str] = []

    for index, repo in enumerate(repos):
        owner, repo_name = split_repository(repo)
        cache_path = None

        # --no-cache 가 지정되면 캐시 경로를 만들지 않아 읽기/쓰기 모두 건너뜁니다.
        if not no_cache:
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
                fetch_contributions(missing_repos[0], token, since, until, page_size)
            ]
        else:
            fetched_contributions = fetch_multiple_contributions(
                missing_repos,
                token,
                since,
                until,
                page_size,
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
                            "schemaVersion": CACHE_SCHEMA_VERSION,
                            "generatedAt": datetime.now(timezone.utc)
                            .isoformat(timespec="seconds")
                            .replace("+00:00", "Z"),
                            "since": _format_cache_date(since),
                            "until": _format_cache_date(until),
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
    # 기존 str 타입에서 Enum(OutputFormatOption) 기반 타입으로 변경하여 CLI 검증 추가
    format: Annotated[
        OutputFormatOption,
        typer.Option(
            "--format",
            "-f",
            help="출력 파일 형식을 지정합니다. (csv | txt | html)",
            case_sensitive=False,
        ),
    ] = OutputFormatOption.txt,
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="결과를 저장할 출력 디렉터리 경로입니다.",
        ),
    ] = "./result",
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
    # 요구사항에 명시된 다중 저장소 집계 여부 선택을 위한 플래그 추가
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
    # main.py에 --claims 옵션 추가
    claims: Annotated[
        bool,
        typer.Option(
            "--claims",
            help="열린 issue의 선점 현황을 조회합니다.",
        ),
    ] = False,
    # main.py에 --keywords 옵션 추가
    keywords: Annotated[
        str | None,
        typer.Option(
            "--keywords",
            help="이슈 선점 키워드 목록입니다. 쉼표로 구분합니다.",
        ),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option(
            "--page-size",
            help="GraphQL 페이지네이션의 페이지 크기입니다. (1~100)",
            envvar="REPOSCORE_PAGE_SIZE",
            min=1,
            max=100,
        ),
    ] = DEFAULT_PAGE_SIZE,
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

    # --claims 모드 조건 부합 시 점수 계산 흐름으로 진입하지 않고
    # 선점 현황만 출력 후 즉시 종료합니다.
    if claims:
        claim_keywords = (
            [kw.strip() for kw in keywords.split(",")]
            if keywords
            else DEFAULT_CLAIM_KEYWORDS
        )

        for repo in repos:
            try:
                open_issues = fetch_open_issue_claims(repo, resolved_token)

                claimed_issues = []
                unclaimed_issues = []

                for issue in open_issues:
                    matched_kw = None
                    claimant = None

                    comments_nodes = issue.get("comments", {}).get("nodes", [])
                    if comments_nodes:
                        latest_comment = comments_nodes[0]
                        body = latest_comment.get("body", "")

                        # 댓글 본문에서 선점 키워드 감지
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
                                "claimant": claimant,
                                "keyword": matched_kw,
                            }
                        )
                    else:
                        unclaimed_issues.append(
                            {"number": issue["number"], "title": issue["title"]}
                        )

                if len(repos) > 1:
                    print(f"=== Repository: {repo} ===")

                # 요구사항 레이아웃 명세대로 분리 출력
                print("Claimed Issues\n")
                for ci in claimed_issues:
                    print(f"- #{ci['number']} {ci['title']}")
                    print(f"  Claimed by: {ci['claimant']}")
                    print(f"  Matched keyword: {ci['keyword']}")
                if not claimed_issues:
                    print("(선점된 이슈가 없습니다.)\n")

                print("\nUnclaimed Issues\n")
                for ui in unclaimed_issues:
                    print(f"- #{ui['number']} {ui['title']}")
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
            page_size,
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

    # --- 수집 완료 데이터 출력 및 집계(--aggregate) 제어 로직 ---
    format_value = format.value

    try:
        if aggregate:
            scores = calculate_total_scores(all_contributions)
        else:
            # 저장소별로 점수를 매긴 뒤 하나의 목록으로 펼칩니다.
            scores = [
                score
                for repo_contributions in all_contributions
                for score in calculate_repository_scores(repo_contributions)
            ]

        results = [_score_to_result(score) for score in scores]

        # 사용자가 선택한 형식만 파일로 저장
        content = build_output(results, format_value)
        saved_path = write_output(content, output, format_value)

        print("결과가 다음 경로에 저장되었습니다:")
        print(f"  - {saved_path.absolute()}")
    except Exception as error:
        print(f"출력 오류: {error}", file=sys.stderr)
        raise typer.Exit(1) from error


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
