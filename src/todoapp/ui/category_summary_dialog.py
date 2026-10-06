from __future__ import annotations

from datetime import date
from typing import Any

from nicegui import ui

from todoapp.domain.models import Category
from todoapp.domain.service import ItemGapRow, TodoService
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.formatting import DONE_TEXT_CLASSES, format_duration, format_gap, gap_background

UNCATEGORIZED_COLOR = "#9e9e9e"
_TAB_CATEGORY = "カテゴリ別"
_TAB_ITEM = "アイテム別"
# valueは秒。カテゴリ別は一覧と同じHH:MM:SSで表示する
_CATEGORY_TOOLTIP_FORMATTER = (
    "p => { const s = Math.round(p.value); const f = n => String(n).padStart(2, '0');"
    " return `${p.name}  ${f(Math.floor(s / 3600))}:${f(Math.floor(s % 3600 / 60))}:${f(s % 60)}"
    " (${p.percent}%)`; }"
)
# アイテム別は、Python側で整形済みの文字列(系列データのtooltip)に、|GAP|全体に対する割合を添える
_GAP_TOOLTIP_FORMATTER = "p => `${p.data.tooltip} (${p.percent}%)`"
_ITEM_ROW_CLASSES = "w-full items-center border-b py-1 px-1 no-wrap gap-1"
_ITEM_NUMBER_CLASSES = "w-20 text-right font-mono px-1"


def pie_chart_data(totals: list[tuple[Category | None, float]]) -> list[dict[str, Any]]:
    """カテゴリ別の合計時間(秒)を円グラフの系列データにする。0秒は除外し、未定はグレーで表す。"""
    return [
        {
            "name": category.name if category is not None else "未定",
            "value": seconds,
            "itemStyle": {"color": category.color if category is not None else UNCATEGORIZED_COLOR},
        }
        for category, seconds in totals
        if seconds > 0
    ]


def gap_pie_data(rows: list[ItemGapRow]) -> list[dict[str, Any]]:
    """アイテムごとのGAPを円グラフの系列データにする。扇の大きさは|GAP|、色は表のGAPセルと同じ赤/青の濃淡。

    GAPが無い(見積り未設定・削除済み)アイテムと、秒に丸めてGAPが0のアイテムは含めない。
    """
    data: list[dict[str, Any]] = []
    for row in rows:
        if row.gap_seconds is None or row.estimate_seconds is None or row.cumulative_seconds is None:
            continue
        color = gap_background(row.gap_seconds, row.estimate_seconds)
        if color is None:
            continue
        data.append(
            {
                "name": row.name,
                "value": abs(row.gap_seconds),
                "itemStyle": {"color": color},
                "tooltip": (
                    f"{row.name}  GAP {format_gap(row.gap_seconds)}"
                    f" (見積り {format_duration(row.estimate_seconds)} / 累積 {format_duration(row.cumulative_seconds)})"
                ),
            }
        )
    return data


