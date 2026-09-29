from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from nicegui import ui
from nicegui.events import GenericEventArguments, ValueChangeEventArguments

from todoapp.domain.service import TodoService
from todoapp.repository.config_repository import WeekStart
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.formatting import format_duration
from todoapp.ui.vendor.fullcalendar.fullcalendar import FullCalendar

_UNCATEGORIZED_COLOR = "#9e9e9e"
_WEEK_START_LABELS: dict[WeekStart, str] = {"sunday": "日曜始まり", "monday": "月曜始まり"}


def _first_day(week_start: WeekStart) -> int:
    return 1 if week_start == "monday" else 0


class CalendarView(DialogMixin):
    def __init__(
        self,
        service: TodoService,
        open_record_edit_dialog: Callable[[str], None],
        initial_week_start: WeekStart,
        on_week_start_change: Callable[[WeekStart], None],
        holidays: dict[date, str],
        refresh_holidays: Callable[[], bool],
    ) -> None:
        self._service = service
        self._open_record_edit_dialog = open_record_edit_dialog
        self._week_start = initial_week_start
        self._on_week_start_change = on_week_start_change
        self._holidays = holidays
        self._refresh_holidays = refresh_holidays

    def build(self) -> None:
        # ネイティブウィンドウ(main.pyのwindow_size=(620, 720))に対して列幅が狭く、
        # 曜日+日付の文字列がぎりぎり収まる列とわずかに折り返される列が混在し
        # 見た目が揃わないため、常に1行で収まるよう固定する
        ui.add_css(".fc .fc-col-header-cell-cushion { white-space: nowrap; font-size: 0.75em; }")
        # 土曜・日曜の列(ヘッダー・時間帯グリッドとも)を色分けする。FullCalendarは
        # 曜日ごとにfc-day-sat/fc-day-sunクラスを自動付与するため、それを利用する。
        # ただし当日がその曜日の場合はFullCalendar既定の「本日」強調(黄色)を優先させる
        ui.add_css(
            ".fc .fc-day-sat:not(.fc-day-today) { background-color: rgba(173, 216, 230, 0.35); }"
            ".fc .fc-day-sun:not(.fc-day-today) { background-color: rgba(255, 182, 193, 0.35); }"
        )
        # 祝日は日付ごとの背景イベント(display: background)として重ねて描画する。
        # 土曜・日曜の背景色より上にレイヤーされるため、既定の不透明度(0.3)のままだと
        # 下の色と混ざって薄まってしまう。祝日の緑を優先して見せたいため、不透明度を
        # 上げた専用のrgba値で塗りつぶす(fc-bg-event既定のopacity変数は使わずopacity: 1で固定)
        ui.add_css(".fc .fc-bg-event.holiday-bg { background-color: rgba(74, 222, 128, 0.55); opacity: 1; }")
        # ネイティブウィンドウ(main.pyのwindow_size=(620, 720))に収まるよう、
        # 他のダイアログ(最大w-[36rem])と同程度の幅に抑える
        with ui.dialog() as self.dialog, ui.card().classes("w-[36rem] gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("実行履歴(カレンダー)").classes("text-lg font-bold")
                with ui.row().classes("items-center gap-2"):
                    ui.button(icon="event_available", on_click=self._on_refresh_holidays).props(
                        "flat dense round"
                    ).tooltip("祝日データを確認・更新")
                    ui.toggle(
                        _WEEK_START_LABELS,
                        value=self._week_start,
                        on_change=self._on_week_start_toggle,
                    ).props("dense")
            # FullCalendar自体はダークモードに対応していないため、アプリのテーマに関わらず
            # 白背景・黒文字で表示する(ダーク時に一部要素だけ白背景が透けて見える崩れを防ぐ)
            with ui.element("div").classes("w-full rounded p-2 bg-white text-black"):
                self._calendar = FullCalendar(
                    {
                        "initialView": "timeGridWeek",
                        "headerToolbar": {
                            "left": "title",
                            "right": "timeGridDay,timeGridWeek,dayGridMonth prev,next today",
                        },
                        "buttonText": {"today": "今日", "day": "当日", "week": "週", "month": "月"},
                        # 月表示の日付・週表示の曜日ヘッダーをクリックすると、その日の
                        # 当日表示(timeGridDay)に切り替わるFullCalendar標準機能を有効化する
                        "navLinks": True,
                        # ブロック内はタスク名のみ表示し、開始・終了・経過時間はホバー時の
                        # ツールチップ(fullcalendar.jsのeventDidMount参照)で確認する
                        "displayEventTime": False,
                        "allDaySlot": False,
                        "height": "auto",
                        "firstDay": _first_day(self._week_start),
                        "events": [],
                    },
                    on_click=self._on_event_click,
                ).classes("w-full")
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def open(self) -> None:
        # ダイアログが実際に表示され幅が確定してからカレンダーを構築させたいため、
        # 先にダイアログを開く(on_open側の詳細はfullcalendar.js参照)
        self.dialog.open()
        self.refresh()
        self._calendar.run_method("on_open")

    def refresh(self) -> None:
        events = self._calendar.events
        events.clear()
        events.extend(self._build_events())
        events.extend(self._build_holiday_events())
        self._calendar.update()
        self._calendar.run_method("set_holidays", self._holiday_name_map())

    def _on_week_start_toggle(self, e: ValueChangeEventArguments[WeekStart]) -> None:
        self._week_start = e.value
        self._calendar.run_method("set_option", "firstDay", _first_day(self._week_start))
        self._on_week_start_change(self._week_start)

    def _on_refresh_holidays(self) -> None:
        if self._refresh_holidays():
            ui.notify(f"祝日データを更新しました({len(self._holidays)}件)")
            self.refresh()
        else:
            ui.notify("祝日データの取得に失敗しました。ネットワーク接続を確認してください", type="negative")

    def _build_holiday_events(self) -> list[dict[str, Any]]:
        return [
            {"start": holiday_date.isoformat(), "display": "background", "classNames": ["holiday-bg"]}
            for holiday_date in self._holidays
        ]

    def _holiday_name_map(self) -> dict[str, str]:
        return {holiday_date.isoformat(): name for holiday_date, name in self._holidays.items()}

    def _build_events(self) -> list[dict[str, Any]]:
        now = datetime.now()
        events: list[dict[str, Any]] = []
        for record in self._service.records:
            category = self._service.category_for_item(record.item_id)
            end = record.end_time or now
            start_label = record.start_time.strftime("%H:%M:%S")
            end_label = end.strftime("%H:%M:%S") if record.end_time else "実行中"
            elapsed_label = format_duration(record.elapsed_seconds(now))
            events.append(
                {
                    "id": record.id,
                    "title": record.item_name,
                    "start": record.start_time.isoformat(),
                    "end": end.isoformat(),
                    "color": category.color if category is not None else _UNCATEGORIZED_COLOR,
                    "extendedProps": {
                        "tooltip": f"開始 {start_label} / 終了 {end_label} / 経過 {elapsed_label}",
                    },
                }
            )
        return events

    def _on_event_click(self, e: GenericEventArguments) -> None:
        record_id = e.args.get("info", {}).get("event", {}).get("id")
        if record_id:
            self._open_record_edit_dialog(record_id)
