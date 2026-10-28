from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time

from nicegui import ui

from todoapp.domain.models import ITEM_NAME_MAX_LENGTH, UNCATEGORIZED_NAME, validate_manual_record
from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin


def parse_manual_record(day: str, start: str, end: str) -> tuple[datetime, datetime] | None:
    """入力欄の文字列(日付・HH:MM:SS)を開始・終了のdatetimeへ変換する。不正なら`None`。"""
    try:
        record_date = date.fromisoformat(day)
        return (
            datetime.combine(record_date, time.fromisoformat(start)),
            datetime.combine(record_date, time.fromisoformat(end)),
        )
    except ValueError:
        return None


class ManualRecordDialog(DialogMixin):
    """実行履歴に、アイテムを持たない記録を手動で追加するフォーム。"""

    def __init__(self, service: TodoService, refresh_all: Callable[[], None]) -> None:
        self._service = service
        self._refresh_all = refresh_all

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            ui.label("実行記録の追加").classes("text-lg font-bold")
            self._date_input = ui.input(label="日付").props("type=date dense").classes("w-full")
            self._category_select = ui.select({}, label="記録のカテゴリ").props("dense").classes("w-full")
            self._name_input = (
                ui.input(label="タスク名(省略するとカテゴリ名)")
                .props(f"maxlength={ITEM_NAME_MAX_LENGTH} dense")
                .classes("w-full")
            )
            self._start_input = ui.time_input(label="開始時刻").classes("w-full")
            self._start_input.picker.props("mask=HH:mm:ss with-seconds")
            self._end_input = ui.time_input(label="終了時刻").classes("w-full")
            self._end_input.picker.props("mask=HH:mm:ss with-seconds")
            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                ui.button("追加", on_click=self.submit)

    def open_for(self, day: date) -> None:
        """`day`を日付の初期値にしてフォームを開く。"""
        options: dict[str, str] = {"": UNCATEGORIZED_NAME}
        for category in self._service.categories:
            label = f"{category.name}({category.prj_code})" if category.prj_code else category.name
            options[category.id] = label
        self._category_select.set_options(options, value="")
        self._date_input.value = day.isoformat()
        self._name_input.value = ""
        self._start_input.value = ""
        self._end_input.value = ""
        self.dialog.open()

    def submit(self) -> bool:
        """入力を検証して記録を追加する。問題があれば警告を表示して追加せず、ダイアログは開いたままにする。"""
        parsed = parse_manual_record(self._date_input.value, self._start_input.value, self._end_input.value)
        if parsed is None:
            ui.notify("日付・開始時刻・終了時刻を正しく入力してください", type="warning")
            return False
        start, end = parsed
        name = self._name_input.value.strip()
        now = datetime.now()
        others = [
            (record.start_time, record.end_time or now) for record in self._service.today_records(start.date())
        ]
        error = validate_manual_record(name, start, end, others)
        if error is not None:
            ui.notify(error, type="warning")
            return False
        self._service.add_manual_record(self._category_select.value or None, name, start, end)
        self.dialog.close()
        self._refresh_all()
        return True
