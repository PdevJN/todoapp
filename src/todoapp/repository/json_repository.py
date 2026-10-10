from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from todoapp.domain.models import AppData, Category, ExecutionRecord, TodoItem
from todoapp.repository.safe_io import atomic_write_text, backup_path, quarantine

SCHEMA_VERSION = 1

DEFAULT_PATH = Path.home() / ".todoapp" / "todos.json"


class UnsupportedSchemaVersionError(Exception):
    pass


# 壊れたファイル(途中で切れたJSON・必須キー欠落など)を示す例外。スキーマ違いは含めない
_CORRUPT_ERRORS = (ValueError, KeyError, TypeError, AttributeError)


class JsonTodoRepository:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path

    def load(self) -> AppData:
        if self._path.exists():
            try:
                return self._read(self._path)
            except _CORRUPT_ERRORS:
                quarantine(self._path)
        return self._restore_from_backup()

    def _restore_from_backup(self) -> AppData:
        backup = backup_path(self._path)
        if backup.exists():
            try:
                data = self._read(backup)
            except _CORRUPT_ERRORS:
                pass
            else:
                # 復元直後に再度落ちても本体だけで読めるよう、すぐ書き戻す
                atomic_write_text(self._path, backup.read_text(encoding="utf-8"))
                return data
        # 壊れたファイルは退避済みなので、空で起動しても内容は失われない
        return AppData(items=[], records=[])

    @staticmethod
    def _read(path: Path) -> AppData:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("version") != SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(raw.get("version"))
        items = [TodoItem.from_dict(item) for item in raw["items"]]
        records = [ExecutionRecord.from_dict(record) for record in raw["records"]]
        categories = [Category.from_dict(category) for category in raw.get("categories", [])]
        return AppData(items=items, records=records, categories=categories)

    def save(self, data: AppData) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "items": [item.to_dict() for item in data.items],
            "records": [record.to_dict() for record in data.records],
            "categories": [category.to_dict() for category in data.categories],
        }
        atomic_write_text(self._path, json.dumps(payload, ensure_ascii=False, indent=2), backup=True)
