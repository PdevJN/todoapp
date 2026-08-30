from __future__ import annotations

from nicegui import ui
from nicegui.events import GenericEventArguments, TableSelectionEventArguments

from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState

COLUMNS = [
    {"name": "name", "label": "カテゴリ", "field": "name", "align": "left"},
    {"name": "kind", "label": "種別", "field": "kind", "align": "left"},
    {"name": "expiry", "label": "有効期限日", "field": "expiry", "align": "left"},
    {"name": "color", "label": "カラー", "field": "color", "align": "left"},
]


class CategoryListDialog:
    def __init__(self, service: TodoService, state: AppState) -> None:
        self._service = service
        self._state = state

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[36rem] gap-2"):
            ui.label("カテゴリ一覧").classes("text-lg font-bold")
            self.table = ui.table(
                columns=COLUMNS,
                rows=[],
                row_key="id",
                selection="single",
                on_select=self._on_select,
            )
            self.table.on("rowClick", self._on_row_click, args=[[], ["id"]])
            self.table.add_slot(
                "body-cell-color",
                r"""
                <q-td :props="props">
                    <q-badge outline :color="props.row.color">{{ props.row.color }}</q-badge>
                </q-td>
                """,
            )
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def is_open(self) -> bool:
        return bool(self.dialog.value)

    def open(self) -> None:
        self.refresh()
        self.dialog.open()

    def refresh(self) -> None:
        rows = []
        for category in self._service.categories:
            rows.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "kind": category.kind or "-",
                    "expiry": category.expiry_date.isoformat() if category.expiry_date else "-",
                    "color": category.color,
                }
            )
        self.table.update_rows(rows, clear_selection=False)

    def _on_select(self, e: TableSelectionEventArguments) -> None:
        if e.selection:
            self._state.select_category(e.selection[0]["id"])

    def _on_row_click(self, e: GenericEventArguments) -> None:
        category_id = e.args[1]["id"]
        self._state.select_category(category_id)
        self.table.selected = [{"id": category_id}]