class CategorySummaryDialog(DialogMixin):
    def __init__(self, service: TodoService) -> None:
        self._service = service
        self._selected_key: str | None = None
        self._built = False
        # 円グラフの表示状態はタブごとに独立して持つ
        self._pie_visible = {_TAB_CATEGORY: False, _TAB_ITEM: False}

    def build(self) -> None:
        # アイテム別タブは列が多いため、他のダイアログ(最大w-[36rem])と同程度の幅に広げる
        with ui.dialog() as self.dialog, ui.card().classes("w-[36rem] gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("集計画面").classes("text-lg font-bold")
                # 円グラフの表示中は、選択中と分かるようボタンの色を変える(テーマ選択と同じ考え方)
                self.pie_button = ui.button(icon="pie_chart", on_click=self._toggle_pie).props("flat dense round")
                self.pie_button.tooltip("円グラフの表示を切り替え")
            with ui.tabs(on_change=self._on_tab_change).classes("w-full") as self.tabs:
                self.category_tab = ui.tab(_TAB_CATEGORY)
                self.item_tab = ui.tab(_TAB_ITEM)
            with ui.tab_panels(self.tabs, value=_TAB_CATEGORY).classes("w-full"):
                with ui.tab_panel(self.category_tab).classes("p-0 gap-2"):
                    self.pie_container, self.pie_chart, self.pie_empty_label = self._build_pie(
                        _CATEGORY_TOOLTIP_FORMATTER, "本日の記録はまだありません"
                    )
                    self.category_container = ui.column().classes("w-full gap-1")
                    ui.separator()
                    ui.label("種別ごとの集計").classes("text-sm font-bold text-gray-600")
                    self.kind_container = ui.column().classes("w-full gap-1")
                with ui.tab_panel(self.item_tab).classes("p-0 gap-2"):
                    self.gap_pie_container, self.gap_pie_chart, self.gap_pie_empty_label = self._build_pie(
                        _GAP_TOOLTIP_FORMATTER, "GAPのあるアイテムがありません"
                    )
                    self.item_container = ui.column().classes("w-full gap-0")
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")
        self._built = True

    def _build_pie(self, tooltip_formatter: str, empty_text: str) -> tuple[ui.column, ui.echart, ui.label]:
        container = ui.column().classes("w-full items-center")
        with container:
            chart = ui.echart(_pie_options(tooltip_formatter)).classes("w-full h-64")
            empty_label = ui.label(empty_text).classes("text-gray-400 italic")
        return container, chart, empty_label

    def open(self) -> None:
        self._pie_visible = {_TAB_CATEGORY: False, _TAB_ITEM: False}
        self.tabs.set_value(_TAB_CATEGORY)
        self.refresh()
        self.dialog.open()

    def refresh(self) -> None:
        today = date.today()
        category_totals = self._service.category_today_totals(today)
        self._refresh_pie(self._service.category_today_all_totals(today))
        self._refresh_items(self._service.item_gap_rows(today))
        categories_by_id = {c.id: c for c in self._service.categories}

        self.category_container.clear()
        with self.category_container:
            rows = [
                (category_id, categories_by_id.get(category_id) if category_id else None, seconds)
                for category_id, seconds in category_totals.items()
            ]
            if not rows:
                ui.label("本日の記録はまだありません").classes("text-gray-400 italic")
            for category_id, category, seconds in rows:
                self._render_category_row(category_id, category, seconds)

        kind_totals = self._service.kind_today_totals(today)
        self.kind_container.clear()
        with self.kind_container:
            if not kind_totals:
                ui.label("-").classes("text-gray-400")
            for kind in sorted(kind_totals):
                ui.label(f"{kind}: {format_duration(kind_totals[kind])}").classes("font-mono text-right w-full")

    def _on_tab_change(self) -> None:
        # タブの初期値が設定される組み立て中にも呼ばれるため、部品が揃うまでは何もしない
        if self._built:
            self._apply_pie_visibility()

    def _refresh_items(self, rows: list[ItemGapRow]) -> None:
        self._update_pie(self.gap_pie_chart, self.gap_pie_empty_label, gap_pie_data(rows))
        self.item_container.clear()
        with self.item_container:
            if not rows:
                ui.label("本日のアイテムはありません").classes("text-gray-400 italic")
                return
            self._render_item_header()
            for row in rows:
                self._render_item_row(row)

    def _render_item_header(self) -> None:
        with ui.row().classes(f"{_ITEM_ROW_CLASSES} text-xs text-gray-500 font-bold"):
            ui.label("アイテム名").classes("col")
            for label in ("本日", "累積", "見積り", "GAP"):
                ui.label(label).classes(_ITEM_NUMBER_CLASSES)

    def _render_item_row(self, row: ItemGapRow) -> None:
        with ui.row().classes(_ITEM_ROW_CLASSES):
            name_classes = "col font-medium ellipsis" + (f" {DONE_TEXT_CLASSES}" if row.done else "")
            ui.label(row.name).classes(name_classes)
            ui.label(format_duration(row.today_seconds)).classes(_ITEM_NUMBER_CLASSES)
            ui.label(_format_optional(row.cumulative_seconds)).classes(_ITEM_NUMBER_CLASSES)
            ui.label(_format_optional(row.estimate_seconds)).classes(_ITEM_NUMBER_CLASSES)
            gap_label = ui.label(format_gap(row.gap_seconds)).classes(_ITEM_NUMBER_CLASSES + " rounded")
            background = gap_background(row.gap_seconds, row.estimate_seconds)
            if background is not None:
                gap_label.style(f"background: {background}")

    def _toggle_pie(self) -> None:
        tab = self.tabs.value
        self._pie_visible[tab] = not self._pie_visible[tab]
        self._apply_pie_visibility()

    def _apply_pie_visibility(self) -> None:
        self.pie_container.set_visibility(self._pie_visible[_TAB_CATEGORY])
        self.gap_pie_container.set_visibility(self._pie_visible[_TAB_ITEM])
        # 表示中の円グラフは、選択中と分かるよう表示中のタブでのボタンの色を変える
        self.pie_button.props(f"color={'primary' if self._pie_visible[self.tabs.value] else 'grey'}")

    @staticmethod
    def _update_pie(
        chart: ui.echart, empty_label: ui.label, data: list[dict[str, Any]]
    ) -> None:
        chart.options["series"][0]["data"] = data
        chart.update()
        chart.set_visibility(bool(data))
        empty_label.set_visibility(not data)

    def _refresh_pie(self, totals: list[tuple[Category | None, float]]) -> None:
        self._update_pie(self.pie_chart, self.pie_empty_label, pie_chart_data(totals))
        self._apply_pie_visibility()

    def _select(self, key: str) -> None:
        self._selected_key = key
        self.refresh()

    def _render_category_row(self, category_id: str | None, category: Category | None, seconds: float) -> None:
        key = category_id or "__uncategorized__"
        is_selected = self._selected_key == key
        name = category.name if category is not None else "未定"

        classes = "w-full justify-between items-center border-b py-1 px-1 rounded cursor-pointer"
        classes += " bg-blue-200" if is_selected else ""
        with ui.row().classes(classes) as row:
            row.on("click", lambda k=key: self._select(k))
            with ui.row().classes("items-center gap-1"):
                ui.label(name).classes("font-medium")
                if category is not None and category.prj_code:
                    ui.badge(category.prj_code).props("outline")
            ui.label(format_duration(seconds)).classes("text-gray-500 font-mono")


def _format_optional(seconds: float | None) -> str:
    return format_duration(seconds) if seconds is not None else "-"


def _pie_options(tooltip_formatter: str) -> dict[str, Any]:
    return {
        "tooltip": {
            "trigger": "item",
            ":formatter": tooltip_formatter,
            # 端に近い扇でもツールチップが円グラフの領域(ダイアログ内)からはみ出さないよう内側へ寄せ、
            # 長い文字列(アイテム別のGAPなど)は幅に収まるよう折り返す
            "confine": True,
            "extraCssText": "max-width: 90%; white-space: normal; word-break: break-all;",
        },
        "series": [
            {
                "type": "pie",
                "radius": ["35%", "65%"],
                # 文字色はテーマに関わらず読めるよう、各扇の色に合わせる
                "label": {"color": "inherit"},
                "data": [],
            }
        ],
    }
