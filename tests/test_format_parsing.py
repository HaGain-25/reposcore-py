import pytest
from typer.testing import CliRunner

import main
from main import parse_output_formats

runner = CliRunner()


def test_parse_single():
    assert parse_output_formats("csv") == ["csv"]


def test_parse_multiple():
    assert parse_output_formats("csv,html") == ["csv", "html"]


def test_parse_strips_and_lowercases():
    assert parse_output_formats(" CSV , Html ") == ["csv", "html"]


def test_parse_dedupes_keeping_order():
    assert parse_output_formats("csv,csv,txt") == ["csv", "txt"]


@pytest.mark.parametrize("raw", ["", ",,,", "csv,", "csv,pdf", "json"])
def test_parse_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_output_formats(raw)


def test_cli_invalid_format_exits_1():
    result = runner.invoke(
        main.app,
        ["oss2026hnu/reposcore-py", "-t", "dummy", "--format", "csv,pdf"],
    )
    assert result.exit_code == 1
