from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from todoapp.domain.service import TodoService
from todoapp.domain.work_summary import (
    WorkDayRow,
    WorkSummary,
    month_bounds,
    monthly_breakdown,
    overtime_exceeds_target,
    validate_period,
)
from todoapp.ui.formatting import WEEKDAY_LABELS, format_hhmm, format_signed_hhmm

_MODE_MONTH = "month"
_MODE_PERIOD = "period"
_MODE_LABELS = {_MODE_MONTH: "月", _MODE_PERIOD: "期間"}
_OVER_CLASS = "text-red-600"
_UNDER_CLASS = "text-green-600"

# 系列データのsecondsを`HH:MM:SS`で表示する。値の無い日(null)は行を出さない
_CHART_TOOLTIP_FORMATTER = (
    "params => { const f = s => { const a = Math.abs(Math.round(s)); const p = n => String(n).padStart(2, '0');"
    " return `${s < 0 ? '-' : ''}${p(Math.floor(a / 3600))}:${p(Math.floor(a % 3600 / 60))}:${p(a % 60)}`; };"
    " const lines = params.filter(x => x.data).map(x => `${x.marker}${x.seriesName} `"
    " + `${x.seriesName === 'GAP' && x.data.seconds > 0 ? '+' : ''}${f(x.data.seconds)}`);"
    " return [params[0].axisValue, ...lines].join('<br>'); }"
)


def _point(seconds: float) -> dict[str, float]:
    return {"value": round(seconds / 3600, 2), "seconds": seconds}


def work_chart_options(rows: list[WorkDayRow]) -> dict[str, Any]:
    """日別の棒グラフ(見積り・実績)と、見積りのある日のGAP(実績 − 見積り)の折れ線のオプション。"""
    has_estimate = any(row.estimate_seconds is not None for row in rows)
    series: list[dict[str, Any]] = []
    if has_estimate:
        series.append(
            {
                "name": "見積り",
                "type": "bar",
                "data": [_point(row.estimate_seconds) if row.estimate_seconds is not None else None for row in rows],
            }
        )
    series.append({"name": "実績", "type": "bar", "data": [_point(row.actual_seconds) for row in rows]})
    if has_estimate:
        series.append(
            {
                "name": "GAP",
                "type": "line",
                "data": [
                    _point(row.actual_seconds - row.estimate_seconds) if row.estimate_seconds is not None else None
                    for row in rows
                ],
            }
        )
    return {
        "tooltip": {"trigger": "axis", ":formatter": _CHART_TOOLTIP_FORMATTER, "confine": True},
        "legend": {"data": [s["name"] for s in series], "top": 0},
        "grid": {"left": 48, "right": 16, "top": 40, "bottom": 28},
        "xAxis": {"type": "category", "data": [f"{row.day.month}/{row.day.day}" for row in rows]},
        "yAxis": {"type": "value", "name": "時間", "axisLabel": {"formatter": "{value}h"}},
        "series": series,
    }


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        return None


