from __future__ import annotations

from datetime import date

from nicegui import ui

from todoapp.domain.models import Category
from todoapp.domain.service import TodoService
from todoapp.ui.formatting import format_duration


class CategorySummaryDialog:
    def __init__(self, service: TodoService) -> None:
        self._service = service
        self._selected_key: str | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[28rem] gap-2"):
            ui.label("カテゴリ別集計").classes("text-lg font-bold")
            self.category_container = ui.column().classes("w-full gap-1")
            ui.separator()
            ui.label("種別ごとの集計").classes("text-sm font-bold text-gray-600")
            self.kind_container = ui.column().classes("w-full gap-1")
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def is_open(self) -> bool:
        return bool(self.dialog.value)

    def open(self) -> None:
        self.refresh()
        self.dialog.open()

    def refresh(self) -> None:
        today = date.today()
        category_totals = self._service.category_today_totals(today)
        categories_by_id = {c.id: c for c in self._service.categories}

        self.category_container.clear()
        with self.category_container:
            rows = [
                (category_id, categories_by_id.get(category_id) if category_id else None, seconds)
                for category_id, seconds in category_totals.items()
            ]
            if not rows:
                ui.label("本日の記録はまだありません").classes("text-gray-400 italic")
            for category_id, category, seconds in rows:
                self._render_category_row(category_id, category, seconds)

        kind_totals = self._service.kind_today_totals(today)
        self.kind_container.clear()
        with self.kind_container:
            if not kind_totals:
                ui.label("-").classes("text-gray-400")
            for kind in sorted(kind_totals):
                ui.label(f"{kind}: {format_duration(kind_totals[kind])}").classes("font-mono text-right w-full")

    def _select(self, key: str) -> None:
        self._selected_key = key
        self.refresh()

    def _render_category_row(self, category_id: str | None, category: Category | None, seconds: float) -> None:
        key = category_id or "__uncategorized__"
        is_selected = self._selected_key == key
        name = category.name if category is not None else "未定"

        classes = "w-full justify-between items-center border-b py-1 px-1 rounded cursor-pointer"
        classes += " bg-blue-200" if is_selected else ""
        with ui.row().classes(classes) as row:
            row.on("click", lambda k=key: self._select(k))
            ui.label(name).classes("font-medium")
            ui.label(format_duration(seconds)).classes("text-gray-500 font-mono")
