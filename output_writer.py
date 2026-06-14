from __future__ import annotations

import csv
import json
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
    has_score = any("totalScore" in result for result in results)

    labels = []
    issues_data = []
    prs_data = []

    for result in results:
        name = get_repository_name(result)
        if has_score:
            score = result.get("totalScore", 0)
            labels.append(f"{name} (점수: {score})")
        else:
            labels.append(name)

        issues_data.append(get_issue_count(result))
        prs_data.append(get_pull_request_count(result))

    chart_height = max(400, len(results) * 40)

    labels_json = json.dumps(labels).replace("<", "\\u003c").replace(">", "\\u003e")
    issues_json = json.dumps(issues_data)
    prs_json = json.dumps(prs_data)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>reposcore-py result</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
  <style>
    .chart-container {{
      position: relative;
      height: {chart_height}px;
      width: 100%;
    }}
  </style>
</head>
<body>
  <div class="chart-container">
    <canvas id="myChart"></canvas>
  </div>
  <script>
    Chart.register(ChartDataLabels);
    const ctx = document.getElementById('myChart').getContext('2d');
    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: {labels_json},
        datasets: [
          {{
            label: 'Issues',
            data: {issues_json},
            backgroundColor: 'rgba(255, 99, 132, 0.5)',
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 1
          }},
          {{
            label: 'Pull Requests',
            data: {prs_json},
            backgroundColor: 'rgba(54, 162, 235, 0.5)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {{
          datalabels: {{
            color: '#000',
            anchor: 'end',
            align: 'right',
            offset: 4
          }}
        }},
        scales: {{
          x: {{
            beginAtZero: true
          }}
        }}
      }}
    }});
  </script>
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
