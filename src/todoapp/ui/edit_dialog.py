from __future__ import annotations

from collections.abc import Callable
from datetime import date

from nicegui import ui

from todoapp.domain.models import ScheduleType
from todoapp.domain.service import TodoService
from todoapp.ui.formatting import SCHEDULE_LABELS


class EditDialog:
    def __init__(self, service: TodoService, refresh_all: Callable[[], None]) -> None:
        self._service = service
        self._refresh_all = refresh_all
        self._item_id: str | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-96 gap-2"):
            ui.label("アイテムの編集").classes("text-lg font-bold")
            self._name_input = ui.input(label="アイテム名").classes("w-full")
            self._schedule_select = ui.select(
                SCHEDULE_LABELS,
                label="実行の曜日",
                value=ScheduleType.ONE_TIME.value,
            ).classes("w-full")
            self._schedule_select.on_value_change(self._update_anchor_visibility)
            self._anchor_input = ui.input(label="基準日").props("type=date").classes("w-full")
            self._estimate_input = ui.number(label="見積り時間(時間)", min=0, step=0.5).classes("w-full")
            self._category_select = ui.select({None: "未定"}, label="カテゴリ", value=None).classes("w-full")
            with ui.row().classes("w-full justify-between mt-2"):
                ui.button("削除", on_click=self._delete).props("flat color=negative")
                with ui.row().classes("gap-2"):
                    ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                    ui.button("保存", on_click=self._save)

    def is_open(self) -> bool:
        return bool(self.dialog.value)

    def open_for(self, item_id: str) -> None:
        item = next((i for i in self._service.items if i.id == item_id), None)
        if item is None:
            return
        self._item_id = item_id
        self._name_input.value = item.name
        self._schedule_select.value = item.schedule_type.value
        self._anchor_input.value = item.anchor_date.isoformat()
        self._estimate_input.value = item.estimate_hours
        category_options: dict[str | None, str] = {None: "未定"}
        category_options.update({c.id: c.name for c in self._service.categories})
        self._category_select.set_options(category_options, value=item.category_id)
        self._update_anchor_visibility()
        self.dialog.open()

    def _update_anchor_visibility(self) -> None:
        self._anchor_input.set_visibility(self._schedule_select.value != ScheduleType.DAILY.value)

    def _save(self) -> None:
        if self._item_id is None:
            return
        schedule_type = ScheduleType(self._schedule_select.value)
        anchor_date = (
            date.fromisoformat(self._anchor_input.value)
            if schedule_type is not ScheduleType.DAILY
            else date.today()
        )
        self._service.edit_item(
            self._item_id,
            name=self._name_input.value.strip(),
            schedule_type=schedule_type,
            anchor_date=anchor_date,
            estimate_hours=float(self._estimate_input.value or 0.0),
        )
        self._service.set_item_category(self._item_id, self._category_select.value)
        self.dialog.close()
        self._refresh_all()

    def _delete(self) -> None:
        if self._item_id is None:
            return
        self._service.delete_item(self._item_id)
        self.dialog.close()
        self._refresh_all()
