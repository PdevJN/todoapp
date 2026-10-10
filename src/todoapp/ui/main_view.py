from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

from nicegui import ui
from nicegui.elements.dark_mode import DarkMode
from nicegui.elements.fab import FabAction
from nicegui.events import GenericEventArguments, SortableEventArguments, ValueChangeEventArguments

from todoapp.domain.models import DoneFilter, ScheduleType, TodoItem, is_category_expired, is_done, matches_done_filter, today_estimate_seconds
from todoapp.domain.service import TodoService
from todoapp.repository.config_repository import Theme
from todoapp.ui.app_state import AppState
from todoapp.ui.formatting import DONE_FILTER_LABELS, DONE_TEXT_CLASSES, SCHEDULE_LABELS, format_duration, format_estimate
from todoapp.ui.js_handlers import IME_SAFE_ENTER_HANDLER

_THEME_ACTIVE_COLOR = "primary"
_THEME_INACTIVE_COLOR = "grey-7"


class MainView:
    def __init__(
        self,
        service: TodoService,
        state: AppState,
        refresh_all: Callable[[], None],
        open_category_pick: Callable[[str], None],
        dark_mode: DarkMode,
        initial_theme: Theme,
        open_help: Callable[[], None],
    ) -> None:
        self._service = service
        self._state = state
        self._refresh_all = refresh_all
        self._open_category_pick = open_category_pick
        self._dark_mode = dark_mode
        self._current_theme: Theme = initial_theme
        self._theme_actions: dict[Theme, FabAction] = {}
        self._open_help = open_help
        self._new_item_input: ui.input | None = None
        self._running_indicator: ui.row | None = None
        self._running_name_label: ui.label | None = None
        self._running_remaining_label: ui.label | None = None
        self._elapsed_label: ui.label | None = None
        self._elapsed_item_id: str | None = None
        self._rendered_item_ids: list[str] = []
        self._row_elements: dict[str, ui.row] = {}
        self._select_anchor_index: int | None = None
        self._select_all_active = False

    def build(self) -> ui.column:
        root = ui.column().classes("w-full gap-2 p-4")
        with root:
            # position: absoluteだとrootの高さ(コンテンツ量やNiceGUI既定のページ余白の影響を
            # 受け、実際のウィンドウの縦幅とは一致しない)を基準にしてしまう。ウィンドウそのもの
            # (ビューポート)の四隅に固定するため、fixedを使う
            with ui.fab("palette", color="grey-7").props("direction=left").classes("fixed top-4 right-4 z-10"):
                self._theme_actions["dark"] = ui.fab_action(
                    "dark_mode", label="ダーク", on_click=lambda: self._select_theme("dark")
                ).tooltip("テーマ切り替え(ダーク)")
                self._theme_actions["light"] = ui.fab_action(
                    "light_mode", label="ライト", on_click=lambda: self._select_theme("light")
                ).tooltip("テーマ切り替え(ライト)")
                self._theme_actions["auto"] = ui.fab_action(
                    "brightness_auto", label="自動", on_click=lambda: self._select_theme("auto")
                ).tooltip("テーマ切り替え(自動)")
            self._update_theme_highlight()
            ui.button(icon="help", on_click=self._open_help).props("fab color=grey-7").classes(
                "fixed bottom-4 right-4 z-10"
            ).tooltip("キー操作ヘルプ")
            # 実行中アイテムを常に把握できるよう、最下部にウィンドウ基準で浮かせて表示する。
            # 背景は透過(30%)にして、下にあるアイテム一覧が透けて見えるようにする
            with ui.row().classes(
                "fixed bottom-20 left-1/2 -translate-x-1/2 items-center gap-2 "
                "bg-black/30 text-white px-4 py-2 rounded-full z-10 pointer-events-none"
            ) as self._running_indicator:
                ui.spinner("hourglass", color="primary")
                self._running_name_label = ui.label().classes("font-medium text-lg")
                self._running_remaining_label = ui.label().classes("font-mono text-lg")
            # 表示する日を前後の日・日付入力で切り替える(今日以外は閲覧用)
            with ui.row().classes("items-center gap-1"):
                ui.button(icon="chevron_left", on_click=lambda: self.shift_view_date(-1)).props("flat dense round")
                self._date_input = ui.input(
                    value=self._state.view_date.isoformat(), on_change=self._on_view_date_change
                ).props("type=date dense")
                ui.button(icon="chevron_right", on_click=lambda: self.shift_view_date(1)).props("flat dense round")
            # 完了アイテムの表示は、未完了のみ(既定)・すべて・完了のみを切り替える
            self._done_filter_toggle = ui.toggle(
                DONE_FILTER_LABELS, value=self._state.done_filter.value, on_change=self._on_done_filter_change
            ).props("dense")
            self.list_container = ui.column().classes("w-full gap-1")
            # delayを設定しないと、素早いクリック(特にダブルクリック)時のわずかなカーソルの
            # ブレでSortableJSがドラッグ開始と誤判定し、click/dblclickイベントが失われることがある
            self.list_container.make_sortable(on_end=self._on_reorder, options={"delay": 150})
            self.render()
            # 既存アイテム・過去の実行記録の名前を、前方一致で薄く表示し、Tabで確定する
            self._new_item_input = ui.input(
                placeholder="新しいアイテムを入力してEnter(Shift+Enterでカテゴリ選択)",
                autocomplete=self._service.item_name_candidates(),
            ).classes("w-full")
            self._new_item_input.on("keydown.enter.exact", self._add_item, js_handler=IME_SAFE_ENTER_HANDLER)
            self._new_item_input.on(
                "keydown.enter.shift", self._add_item_and_pick_category, js_handler=IME_SAFE_ENTER_HANDLER
            )
        ui.timer(1.0, self._tick)
        return root

    def _select_theme(self, theme: Theme) -> None:
        if theme == "dark":
            self._dark_mode.enable()
        elif theme == "light":
            self._dark_mode.disable()
        else:
            self._dark_mode.auto()
        self._current_theme = theme
        self._update_theme_highlight()

    def _update_theme_highlight(self) -> None:
        for theme, action in self._theme_actions.items():
            is_active = theme == self._current_theme
            action.set_background_color(_THEME_ACTIVE_COLOR if is_active else _THEME_INACTIVE_COLOR)

    def _add_item(self) -> TodoItem | None:
        assert self._new_item_input is not None
        name = self._new_item_input.value.strip()
        if not name:
            return None
        item = self._service.add_item(name, ScheduleType.ONE_TIME, date.today())
        self._new_item_input.value = ""
        self._state.select(item.id)
        self._refresh_all()
        return item

    def _add_item_and_pick_category(self) -> None:
        item = self._add_item()
        if item is not None:
            self._open_category_pick(item.id)

    def select_all(self) -> None:
        self._state.select_items(set(self._rendered_item_ids))
        self._select_all_active = True
        self.render.refresh()

    def is_select_all_active(self) -> bool:
        return self._select_all_active

    def clear_select_all(self) -> None:
        self._state.select_items(set())
        self._select_all_active = False
        self.render.refresh()

    def _on_row_click(self, item_id: str, e: GenericEventArguments) -> None:
        self._select_all_active = False
        modifiers = e.args
        ctrl = bool(modifiers["ctrlKey"] or modifiers["metaKey"])
        shift = bool(modifiers["shiftKey"])
        index = self._rendered_item_ids.index(item_id) if item_id in self._rendered_item_ids else None
        previous_selection = set(self._state.selected_item_ids)

        if shift and self._select_anchor_index is not None and index is not None:
            lo, hi = sorted((self._select_anchor_index, index))
            self._state.select_items(set(self._rendered_item_ids[lo : hi + 1]))
        elif ctrl:
            selected = set(self._state.selected_item_ids)
            if item_id in selected:
                selected.discard(item_id)
            else:
                selected.add(item_id)
            self._state.select_items(selected)
            self._select_anchor_index = index
        else:
            self._state.select_items({item_id})
            self._select_anchor_index = index

        self._state.select(item_id)
        # 選択のたびにrender.refresh()で全行を作り直すと、ダブルクリックの1回目のクリックで
        # 対象行のDOM要素自体が入れ替わってしまい、2回目のクリックとの間でdblclickが
        # 成立しないことがある。選択に伴う見た目の変化はCSSクラスの差分更新に留め、
        # 行のDOM要素をダブルクリック中も維持する
        self._update_selection_classes(previous_selection)

    def move_selection(self, delta: int) -> None:
        if not self._rendered_item_ids:
            return
        self._select_all_active = False
        current = self._state.selected_item_id
        if current in self._rendered_item_ids:
            index = self._rendered_item_ids.index(current) + delta
            index = max(0, min(len(self._rendered_item_ids) - 1, index))
        else:
            index = 0 if delta > 0 else len(self._rendered_item_ids) - 1
        new_id = self._rendered_item_ids[index]
        previous_selection = set(self._state.selected_item_ids)
        self._state.select(new_id)
        self._state.select_items({new_id})
        self._select_anchor_index = index
        self._update_selection_classes(previous_selection)

    def _update_selection_classes(self, previous_selection: set[str]) -> None:
        changed_ids = previous_selection ^ self._state.selected_item_ids
        for changed_id in changed_ids:
            row = self._row_elements.get(changed_id)
            if row is None:
                continue
            if changed_id in self._state.selected_item_ids:
                row.classes(add="border-primary bg-blue-50", remove="border-transparent")
            else:
                row.classes(add="border-transparent", remove="border-primary bg-blue-50")

    def _toggle(self, item_id: str) -> None:
        if self._state.is_read_only_view:
            return
        self._select_all_active = False
        self._state.select(item_id)
        self._state.select_items({item_id})
        self._service.toggle_execution(item_id)
        self._refresh_all()

    def shift_view_date(self, days: int) -> None:
        self._date_input.value = (self._state.view_date + timedelta(days=days)).isoformat()

    def _on_view_date_change(self, e: ValueChangeEventArguments[str | None]) -> None:
        if not e.value:
            return
        self._state.view_date = date.fromisoformat(e.value)
        # 表示が切り替わると見えなくなるアイテムが選択されたままにならないよう、選択を解除する
        self._select_all_active = False
        self._state.select(None)
        self._state.select_items(set())
        self.render.refresh()

    def _on_done_filter_change(self, e: ValueChangeEventArguments[str]) -> None:
        self._state.done_filter = DoneFilter(e.value)
        # 絞り込みで見えなくなったアイテムが選択されたままにならないよう、選択を解除する
        self._select_all_active = False
        self._state.select(None)
        self._state.select_items(set())
        self.render.refresh()

    def _on_reorder(self, e: SortableEventArguments) -> None:
        # 完了アイテムを非表示にしていると、表示上の位置と全アイテムの中での位置がずれるため、
        # 移動したアイテムを、移動先に居たアイテムの位置へ動かす形で全体の並びを更新する
        ids = self._rendered_item_ids
        moved_id = ids[e.old_index]
        target_id = ids[e.new_index]
        if moved_id != target_id:
            self._service.move_item_to(moved_id, target_id)
        self._refresh_all()

    def _tick(self) -> None:
        self._watch_running()
        self._update_running_indicator()
        running = self._service.running_record()
        if running is None or self._elapsed_label is None:
            return
        if self._elapsed_item_id == running.item_id:
            self._elapsed_label.set_text(format_duration(running.elapsed_seconds(datetime.now())))
            self._apply_over_estimate_color(self._elapsed_label, running.item_id)

    def _watch_running(self) -> None:
        """実行中の見守り: 0:00を跨いだ記録の分割、スリープ等で止まっていた場合の停止、表示日の追従。"""
        suspended = self._service.keep_alive()
        rolled = self._state.roll_over(date.today())
        if rolled:
            # 日付入力も新しい表示日に揃える(変更ハンドラが選択解除と再描画を行う)
            self._date_input.value = self._state.view_date.isoformat()
        if suspended:
            ui.notify("処理が長く止まっていたため、最後に動作していた時刻で実行を停止しました", type="warning")
        if suspended or rolled:
            self._refresh_all()

    def _apply_over_estimate_color(self, label: ui.label, item_id: str) -> None:
        # 累積経過時間が見積りを超えたら赤、それ以外は通常の強調色で表示する
        if self._service.is_over_estimate(item_id):
            label.classes(add="text-negative", remove="text-primary")
        else:
            label.classes(add="text-primary", remove="text-negative")

    def _update_running_indicator(self) -> None:
        assert self._running_indicator is not None
        assert self._running_name_label is not None
        assert self._running_remaining_label is not None
        running = self._service.running_record()
        if running is None:
            self._running_indicator.set_visibility(False)
            return
        self._running_indicator.set_visibility(True)
        self._running_name_label.set_text(running.item_name)
        self._running_remaining_label.set_text(self._remaining_display(running.item_id))

    def _remaining_display(self, item_id: str) -> str:
        item = next((i for i in self._service.items if i.id == item_id), None)
        if item is None:
            return "-"
        # 本日だけの限定見積りがあれば、本日の実行時間を引いた残りを優先して表示する
        today_remaining = self._service.today_remaining_seconds(item_id, date.today())
        if today_remaining is not None:
            return format_duration(today_remaining)
        if item.estimate_hours <= 0:
            return "-"
        return format_duration(self._service.remaining_seconds(item_id))

    @ui.refreshable_method
    def render(self) -> None:
        self._elapsed_label = None
        self._elapsed_item_id = None
        self._row_elements = {}
        self.list_container.clear()
        with self.list_container:
            today = date.today()
            view_date = self._state.view_date
            # 実行中のアイテムは、完了状態による絞り込みに関わらず(元の並びの位置で)表示する
            running = self._service.running_record()
            items = [
                item
                for item in self._service.items_due_today(view_date)
                if matches_done_filter(item, view_date, self._state.done_filter)
                or (running is not None and running.item_id == item.id)
            ]
            self._rendered_item_ids = [item.id for item in items]
            if not items:
                ui.label("").classes("text-gray-400 italic h-8")
            else:
                for item in items:
                    self._render_row(item, today, view_date)
        if self._new_item_input is not None:
            self._new_item_input.set_autocomplete(self._service.item_name_candidates())
        self._update_running_indicator()

    def _render_row(self, item: TodoItem, today: date, view_date: date) -> None:
        running = self._service.running_record()
        is_running = running is not None and running.item_id == item.id
        is_selected = item.id in self._state.selected_item_ids

        classes = "w-full items-center gap-3 p-2 rounded cursor-pointer border"
        classes += " border-primary bg-blue-50" if is_selected else " border-transparent"

        with ui.row().classes(classes) as row:
            self._row_elements[item.id] = row
            row.on("click", lambda e, i=item.id: self._on_row_click(i, e), args=["ctrlKey", "metaKey", "shiftKey"])
            row.on("dblclick", lambda i=item.id: self._toggle(i))
            category = self._service.category_for_item(item.id)
            expired_mark = "❗️" if category is not None and is_category_expired(category, today) else ""
            category_label = f"{expired_mark}{category.name}" if category is not None else "未定"
            category_color = category.color if category is not None else "grey"
            ui.badge(category_label).props(f"outline color={category_color}")
            name_classes = "font-medium" + (f" {DONE_TEXT_CLASSES}" if is_done(item, view_date) else "")
            ui.label(item.name).classes(name_classes)
            ui.badge(SCHEDULE_LABELS[item.schedule_type.value]).props("outline")
            if is_running:
                assert running is not None
                label = ui.label(format_duration(running.elapsed_seconds(datetime.now())))
                label.classes("font-mono")
                self._apply_over_estimate_color(label, item.id)
                self._elapsed_label = label
                self._elapsed_item_id = item.id
            else:
                total = self._service.today_total_seconds(item.id, view_date)
                if total > 0:
                    over = self._service.is_over_estimate(item.id)
                    ui.label(f"{'本日' if view_date == today else ''}合計 {format_duration(total)}").classes(
                        "font-mono " + ("text-negative" if over else "text-gray-500")
                    )
            if item.estimate_hours > 0:
                ui.label(f"見積り {format_estimate(item.estimate_hours)}").classes("text-gray-400 text-sm")
            today_estimate = today_estimate_seconds(item, today)
            if today_estimate is not None:
                ui.label(f"本日の見積り {format_estimate(today_estimate / 3600)}").classes("text-gray-400 text-sm")
