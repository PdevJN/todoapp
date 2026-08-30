from __future__ import annotations

from collections.abc import Callable

from nicegui import ui
from nicegui.events import GenericEventArguments, TableSelectionEventArguments

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

    def build(self) -> ui.column:
        root = ui.column().classes("w-full gap-2 p-4")
        with root:
            ui.label("編集一覧").classes("text-lg font-bold")
            self.table = ui.table(
                columns=COLUMNS,
                rows=[],
                row_key="id",
                selection="single",
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
                    </div>
                </q-td>
                """,
            )
            self.render()
        ui.timer(1.0, self._tick)
        return root

    def _on_select(self, e: TableSelectionEventArguments) -> None:
        if e.selection:
            self._state.select(e.selection[0]["id"])

    def _on_row_click(self, e: GenericEventArguments) -> None:
        item_id = e.args[1]["id"]
        self._state.select(item_id)
        self.table.selected = [{"id": item_id}]

    def _tick(self) -> None:
        if self._state.screen is Screen.LIST and self._service.running_record() is not None:
            self.render.refresh()

    @ui.refreshable_method
    def render(self) -> None:
        rows = []
        for item in self._service.items:
            cumulative = self._service.cumulative_seconds(item.id)
            remaining = self._service.remaining_seconds(item.id)
            rows.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "schedule": SCHEDULE_LABELS[item.schedule_type.value],
                    "anchor": item.anchor_date.strftime("%m/%d"),
                    "cumulative": format_duration(cumulative),
                    "remaining": format_duration(remaining) if item.estimate_hours > 0 else "-",
                }
            )
        self.table.update_rows(rows, clear_selection=False)
