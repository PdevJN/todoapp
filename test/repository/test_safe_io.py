import os
from pathlib import Path

import pytest

from todoapp.repository import safe_io


def test_atomic_write_creates_file_and_parent(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "a.json"
    safe_io.atomic_write_text(path, "hello")
    assert path.read_text(encoding="utf-8") == "hello"


def test_atomic_write_keeps_old_content_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "a.json"
    path.write_text("old", encoding="utf-8")

    def boom(src: object, dst: object) -> None:
        raise OSError("disk error")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        safe_io.atomic_write_text(path, "new")

    assert path.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["a.json"]  # 一時ファイルが残らない


def test_atomic_write_with_backup_keeps_previous_generation(tmp_path: Path) -> None:
    path = tmp_path / "a.json"
    safe_io.atomic_write_text(path, "v1", backup=True)
    assert not (tmp_path / "a.json.bak").exists()

    safe_io.atomic_write_text(path, "v2", backup=True)

    assert path.read_text(encoding="utf-8") == "v2"
    assert (tmp_path / "a.json.bak").read_text(encoding="utf-8") == "v1"


def test_quarantine_moves_file_aside(tmp_path: Path) -> None:
    path = tmp_path / "a.json"
    path.write_text("broken", encoding="utf-8")

    moved = safe_io.quarantine(path)

    assert not path.exists()
    assert moved.name.startswith("a.json.corrupt-")
    assert moved.read_text(encoding="utf-8") == "broken"
