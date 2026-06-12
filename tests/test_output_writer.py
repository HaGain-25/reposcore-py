from __future__ import annotations

import pytest

from output_writer import (
    build_csv_output,
    build_html_output,
    build_output,
    build_txt_output,
    normalize_output_format,
    write_output,
)


# output_writer 가 기대하는 입력 구조 (GraphQL 응답과 동일한 중첩 dict)
def make_result(name: str, issues: int, prs: int) -> dict:
    return {
        "nameWithOwner": name,
        "issues": {"totalCount": issues},
        "pullRequests": {"totalCount": prs},
    }


SAMPLE = [make_result("owner/repo1", 5, 3)]


# ── normalize_output_format ────────────────────────────────
@pytest.mark.parametrize("value", ["csv", "txt", "html"])
def test_normalize_allows_supported_formats(value):
    assert normalize_output_format(value) == value


def test_normalize_is_case_insensitive():
    assert normalize_output_format("CSV") == "csv"


def test_normalize_rejects_unsupported_format():
    with pytest.raises(ValueError):
        normalize_output_format("json")


# ── build_csv_output ───────────────────────────────────────
def test_csv_has_header_and_row():
    out = build_csv_output(SAMPLE)
    # csv.writer 는 \r\n 으로 줄을 끝내므로 정확히 일치 비교 대신 부분 포함으로 검증
    assert "repo,issues,pull_requests" in out
    assert "owner/repo1" in out
    assert ",5," in out
    assert ",3" in out


# ── build_txt_output ───────────────────────────────────────
def test_txt_has_headers_and_values():
    out = build_txt_output(SAMPLE)
    for header in ("repo", "issues", "pull_requests"):
        assert header in out
    assert "owner/repo1" in out
    assert "5" in out
    assert "3" in out


# ── build_html_output ──────────────────────────────────────
def test_html_has_table_and_name():
    out = build_html_output(SAMPLE)
    assert "<table>" in out
    assert "owner/repo1" in out


def test_html_escapes_special_characters():
    out = build_html_output([make_result("a<b>&x", 1, 2)])
    assert "&lt;" in out
    assert "&gt;" in out
    assert "&amp;" in out
    assert "<b>" not in out  # 원본 특수문자가 그대로 남으면 안 됨


# ── build_output 분기 ──────────────────────────────────────
def test_build_output_csv_branch():
    assert build_output(SAMPLE, "csv") == build_csv_output(SAMPLE)


def test_build_output_txt_branch():
    assert build_output(SAMPLE, "txt") == build_txt_output(SAMPLE)


def test_build_output_html_branch():
    assert build_output(SAMPLE, "html") == build_html_output(SAMPLE)


def test_build_output_rejects_unsupported_format():
    with pytest.raises(ValueError):
        build_output(SAMPLE, "json")


# ── write_output: stdout ───────────────────────────────────
def test_write_output_to_stdout(capsys):
    result = write_output("hello-content", None, "csv")
    captured = capsys.readouterr()
    assert result is None
    assert "hello-content" in captured.out


# ── write_output: 파일 저장 ────────────────────────────────
@pytest.mark.parametrize("fmt", ["csv", "txt", "html"])
def test_write_output_creates_result_file(tmp_path, fmt):
    content = f"sample-{fmt}"
    result_path = write_output(content, str(tmp_path), fmt)

    expected = tmp_path / f"results.{fmt}"
    assert result_path == expected
    assert expected.exists()
    assert expected.read_text(encoding="utf-8") == content
