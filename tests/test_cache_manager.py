from pathlib import Path

from cache_manager import load_cache, save_cache


def test_load_cache_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.json"
    assert load_cache(missing_file) == {}


def test_load_cache_invalid_json(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{ invalid json", encoding="utf-8")
    assert load_cache(cache_path) == {}


def test_save_cache_creates_directory_and_file(tmp_path: Path) -> None:
    cache_path = tmp_path / "nested" / "cache.json"
    save_cache(cache_path, {"contributions": []})
    assert cache_path.exists()


def test_save_and_load_cache(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    data = {"contributions": [{"user": "pangsu12"}]}
    save_cache(cache_path, data)
    assert load_cache(cache_path) == data