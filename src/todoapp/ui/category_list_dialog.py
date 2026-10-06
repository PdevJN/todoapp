from __future__ import annotations

from collections.abc import Callable
from datetime import date

from nicegui import ui
from nicegui.events import GenericEventArguments, TableSelectionEventArguments

from todoapp.domain.models import Category
from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.js_handlers import IME_SAFE_ENTER_HANDLER

UNCATEGORIZED_ID = "__uncategorized__"

COLUMNS = [
    {"name": "name", "label": "カテゴリ", "field": "name", "align": "left"},
    {"name": "kind", "label": "種別", "field": "kind", "align": "left"},
    {"name": "prj_code", "label": "PRJコード", "field": "prj_code", "align": "left"},
    {"name": "expiry", "label": "有効期限日", "field": "expiry", "align": "left"},
    {"name": "color", "label": "カラー", "field": "color", "align": "left"},
]


class CategoryListDialog(DialogMixin):
    def __init__(
        self,
        service: TodoService,
        state: AppState,
        refresh_all: Callable[[], None],
        open_category_kind: Callable[[str], None],
    ) -> None:
        self._service = service
        self._state = state
        self._refresh_all = refresh_all
        self._open_category_kind = open_category_kind
        self._rendered_ids: list[str] = []
        self._new_category_input: ui.input | None = None

    def build(self) -> None:
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[36rem] gap-2"):
            ui.label("カテゴリ一覧").classes("text-lg font-bold")
            self.table = ui.table(
                columns=COLUMNS,
                rows=[],
                row_key="id",
                selection="multiple",
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
            # マウスオーバーで、このカテゴリに属する本日のアイテムを一覧表示する
            self.table.add_slot(
                "body-cell-name",
                r"""
                <q-td :props="props">
                    <span>{{ props.row.name }}</span>
                    <q-tooltip>
                        <div v-if="props.row.today_items.length === 0">本日のアイテムはありません</div>
                        <div v-for="itemName in props.row.today_items" :key="itemName">{{ itemName }}</div>
                    </q-tooltip>
                </q-td>
                """,
            )
            self._new_category_input = ui.input(placeholder="新しいカテゴリ名を入力してEnter(Shift+Enterで種別入力)").classes(
                "w-full"
            )
            self._new_category_input.on(
                "keydown.enter.exact", self._add_category, js_handler=IME_SAFE_ENTER_HANDLER
            )
            self._new_category_input.on(
                "keydown.enter.shift", self._add_category_and_pick_kind, js_handler=IME_SAFE_ENTER_HANDLER
            )
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def open(self) -> None:
        self.refresh()
        self.dialog.open()

    def refresh(self) -> None:
        today_items = self._service.items_due_today(date.today())
        rows = [
            {
                "id": UNCATEGORIZED_ID,
                "name": "未定",
                "kind": "-",
                "prj_code": "-",
                "expiry": "-",
                "color": "grey",
                "today_items": [item.name for item in today_items if item.category_id is None],
            }
        ]
        for category in self._service.categories:
            today_item_names = [item.name for item in today_items if item.category_id == category.id]
            rows.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "kind": category.kind or "-",
                    "prj_code": category.prj_code or "-",
                    "expiry": category.expiry_date.isoformat() if category.expiry_date else "-",
                    "color": category.color,
                    "today_items": today_item_names,
                }
            )
        # 「未定」は実体を持たないカテゴリのため、選択・編集・削除の対象からは除外する
        self._rendered_ids = [str(row["id"]) for row in rows if row["id"] != UNCATEGORIZED_ID]
        self.table.update_rows(rows, clear_selection=False)

    def _add_category(self) -> Category | None:
        assert self._new_category_input is not None
        name = self._new_category_input.value.strip()
        if not name:
            return None
        category = self._service.add_category(name)
        self._new_category_input.value = ""
        self._refresh_all()
        return category

    def _add_category_and_pick_kind(self) -> None:
        category = self._add_category()
        if category is not None:
            self._open_category_kind(category.id)

    def _on_select(self, e: TableSelectionEventArguments) -> None:
        ids = {row["id"] for row in e.selection if row["id"] != UNCATEGORIZED_ID}
        self._state.select_categories(ids)
        if ids:
            self._state.select_category(next(iter(ids)))

    def _on_row_click(self, e: GenericEventArguments) -> None:
        category_id = e.args[1]["id"]
        if category_id == UNCATEGORIZED_ID:
            return
        self._state.select_category(category_id)
        self._state.select_categories({category_id})
        self.table.selected = [{"id": category_id}]

    def select_all(self) -> None:
        rows = [{"id": category_id} for category_id in self._rendered_ids]
        self.table.selected = rows
        self._state.select_categories(set(self._rendered_ids))

    def move_selection(self, delta: int) -> None:
        if not self._rendered_ids:
            return
        current = self._state.selected_category_id
        if current in self._rendered_ids:
            index = self._rendered_ids.index(current) + delta
            index = max(0, min(len(self._rendered_ids) - 1, index))
        else:
            index = 0 if delta > 0 else len(self._rendered_ids) - 1
        new_id = self._rendered_ids[index]
        self._state.select_category(new_id)
        self._state.select_categories({new_id})
        self.table.selected = [{"id": new_id}]

    def has_selection(self) -> bool:
        return bool(self._state.selected_category_id or self._state.selected_category_ids)

    def clear_selection(self) -> None:
        self.table.selected = []
        self._state.select_category(None)
        self._state.select_categories(set())

    def close(self) -> None:
        self.dialog.close()
