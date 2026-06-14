from typer.testing import CliRunner

import main

runner = CliRunner()


def test_format_option_is_case_insensitive(monkeypatch):
    def fake_load_or_fetch_contributions(
        repos,
        token,
        output,
        no_cache=False,
        since=None,
        until=None,
    ):
        return [[] for _ in repos]

    monkeypatch.setattr(
        main,
        "_load_or_fetch_contributions",
        fake_load_or_fetch_contributions,
    )

    result = runner.invoke(
        main.app,
        [
            "oss2026hnu/reposcore-py",
            "--format",
            "CSV",
            "--token",
            "dummy-token",
        ],
    )

    assert result.exit_code == 0
