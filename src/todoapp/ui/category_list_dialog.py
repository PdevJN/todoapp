from __future__ import annotations

from collections.abc import Callable
from datetime import date

from nicegui import ui
from nicegui.events import GenericEventArguments, TableSelectionEventArguments

from todoapp.domain.models import (
    CATEGORY_NAME_MAX_LENGTH,
    Category,
    expired_category_tooltip,
    is_category_expired,
    validate_category_fields,
)
from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.js_handlers import IME_SAFE_ENTER_HANDLER
from todoapp.ui.table_layout import FIT_TABLE_CLASS, FIT_TABLE_CSS, fixed_width
from todoapp.ui.vendor.sortable_table.sortable_table import SortableTable

UNCATEGORIZED_ID = "__uncategorized__"

# 表はウィンドウ幅に収める(`ui/table_layout.py`)。カテゴリ列が残りの幅を取り、他の列は幅を固定する。
# 収まらない文字(カテゴリ名・種別・PRJコード)は「...」で省略し、マウスオーバーのチップで全文を見せる
COLUMNS = [
    {"name": "name", "label": "カテゴリ", "field": "name", "align": "left", "classes": "ellipsis"},
    fixed_width({"name": "kind", "label": "種別", "field": "kind", "align": "left"}, 5, ellipsis=True),
    fixed_width({"name": "prj_code", "label": "PRJコード", "field": "prj_code", "align": "left"}, 6.5, ellipsis=True),
    fixed_width({"name": "expiry", "label": "有効期限日", "field": "expiry", "align": "left"}, 7),
    fixed_width({"name": "color", "label": "カラー", "field": "color", "align": "left"}, 5),
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
        ui.add_css(FIT_TABLE_CSS)
        # 幅はウィンドウに収まる範囲に制限する(Quasar既定の560px上限も、ここで上書きする)
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("gap-2").style(
            "width: 48rem; max-width: calc(100vw - 2rem)"
        ):
            ui.label("カテゴリ一覧").classes("text-lg font-bold")
            self.table = (
                ui.table(
                    columns=COLUMNS,
                    rows=[],
                    row_key="id",
                    selection="multiple",
                    on_select=self._on_select,
                )
                .props("dense")
                .classes(f"{FIT_TABLE_CLASS} w-full")
            )
            self.table.on("rowClick", self._on_row_click, args=[[], ["id"]])
            # 行をドラッグ&ドロップで並べ替える。先頭の「未定」行は固定
            SortableTable(self.table, self._on_reorder, fixed_rows=1)
            self.table.add_slot(
                "body-cell-color",
                r"""
                <q-td :props="props">
                    <q-badge outline :color="props.row.color">{{ props.row.color }}</q-badge>
                </q-td>
                """,
            )
            # マウスオーバーで、カテゴリの内容と、このカテゴリに属する本日のタスクを、見出し付きの2つの区画に分けて表示する
            self.table.add_slot(
                "body-cell-name",
                r"""
                <q-td :props="props">
                    {{ props.row.name }}
                    <q-tooltip max-width="22rem">
                        <div class="text-caption text-grey-5">カテゴリ</div>
                        <div class="text-weight-bold" style="word-break: break-all">{{ props.row.name }}</div>
                        <template v-if="!props.row.undecided">
                            <div class="text-caption">種別: {{ props.row.kind }}</div>
                            <div class="text-caption">PRJコード: {{ props.row.prj_code }}</div>
                            <div class="text-caption">有効期限日: {{ props.row.expiry }}</div>
                            <div v-if="props.row.expired" class="text-caption text-red-3">❗️{{ props.row.expired_tip }}</div>
                        </template>
                        <q-separator dark class="q-my-sm" />
                        <div class="text-caption text-grey-5">本日のタスク</div>
                        <div v-if="props.row.today_items.length === 0" class="text-caption">本日のタスクはありません</div>
                        <div v-for="itemName in props.row.today_items" :key="itemName" style="word-break: break-all">・{{ itemName }}</div>
                    </q-tooltip>
                </q-td>
                """,
            )
            # 省略された種別・PRJコードの全文を、マウスオーバーで表示する
            for column in ("kind", "prj_code"):
                self.table.add_slot(
                    f"body-cell-{column}",
                    r"""
                    <q-td :props="props">
                        {{ props.value }}
                        <q-tooltip v-if="props.value !== '-'" max-width="20rem" style="word-break: break-all">{{ props.value }}</q-tooltip>
                    </q-td>
                    """,
                )
            self._new_category_input = ui.input(placeholder="新しいカテゴリ名を入力してEnter(Shift+Enterで種別入力)").props(
                f"maxlength={CATEGORY_NAME_MAX_LENGTH}"
            ).classes("w-full")
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
                "undecided": True,
                "expired": False,
                "expired_tip": "",
                "today_items": [item.name for item in today_items if item.category_id is None],
            }
        ]
        for category in self._service.categories:
            today_item_names = [item.name for item in today_items if item.category_id == category.id]
            expired = is_category_expired(category, date.today())
            rows.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "kind": category.kind or "-",
                    "prj_code": category.prj_code or "-",
                    "expiry": category.expiry_date.isoformat() if category.expiry_date else "-",
                    "color": category.color,
                    "undecided": False,
                    "expired": expired,
                    "expired_tip": expired_category_tooltip(category) if expired else "",
                    "today_items": today_item_names,
                }
            )
        # 「未定」は実体を持たないカテゴリのため、選択・編集・削除の対象からは除外する
        self._rendered_ids = [str(row["id"]) for row in rows if row["id"] != UNCATEGORIZED_ID]
        self.table.update_rows(rows, clear_selection=False)

    def _on_reorder(self, old_index: int, new_index: int) -> None:
        # 表の添字には先頭の固定行(未定)が含まれるため、1つずらして登録済みカテゴリの添字にする
        ids = self._rendered_ids
        old, new = old_index - 1, new_index - 1
        if 0 <= old < len(ids) and 0 <= new < len(ids) and old != new:
            self._service.move_category_to(ids[old], ids[new])
        self._refresh_all()

    def _add_category(self) -> Category | None:
        assert self._new_category_input is not None
        name = self._new_category_input.value.strip()
        if not name:
            return None
        error = validate_category_fields(name=name)
        if error is None and self._service.is_category_name_taken(name):
            error = "同じ名前のカテゴリが既にあります"
        if error is not None:
            ui.notify(error, type="warning")
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
