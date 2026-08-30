from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time

from nicegui import ui

from todoapp.domain.service import TodoService


class RecordEditDialog:
    def __init__(self, service: TodoService, refresh_all: Callable[[], None]) -> None:
        self._service = service
        self._refresh_all = refresh_all
        self._record_id: str | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            ui.label("実行記録の編集").classes("text-lg font-bold")
            self._item_label = ui.label().classes("text-sm text-gray-500")
            self._start_input = ui.time_input(label="開始時刻").classes("w-full")
            self._start_input.picker.props("mask=HH:mm:ss with-seconds")
            self._end_input = ui.time_input(label="終了時刻").classes("w-full")
            self._end_input.picker.props("mask=HH:mm:ss with-seconds")
            with ui.row().classes("w-full justify-between mt-2"):
                ui.button("削除", on_click=self._delete).props("flat color=negative")
                with ui.row().classes("gap-2"):
                    ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                    ui.button("保存", on_click=self._save)

    def is_open(self) -> bool:
        return bool(self.dialog.value)

    def open_for(self, record_id: str) -> None:
        record = next((r for r in self._service.records if r.id == record_id), None)
        if record is None:
            return
        self._record_id = record_id
        self._item_label.text = record.item_name
        self._start_input.value = record.start_time.strftime("%H:%M:%S")
        self._end_input.value = record.end_time.strftime("%H:%M:%S") if record.end_time else ""
        self.dialog.open()

    def _save(self) -> None:
        if self._record_id is None:
            return
        record = next((r for r in self._service.records if r.id == self._record_id), None)
        if record is None:
            return
        record_date = record.start_time.date()
        start_time = datetime.combine(record_date, time.fromisoformat(self._start_input.value))
        end_time = (
            datetime.combine(record_date, time.fromisoformat(self._end_input.value))
            if self._end_input.value
            else None
        )
        self._service.edit_record(self._record_id, start_time=start_time, end_time=end_time)
        self.dialog.close()
        self._refresh_all()

    def _delete(self) -> None:
        if self._record_id is None:
            return
        self._service.delete_record(self._record_id)
        self.dialog.close()
        self._refresh_all()
