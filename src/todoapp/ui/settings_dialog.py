from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from todoapp.repository.config_repository import MAX_OVERTIME_TARGET_HOURS
from todoapp.ui.dialog_base import DialogMixin

_MAX_WORK_HOURS = 24.0


class SettingsDialog(DialogMixin):
    """アプリの設定ダイアログ。設定項目は`標準労働時間`・`残業時間の目標`・`スリープ検知`。"""

    def __init__(
        self,
        get_standard_work_hours: Callable[[], float],
        get_overtime_target_hours: Callable[[], float],
        get_suspend_detection: Callable[[], bool],
        on_save: Callable[[float, float, bool], None],
    ) -> None:
        self._get_standard_work_hours = get_standard_work_hours
        self._get_overtime_target_hours = get_overtime_target_hours
        self._get_suspend_detection = get_suspend_detection
        self._on_save = on_save

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            ui.label("設定").classes("text-lg font-bold")
            self._hours_input = ui.number(
                label="標準労働時間(時間)", min=0.1, max=_MAX_WORK_HOURS, step=0.1, format="%.1f"
            ).classes("w-full")
            self._overtime_input = (
                ui.number(label="残業時間の目標(時間)", min=0, max=MAX_OVERTIME_TARGET_HOURS, step=1, format="%.1f")
                .classes("w-full")
                .mark("settings-overtime")
            )
            self._suspend_checkbox = ui.checkbox("スリープ検知(処理が長く止まったら実行を停止)")
            with ui.row().classes("w-full justify-end mt-2 gap-2"):
                ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                ui.button("保存", on_click=self._save)

    def open(self) -> None:
        self._hours_input.value = self._get_standard_work_hours()
        self._overtime_input.value = self._get_overtime_target_hours()
        self._suspend_checkbox.value = self._get_suspend_detection()
        self.dialog.open()

    def _save(self) -> None:
        value = self._hours_input.value
        if value is None or not 0 < value <= _MAX_WORK_HOURS:
            ui.notify(f"0より大きく{_MAX_WORK_HOURS:g}以下で入力してください", type="warning")
            return
        overtime = self._overtime_input.value
        if overtime is None or not 0 <= overtime <= MAX_OVERTIME_TARGET_HOURS:
            ui.notify(f"0以上{MAX_OVERTIME_TARGET_HOURS:g}以下で入力してください", type="warning")
            return
        self._on_save(float(value), float(overtime), bool(self._suspend_checkbox.value))
        self.dialog.close()
