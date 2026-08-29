from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from todoapp.domain.models import AppData, ExecutionRecord, TodoItem

SCHEMA_VERSION = 1

DEFAULT_PATH = Path.home() / ".todoapp" / "todos.json"


class UnsupportedSchemaVersionError(Exception):
    pass


class JsonTodoRepository:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path

    def load(self) -> AppData:
        if not self._path.exists():
            return AppData(items=[], records=[])
        raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
        if raw.get("version") != SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(raw.get("version"))
        items = [TodoItem.from_dict(item) for item in raw["items"]]
        records = [ExecutionRecord.from_dict(record) for record in raw["records"]]
        return AppData(items=items, records=records)

    def save(self, data: AppData) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SCHEMA_VERSION,
            "items": [item.to_dict() for item in data.items],
            "records": [record.to_dict() for record in data.records],
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
