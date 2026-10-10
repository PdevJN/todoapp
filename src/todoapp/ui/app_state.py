from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from todoapp.domain.models import DoneFilter


class Screen(Enum):
    MAIN = "main"
    LIST = "list"


@dataclass
class AppState:
    screen: Screen = Screen.MAIN
    done_filter: DoneFilter = DoneFilter.ACTIVE
    view_date: date = field(default_factory=date.today)  # メインパネルに表示する日(保存しない)
    today_seen: date = field(default_factory=date.today)  # 最後に確認した「今日」。日跨ぎの検知に使う
    selected_item_id: str | None = None
    selected_record_id: str | None = None
    selected_category_id: str | None = None
    selected_item_ids: set[str] = field(default_factory=set)
    selected_record_ids: set[str] = field(default_factory=set)
    selected_category_ids: set[str] = field(default_factory=set)

    @property
    def is_read_only_view(self) -> bool:
        """今日以外の日をメインパネルで表示している間は、実行・完了の操作を受け付けない。"""
        return self.screen is Screen.MAIN and self.view_date != date.today()

    def roll_over(self, today: date) -> bool:
        """日付が変わっていたら、今日を表示していた場合に限り新しい今日へ追従する。変わっていれば`True`。"""
        if today == self.today_seen:
            return False
        if self.view_date == self.today_seen:
            self.view_date = today
        self.today_seen = today
        return True

    def shift_view_date(self, days: int) -> None:
        self.view_date += timedelta(days=days)

    def select(self, item_id: str | None) -> None:
        self.selected_item_id = item_id

    def select_record(self, record_id: str | None) -> None:
        self.selected_record_id = record_id

    def select_category(self, category_id: str | None) -> None:
        self.selected_category_id = category_id

    def select_items(self, item_ids: set[str]) -> None:
        self.selected_item_ids = item_ids

    def select_records(self, record_ids: set[str]) -> None:
        self.selected_record_ids = record_ids

    def select_categories(self, category_ids: set[str]) -> None:
        self.selected_category_ids = category_ids

    def toggle_screen(self) -> None:
        self.screen = Screen.LIST if self.screen is Screen.MAIN else Screen.MAIN
