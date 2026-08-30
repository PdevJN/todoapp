from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from todoapp.ui.dialog_base import DialogMixin


class ConfirmDialog(DialogMixin):
    def __init__(self) -> None:
        self._on_confirm: Callable[[], None] | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            self._message = ui.label()
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                ui.button("削除する", on_click=self._confirm).props("color=negative")

    def open(self, message: str, on_confirm: Callable[[], None]) -> None:
        self._message.text = message
        self._on_confirm = on_confirm
        self.dialog.open()

    def _confirm(self) -> None:
        self.dialog.close()
        if self._on_confirm is not None:
            self._on_confirm()
