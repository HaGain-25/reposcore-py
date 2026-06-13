import json
from pathlib import Path
from typing import Any


def load_cache(cache_path: Path) -> dict[str, Any]:
    """지정 경로의 cache.json을 읽어 dict로 반환.
    파일이 없거나 파싱 실패 시 빈 dict 반환.
    """
    if not cache_path.is_file():
        return {}

    try:
        content = cache_path.read_text(encoding="utf-8")
        return json.loads(content)
    except Exception:
        return {}


def save_cache(cache_path: Path, data: dict[str, Any]) -> None:
    """dict를 cache.json으로 직렬화하여 저장. 디렉토리가 없으면 자동 생성."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
