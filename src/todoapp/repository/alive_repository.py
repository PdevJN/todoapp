from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from todoapp.repository.safe_io import atomic_write_text

DEFAULT_ALIVE_PATH = Path.home() / ".todoapp" / "alive.json"


class AliveRepository:
    """実行中の「最後に動作していた時刻」を保存する。todos.jsonを頻繁に書き換えないよう別ファイルにする。"""

    def __init__(self, path: Path = DEFAULT_ALIVE_PATH) -> None:
        self._path = path

    def load(self) -> datetime | None:
        try:
            raw: Any = json.loads(self._path.read_text(encoding="utf-8"))
            return datetime.fromisoformat(raw["alive_at"])
        except (OSError, ValueError, KeyError, TypeError):
            # 無い・壊れている場合は、生存時刻が分からないものとして扱う
            return None

    def save(self, value: datetime) -> None:
        atomic_write_text(self._path, json.dumps({"alive_at": value.isoformat()}))
