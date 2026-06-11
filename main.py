from __future__ import annotations

import os
import sys
from enum import Enum
from typing import Annotated
from pathlib import Path

import typer
from gql.transport.exceptions import TransportQueryError, TransportServerError

from calc_score import calculate_total_scores, UserContributionCounts
from gh_service import fetch_contributions
from output_writer import build_output, write_output
from cache_manager import load_cache, save_cache

DEFAULT_REPOSITORY = "oss2026hnu/reposcore-py"

app = typer.Typer(help="reposcore-py CLI")



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


@app.command()
def main(
    repos: Annotated[
        list[str],
        typer.Argument(help="조회할 GitHub 저장소 경로입니다. 예: owner/repo1 owner/repo2"),
    ],
    # 기존 str 타입에서 Enum(OutputFormatOption) 기반 타입으로 변경하여 CLI 검증 추가
    format: Annotated[
        OutputFormatOption,
        typer.Option("--format", "-f", help="출력 파일 형식을 지정합니다. (csv | txt | html)"),
    ] = OutputFormatOption.txt,
    output: Annotated[
        str | None,
        typer.Option(
            "--output", "-o",
            help=(
                "결과를 저장할 출력 디렉터리 경로입니다. "
                "생략하면 파일로 저장하지 않고 stdout에 출력합니다. 예: ./result"
            ),
        ),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="GitHub Personal Access Token. 미제공 시 GITHUB_TOKEN 환경 변수를 사용합니다."),
    ] = None,
    # 요구사항에 명시된 다중 저장소 집계 여부 선택을 위한 플래그 추가
    aggregate: Annotated[
        bool,
        typer.Option("--aggregate", help="여러 저장소의 결과를 하나로 합산하여 전체 기여 점수를 출력합니다."),
    ] = False,
) -> None:
    """Fetch basic repository counts from GitHub GraphQL API."""

    if len(repos) == 0:
        print("오류: 저장소를 하나 이상 입력해주세요.", file=sys.stderr)
        raise typer.Exit(1)

    resolved_token = token or os.environ.get("GITHUB_TOKEN")
    if not resolved_token:
        typer.echo("오류: GITHUB_TOKEN 환경 변수 또는 --token 옵션이 필요합니다.", err=True)
        raise typer.Exit(1)

    all_contributions: list[list[UserContributionCounts]] = []

    for repo in repos:
        try:
            owner, repo_name = split_repository(repo)

            cache_path = None
            if output:
                cache_path = Path(output) / f"{owner}_{repo_name}" / "cache.json"

            cached_data = {}
            if cache_path:
                cached_data = load_cache(cache_path)

            if cached_data and "contributions" in cached_data:
                contributions = [UserContributionCounts(**c) for c in cached_data["contributions"]]
            else:
                contributions = fetch_contributions(repo, resolved_token)
                if cache_path:
                    dumped = [
                        c.model_dump() if hasattr(c, "model_dump") else vars(c)
                        for c in contributions
                    ]
                    save_cache(cache_path, {"contributions": dumped})
            all_contributions.append(contributions)

        except ValueError as error:
            print(f"오류 ({repo}): {error}", file=sys.stderr)
            raise typer.Exit(1) from error

        except TransportQueryError as error:
            print(f"오류 ({repo}): 저장소를 찾을 수 없습니다. 존재 여부와 권한을 확인하세요. (Detail: {error})", file=sys.stderr)
            raise typer.Exit(3) from error

        except TransportServerError as error:
            status_code = getattr(error, "code", None)

            if status_code in [403, 429]:
                print(f"오류 ({repo}): GitHub API 호출 한도(Rate Limit)를 초과했습니다. 잠시 후 다시 시도하세요. (Status: {status_code})", file=sys.stderr)
                raise typer.Exit(2) from error
            elif status_code == 401:
                print(f"오류 ({repo}): GitHub API 인증에 실패했습니다. GITHUB_TOKEN을 확인하세요. (Status: {status_code})", file=sys.stderr)
                raise typer.Exit(4) from error
            else:
                print(f"오류 ({repo}): GitHub 서버 통신 중 HTTP 오류가 발생했습니다. (Status: {status_code})", file=sys.stderr)
                raise typer.Exit(1) from error

        except Exception as error:
            print(f"오류 ({repo}): {error}", file=sys.stderr)
            raise typer.Exit(1) from error

    # --- 수집 완료 데이터 출력 및 집계(--aggregate) 제어 로직 ---
    format_value = format.value

    if aggregate:
        try:
            total_scores = calculate_total_scores(all_contributions)

            # output_writer가 100% 호환되도록 중첩 딕셔너리 구조로 직접 매핑 변환
            aggregated_results = []
            for score in total_scores:
                aggregated_results.append({
                    "nameWithOwner": score.user,
                    "issues": {"totalCount": score.feature_bug_issue_count + score.doc_issue_count},
                    "pullRequests": {"totalCount": score.feature_bug_pr_count + score.doc_pr_count + score.typo_pr_count},
                    "totalScore": score.score
                })
            content = build_output(aggregated_results, format_value)
            write_output(content, output, format_value)
        except Exception as error:
            print(f"집계 출력 오류: {error}", file=sys.stderr)
            raise typer.Exit(1) from error
    else:
        try:
            # 개별 출력 모드에서도 output_writer 규격에 맞추어 변환 처리
            flatten_results = []
            for repo_contribs in all_contributions:
                for contrib in repo_contribs:
                    flatten_results.append({
                        "nameWithOwner": contrib.user,
                        "issues": {"totalCount": contrib.feature_bug_issue_count + contrib.doc_issue_count},
                        "pullRequests": {"totalCount": contrib.feature_bug_pr_count + contrib.doc_pr_count + contrib.typo_pr_count}
                    })

            content = build_output(flatten_results, format_value)
            write_output(content, output, format_value)
        except Exception as error:
            print(f"출력 오류: {error}", file=sys.stderr)
            raise typer.Exit(1) from error


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()