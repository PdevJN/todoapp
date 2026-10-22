from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from todoapp.domain.models import AppData, Category, DailyEstimate, ExecutionRecord, LinkTemplate, TodoItem
from todoapp.repository.safe_io import atomic_write_text, backup_path, quarantine

SCHEMA_VERSION = 3

DEFAULT_PATH = Path.home() / ".todoapp" / "todos.json"

# 旧バージョンの辞書を、1つ新しいバージョンの辞書へ変換する関数。キーは変換元のバージョン
Migration = Callable[[dict[str, Any]], dict[str, Any]]


def _migrate_v1_to_v2(raw: dict[str, Any]) -> dict[str, Any]:
    """v2でリンクテンプレート(`link_templates`)とアイテムのリンク(`links`)を追加した。"""
    items = [{**item, "links": []} for item in raw["items"]]
    return {**raw, "version": 2, "items": items, "link_templates": []}


def _migrate_v2_to_v3(raw: dict[str, Any]) -> dict[str, Any]:
    """v3で日ごとの見積り履歴(`estimate_history`)と稼働日の上書き(`workday_overrides`)を追加した。

    移行時点で有効な`本日の見積り`は、導入日の見積りを失わないよう履歴へ入れる。
    """
    history = []
    for item in raw["items"]:
        seconds = round(item.get("today_estimate_hours", 0.0) * 3600)
        if item.get("today_estimate_date") and seconds > 0:
            history.append({"date": item["today_estimate_date"], "item_id": item["id"], "seconds": seconds})
    return {**raw, "version": 3, "estimate_history": history, "workday_overrides": {}}


MIGRATIONS: dict[int, Migration] = {1: _migrate_v1_to_v2, 2: _migrate_v2_to_v3}


class UnsupportedSchemaVersionError(Exception):
    pass


# 壊れたファイル(途中で切れたJSON・必須キー欠落など)を示す例外。スキーマ違いは含めない
_CORRUPT_ERRORS = (ValueError, KeyError, TypeError, AttributeError)


class JsonTodoRepository:
    def __init__(self, path: Path = DEFAULT_PATH, migrations: Mapping[int, Migration] | None = None) -> None:
        self._path = path
        self._migrations = MIGRATIONS if migrations is None else migrations

    def load(self) -> AppData:
        if self._path.exists():
            try:
                return self._read(self._path, keep_pre_migration=True)
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

    def _read(self, path: Path, *, keep_pre_migration: bool = False) -> AppData:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        version = raw.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version > SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(version)  # 新しい版のファイルは読めないだけなので触らない
        if version < SCHEMA_VERSION:
            if version not in self._migrations:
                raise UnsupportedSchemaVersionError(version)
            if keep_pre_migration:
                shutil.copy2(path, path.with_name(f"{self._path.name}.v{version}.bak"))
            while version < SCHEMA_VERSION:
                if version not in self._migrations:
                    raise UnsupportedSchemaVersionError(version)
                raw = self._migrations[version](raw)
                version = raw["version"]
        items = [TodoItem.from_dict(item) for item in raw["items"]]
        records = [ExecutionRecord.from_dict(record) for record in raw["records"]]
        categories = [Category.from_dict(category) for category in raw.get("categories", [])]
        link_templates = [LinkTemplate.from_dict(template) for template in raw.get("link_templates", [])]
        estimate_history = [DailyEstimate.from_dict(entry) for entry in raw.get("estimate_history", [])]
        workday_overrides = {
            date.fromisoformat(day): bool(workday) for day, workday in raw.get("workday_overrides", {}).items()
        }
        return AppData(
            items=items,
            records=records,
            categories=categories,
            link_templates=link_templates,
            estimate_history=estimate_history,
            workday_overrides=workday_overrides,
        )

    def save(self, data: AppData) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "items": [item.to_dict() for item in data.items],
            "records": [record.to_dict() for record in data.records],
            "categories": [category.to_dict() for category in data.categories],
            "link_templates": [template.to_dict() for template in data.link_templates],
            "estimate_history": [entry.to_dict() for entry in data.estimate_history],
            "workday_overrides": {day.isoformat(): workday for day, workday in sorted(data.workday_overrides.items())},
        }
        atomic_write_text(self._path, json.dumps(payload, ensure_ascii=False, indent=2), backup=True)
