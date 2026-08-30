from __future__ import annotations

from datetime import date, datetime

from nicegui import ui
from nicegui.events import GenericEventArguments

from todoapp.domain.models import ExecutionRecord
from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.formatting import format_duration


class LogView(DialogMixin):
    def __init__(self, service: TodoService, state: AppState) -> None:
        self._service = service
        self._state = state
        self._rendered_record_ids: list[str] = []
        self._select_anchor_index: int | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[32rem] gap-2"):
            ui.label("本日の作業ログ").classes("text-lg font-bold")
            self.log_container = ui.column().classes("w-full gap-1")
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def open(self) -> None:
        self._render()
        self.dialog.open()

    def refresh(self) -> None:
        self._render.refresh()

    def select_all(self) -> None:
        self._state.select_records(set(self._rendered_record_ids))
        self._render.refresh()

    def _on_row_click(self, record_id: str, e: GenericEventArguments) -> None:
        modifiers = e.args
        ctrl = bool(modifiers["ctrlKey"] or modifiers["metaKey"])
        shift = bool(modifiers["shiftKey"])
        index = self._rendered_record_ids.index(record_id) if record_id in self._rendered_record_ids else None

        if shift and self._select_anchor_index is not None and index is not None:
            lo, hi = sorted((self._select_anchor_index, index))
            self._state.select_records(set(self._rendered_record_ids[lo : hi + 1]))
        elif ctrl:
            selected = set(self._state.selected_record_ids)
            if record_id in selected:
                selected.discard(record_id)
            else:
                selected.add(record_id)
            self._state.select_records(selected)
            self._select_anchor_index = index
        else:
            self._state.select_records({record_id})
            self._select_anchor_index = index

        self._state.select_record(record_id)
        self._render.refresh()

    @ui.refreshable_method
    def _render(self) -> None:
        self.log_container.clear()
        with self.log_container:
            records = self._service.today_records(date.today())
            self._rendered_record_ids = [record.id for record in records]
            if not records:
                ui.label("本日の記録はまだありません").classes("text-gray-400 italic")
                return
            for record in records:
                self._render_row(record)

    def _render_row(self, record: ExecutionRecord) -> None:
        is_selected = record.id in self._state.selected_record_ids
        elapsed = format_duration(record.elapsed_seconds(record.end_time or datetime.now()))
        start = record.start_time.strftime("%H:%M:%S")
        end = record.end_time.strftime("%H:%M:%S") if record.end_time else "実行中"

        classes = "w-full justify-between items-center border-b py-1 px-1 rounded cursor-pointer"
        classes += " bg-blue-200" if is_selected else ""
        with ui.row().classes(classes) as row:
            row.on(
                "click",
                lambda e, rid=record.id: self._on_row_click(rid, e),
                args=["ctrlKey", "metaKey", "shiftKey"],
            )
            ui.label(record.item_name).classes("font-medium")
            ui.label(f"{start} - {end} ({elapsed})").classes("text-gray-500 font-mono")
