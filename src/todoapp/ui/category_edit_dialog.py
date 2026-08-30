from __future__ import annotations

from collections.abc import Callable
from datetime import date

from nicegui import ui

from todoapp.domain.models import CATEGORY_COLORS
from todoapp.domain.service import TodoService
from todoapp.ui.confirm_dialog import ConfirmDialog
from todoapp.ui.dialog_base import DialogMixin


class CategoryEditDialog(DialogMixin):
    def __init__(
        self,
        service: TodoService,
        refresh_all: Callable[[], None],
        confirm_dialog: ConfirmDialog,
    ) -> None:
        self._service = service
        self._refresh_all = refresh_all
        self._confirm_dialog = confirm_dialog
        self._category_id: str | None = None
        self._selected_color = CATEGORY_COLORS[0]
        self._color_swatches: dict[str, ui.button] = {}

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-96 gap-2"):
            ui.label("カテゴリの編集").classes("text-lg font-bold")
            with ui.row().classes("items-center gap-2"):
                self._color_badge = ui.badge("").props("outline")
                self._name_input = ui.input(label="カテゴリ名").classes("flex-grow")
            self._kind_input = ui.input(label="種別").classes("w-full")
            self._expiry_input = ui.input(label="有効期限日").props("type=date").classes("w-full")
            ui.label("カラー").classes("text-sm text-gray-500 -mb-1")
            with ui.row().classes("gap-1"):
                for color in CATEGORY_COLORS:
                    swatch = ui.button(on_click=lambda _, c=color: self._select_color(c))
                    swatch.props(f"round unelevated color={color} size=sm")
                    self._color_swatches[color] = swatch
            with ui.row().classes("w-full justify-between mt-2"):
                ui.button("削除", on_click=self._confirm_delete).props("flat color=negative")
                with ui.row().classes("gap-2"):
                    ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                    ui.button("保存", on_click=self._save)

    def open_for(self, category_id: str) -> None:
        category = next((c for c in self._service.categories if c.id == category_id), None)
        if category is None:
            return
        self._category_id = category_id
        self._name_input.value = category.name
        self._kind_input.value = category.kind
        self._expiry_input.value = category.expiry_date.isoformat() if category.expiry_date else ""
        self._color_badge.text = category.name
        self._select_color(category.color)
        self.dialog.open()

    def _select_color(self, color: str) -> None:
        self._selected_color = color
        self._color_badge.props(f"color={color}")
        for swatch_color, swatch in self._color_swatches.items():
            if swatch_color == color:
                swatch.classes(add="ring-2 ring-offset-1 ring-black")
            else:
                swatch.classes(remove="ring-2 ring-offset-1 ring-black")

    def _save(self) -> None:
        if self._category_id is None:
            return
        expiry_date = date.fromisoformat(self._expiry_input.value) if self._expiry_input.value else None
        self._service.edit_category(
            self._category_id,
            name=self._name_input.value.strip(),
            kind=self._kind_input.value.strip(),
            expiry_date=expiry_date,
            color=self._selected_color,
        )
        self.dialog.close()
        self._refresh_all()

    def _confirm_delete(self) -> None:
        if self._category_id is None:
            return
        linked_count = self._service.linked_item_count([self._category_id])
        if linked_count == 0:
            self._delete()
            return
        message = (
            f"このカテゴリを使用しているアイテムが{linked_count}件あります。"
            "削除すると、それらのアイテムは「未定」に戻ります。削除しますか?"
        )
        self._confirm_dialog.open(message, self._delete)

    def _delete(self) -> None:
        if self._category_id is None:
            return
        self._service.delete_category(self._category_id)
        self.dialog.close()
        self._refresh_all()
