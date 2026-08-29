from __future__ import annotations

from nicegui import ui

from todoapp.domain.service import TodoService
from todoapp.repository.json_repository import JsonTodoRepository
from todoapp.ui.app_state import AppState, Screen
from todoapp.ui.edit_dialog import EditDialog
from todoapp.ui.keyboard import KeyboardController
from todoapp.ui.list_view import ListView
from todoapp.ui.log_view import LogView
from todoapp.ui.main_view import MainView


@ui.page("/")
def build_app() -> None:
    repository = JsonTodoRepository()
    service = TodoService(repository)
    state = AppState()

    def refresh_all() -> None:
        main_view.render.refresh()
        list_view.render.refresh()

    main_view = MainView(service, state, refresh_all=refresh_all)
    list_view = ListView(service, state)
    edit_dialog = EditDialog(service, refresh_all=refresh_all)
    log_view = LogView(service)

    main_root = main_view.build()
    list_root = list_view.build()
    edit_dialog.build()
    log_view.build()

    main_root.bind_visibility_from(state, "screen", backward=lambda s: s is Screen.MAIN)
    list_root.bind_visibility_from(state, "screen", backward=lambda s: s is Screen.LIST)

    keyboard = KeyboardController(
        service,
        state,
        is_dialog_open=lambda: edit_dialog.is_open() or log_view.is_open(),
        open_edit_dialog=edit_dialog.open_for,
        open_log_dialog=log_view.open,
        refresh_all=refresh_all,
    )
    keyboard.build()


def main() -> None:
    ui.run(native=True, window_size=(480, 720), title="TODO", reload=False)


if __name__ == "__main__":
    main()
