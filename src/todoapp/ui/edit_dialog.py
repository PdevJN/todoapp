from __future__ import annotations

from collections.abc import Callable
from datetime import date

from nicegui import ui

from todoapp.domain.models import ScheduleType
from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.formatting import SCHEDULE_LABELS, estimate_to_hours_minutes, hours_minutes_to_estimate

# ui.selectのoption/selected-itemスロットでPRJコード・種別をバッジ表示するため、
# ラベル文字列にこの区切り文字で埋め込む(_props["options"]への直接介入は
# ChoiceElement.update()と競合しクライアントに反映されないことがあるため避ける)
_CATEGORY_LABEL_SEP = "\x1f"


def _category_label(name: str, prj_code: str = "", kind: str = "") -> str:
    return f"{name}{_CATEGORY_LABEL_SEP}{prj_code}{_CATEGORY_LABEL_SEP}{kind}"


class EditDialog(DialogMixin):
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
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                ui.label("見積り").classes("text-gray-600")
                self._estimate_hours_input = ui.number(label="時間", min=0, step=1).classes("flex-grow")
                self._estimate_minutes_input = ui.number(
                    label="分", min=0, max=59, step=1, precision=0
                ).classes("flex-grow")
            self._category_select = ui.select(
                {None: _category_label("未定")}, label="カテゴリ", value=None
            ).classes("w-full")
            self._category_select.add_slot(
                "option",
                r"""
                <q-item v-bind="props.itemProps">
                    <q-item-section>
                        <div class="row items-center q-gutter-x-sm">
                            <span>{{ props.opt.label.split('\u001f')[0] }}</span>
                            <q-badge v-if="props.opt.label.split('\u001f')[1]" outline>
                                {{ props.opt.label.split('\u001f')[1] }}
                            </q-badge>
                            <q-badge v-if="props.opt.label.split('\u001f')[2]" outline>
                                {{ props.opt.label.split('\u001f')[2] }}
                            </q-badge>
                        </div>
                    </q-item-section>
                </q-item>
                """,
            )
            self._category_select.add_slot(
                "selected-item",
                r"""<span>{{ props.opt.label.split('\u001f')[0] }}</span>""",
            )
            with ui.row().classes("w-full justify-between mt-2"):
                ui.button("削除", on_click=self._delete).props("flat color=negative")
                with ui.row().classes("gap-2"):
                    ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                    ui.button("保存", on_click=self._save)

    def open_for(self, item_id: str) -> None:
        item = next((i for i in self._service.items if i.id == item_id), None)
        if item is None:
            return
        self._item_id = item_id
        self._name_input.value = item.name
        self._schedule_select.value = item.schedule_type.value
        self._anchor_input.value = item.anchor_date.isoformat()
        hours, minutes = estimate_to_hours_minutes(item.estimate_hours)
        self._estimate_hours_input.value = hours
        self._estimate_minutes_input.value = minutes
        category_options: dict[str | None, str] = {None: _category_label("未定")}
        category_options.update(
            {c.id: _category_label(c.name, c.prj_code, c.kind) for c in self._service.categories}
        )
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
            estimate_hours=hours_minutes_to_estimate(
                float(self._estimate_hours_input.value or 0), float(self._estimate_minutes_input.value or 0)
            ),
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
