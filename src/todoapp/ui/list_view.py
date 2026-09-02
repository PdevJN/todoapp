from __future__ import annotations

from collections.abc import Callable
from datetime import date

from nicegui import ui
from nicegui.events import GenericEventArguments, TableSelectionEventArguments

from todoapp.domain.models import is_category_expired
from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState, Screen
from todoapp.ui.formatting import SCHEDULE_LABELS, format_duration

COLUMNS = [
    {"name": "name", "label": "アイテム名", "field": "name", "align": "left"},
    {"name": "anchor", "label": "基準日", "field": "anchor", "align": "left"},
    {"name": "cumulative", "label": "累積経過時間", "field": "cumulative", "align": "right"},
    {"name": "remaining", "label": "残りの完了時間", "field": "remaining", "align": "right"},
]


class ListView:
    def __init__(self, service: TodoService, state: AppState) -> None:
        self._service = service
        self._state = state
        self._rendered_ids: list[str] = []

    def build(self) -> ui.column:
        root = ui.column().classes("w-full gap-2 p-4")
        with root:
            ui.label("編集一覧").classes("text-lg font-bold")
            with ui.row().classes("w-full gap-2 items-end"):
                self._name_filter = ui.input(label="アイテム名で絞り込み").classes("flex-grow")
                self._name_filter.on_value_change(self.render.refresh)
                self._schedule_filter = ui.select(
                    SCHEDULE_LABELS, label="実行の曜日", multiple=True
                ).classes("w-48")
                self._schedule_filter.on_value_change(self.render.refresh)
                self._anchor_filter = ui.input(
                    label="基準日", value=date.today().isoformat()
                ).props("type=date")
                self._anchor_filter.on_value_change(self.render.refresh)
            self.table = ui.table(
                columns=COLUMNS,
                rows=[],
                row_key="id",
                selection="multiple",
                on_select=self._on_select,
            )
            # QTableは既定でチェックボックス以外の行クリックでは選択されないため、
            # 行のどこをクリックしても選択できるようにrowClickでも選択状態を反映する
            self.table.on("rowClick", self._on_row_click, args=[[], ["id"]])
            # メインパネルと同様に、アイテム名の隣にスケジュール種別をバッジで併記する
            self.table.add_slot(
                "body-cell-name",
                r"""
                <q-td :props="props">
                    <div class="row items-center q-gutter-x-sm">
                        <span>{{ props.row.name }}</span>
                        <q-badge outline color="primary">{{ props.row.schedule }}</q-badge>
                        <q-badge outline :color="props.row.category_color">
                            <span v-if="props.row.category_expired">❗️</span>{{ props.row.category_label }}
                        </q-badge>
                    </div>
                </q-td>
                """,
            )
            self.render()
        ui.timer(1.0, self._tick)
        return root

    def _on_select(self, e: TableSelectionEventArguments) -> None:
        self._state.select_items({row["id"] for row in e.selection})
        if e.selection:
            self._state.select(e.selection[0]["id"])

    def _on_row_click(self, e: GenericEventArguments) -> None:
        item_id = e.args[1]["id"]
        self._state.select(item_id)
        self._state.select_items({item_id})
        self.table.selected = [{"id": item_id}]

    def select_all(self) -> None:
        rows = [{"id": item_id} for item_id in self._rendered_ids]
        self.table.selected = rows
        self._state.select_items(set(self._rendered_ids))

    def move_selection(self, delta: int) -> None:
        if not self._rendered_ids:
            return
        current = self._state.selected_item_id
        if current in self._rendered_ids:
            index = self._rendered_ids.index(current) + delta
            index = max(0, min(len(self._rendered_ids) - 1, index))
        else:
            index = 0 if delta > 0 else len(self._rendered_ids) - 1
        new_id = self._rendered_ids[index]
        self._state.select(new_id)
        self._state.select_items({new_id})
        self.table.selected = [{"id": new_id}]

    def has_selection(self) -> bool:
        return bool(self._state.selected_item_id or self._state.selected_item_ids)

    def clear_selection(self) -> None:
        self.table.selected = []
        self._state.select(None)
        self._state.select_items(set())

    def _tick(self) -> None:
        if self._state.screen is Screen.LIST and self._service.running_record() is not None:
            self.render.refresh()

    @ui.refreshable_method
    def render(self) -> None:
        today = date.today()
        name_filter = self._name_filter.value.strip()
        schedule_filter = set(self._schedule_filter.value or [])
        anchor_filter_value = self._anchor_filter.value
        anchor_filter = date.fromisoformat(anchor_filter_value) if anchor_filter_value else None

        rows = []
        for item in self._service.items:
            if name_filter and name_filter not in item.name:
                continue
            if schedule_filter and item.schedule_type.value not in schedule_filter:
                continue
            if anchor_filter is not None and item.anchor_date != anchor_filter:
                continue
            cumulative = self._service.cumulative_seconds(item.id)
            remaining = self._service.remaining_seconds(item.id)
            category = self._service.category_for_item(item.id)
            rows.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "schedule": SCHEDULE_LABELS[item.schedule_type.value],
                    "anchor": item.anchor_date.strftime("%m/%d"),
                    "cumulative": format_duration(cumulative),
                    "remaining": format_duration(remaining) if item.estimate_hours > 0 else "-",
                    "category_label": category.name if category else "未定",
                    "category_color": category.color if category else "grey",
                    "category_expired": bool(category and is_category_expired(category, today)),
                }
            )
        self._rendered_ids = [str(row["id"]) for row in rows]
        self.table.update_rows(rows, clear_selection=False)
