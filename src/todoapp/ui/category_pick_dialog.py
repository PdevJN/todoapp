from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin


class CategoryPickDialog(DialogMixin):
    def __init__(self, service: TodoService, refresh_all: Callable[[], None]) -> None:
        self._service = service
        self._refresh_all = refresh_all
        self._item_id: str | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            ui.label("カテゴリを選択").classes("text-lg font-bold")
            self.category_container = ui.column().classes("w-full gap-1")
            with ui.row().classes("w-full items-center gap-2"):
                self._new_category_input = ui.input(placeholder="新しいカテゴリ名").classes("flex-grow")
                ui.button("追加", on_click=self._create_and_assign)
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def open_for(self, item_id: str) -> None:
        self._item_id = item_id
        self._new_category_input.value = ""
        self._render()
        self.dialog.open()

    def _render(self) -> None:
        self.category_container.clear()
        with self.category_container:
            if not self._service.categories:
                ui.label("カテゴリがまだありません").classes("text-gray-400 italic")
            for category in self._service.categories:
                badge = ui.badge(category.name).props(f"outline color={category.color}").classes("cursor-pointer")
                badge.on("click", lambda cid=category.id: self._assign(cid))

    def _assign(self, category_id: str | None) -> None:
        if self._item_id is None:
            return
        self._service.set_item_category(self._item_id, category_id)
        self.dialog.close()
        self._refresh_all()

    def _create_and_assign(self) -> None:
        name = self._new_category_input.value.strip()
        if not name:
            return
        category = self._service.add_category(name)
        self._assign(category.id)
