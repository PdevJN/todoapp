from datetime import datetime
from pathlib import Path

import pytest

from todoapp.repository.alive_repository import AliveRepository


def test_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert AliveRepository(tmp_path / "alive.json").load() is None


def test_save_then_load_roundtrips_the_time(tmp_path: Path) -> None:
    repository = AliveRepository(tmp_path / "alive.json")

    repository.save(datetime(2026, 10, 10, 9, 30, 15))

    assert repository.load() == datetime(2026, 10, 10, 9, 30, 15)


def test_save_creates_missing_parent_directory(tmp_path: Path) -> None:
    repository = AliveRepository(tmp_path / "nested" / "alive.json")

    repository.save(datetime(2026, 10, 10, 9))

    assert repository.load() == datetime(2026, 10, 10, 9)


@pytest.mark.parametrize("content", ["", "not json", "[]", '{"alive_at": 123}', '{"alive_at": "garbage"}', "{}"])
def test_load_returns_none_for_broken_content(tmp_path: Path, content: str) -> None:
    path = tmp_path / "alive.json"
    path.write_text(content, encoding="utf-8")

    assert AliveRepository(path).load() is None


def test_save_leaves_no_temp_file(tmp_path: Path) -> None:
    from datetime import datetime

    AliveRepository(path=tmp_path / "alive.json").save(datetime(2026, 10, 10, 9, 0, 0))
    assert [p.name for p in tmp_path.iterdir()] == ["alive.json"]
