from __future__ import annotations

from collections.abc import Callable

from nicegui import ui
from nicegui.events import KeyEventArguments

from todoapp.domain.service import TodoService
from todoapp.ui.app_state import AppState


class KeyboardController:
    def __init__(
        self,
        service: TodoService,
        state: AppState,
        *,
        is_dialog_open: Callable[[], bool],
        is_log_open: Callable[[], bool],
        open_edit_dialog: Callable[[str], None],
        open_log_dialog: Callable[[], None],
        open_record_edit_dialog: Callable[[str], None],
        refresh_all: Callable[[], None],
    ) -> None:
        self._service = service
        self._state = state
        self._is_dialog_open = is_dialog_open
        self._is_log_open = is_log_open
        self._open_edit_dialog = open_edit_dialog
        self._open_log_dialog = open_log_dialog
        self._open_record_edit_dialog = open_record_edit_dialog
        self._refresh_all = refresh_all

    def build(self) -> None:
        ui.keyboard(on_key=self._on_key)

    def _on_key(self, e: KeyEventArguments) -> None:
        if not e.action.keydown or e.action.repeat:
            return

        if e.key.escape:
            if not self._is_dialog_open():
                self._state.toggle_screen()
                self._refresh_all()
            return

        item_id = self._state.selected_item_id

        if e.key.enter:
            if item_id is not None:
                self._service.toggle_execution(item_id)
                self._refresh_all()
            return

        if e.key == "e":
            if self._is_log_open() and self._state.selected_record_id is not None:
                self._open_record_edit_dialog(self._state.selected_record_id)
            elif item_id is not None:
                self._open_edit_dialog(item_id)
        elif e.key == "c" and item_id is not None:
            self._service.cancel_running(item_id)
            self._refresh_all()
        elif e.key == "l":
            self._open_log_dialog()
