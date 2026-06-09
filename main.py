from __future__ import annotations

import os
import sys
from typing import Annotated, Optional


import typer

from calc_score import UserContributionCounts
from gh_service import fetch_contributions
from output_writer import build_output, write_output


DEFAULT_REPOSITORY = "oss2026hnu/reposcore-py"

app = typer.Typer(help="reposcore-py CLI")


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
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="출력 파일 형식을 지정합니다. (csv | txt | html)"),
    ] = "txt",
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="결과를 저장할 출력 디렉터리 경로입니다. 예: ./result"),
    ] = None,
) -> None:
    """Fetch basic repository counts from GitHub GraphQL API."""

    if len(repos) == 0:
        typer.echo("오류: 저장소를 하나 이상 입력해주세요.", err=True)
        raise typer.Exit(1)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        typer.echo("오류: GITHUB_TOKEN 환경 변수가 필요합니다.", err=True)
        raise typer.Exit(1)

    all_contributions: list[list[UserContributionCounts]] = []

    for repo in repos:
        try:
            contributions = fetch_contributions(repo, token)
            all_contributions.append(contributions)
        except Exception as error:
            print(f"오류 ({repo}): {error}", file=sys.stderr)
            raise typer.Exit(1) from error

def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
