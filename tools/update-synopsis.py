#!/usr/bin/env python3
"""
update-synopsis.py — CLI 도움말을 캡처하여 최상위 README.md를 생성합니다.

사용법:
    python tools/update-synopsis.py

동작:
    1. reposcore-py CLI의 --help 출력 캡처
    2. README-template.md의 {{ SYNOPSIS }}를 실제 help 출력으로 치환
    3. README.md 생성
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
README_TEMPLATE = ROOT / "README-template.md"
README_OUTPUT = ROOT / "README.md"


def capture_cli_help() -> str:
    candidates = [
        ["reposcore", "--help"],
        [sys.executable, str(ROOT / "main.py"), "--help"],
    ]

    last_error = ""

    for command in candidates:
        try:
            proc = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            last_error = f"{command[0]} 명령을 찾을 수 없습니다: {error}"
            continue

        output = ((proc.stdout or "") + (proc.stderr or "")).strip()

        if proc.returncode == 0 and output:
            return output

        last_error = output or f"{command} returned exit code {proc.returncode}"

    raise RuntimeError("CLI 도움말을 생성하지 못했습니다:\n" + last_error)


def normalize(help_text: str) -> str:
    for marker in ["Usage:", "usage:"]:
        index = help_text.find(marker)

        if index != -1:
            return help_text[index:].strip()

    return help_text.strip()


def render_readme(synopsis: str) -> str:
    if not README_TEMPLATE.exists():
        raise FileNotFoundError(f"README 템플릿을 찾을 수 없습니다: {README_TEMPLATE}")

    template = README_TEMPLATE.read_text(encoding="utf-8")
    placeholder = "{{ SYNOPSIS }}"

    if placeholder not in template:
        raise RuntimeError(f"README-template.md에 {placeholder} 플레이스홀더가 없습니다.")

    return template.replace(placeholder, synopsis)


def main() -> None:
    print("[캡처] CLI --help 실행 중...")

    raw_help = capture_cli_help()
    synopsis = normalize(raw_help)

    README_OUTPUT.write_text(render_readme(synopsis), encoding="utf-8")

    print(synopsis)
    print(f"\n[생성] {README_OUTPUT}")


if __name__ == "__main__":
    main()