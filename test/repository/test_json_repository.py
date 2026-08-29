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
