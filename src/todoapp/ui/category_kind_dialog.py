from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin


class CategoryKindDialog(DialogMixin):
    def __init__(self, service: TodoService, refresh_all: Callable[[], None]) -> None:
        self._service = service
        self._refresh_all = refresh_all
        self._category_id: str | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            ui.label("種別を入力").classes("text-lg font-bold")
            self._kind_input = ui.input(label="種別").classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("閉じる", on_click=self.dialog.close).props("flat")
                ui.button("保存", on_click=self._save)

    def open_for(self, category_id: str) -> None:
        category = next((c for c in self._service.categories if c.id == category_id), None)
        if category is None:
            return
        self._category_id = category_id
        self._kind_input.value = category.kind
        self.dialog.open()

    def _save(self) -> None:
        if self._category_id is None:
            return
        category = next((c for c in self._service.categories if c.id == self._category_id), None)
        if category is None:
            return
        self._service.edit_category(
            self._category_id,
            name=category.name,
            kind=self._kind_input.value.strip(),
            expiry_date=category.expiry_date,
            color=category.color,
        )
        self.dialog.close()
        self._refresh_all()
