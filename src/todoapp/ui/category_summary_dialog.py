from __future__ import annotations

from datetime import date
from typing import Any

from nicegui import ui

from todoapp.domain.models import Category
from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.formatting import format_duration


UNCATEGORIZED_COLOR = "#9e9e9e"


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


class CategorySummaryDialog(DialogMixin):
    def __init__(self, service: TodoService) -> None:
        self._service = service
        self._selected_key: str | None = None
        self._pie_visible = False

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[28rem] gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("カテゴリ別集計").classes("text-lg font-bold")
                # 円グラフの表示中は、選択中と分かるようボタンの色を変える(テーマ選択と同じ考え方)
                self.pie_button = ui.button(icon="pie_chart", on_click=self._toggle_pie).props("flat dense round")
                self.pie_button.tooltip("円グラフの表示を切り替え")
            self.pie_container = ui.column().classes("w-full items-center")
            with self.pie_container:
                self.pie_chart = ui.echart(_pie_options([])).classes("w-full h-64")
                self.pie_empty_label = ui.label("本日の記録はまだありません").classes("text-gray-400 italic")
            self.category_container = ui.column().classes("w-full gap-1")
            ui.separator()
            ui.label("種別ごとの集計").classes("text-sm font-bold text-gray-600")
            self.kind_container = ui.column().classes("w-full gap-1")
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def open(self) -> None:
        self._pie_visible = False
        self.refresh()
        self.dialog.open()

    def refresh(self) -> None:
        today = date.today()
        category_totals = self._service.category_today_totals(today)
        self._refresh_pie(self._service.category_today_all_totals(today))
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

    def _toggle_pie(self) -> None:
        self._pie_visible = not self._pie_visible
        self._apply_pie_visibility()

    def _apply_pie_visibility(self) -> None:
        self.pie_container.set_visibility(self._pie_visible)
        self.pie_button.props(f"color={'primary' if self._pie_visible else 'grey'}")

    def _refresh_pie(self, totals: list[tuple[Category | None, float]]) -> None:
        data = pie_chart_data(totals)
        self.pie_chart.options["series"][0]["data"] = data
        self.pie_chart.update()
        self.pie_chart.set_visibility(bool(data))
        self.pie_empty_label.set_visibility(not data)
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


def _pie_options(data: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "tooltip": {
            "trigger": "item",
            # valueは秒。一覧と同じHH:MM:SSで表示する
            ":formatter": (
                "p => { const s = Math.round(p.value); const f = n => String(n).padStart(2, '0');"
                " return `${p.name}  ${f(Math.floor(s / 3600))}:${f(Math.floor(s % 3600 / 60))}:${f(s % 60)}"
                " (${p.percent}%)`; }"
            ),
        },
        "series": [
            {
                "type": "pie",
                "radius": ["35%", "65%"],
                # 文字色はテーマに関わらず読めるよう、各扇の色に合わせる
                "label": {"color": "inherit"},
                "data": data,
            }
        ],
    }
