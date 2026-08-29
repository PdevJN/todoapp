from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from nicegui import ui
from nicegui.events import SortableEventArguments

from todoapp.domain.models import ScheduleType, TodoItem
from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState
from todoapp.ui.formatting import SCHEDULE_LABELS, format_duration


class MainView:
    def __init__(
        self,
        service: TodoService,
        state: AppState,
        refresh_all: Callable[[], None],
    ) -> None:
        self._service = service
        self._state = state
        self._refresh_all = refresh_all
        self._new_item_input: ui.input | None = None
        self._elapsed_label: ui.label | None = None
        self._elapsed_item_id: str | None = None

    def build(self) -> ui.column:
        root = ui.column().classes("w-full gap-2 p-4")
        with root:
            self.list_container = ui.column().classes("w-full gap-1")
            self.list_container.make_sortable(on_end=self._on_reorder)
            self.render()
            self._new_item_input = ui.input(placeholder="新しいアイテムを入力してEnter").classes("w-full")
            self._new_item_input.on("keydown.enter", self._add_item)
        ui.timer(1.0, self._tick)
        return root

    def _add_item(self) -> None:
        assert self._new_item_input is not None
        name = self._new_item_input.value.strip()
        if not name:
            return
        item = self._service.add_item(name, ScheduleType.ONE_TIME, date.today())
        self._new_item_input.value = ""
        self._state.select(item.id)
        self._refresh_all()

    def _select(self, item_id: str) -> None:
        self._state.select(item_id)
        self.render.refresh()

    def _toggle(self, item_id: str) -> None:
        self._state.select(item_id)
        self._service.toggle_execution(item_id)
        self._refresh_all()

    def _on_reorder(self, e: SortableEventArguments) -> None:
        self._service.reorder(e.old_index, e.new_index)
        self._refresh_all()

    def _tick(self) -> None:
        running = self._service.running_record()
        if running is None or self._elapsed_label is None:
            return
        if self._elapsed_item_id == running.item_id:
            self._elapsed_label.set_text(format_duration(running.elapsed_seconds(datetime.now())))

    @ui.refreshable_method
    def render(self) -> None:
        self._elapsed_label = None
        self._elapsed_item_id = None
        self.list_container.clear()
        with self.list_container:
            today = date.today()
            items = self._service.items_due_today(today)
            if not items:
                ui.label("").classes("text-gray-400 italic h-8")
                return
            for item in items:
                self._render_row(item, today)

    def _render_row(self, item: TodoItem, today: date) -> None:
        running = self._service.running_record()
        is_running = running is not None and running.item_id == item.id
        is_selected = self._state.selected_item_id == item.id

        classes = "w-full items-center gap-3 p-2 rounded cursor-pointer border"
        classes += " border-primary bg-blue-50" if is_selected else " border-transparent"

        with ui.row().classes(classes) as row:
            row.on("click", lambda i=item.id: self._select(i))
            row.on("dblclick", lambda i=item.id: self._toggle(i))
            ui.label(item.name).classes("font-medium")
            ui.badge(SCHEDULE_LABELS[item.schedule_type.value]).props("outline")
            if is_running:
                assert running is not None
                label = ui.label(format_duration(running.elapsed_seconds(datetime.now())))
                label.classes("text-primary font-mono")
                self._elapsed_label = label
                self._elapsed_item_id = item.id
            else:
                total = self._service.today_total_seconds(item.id, today)
                if total > 0:
                    ui.label(f"本日合計 {format_duration(total)}").classes("text-gray-500 font-mono")
            if item.estimate_hours > 0:
                ui.label(f"見積り {item.estimate_hours}h").classes("text-gray-400 text-sm")
