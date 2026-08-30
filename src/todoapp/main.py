from __future__ import annotations

from nicegui import ui

from todoapp.domain.service import TodoService
from todoapp.repository.json_repository import JsonTodoRepository
from todoapp.ui.app_state import AppState, Screen
from todoapp.ui.category_edit_dialog import CategoryEditDialog
from todoapp.ui.category_list_dialog import CategoryListDialog
from todoapp.ui.category_pick_dialog import CategoryPickDialog
from todoapp.ui.category_summary_dialog import CategorySummaryDialog
from todoapp.ui.confirm_dialog import ConfirmDialog
from todoapp.ui.edit_dialog import EditDialog
from todoapp.ui.keyboard import KeyboardController
from todoapp.ui.list_view import ListView
from todoapp.ui.log_view import LogView
from todoapp.ui.main_view import MainView
from todoapp.ui.record_edit_dialog import RecordEditDialog


@ui.page("/")
def build_app() -> None:
    repository = JsonTodoRepository()
    service = TodoService(repository)
    state = AppState()

    # ネイティブブラウザのCmd/Ctrl+A(ページ全体のテキスト選択)を抑止し、
    # 独自の全選択キー操作と見た目が競合しないようにする
    ui.add_body_html(
        "<script>document.addEventListener('keydown', (e) => {"
        "if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'a') e.preventDefault();"
        "});</script>"
    )

    def refresh_all() -> None:
        main_view.render.refresh()
        list_view.render.refresh()
        log_view.refresh()
        category_list_dialog.refresh()
        category_summary_dialog.refresh()

    def delete_selected_items() -> None:
        ids = set(state.selected_item_ids)
        if not ids:
            return

        def do_delete() -> None:
            service.delete_items(ids)
            state.select_items(set())
            refresh_all()

        if len(ids) >= 2:
            confirm_dialog.open(f"選択した{len(ids)}件のアイテムを削除します。よろしいですか?", do_delete)
        else:
            do_delete()

    def delete_selected_records() -> None:
        ids = set(state.selected_record_ids)
        if not ids:
            return

        def do_delete() -> None:
            service.delete_records(ids)
            state.select_records(set())
            refresh_all()

        if len(ids) >= 2:
            confirm_dialog.open(f"選択した{len(ids)}件の記録を削除します。よろしいですか?", do_delete)
        else:
            do_delete()

    def delete_selected_categories() -> None:
        ids = set(state.selected_category_ids)
        if not ids:
            return
        linked_count = service.linked_item_count(ids)

        def do_delete() -> None:
            service.delete_categories(ids)
            state.select_categories(set())
            refresh_all()

        if len(ids) >= 2 or linked_count > 0:
            message = f"選択した{len(ids)}件のカテゴリを削除します。"
            if linked_count > 0:
                message += f"紐づくアイテムが{linked_count}件あり、削除すると「未定」に戻ります。"
            message += "削除しますか?"
            confirm_dialog.open(message, do_delete)
        else:
            do_delete()

    confirm_dialog = ConfirmDialog()
    category_list_dialog = CategoryListDialog(service, state)
    category_edit_dialog = CategoryEditDialog(service, refresh_all=refresh_all, confirm_dialog=confirm_dialog)
    category_summary_dialog = CategorySummaryDialog(service)
    category_pick_dialog = CategoryPickDialog(service, refresh_all=refresh_all)

    main_view = MainView(service, state, refresh_all=refresh_all, open_category_pick=category_pick_dialog.open_for)
    list_view = ListView(service, state)
    edit_dialog = EditDialog(service, refresh_all=refresh_all)
    log_view = LogView(service, state)
    record_edit_dialog = RecordEditDialog(service, refresh_all=refresh_all)

    main_root = main_view.build()
    list_root = list_view.build()
    edit_dialog.build()
    log_view.build()
    record_edit_dialog.build()
    category_list_dialog.build()
    category_edit_dialog.build()
    category_summary_dialog.build()
    category_pick_dialog.build()
    confirm_dialog.build()

    main_root.bind_visibility_from(state, "screen", backward=lambda s: s is Screen.MAIN)
    list_root.bind_visibility_from(state, "screen", backward=lambda s: s is Screen.LIST)

    keyboard = KeyboardController(
        service,
        state,
        is_dialog_open=lambda: (
            edit_dialog.is_open()
            or log_view.is_open()
            or record_edit_dialog.is_open()
            or category_list_dialog.is_open()
            or category_edit_dialog.is_open()
            or category_summary_dialog.is_open()
            or category_pick_dialog.is_open()
            or confirm_dialog.is_open()
        ),
        is_log_open=log_view.is_open,
        is_category_list_open=category_list_dialog.is_open,
        open_edit_dialog=edit_dialog.open_for,
        open_log_dialog=log_view.open,
        open_record_edit_dialog=record_edit_dialog.open_for,
        open_category_list=category_list_dialog.open,
        open_category_edit_dialog=category_edit_dialog.open_for,
        open_category_summary=category_summary_dialog.open,
        delete_selected_items=delete_selected_items,
        delete_selected_records=delete_selected_records,
        delete_selected_categories=delete_selected_categories,
        select_all_main_items=main_view.select_all,
        select_all_list_items=list_view.select_all,
        select_all_records=log_view.select_all,
        select_all_categories=category_list_dialog.select_all,
        is_main_select_all_active=main_view.is_select_all_active,
        clear_main_select_all=main_view.clear_select_all,
        has_list_selection=list_view.has_selection,
        clear_list_selection=list_view.clear_selection,
        has_category_selection=category_list_dialog.has_selection,
        clear_category_selection=category_list_dialog.clear_selection,
        close_category_list=category_list_dialog.close,
        refresh_all=refresh_all,
    )
    keyboard.build()


def main() -> None:
    ui.run(native=True, window_size=(620, 720), title="TODO", reload=False)


if __name__ == "__main__":
    main()
