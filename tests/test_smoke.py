from typer.testing import CliRunner

# 실제 CLI 앱 객체를 가져옵니다.
from main import app

runner = CliRunner()


def test_module_imports():
    import gh_service
    import main

    assert main is not None
    assert gh_service is not None


def test_cli_help_command():
    result = runner.invoke(app, ["--help"])

    # 종료 코드가 0(정상)인지 확인
    assert result.exit_code == 0
    # 출력된 텍스트에 도움말 관련 키워드가 포함되어 있는지 확인
    assert "Usage" in result.stdout or "help" in result.stdout
