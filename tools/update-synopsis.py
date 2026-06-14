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

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README_TEMPLATE = ROOT / "README-template.md"
README_OUTPUT = ROOT / "README.md"


def capture_cli_help() -> str:
    candidates = [
        [sys.executable, str(ROOT / "main.py"), "--help"],
        ["reposcore", "--help"],
    ]

    last_error = ""
    env = os.environ.copy()
    env["COLUMNS"] = "100"

    # CI 환경(GitHub Actions 등)에서 Rich의 강제 색상/서식 출력 방지
    env["NO_COLOR"] = "1"
    env.pop("GITHUB_ACTIONS", None)
    env.pop("CI", None)

    for command in candidates:
        try:
            proc = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                env=env,
            )
        except FileNotFoundError as error:
            last_error = f"{command[0]} 명령을 찾을 수 없습니다: {error}"
            continue

        output = ((proc.stdout or "") + (proc.stderr or "")).strip()

        if proc.returncode == 0 and output:
            if command[0] == sys.executable:
                output = output.replace("Usage: main.py", "Usage: reposcore", 1)
            return output

        last_error = output or f"{command} returned exit code {proc.returncode}"

    raise RuntimeError("CLI 도움말을 생성하지 못했습니다:\n" + last_error)


def normalize(help_text: str) -> str:

    # ANSI 색상 코드 제거
    # (환경 변수를 무시하고 강제로 색상이 섞인 경우 정규식 매칭 실패 방지)
    help_text = re.sub(r"\x1b\[[0-9;]*m", "", help_text)

    # 터미널 박스 문자(Rich) 제거 (GitHub Markdown에서의 한글 너비 정렬 깨짐 방지)
    # 로컬(Unicode: ╭, ─, │) 및 CI 폴백(ASCII: +, -, |) 환경을 모두 고려
    help_text = re.sub(
        r"^[╭\+][─\-]+\s*(.*?)\s*[─\-]*[╮\+]$",
        r"\1",
        help_text,
        flags=re.MULTILINE,
    )
    help_text = re.sub(
        r"^[╰\+][─\-]*[╯\+]$",
        "",
        help_text,
        flags=re.MULTILINE,
    )
    help_text = re.sub(r"^[│\|]", " ", help_text, flags=re.MULTILINE)
    help_text = re.sub(r"\s*[│\|]$", "", help_text, flags=re.MULTILINE)

    for marker in ["Usage:", "usage:"]:
        index = help_text.find(marker)

        if index != -1:
            normalized = help_text[index:].strip()
            result = "\n".join(line.rstrip() for line in normalized.splitlines())
            return re.sub(r"\n{3,}", "\n\n", result)

    normalized = help_text.strip()
    result = "\n".join(line.rstrip() for line in normalized.splitlines())
    return re.sub(r"\n{3,}", "\n\n", result)


def render_readme(synopsis: str) -> str:
    if not README_TEMPLATE.exists():
        raise FileNotFoundError(f"README 템플릿을 찾을 수 없습니다: {README_TEMPLATE}")

    template = README_TEMPLATE.read_text(encoding="utf-8")
    placeholder = "{{ SYNOPSIS }}"

    if placeholder not in template:
        raise RuntimeError(
            f"README-template.md에 {placeholder} 플레이스홀더가 없습니다."
        )

    return template.replace(placeholder, synopsis).rstrip() + "\n"


def main() -> None:
    print("[캡처] CLI --help 실행 중...")

    raw_help = capture_cli_help()
    synopsis = normalize(raw_help)

    README_OUTPUT.write_text(render_readme(synopsis), encoding="utf-8")

    print(synopsis)
    print(f"\n[생성] {README_OUTPUT}")


if __name__ == "__main__":
    main()
