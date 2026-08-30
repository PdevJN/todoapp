from __future__ import annotations

from datetime import date, datetime

from nicegui import ui

from todoapp.domain.models import ExecutionRecord
from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState
from todoapp.ui.formatting import format_duration


class LogView:
    def __init__(self, service: TodoService, state: AppState) -> None:
        self._service = service
        self._state = state

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[32rem] gap-2"):
            ui.label("本日の作業ログ").classes("text-lg font-bold")
            self.log_container = ui.column().classes("w-full gap-1")
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def is_open(self) -> bool:
        return bool(self.dialog.value)

    def open(self) -> None:
        self._render()
        self.dialog.open()

    def refresh(self) -> None:
        self._render.refresh()

    def _select(self, record_id: str) -> None:
        self._state.select_record(record_id)
        self._render.refresh()

    @ui.refreshable_method
    def _render(self) -> None:
        self.log_container.clear()
        with self.log_container:
            records = self._service.today_records(date.today())
            if not records:
                ui.label("本日の記録はまだありません").classes("text-gray-400 italic")
                return
            for record in records:
                self._render_row(record)

    def _render_row(self, record: ExecutionRecord) -> None:
        is_selected = self._state.selected_record_id == record.id
        elapsed = format_duration(record.elapsed_seconds(record.end_time or datetime.now()))
        start = record.start_time.strftime("%H:%M:%S")
        end = record.end_time.strftime("%H:%M:%S") if record.end_time else "実行中"

        classes = "w-full justify-between items-center border-b py-1 px-1 rounded cursor-pointer"
        classes += " bg-blue-200" if is_selected else ""
        with ui.row().classes(classes) as row:
            row.on("click", lambda rid=record.id: self._select(rid))
            ui.label(record.item_name).classes("font-medium")
            ui.label(f"{start} - {end} ({elapsed})").classes("text-gray-500 font-mono")
