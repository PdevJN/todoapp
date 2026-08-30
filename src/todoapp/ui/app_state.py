from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Screen(Enum):
    MAIN = "main"
    LIST = "list"


@dataclass
class AppState:
    screen: Screen = Screen.MAIN
    selected_item_id: str | None = None
    selected_record_id: str | None = None

    def select(self, item_id: str | None) -> None:
        self.selected_item_id = item_id

    def select_record(self, record_id: str | None) -> None:
        self.selected_record_id = record_id

    def toggle_screen(self) -> None:
        self.screen = Screen.LIST if self.screen is Screen.MAIN else Screen.MAIN
