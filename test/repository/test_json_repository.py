import json
from datetime import date, datetime
from pathlib import Path

import pytest

from todoapp.domain.models import AppData, ExecutionRecord, ScheduleType, TodoItem
from todoapp.repository.json_repository import JsonTodoRepository, UnsupportedSchemaVersionError


def test_load_returns_empty_app_data_when_file_missing(tmp_path: Path) -> None:
    repository = JsonTodoRepository(path=tmp_path / "todos.json")
    data = repository.load()
    assert data == AppData(items=[], records=[])


def test_save_then_load_roundtrips(tmp_path: Path) -> None:
    repository = JsonTodoRepository(path=tmp_path / "todos.json")
    item = TodoItem(
        name="散歩",
        schedule_type=ScheduleType.WEEKLY,
        anchor_date=date(2026, 8, 24),
        estimate_hours=1.5,
    )
    record = ExecutionRecord(
        item_id=item.id,
        item_name=item.name,
        start_time=datetime(2026, 8, 30, 9, 0, 0),
        end_time=datetime(2026, 8, 30, 9, 20, 0),
    )
    repository.save(AppData(items=[item], records=[record]))

    loaded = repository.load()

    assert loaded == AppData(items=[item], records=[record])


def test_raises_on_unsupported_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    path.write_text(json.dumps({"version": 999, "items": [], "records": []}), encoding="utf-8")
    repository = JsonTodoRepository(path=path)

    with pytest.raises(UnsupportedSchemaVersionError):
        repository.load()


def _item_data(name: str) -> AppData:
    return AppData(items=[TodoItem(name=name, schedule_type=ScheduleType.DAILY, anchor_date=date(2026, 8, 24))], records=[])


def test_load_restores_from_backup_when_main_file_is_corrupt(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    repository = JsonTodoRepository(path=path)
    first = _item_data("一つ目")
    repository.save(first)
    repository.save(_item_data("二つ目"))  # 一つ目が.bakに残る
    path.write_text('{"version": 1, "items": [', encoding="utf-8")  # 書き込み途中で切れた状態

    loaded = repository.load()

    assert [i.name for i in loaded.items] == ["一つ目"]
    assert list(tmp_path.glob("todos.json.corrupt-*"))  # 壊れたファイルは退避される


def test_load_starts_empty_and_keeps_corrupt_file_when_no_backup(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    path.write_text("not json", encoding="utf-8")

    loaded = JsonTodoRepository(path=path).load()

    assert loaded == AppData(items=[], records=[])
    assert [p.read_text(encoding="utf-8") for p in tmp_path.glob("todos.json.corrupt-*")] == ["not json"]


def test_load_does_not_quarantine_unsupported_schema(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    path.write_text(json.dumps({"version": 999, "items": [], "records": []}), encoding="utf-8")

    with pytest.raises(UnsupportedSchemaVersionError):
        JsonTodoRepository(path=path).load()

    assert path.exists()


def test_load_uses_backup_when_main_file_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    repository = JsonTodoRepository(path=path)
    repository.save(_item_data("一つ目"))
    repository.save(_item_data("二つ目"))
    path.unlink()

    loaded = repository.load()

    assert [i.name for i in loaded.items] == ["一つ目"]


def test_restore_from_backup_writes_main_file_back(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    repository = JsonTodoRepository(path=path)
    repository.save(_item_data("一つ目"))
    repository.save(_item_data("二つ目"))
    path.write_text("broken", encoding="utf-8")
    repository.load()

    path.with_name("todos.json.bak").unlink()  # 復元直後に再度落ちても、本体だけで読める
    loaded = repository.load()

    assert [i.name for i in loaded.items] == ["一つ目"]
