from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from todoapp.domain.models import (
    LINK_TEMPLATE_NAME_MAX_LENGTH,
    LINK_URL_MAX_LENGTH,
    LinkTemplate,
    validate_link_template_fields,
)
from todoapp.domain.service import TodoService
from todoapp.ui.confirm_dialog import ConfirmDialog
from todoapp.ui.dialog_base import DialogMixin


class LinkTemplateDialog(DialogMixin):
    """リンクテンプレートの一覧と、追加・編集・削除。"""

    def __init__(self, service: TodoService, refresh_all: Callable[[], None], confirm_dialog: ConfirmDialog) -> None:
        self._service = service
        self._refresh_all = refresh_all
        self._confirm_dialog = confirm_dialog
        self._editing_id: str | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[36rem] gap-2"):
            ui.label("リンクテンプレート").classes("text-lg font-bold")
            self._list = ui.column().classes("w-full gap-1")
            ui.separator()
            self._name_input = (
                ui.input(label="テンプレート名")
                .props(f"maxlength={LINK_TEMPLATE_NAME_MAX_LENGTH}")
                .classes("w-full")
            )
            self._url_input = (
                ui.input(label="URL雛形", placeholder="https://example.com/{project}/issues/{id}")
                .props(f"maxlength={LINK_URL_MAX_LENGTH}")
                .classes("w-full")
            )
            ui.label("{名前}の部分を、アイテムのリンクで入力した値に置き換えます(名前は半角英数字と _、5個まで)").classes(
                "text-xs text-gray-500"
            )
            with ui.row().classes("w-full justify-end gap-2"):
                self._cancel_button = ui.button("編集をやめる", on_click=self._reset_form).props("flat")
                self._submit_button = ui.button("テンプレートを追加", on_click=self._submit)
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")
        self._reset_form()
        self.refresh()

    def open(self) -> None:
        self._reset_form()
        self.refresh()
        self.dialog.open()

    def refresh(self) -> None:
        self._list.clear()
        with self._list:
            if not self._service.link_templates:
                ui.label("テンプレートはまだありません").classes("text-gray-400 italic")
            for template in self._service.link_templates:
                with ui.row().classes("w-full items-center no-wrap gap-2"):
                    with ui.column().classes("flex-grow gap-0"):
                        ui.label(template.name).classes("font-medium")
                        ui.label(template.url_template).classes("text-xs text-gray-500 break-all")
                    ui.button(icon="edit", on_click=lambda t=template: self._start_edit(t)).props("flat dense round")
                    ui.button(icon="delete", on_click=lambda t=template: self._delete(t)).props(
                        "flat dense round color=negative"
                    )

    def _reset_form(self) -> None:
        self._editing_id = None
        self._name_input.value = ""
        self._url_input.value = ""
        self._submit_button.set_text("テンプレートを追加")
        self._cancel_button.set_visibility(False)

    def _start_edit(self, template: LinkTemplate) -> None:
        self._editing_id = template.id
        self._name_input.value = template.name
        self._url_input.value = template.url_template
        self._submit_button.set_text("テンプレートを更新")
        self._cancel_button.set_visibility(True)

    def _submit(self) -> None:
        name = (self._name_input.value or "").strip()
        url_template = (self._url_input.value or "").strip()
        error = validate_link_template_fields(name, url_template)
        if error is not None:
            ui.notify(error, type="warning")
            return
        if self._editing_id is None:
            self._service.add_link_template(name, url_template)
        else:
            self._service.edit_link_template(self._editing_id, name=name, url_template=url_template)
        self._reset_form()
        self._refresh_all()

    def _delete(self, template: LinkTemplate) -> None:
        count = self._service.linked_link_count([template.id])

        def do_delete() -> None:
            self._service.delete_link_templates([template.id])
            if self._editing_id == template.id:
                self._reset_form()
            self._refresh_all()

        if count > 0:
            self._confirm_dialog.open(
                f"このテンプレートを使うリンクが{count}件あり、削除するとそのリンクも削除されます。削除しますか?",
                do_delete,
            )
        else:
            do_delete()
