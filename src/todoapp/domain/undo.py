from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from todoapp.domain.models import Category, DailyEstimate, LinkTemplate, TodoItem

MAX_HISTORY = 50


@dataclass(frozen=True)
class Snapshot:
    """Undo/Redoで復元する状態。実行記録の本体は含めない(取り消しで、その後の計測時間が消えないようにするため)。"""

    items: list[TodoItem]
    categories: list[Category]
    link_templates: list[LinkTemplate]
    estimate_history: list[DailyEstimate] = field(default_factory=list)  # アイテムの編集と食い違わないよう一緒に戻す


class UndoHistory:
    def __init__(self, limit: int = MAX_HISTORY) -> None:
        self._undo: deque[tuple[str, Snapshot]] = deque(maxlen=limit)
        self._redo: deque[tuple[str, Snapshot]] = deque(maxlen=limit)

    def push(self, label: str, before: Snapshot) -> None:
        self._undo.append((label, before))
        self._redo.clear()

    def undo(self, current: Snapshot) -> tuple[str, Snapshot] | None:
        return self._swap(self._undo, self._redo, current)

    def redo(self, current: Snapshot) -> tuple[str, Snapshot] | None:
        return self._swap(self._redo, self._undo, current)

    @staticmethod
    def _swap(
        source: deque[tuple[str, Snapshot]], target: deque[tuple[str, Snapshot]], current: Snapshot
    ) -> tuple[str, Snapshot] | None:
        if not source:
            return None
        label, snapshot = source.pop()
        target.append((label, current))
        return label, snapshot
