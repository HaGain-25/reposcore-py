from __future__ import annotations

import csv
from html import escape
from io import StringIO
from pathlib import Path
from typing import Any, Literal

from tabulate import tabulate

OutputFormat = Literal["csv", "txt", "html"]


def normalize_output_format(output_format: str) -> OutputFormat:
    normalized = output_format.lower()

    if normalized not in ("csv", "txt", "html"):
        raise ValueError("출력 형식은 csv, txt, html 중 하나여야 합니다.")

    return normalized  # type: ignore[return-value]


def get_repository_name(result: dict[str, Any]) -> str:
    return str(result["nameWithOwner"])


def get_issue_count(result: dict[str, Any]) -> int:
    return int(result["issues"]["totalCount"])


def get_pull_request_count(result: dict[str, Any]) -> int:
    return int(result["pullRequests"]["totalCount"])


def build_txt_output(results: list[dict[str, Any]]) -> str:
    has_score = any("totalScore" in result for result in results)

    headers = ["repo", "issues", "pull_requests"] + (
        ["total_score"] if has_score else []
    )

    rows = [
        [
            get_repository_name(result),
            get_issue_count(result),
            get_pull_request_count(result),
        ]
        + ([result.get("totalScore", 0)] if has_score else [])
        for result in results
    ]

    return tabulate(rows, headers=headers)


def build_csv_output(results: list[dict[str, Any]]) -> str:
    has_score = any("totalScore" in result for result in results)

    output = StringIO()
    writer = csv.writer(output)

    headers = ["repo", "issues", "pull_requests"] + (
        ["total_score"] if has_score else []
    )
    writer.writerow(headers)

    for result in results:
        writer.writerow(
            [
                get_repository_name(result),
                get_issue_count(result),
                get_pull_request_count(result),
            ]
            + ([result.get("totalScore", 0)] if has_score else [])
        )

    return output.getvalue().strip()


def build_html_output(results: list[dict[str, Any]]) -> str:
    # 1. 데이터셋에 totalScore가 존재하는지 확인
    has_score = any("totalScore" in result for result in results)

    # 2. 점수가 있을 때만 HTML th 태그를 동적으로 생성
    th_score = "\n        <th>total_score</th>" if has_score else ""

    html_rows = []
    for result in results:
        row = (
            "      <tr>"
            f"<td>{escape(get_repository_name(result))}</td>"
            f"<td>{get_issue_count(result)}</td>"
            f"<td>{get_pull_request_count(result)}</td>"
        )
        # 점수가 있을 때만 안전하게 td 태그를 더해줍니다.
        if has_score:
            row += f"<td>{result.get('totalScore', 0)}</td>"

        row += "</tr>"
        html_rows.append(row)

    rows = "\n".join(html_rows)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>reposcore-py result</title>
</head>
<body>
  <table>
    <thead>
      <tr>
        <th>repo</th>
        <th>issues</th>
        <th>pull_requests</th>{th_score}
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</body>
</html>"""


def build_output(results: list[dict[str, Any]], output_format: str) -> str:
    normalized_format = normalize_output_format(output_format)

    if normalized_format == "csv":
        return build_csv_output(results)

    if normalized_format == "html":
        return build_html_output(results)

    return build_txt_output(results)


def write_output(
    content: str,
    output_dir: str | None,
    output_format: str,
) -> Path | None:
    if output_dir is None:
        print(content)
        return None

    normalized_format = normalize_output_format(output_format)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result_path = output_path / f"results.{normalized_format}"
    result_path.write_text(content, encoding="utf-8")

    return result_path
