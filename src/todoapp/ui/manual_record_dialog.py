from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time

from nicegui import ui

from todoapp.domain.record_layout import fit_to_gap, snap_end_out, snap_start_out
from todoapp.domain.models import ITEM_NAME_MAX_LENGTH, UNCATEGORIZED_NAME, validate_manual_record
from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin


def parse_manual_record(day: str, start: str, end: str) -> tuple[datetime, datetime] | None:
    """入力欄の文字列(日付・HH:MM:SS)を開始・終了のdatetimeへ変換する。不正なら`None`。"""
    try:
        record_date = date.fromisoformat(day)
        return (
            datetime.combine(record_date, time.fromisoformat(start)),
            datetime.combine(record_date, time.fromisoformat(end)),
        )
    except ValueError:
        return None


class ManualRecordDialog(DialogMixin):
    """実行履歴に、アイテムを持たない記録を手動で追加するフォーム。"""

    def __init__(self, service: TodoService, refresh_all: Callable[[], None]) -> None:
        self._service = service
        self._refresh_all = refresh_all

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            ui.label("実行記録の追加").classes("text-lg font-bold")
            self._date_input = ui.input(label="日付").props("type=date dense").classes("w-full")
            self._category_select = ui.select({}, label="記録のカテゴリ").props("dense").classes("w-full")
            self._name_input = (
                ui.input(label="タスク名(省略するとカテゴリ名)")
                .props(f"maxlength={ITEM_NAME_MAX_LENGTH} dense")
                .classes("w-full")
            )
            self._start_input = ui.time_input(label="開始時刻").classes("w-full")
            self._start_input.picker.props("mask=HH:mm:ss with-seconds")
            self._bind_snap(self._start_input, snap_start_out)
            self._end_input = ui.time_input(label="終了時刻").classes("w-full")
            self._end_input.picker.props("mask=HH:mm:ss with-seconds")
            self._bind_snap(self._end_input, snap_end_out)
            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                ui.button("追加", on_click=self.submit)

    def open_for(self, day: date) -> None:
        """`day`を日付の初期値にしてフォームを開く。"""
        options: dict[str, str] = {"": UNCATEGORIZED_NAME}
        for category in self._service.selectable_categories():
            label = f"{category.name}({category.prj_code})" if category.prj_code else category.name
            options[category.id] = label
        self._category_select.set_options(options, value="")
        self._date_input.value = day.isoformat()
        self._name_input.value = ""
        self._start_input.value = ""
        self._end_input.value = ""
        self.dialog.open()

    def _others(self, day: date) -> list[tuple[datetime, datetime]]:
        now = datetime.now()
        return [(record.start_time, record.end_time or now) for record in self._service.today_records(day)]

    def _bind_snap(self, field: ui.time_input, snap: Callable[[datetime, list[tuple[datetime, datetime]]], datetime]) -> None:
        """時刻の確定(時計コントロールの選択・数字入力のEnter/フォーカス外れ)で補正する。

        `time_input`は画面側から来た変更を画面へ返さないため、変更ハンドラの中で値を書き換えても反映されない。
        そこで、ハンドラの処理が終わった後にタイマーで補正する。数字入力は1文字ごとには補正しない(入力中に値が変わるため)。
        """

        def schedule(_: object = None) -> None:
            ui.timer(0.05, lambda: self._snap_input(field, snap), once=True)

        field.on("blur", schedule)
        field.on("keydown.enter", schedule)
        field.picker.on("update:model-value", schedule)

    def _snap_input(self, field: ui.time_input, snap: Callable[[datetime, list[tuple[datetime, datetime]]], datetime]) -> None:
        """時刻の入力が既存の記録と重なっていたら、その記録の境界の時刻へ合わせる(入力した側だけ)。"""
        parsed = parse_manual_record(self._date_input.value, field.value, field.value)
        if parsed is None:
            return
        value = parsed[0]
        snapped = snap(value, self._others(value.date()))
        if snapped != value and snapped.date() == value.date():
            is_start = field is self._start_input
            other_field = self._end_input if is_start else self._start_input
            other = parse_manual_record(self._date_input.value, other_field.value, other_field.value)
            if other is not None:
                before = (value, other[0]) if is_start else (other[0], value)
                after = (snapped, other[0]) if is_start else (other[0], snapped)
                if before[0] < before[1] and after[0] >= after[1]:
                    # 開始・終了が同じ記録の中などで、補正すると逆転する場合は書き換えない(追加時に空きが無い旨を警告する)
                    ui.notify("この時間帯は既存の記録の中にあり、空きがありません", type="warning")
                    return
            field.value = snapped.strftime("%H:%M:%S")
            ui.notify(f"既存の記録と重なるため、{snapped:%H:%M:%S}に合わせました", type="info")

    def submit(self) -> bool:
        """入力を検証して記録を追加する。問題があれば警告を表示して追加せず、ダイアログは開いたままにする。"""
        parsed = parse_manual_record(self._date_input.value, self._start_input.value, self._end_input.value)
        if parsed is None:
            ui.notify("日付・開始時刻・終了時刻を正しく入力してください", type="warning")
            return False
        start, end = parsed
        name = self._name_input.value.strip()
        others = self._others(start.date())
        if start < end and start.date() == end.date() and any(s < end and start < e for s, e in others):
            fitted = fit_to_gap(start, end, others)
            if fitted is None:
                ui.notify("この時間帯に空きがありません(既存の記録と重なっています)", type="warning")
                return False
            if fitted != (start, end):
                self._start_input.value = fitted[0].strftime("%H:%M:%S")
                self._end_input.value = fitted[1].strftime("%H:%M:%S")
                ui.notify(
                    f"既存の記録と重なるため、{fitted[0]:%H:%M:%S}〜{fitted[1]:%H:%M:%S}の空き時間に補正しました。"
                    "内容を確認して、もう一度「追加」を押してください",
                    type="info",
                )
                return False
        error = validate_manual_record(name, start, end, others)
        if error is not None:
            ui.notify(error, type="warning")
            return False
        self._service.add_manual_record(self._category_select.value or None, name, start, end)
        self.dialog.close()
        self._refresh_all()
        return True
