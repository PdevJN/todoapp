from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from todoapp.domain.models import DoneFilter


class Screen(Enum):
    MAIN = "main"
    LIST = "list"


@dataclass
class AppState:
    screen: Screen = Screen.MAIN
    done_filter: DoneFilter = DoneFilter.ACTIVE
    selected_item_id: str | None = None
    selected_record_id: str | None = None
    selected_category_id: str | None = None
    selected_item_ids: set[str] = field(default_factory=set)
    selected_record_ids: set[str] = field(default_factory=set)
    selected_category_ids: set[str] = field(default_factory=set)

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
