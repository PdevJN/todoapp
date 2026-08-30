from __future__ import annotations

from nicegui import ui


class DialogMixin:
    """`build()`内で`self.dialog`(`ui.dialog`)を生成するダイアログ系UIクラスの共通処理。"""

    dialog: ui.dialog

    def is_open(self) -> bool:
        return bool(self.dialog.value)
