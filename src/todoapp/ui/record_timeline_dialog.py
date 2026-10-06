from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from nicegui import ui
from nicegui.events import GenericEventArguments

from todoapp.domain.models import ExecutionRecord
from todoapp.domain.record_layout import Interval, snap_move, snap_resize
from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin
from todoapp.ui.formatting import format_duration
from todoapp.ui.vendor.fullcalendar.fullcalendar import FullCalendar

_UNCATEGORIZED_COLOR = "#9e9e9e"
_OTHER_RECORD_COLOR = "#cfd8dc"
_SCROLL_MARGIN = timedelta(hours=1)


class RecordTimelineDialog(DialogMixin):
    """1件の実行記録を、当日の日表示カレンダー上でドラッグ&ドロップして編集するダイアログ。

    バーの移動・上下端のリサイズは1分単位で、秒は切り捨てる。同日の他の記録と重なる場合は
    その境界へ密着させる。変更は`保存`を押すまでは記録に反映しない。
    """

    def __init__(self, service: TodoService, refresh_all: Callable[[], None]) -> None:
        self._service = service
        self._refresh_all = refresh_all
        self._record: ExecutionRecord | None = None
        self._start = datetime.min
        self._end = datetime.min
        self._others: list[Interval] = []

    def build(self) -> None:
        # ネイティブウィンドウ(main.pyのwindow_size=(620, 720))に収まるよう、他のダイアログと同程度の幅・高さに抑える
        with ui.dialog() as self.dialog, ui.card().classes("w-[36rem] gap-2"):
            ui.label("実行記録の編集(カレンダー)").classes("text-lg font-bold")
            self._summary_label = ui.label().classes("text-sm text-gray-500 font-mono")
            # FullCalendar自体はダークモードに対応していないため、アプリのテーマに関わらず白背景・黒文字で表示する
            with ui.element("div").classes("w-full rounded p-2 bg-white text-black"):
                self._calendar = FullCalendar(
                    {
                        "initialView": "timeGridDay",
                        # lib/ja.global.min.js(fullcalendar.jsで読み込み)の日本語locale
                        "locale": "ja",
                        "headerToolbar": False,
                        "allDaySlot": False,
                        "displayEventTime": False,
                        "height": 480,
                        "snapDuration": "00:01:00",
                        "slotDuration": "00:15:00",
                        "slotLabelInterval": "01:00:00",
                        "nowIndicator": False,
                        "editable": False,
                        "events": [],
                    },
                    on_change=self._on_change,
                ).classes("w-full")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                ui.button("保存", on_click=self._save)

    def open_for(self, record_id: str) -> None:
        record = next((r for r in self._service.records if r.id == record_id), None)
        if record is None or record.end_time is None:
            return
        self._record = record
        self._start = record.start_time
        self._end = record.end_time
        day = record.start_time.date()
        now = datetime.now()
        self._others = [
            (other.start_time, other.end_time or now)
            for other in self._service.today_records(day)
            if other.id != record.id
        ]
        self._calendar.props["options"]["initialDate"] = day.isoformat()
        self._calendar.props["options"]["scrollTime"] = _scroll_time(self._start)
        # ダイアログが実際に表示され幅が確定してからカレンダーを構築させるため、先に開く(CalendarView.openと同じ)
        self.dialog.open()
        self._refresh_calendar()
        self._calendar.run_method("on_open")

    def _refresh_calendar(self) -> None:
        if self._record is None:
            return
        events = self._calendar.events
        events.clear()
        events.extend(self._build_events(self._record))
        self._calendar.update()
        self._summary_label.set_text(
            f"{self._record.item_name}  開始 {self._start:%H:%M:%S} / 終了 {self._end:%H:%M:%S}"
            f" / 経過 {format_duration((self._end - self._start).total_seconds())}"
        )

    def _build_events(self, record: ExecutionRecord) -> list[dict[str, Any]]:
        now = datetime.now()
        events: list[dict[str, Any]] = []
        for other in self._service.today_records(record.start_time.date()):
            if other.id == record.id:
                continue
            events.append(
                {
                    "id": other.id,
                    "title": other.item_name,
                    "start": other.start_time.isoformat(),
                    "end": (other.end_time or now).isoformat(),
                    "color": _OTHER_RECORD_COLOR,
                    "textColor": "#455a64",
                    "editable": False,
                }
            )
        category = self._service.category_for_item(record.item_id)
        events.append(
            {
                "id": record.id,
                "title": record.item_name,
                "start": self._start.isoformat(),
                "end": self._end.isoformat(),
                "color": category.color if category is not None else _UNCATEGORIZED_COLOR,
                "editable": True,
            }
        )
        return events

    def _on_change(self, e: GenericEventArguments) -> None:
        if self._record is None or e.args.get("id") != self._record.id:
            return
        day = self._record.start_time.date()
        start = datetime.fromisoformat(e.args["start"])
        end = datetime.fromisoformat(e.args["end"])
        if e.args["kind"] == "resize":
            if e.args["edge"] == "start":
                result = snap_resize("start", start, self._end, self._others, day)
            else:
                result = snap_resize("end", end, self._start, self._others, day)
        else:
            result = snap_move(start, end, self._others, day)
        if result is None:
            ui.notify("その位置には配置できません", type="warning")
            return
        self._start, self._end = result
        self._refresh_calendar()

    def _save(self) -> None:
        if self._record is None:
            return
        self._service.edit_record(self._record.id, start_time=self._start, end_time=self._end)
        self.dialog.close()
        self._refresh_all()


def _scroll_time(start: datetime) -> str:
    """対象のバーが見える位置までスクロールするための、表示開始時刻(HH:MM:SS)。"""
    top = max(start - _SCROLL_MARGIN, start.replace(hour=0, minute=0, second=0, microsecond=0))
    return f"{top:%H:%M:%S}"
