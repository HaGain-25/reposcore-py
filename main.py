from __future__ import annotations

import os
import sys
from typing import Annotated, Optional

import typer
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport


DEFAULT_REPOSITORY = "oss2026hnu/reposcore-py"

app = typer.Typer(help="reposcore-py CLI")


def split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/", maxsplit=1)

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("저장소는 owner/repo 형식이어야 합니다.")

    return parts[0], parts[1]


def fetch_repository_counts(repository: str) -> dict[str, object]:
    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise RuntimeError("GitHub GraphQL API 호출을 위해 GITHUB_TOKEN 환경 변수가 필요합니다.")

    owner, name = split_repository(repository)

    transport = RequestsHTTPTransport(
        url="https://api.github.com/graphql",
        headers={"Authorization": f"Bearer {token}"},
        verify=True,
        retries=3,
    )

    query = gql(
        """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            nameWithOwner
            issues(first: 1) {
              totalCount
            }
            pullRequests(first: 1) {
              totalCount
            }
          }
        }
        """
    )

    with Client(transport=transport, fetch_schema_from_transport=False) as session:
        result = session.execute(
            query,
            variable_values={
                "owner": owner,
                "name": name,
            },
        )

    return result["repository"]


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

    for repo in repos:
        try:
            data = fetch_repository_counts(repo)
        except Exception as error:
            print(f"오류 ({repo}): {error}", file=sys.stderr)
            raise typer.Exit(1) from error

        typer.echo(f"Repository: {data['nameWithOwner']}")
        typer.echo(f"Issues: {data['issues']['totalCount']}")
        typer.echo(f"Pull Requests: {data['pullRequests']['totalCount']}")


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
