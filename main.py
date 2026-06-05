from __future__ import annotations

import os
import sys
from typing import Annotated

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
    repository: Annotated[
        str,
        typer.Argument(help="조회할 GitHub 저장소 경로입니다. 예: owner/repo"),
    ] = DEFAULT_REPOSITORY,
) -> None:
    """Fetch basic repository counts from GitHub GraphQL API."""
    try:
        data = fetch_repository_counts(repository)
    except Exception as error:
        print(f"오류: {error}", file=sys.stderr)
        raise typer.Exit(1) from error

    typer.echo(f"Repository: {data['nameWithOwner']}")
    typer.echo(f"Issues: {data['issues']['totalCount']}")
    typer.echo(f"Pull Requests: {data['pullRequests']['totalCount']}")


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
