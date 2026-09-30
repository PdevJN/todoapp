from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from nicegui import ui
from nicegui.events import GenericEventArguments, ValueChangeEventArguments

from todoapp.domain.models import Category, ExecutionRecord
from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.formatting import DONE_TEXT_CLASSES, format_duration
from todoapp.ui.js_handlers import CLIPBOARD_COPY_HANDLER

_MODE_ORDER = "order"
_MODE_CATEGORY = "category"
_MODE_LABELS = {_MODE_ORDER: "実行順", _MODE_CATEGORY: "カテゴリ別"}

# (カテゴリ(Noneは未定), 本日の合計秒数, [(タスク名, 本日の実行秒数)])
_CategoryRow = tuple[Category | None, float, list[tuple[str, float, bool]]]


class LogView(DialogMixin):
    def __init__(
        self, service: TodoService, state: AppState, open_timeline_edit: Callable[[str], None]
    ) -> None:
        self._service = service
        self._state = state
        self._open_timeline_edit = open_timeline_edit
        self._rendered_record_ids: list[str] = []
        self._select_anchor_index: int | None = None
        self._mode = _MODE_ORDER
        self._category_signature: list[tuple[str | None, list[tuple[str, bool]]]] = []
        self._category_time_labels: list[tuple[ui.label, list[ui.label]]] = []

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[32rem] gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("本日の作業ログ").classes("text-lg font-bold")
                self.mode_toggle = ui.toggle(
                    _MODE_LABELS, value=self._mode, on_change=self._on_mode_change
                ).props("dense")
            self.log_container = ui.column().classes("w-full gap-1")
            with ui.row().classes("w-full justify-end gap-2"):
                self.copy_button = ui.button("経過時間をコピー", icon="content_copy").props("flat")
                self.copy_button.on("click", self._on_copied, js_handler=CLIPBOARD_COPY_HANDLER)
                self.copy_button.set_visibility(False)
                ui.button("閉じる", on_click=self.dialog.close).props("flat")
        ui.timer(1.0, self._tick)

    def open(self) -> None:
        self._mode = _MODE_ORDER
        self.mode_toggle.set_value(_MODE_ORDER)
        self._render()
        self.dialog.open()

    def refresh(self) -> None:
        self._render.refresh()

    def _tick(self) -> None:
        # 行を作り直すと表示中のツールチップが消えるため、構成が同じなら時間の文字だけ更新する
        if not self.is_open() or self._mode != _MODE_CATEGORY or self._service.running_record() is None:
            return
        rows = self._category_rows()
        if _signature(rows) != self._category_signature:
            self._render.refresh()
            return
        self._update_copy_text(rows)
        for (total_label, item_labels), (_, seconds, items) in zip(self._category_time_labels, rows):
            total_label.set_text(format_duration(seconds))
            for item_label, (_, item_seconds, _) in zip(item_labels, items):
                item_label.set_text(format_duration(item_seconds))

    def _category_rows(self) -> list[_CategoryRow]:
        today = date.today()
        items_by_category = self._service.category_today_item_totals(today)
        return [
            (category, seconds, items_by_category.get(category.id if category else None, []))
            for category, seconds in self._service.category_today_all_totals(today)
        ]

    def _update_copy_text(self, rows: list[_CategoryRow]) -> None:
        text = category_durations_text([(category, seconds) for category, seconds, _ in rows])
        self.copy_button.props["data-copy-text"] = text
        self.copy_button.set_enabled(bool(text))

    def _on_copied(self, e: GenericEventArguments) -> None:
        if e.args:
            ui.notify("経過時間をコピーしました", type="positive")
        else:
            ui.notify("クリップボードへのコピーに失敗しました", type="negative")

    def _on_mode_change(self, e: ValueChangeEventArguments[str]) -> None:
        # カテゴリ別表示では記録を選択できないため、切り替え時に記録の選択を解除する
        self._mode = e.value
        self.copy_button.set_visibility(self._mode == _MODE_CATEGORY)
        self._state.select_records(set())
        self._state.select_record(None)
        self._select_anchor_index = None
        self._render.refresh()

    def select_all(self) -> None:
        if self._mode != _MODE_ORDER:
            return
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

    def move_selection(self, delta: int) -> None:
        if self._mode != _MODE_ORDER or not self._rendered_record_ids:
            return
        current = self._state.selected_record_id
        if current in self._rendered_record_ids:
            index = self._rendered_record_ids.index(current) + delta
            index = max(0, min(len(self._rendered_record_ids) - 1, index))
        else:
            index = 0 if delta > 0 else len(self._rendered_record_ids) - 1
        new_id = self._rendered_record_ids[index]
        self._select_anchor_index = index
        self._state.select_records({new_id})
        self._state.select_record(new_id)
        self._render.refresh()

    @ui.refreshable_method
    def _render(self) -> None:
        self.log_container.clear()
        with self.log_container:
            if self._mode == _MODE_CATEGORY:
                self._rendered_record_ids = []
                rows = self._category_rows()
                self._category_signature = _signature(rows)
                self._category_time_labels = [self._render_category_row(*row) for row in rows]
                self._update_copy_text(rows)
                return
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
            # アイテムに設定されたカテゴリをバッジで表示する(未設定・削除済みアイテムは未定)
            category = self._service.category_for_item(record.item_id)
            category_name = category.name if category is not None else "未定"
            category_color = category.color if category is not None else "grey"
            # 左側(バッジ+タスク名)だけを縮められるようにし、長いタスク名は「...」で省略して
            # マウスオーバーで全文をツールチップ表示する(時刻・ボタン側は幅を固定して見切れを防ぐ)
            with ui.row().classes("items-center gap-2 no-wrap min-w-0 flex-1"):
                ui.badge(category_name).props(f"outline color={category_color}").classes("shrink-0")
                with ui.label(record.item_name).classes("font-medium truncate min-w-0"):
                    ui.tooltip(record.item_name)
            with ui.row().classes("items-center gap-1 no-wrap shrink-0"):
                ui.label(f"{start} - {end} ({elapsed})").classes("text-gray-500 font-mono")
                # 実行中の記録は終了時刻が未確定のためカレンダーでは編集できない。
                # 行クリック(選択)を発火させないよう、クリックの伝播を止める
                edit_button = ui.button(icon="calendar_month").props("flat dense round size=sm")
                edit_button.on("click.stop", lambda rid=record.id: self._open_timeline_edit(rid))
                edit_button.set_enabled(record.end_time is not None)
                edit_button.tooltip("カレンダーで時間を編集")

    def _render_category_row(
        self, category: Category | None, seconds: float, items: list[tuple[str, float, bool]]
    ) -> tuple[ui.label, list[ui.label]]:
        classes = "w-full justify-between items-center border-b py-1 px-1 rounded"
        with ui.row().classes(classes + (" bg-gray-100" if category is None else "")):
            with ui.row().classes("items-center gap-1"):
                if category is None:
                    ui.label("未定").classes("font-medium text-gray-500")
                else:
                    ui.label(category.name).classes("font-medium")
                    if category.prj_code:
                        ui.badge(category.prj_code).props("outline")
            total_label = ui.label(format_duration(seconds)).classes("text-gray-500 font-mono")
            item_labels: list[ui.label] = []
            with ui.tooltip().classes("text-sm"):
                if not items:
                    ui.label("本日のタスクはありません")
                for name, item_seconds, done in items:
                    # 完了したアイテムは、他の画面と同じく取り消し線とグレーで表示する
                    done_classes = f" {DONE_TEXT_CLASSES}" if done else ""
                    with ui.row().classes("w-full justify-between gap-4 no-wrap"):
                        ui.label(f"・{name}").classes(done_classes.strip())
                        item_labels.append(ui.label(format_duration(item_seconds)).classes("font-mono" + done_classes))
        return total_label, item_labels


def category_durations_text(totals: list[tuple[Category | None, float]]) -> str:
    """登録済みカテゴリの経過時間を画面の並び順に1行ずつ並べる(未定は含めない)。"""
    return "\n".join(format_duration(seconds) for category, seconds in totals if category is not None)


def _signature(rows: list[_CategoryRow]) -> list[tuple[str | None, list[tuple[str, bool]]]]:
    # 完了状態が変わったときも、取り消し線を反映するため行を作り直す対象にする
    return [
        (category.id if category else None, [(name, done) for name, _, done in items])
        for category, _, items in rows
    ]
