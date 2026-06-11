from __future__ import annotations

import os
import sys
from enum import Enum
from typing import Annotated

import typer
from gql.transport.exceptions import TransportQueryError, TransportServerError

from calc_score import calculate_total_scores, UserContributionCounts
from gh_service import fetch_contributions
from output_writer import build_output, write_output

DEFAULT_REPOSITORY = "oss2026hnu/reposcore-py"

app = typer.Typer(help="reposcore-py CLI")


# [추가] --format 옵션을 csv, txt, html로 제한하기 위한 Enum 클래스 정의
class OutputFormatOption(str, Enum):
    csv = "csv"
    txt = "txt"
    html = "html"


def split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/", maxsplit=1)

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("저장소는 owner/repo 형식이어야 합니다.")

    return parts[0], parts[1]


@app.command()
def main(
    repos: Annotated[
        list[str],
        typer.Argument(help="조회할 GitHub 저장소 경로입니다. 예: owner/repo1 owner/repo2"),
    ],
    # [변경] 기존 str 타입에서 Enum(OutputFormatOption) 기반 타입으로 변경하여 CLI 검증 추가
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
    # [추가] 요구사항에 명시된 다중 저장소 집계 여부 선택을 위한 플래그 추가
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
            contributions = fetch_contributions(repo, resolved_token)
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

    # --- [추가] 수집 완료 데이터 출력 및 집계(--aggregate) 제어 로직 ---
    format_value = format.value  # Enum에서 문자열 추출 (csv, txt, html)

    if aggregate:
        try:
            # 1. calc_score.py에 구현된 집계 함수로 전체 기여 점수 합산
            total_scores = calculate_total_scores(all_contributions)
            
            # 2. Pydantic 모델 리스트를 output_writer가 해석할 수 있는 매핑 딕셔너리 구조로 덤프
            aggregated_results = [score.model_dump() for score in total_scores]
            
            # 3. 데이터 출력 및 파일 저장 수행
            content = build_output(aggregated_results, format_value)
            write_output(content, output, format_value)
        except Exception as error:
            print(f"집계 출력 오류: {error}", file=sys.stderr)
            raise typer.Exit(1) from error
    else:
        try:
            # 개별 저장소 결과를 순서대로 평탄화(Flatten)하여 개별 결과 출력 구조 유지
            flatten_results = []
            for repo_contribs in all_contributions:
                for contrib in repo_contribs:
                    flatten_results.append(contrib.model_dump())
                    
            content = build_output(flatten_results, format_value)
            write_output(content, output, format_value)
        except Exception as error:
            print(f"출력 오류: {error}", file=sys.stderr)
            raise typer.Exit(1) from error


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()