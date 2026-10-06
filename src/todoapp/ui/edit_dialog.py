from __future__ import annotations

from collections.abc import Callable
from datetime import date

from nicegui import ui

from todoapp.domain.models import ScheduleType, today_estimate_seconds
from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.formatting import (
    SCHEDULE_LABELS,
    estimate_to_hours_minutes,
    format_work_balance,
    hours_minutes_to_estimate,
)

# ui.selectのoption/selected-itemスロットでPRJコード・種別をバッジ表示するため、
# ラベル文字列にこの区切り文字で埋め込む(_props["options"]への直接介入は
# ChoiceElement.update()と競合しクライアントに反映されないことがあるため避ける)
_CATEGORY_LABEL_SEP = "\x1f"


def _category_label(name: str, prj_code: str = "", kind: str = "", color: str = "grey") -> str:
    return f"{name}{_CATEGORY_LABEL_SEP}{prj_code}{_CATEGORY_LABEL_SEP}{kind}{_CATEGORY_LABEL_SEP}{color}"


class EditDialog(DialogMixin):
    def __init__(
        self,
        service: TodoService,
        refresh_all: Callable[[], None],
        get_standard_work_hours: Callable[[], float],
    ) -> None:
        self._service = service
        self._get_standard_work_hours = get_standard_work_hours
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
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                ui.label("本日の見積り").classes("text-gray-600")
                self._today_estimate_hours_input = ui.number(label="時間", min=0, step=1).classes("flex-grow")
                self._today_estimate_minutes_input = ui.number(
                    label="分", min=0, max=59, step=1, precision=0
                ).classes("flex-grow")
            self._work_balance_label = ui.label("").classes("text-sm")
            for today_input in (self._today_estimate_hours_input, self._today_estimate_minutes_input):
                today_input.on_value_change(self._update_work_balance)
            self._category_select = ui.select(
                {None: _category_label("未定")}, label="カテゴリ", value=None
            ).classes("w-full")
            self._category_select.add_slot(
                "option",
                r"""
                <q-item v-bind="props.itemProps" :class="'bg-' + props.opt.label.split('\u001f')[3] + ' text-white'">
                    <q-item-section>
                        <div class="row items-center q-gutter-x-sm">
                            <span>{{ props.opt.label.split('\u001f')[0] }}</span>
                            <q-badge v-if="props.opt.label.split('\u001f')[1]" outline color="white">
                                {{ props.opt.label.split('\u001f')[1] }}
                            </q-badge>
                            <q-badge v-if="props.opt.label.split('\u001f')[2]" outline color="white">
                                {{ props.opt.label.split('\u001f')[2] }}
                            </q-badge>
                        </div>
                    </q-item-section>
                </q-item>
                """,
            )
            self._category_select.add_slot(
                "selected-item",
                r"""<q-badge :color="props.opt.label.split('\u001f')[3]">{{ props.opt.label.split('\u001f')[0] }}</q-badge>""",
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
        # 限定見積りは設定した日だけ有効なので、他の日は未設定として表示する
        today_estimate = today_estimate_seconds(item, date.today())
        today_hours, today_minutes = estimate_to_hours_minutes((today_estimate or 0) / 3600)
        self._today_estimate_hours_input.value = today_hours
        self._today_estimate_minutes_input.value = today_minutes
        category_options: dict[str | None, str] = {None: _category_label("未定")}
        category_options.update(
            {c.id: _category_label(c.name, c.prj_code, c.kind, c.color) for c in self._service.categories}
        )
        self._category_select.set_options(category_options, value=item.category_id)
        self._update_anchor_visibility()
        self._update_work_balance()
        self.dialog.open()

    def _update_work_balance(self) -> None:
        """標準労働時間から、本日の見積り合計(編集中の入力値を含む)を引いた残りを表示する。"""
        if self._item_id is None:
            return
        editing = hours_minutes_to_estimate(
            float(self._today_estimate_hours_input.value or 0),
            float(self._today_estimate_minutes_input.value or 0),
        )
        others = self._service.today_estimate_total_seconds(date.today(), exclude_item_id=self._item_id)
        standard_hours = self._get_standard_work_hours()
        text, over = format_work_balance(standard_hours, others + editing * 3600)
        self._work_balance_label.set_text(f"{text}(標準労働時間 {standard_hours:g}時間 − 本日の見積り合計)")
        if over:
            self._work_balance_label.classes(add="text-negative", remove="text-gray-600")
        else:
            self._work_balance_label.classes(add="text-gray-600", remove="text-negative")

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
            today_estimate_hours=hours_minutes_to_estimate(
                float(self._today_estimate_hours_input.value or 0),
                float(self._today_estimate_minutes_input.value or 0),
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