class WorkSummaryPanel:
    """集計画面の`稼働集計`タブ。月または指定期間の稼働日数・合計・実績・残業時間・見積りGAPと日別グラフを表示する。"""

    def __init__(
        self,
        service: TodoService,
        get_standard_work_hours: Callable[[], float],
        get_overtime_target_hours: Callable[[], float],
        holidays: dict[date, str],
    ) -> None:
        self._service = service
        self._get_standard_work_hours = get_standard_work_hours
        self._get_overtime_target_hours = get_overtime_target_hours
        self._holidays = holidays
        self._built = False
        self._suppress_events = False
        self._mode = _MODE_MONTH
        self._month_start = date.today().replace(day=1)
        self._period = month_bounds(self._month_start.year, self._month_start.month)

    def build(self) -> None:
        with ui.column().classes("w-full gap-2"):
            self._mode_toggle = ui.toggle(_MODE_LABELS, value=self._mode, on_change=self._on_mode_change).props(
                "dense"
            )
            with ui.row().classes("items-center gap-1") as self._month_row:
                ui.button(icon="chevron_left", on_click=lambda: self._shift_month(-1)).props(
                    "flat dense round"
                ).mark("work-prev-month")
                self._month_label = ui.label().classes("font-medium").mark("work-month-label")
                ui.button(icon="chevron_right", on_click=lambda: self._shift_month(1)).props(
                    "flat dense round"
                ).mark("work-next-month")
            with ui.row().classes("items-center gap-2") as self._period_row:
                self._start_input = (
                    ui.input(label="開始日", on_change=self._on_period_change).props("type=date dense").mark("work-start")
                )
                self._end_input = (
                    ui.input(label="終了日", on_change=self._on_period_change).props("type=date dense").mark("work-end")
                )
            self.chart_container = ui.column().classes("w-full items-center").mark("work-chart")
            with self.chart_container:
                self._chart = ui.echart(work_chart_options([])).classes("w-full h-64")
                self._chart_empty_label = ui.label("この期間の記録はありません").classes("text-gray-400 italic")
            self._summary_container = ui.column().classes("w-full gap-0")
            self._breakdown_container = ui.column().classes("w-full gap-0")
            with ui.expansion("稼働日を選ぶ").classes("w-full"):
                self._calendar_container = ui.column().classes("w-full gap-2")
        self._built = True

    def reset(self) -> None:
        """集計画面を開くたびに、今月の月表示から始める(保存しない)。"""
        self._mode = _MODE_MONTH
        self._month_start = date.today().replace(day=1)
        self._period = month_bounds(self._month_start.year, self._month_start.month)
        self._suppress_events = True
        try:
            self._mode_toggle.set_value(_MODE_MONTH)
        finally:
            self._suppress_events = False
        self.refresh()

    def refresh(self) -> None:
        if not self._built:
            return
        start, end = self._range()
        self._month_row.set_visibility(self._mode == _MODE_MONTH)
        self._period_row.set_visibility(self._mode == _MODE_PERIOD)
        self._month_label.set_text(f"{self._month_start.year}年{self._month_start.month}月")
        self._suppress_events = True
        try:
            self._start_input.set_value(self._period[0].isoformat())
            self._end_input.set_value(self._period[1].isoformat())
        finally:
            self._suppress_events = False
        summary = self._service.work_summary(start, end, self._holidays, self._get_standard_work_hours())
        self._render_summary(summary)
        self._render_breakdown(summary)
        self._update_chart(summary)
        self._render_calendar(summary)

    def _range(self) -> tuple[date, date]:
        if self._mode == _MODE_MONTH:
            return month_bounds(self._month_start.year, self._month_start.month)
        return self._period

    def _on_mode_change(self, e: ValueChangeEventArguments[str]) -> None:
        if self._suppress_events:
            return
        self._mode = e.value
        self.refresh()

    def _shift_month(self, months: int) -> None:
        # 月初の日付から1か月ずらす(月初に31日を足して月初へ戻す方法で、月ごとの日数差を避ける)
        base = self._month_start
        if months > 0:
            self._month_start = (base + timedelta(days=31)).replace(day=1)
        else:
            self._month_start = (base - timedelta(days=1)).replace(day=1)
        self.refresh()

    def _on_period_change(self, _: ValueChangeEventArguments[str | None]) -> None:
        if self._suppress_events:
            return
        start = _parse_date(self._start_input.value)
        end = _parse_date(self._end_input.value)
        if start is None or end is None:
            return
        message = validate_period(start, end)
        if message is not None:
            ui.notify(message, type="warning")
            return
        self._period = (start, end)
        self.refresh()

    def _render_summary(self, summary: WorkSummary) -> None:
        target_hours = self._get_overtime_target_hours()
        over = overtime_exceeds_target(summary.overtime_seconds, target_hours)
        has_estimate = summary.estimate_day_count > 0
        # 終わっていない期間は、今日までの稼働日との差なので残業ではなく過不足時間として表示する
        overtime_title = "過不足時間" if summary.in_progress else "残業時間"
        if self._mode == _MODE_PERIOD:
            overtime_title += "(合計)"
        tooltip = f"目標 {target_hours:g}時間"
        if summary.in_progress:
            tooltip = f"今日までの稼働日の標準労働時間との差。{tooltip}"
        self._summary_container.clear()
        with self._summary_container:
            self._summary_row("稼働日数", f"{summary.workday_count}日")
            self._summary_row("合計", format_hhmm(summary.total_seconds))
            self._summary_row("実績", format_hhmm(summary.actual_seconds))
            value_label = self._summary_row(
                overtime_title,
                format_signed_hhmm(summary.overtime_seconds),
                color_class=_OVER_CLASS if over else _UNDER_CLASS,
                title_marker="work-overtime-title",
            )
            value_label.mark("work-overtime")
            with value_label:
                ui.tooltip(tooltip)
            self._summary_row("見積り", format_hhmm(summary.estimate_seconds) if has_estimate else "-")
            self._summary_row("見積りGAP", format_signed_hhmm(summary.gap_seconds) if has_estimate else "-")

    def _render_breakdown(self, summary: WorkSummary) -> None:
        """期間指定のときだけ、月ごとの内訳と通算(通算の行は色を付けない)を表示する。"""
        self._breakdown_container.clear()
        self._breakdown_container.set_visibility(self._mode == _MODE_PERIOD)
        if self._mode != _MODE_PERIOD:
            return
        target_hours = self._get_overtime_target_hours()
        with self._breakdown_container:
            ui.label("月別の内訳").classes("text-sm font-bold text-gray-600 mt-2")
            self._breakdown_row(("月", "稼働日数", "合計", "実績", "残業時間"), header=True)
            for month in monthly_breakdown(summary):
                over = overtime_exceeds_target(month.overtime_seconds, target_hours)
                name = f"{month.year}年{month.month}月" + ("(途中)" if month.in_progress else "")
                value_label = self._breakdown_row(
                    (
                        name,
                        f"{month.workday_count}日",
                        format_hhmm(month.total_seconds),
                        format_hhmm(month.actual_seconds),
                        format_signed_hhmm(month.overtime_seconds),
                    ),
                    color_class=_OVER_CLASS if over else _UNDER_CLASS,
                )
                value_label.mark(f"work-month-{month.year}-{month.month:02d}")
                if month.in_progress:
                    with value_label:
                        ui.tooltip("過不足時間(今日までの稼働日の標準労働時間との差)")
            total_label = self._breakdown_row(
                (
                    "通算",
                    f"{summary.workday_count}日",
                    format_hhmm(summary.total_seconds),
                    format_hhmm(summary.actual_seconds),
                    format_signed_hhmm(summary.overtime_seconds),
                ),
                bold=True,
            )
            total_label.mark("work-month-total")

    @staticmethod
    def _breakdown_row(
        cells: tuple[str, str, str, str, str], *, color_class: str = "", bold: bool = False, header: bool = False
    ) -> ui.label:
        row_classes = "w-full items-center border-b py-1 px-1 no-wrap gap-1"
        if header:
            row_classes += " text-xs text-gray-500 font-bold"
        weight = " font-bold" if bold else ""
        with ui.row().classes(row_classes):
            ui.label(cells[0]).classes("col ellipsis" + weight)
            for cell in cells[1:4]:
                ui.label(cell).classes("w-20 text-right font-mono" + weight)
            return ui.label(cells[4]).classes(f"w-20 text-right font-mono{weight} {color_class}".rstrip())

    @staticmethod
    def _summary_row(name: str, value: str, color_class: str = "", title_marker: str | None = None) -> ui.label:
        with ui.row().classes("w-full justify-between items-center border-b py-1 px-1"):
            title = ui.label(name).classes(f"text-gray-600 {color_class}".strip())
            if title_marker:
                title.mark(title_marker)
            return ui.label(value).classes(f"font-mono font-medium {color_class}".strip())

    def _update_chart(self, summary: WorkSummary) -> None:
        has_data = any(row.actual_seconds > 0 or row.estimate_seconds for row in summary.rows)
        self._chart.options.update(work_chart_options(summary.rows))
        self._chart.update()
        self._chart.set_visibility(has_data)
        self._chart_empty_label.set_visibility(not has_data)

    def _render_calendar(self, summary: WorkSummary) -> None:
        """期間内の日を月ごとの格子で並べる。クリックで稼働/非稼働を切り替える。"""
        months: dict[tuple[int, int], list[WorkDayRow]] = {}
        for row in summary.rows:
            months.setdefault((row.day.year, row.day.month), []).append(row)
        self._calendar_container.clear()
        with self._calendar_container:
            for (year, month), rows in months.items():
                ui.label(f"{year}年{month}月").classes("text-sm font-bold text-gray-600")
                with ui.grid(columns=7).classes("gap-1"):
                    for weekday in WEEKDAY_LABELS:
                        ui.label(weekday).classes("text-xs text-center text-gray-500")
                    for _ in range(rows[0].day.weekday()):  # 月曜始まりで、月初の曜日まで空ける
                        ui.label("")
                    for row in rows:
                        self._render_day_button(row)

    def _render_day_button(self, row: WorkDayRow) -> None:
        holiday_name = self._holidays.get(row.day)
        if row.is_workday:
            props = "color=primary"
        elif holiday_name:
            props = "color=green-2 text-color=green-9"
        else:
            props = "color=grey-4 text-color=grey-8"
        button = (
            ui.button(
                str(row.day.day), on_click=lambda day=row.day, workday=row.is_workday: self._toggle(day, not workday)
            )
            .props(f"dense unelevated size=sm {props}")
            .classes("w-8")
            .mark(f"work-day-{row.day.isoformat()}")
        )
        if row.day in self._service.workday_overrides:
            button.classes("outline outline-2 outline-orange-400")  # 既定から変更した日
        state = "稼働日" if row.is_workday else "非稼働日"
        with button:
            ui.tooltip(f"{holiday_name}・{state}" if holiday_name else state)

    def _toggle(self, day: date, workday: bool) -> None:
        self._service.set_workday(day, workday, self._holidays)
        self.refresh()
