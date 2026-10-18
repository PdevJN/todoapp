from __future__ import annotations

from dataclasses import dataclass, field

from nicegui import ui

from todoapp.domain.models import (
    LINK_NAME_MAX_LENGTH,
    LINK_URL_MAX_LENGTH,
    LINK_VALUE_MAX_LENGTH,
    ItemLink,
    LinkTemplate,
    template_placeholders,
    validate_item_link_fields,
)

NO_TEMPLATE_LABEL = "なし(URLを直接入力)"


@dataclass
class _LinkRow:
    link_id: str
    card: ui.element
    name_input: ui.input
    template_select: ui.select
    fields: ui.element
    url_text: str = ""
    values: dict[str, str] = field(default_factory=dict)  # 入力済みの値。テンプレートを切り替えても同名の項目へ引き継ぐ
    url_input: ui.input | None = None
    value_inputs: dict[str, ui.input] = field(default_factory=dict)


class LinkRowsEditor:
    """アイテム編集フォームのリンク欄。選んだテンプレートの置換項目ごとに入力欄を表示する。"""

    def __init__(self) -> None:
        self._templates: dict[str, LinkTemplate] = {}
        self._rows: list[_LinkRow] = []

    def build(self) -> None:
        ui.label("リンク").classes("text-gray-600")
        self._container = ui.column().classes("w-full gap-2")
        ui.button("リンクを追加", icon="add", on_click=lambda: self._add_row(ItemLink(name=""))).props("flat dense")

    def load(self, links: list[ItemLink], templates: list[LinkTemplate]) -> None:
        self._templates = {template.id: template for template in templates}
        self._rows = []
        self._container.clear()
        for link in links:
            self._add_row(link)

    def collect(self) -> list[ItemLink] | None:
        """入力中のリンクを検証して返す。問題があれば警告を表示して`None`を返す。"""
        links: list[ItemLink] = []
        for row in self._rows:
            template = self._templates.get(row.template_select.value)
            name = (row.name_input.value or "").strip()
            url = ""
            values: dict[str, str] = {}
            if template is None:
                url = ((row.url_input.value if row.url_input else "") or "").strip()
            else:
                values = {key: (inp.value or "").strip() for key, inp in row.value_inputs.items()}
            error = validate_item_link_fields(name, template, url, values)
            if error is not None:
                ui.notify(f"リンク「{name or '(表示名なし)'}」: {error}", type="warning")
                return None
            links.append(
                ItemLink(
                    id=row.link_id,
                    name=name,
                    template_id=template.id if template else None,
                    url=url,
                    values=values,
                )
            )
        return links

    def _add_row(self, link: ItemLink) -> None:
        options: dict[str | None, str] = {None: NO_TEMPLATE_LABEL}
        options.update({template_id: template.name for template_id, template in self._templates.items()})
        selected = link.template_id if link.template_id in options else None
        with self._container, ui.column().classes("w-full gap-1 p-2 border rounded") as card:
            with ui.row().classes("w-full items-center no-wrap"):
                name_input = (
                    ui.input(label="表示名", value=link.name)
                    .props(f"dense maxlength={LINK_NAME_MAX_LENGTH}")
                    .classes("flex-grow")
                )
                remove_button = ui.button(icon="delete").props("flat dense round color=negative")
            template_select = ui.select(options, label="テンプレート", value=selected).props("dense").classes("w-full")
            fields = ui.column().classes("w-full gap-1")
        row = _LinkRow(link.id, card, name_input, template_select, fields, url_text=link.url, values=dict(link.values))
        self._rows.append(row)
        remove_button.on_click(lambda r=row: self._remove_row(r))
        template_select.on_value_change(lambda _e, r=row: self._rebuild_fields(r))
        self._rebuild_fields(row)

    def _remove_row(self, row: _LinkRow) -> None:
        self._rows.remove(row)
        row.card.delete()

    def _rebuild_fields(self, row: _LinkRow) -> None:
        if row.url_input is not None:
            row.url_text = row.url_input.value or ""
        row.values.update({key: inp.value or "" for key, inp in row.value_inputs.items()})
        row.fields.clear()
        row.url_input = None
        row.value_inputs = {}
        template = self._templates.get(row.template_select.value)
        with row.fields:
            if template is None:
                row.url_input = (
                    ui.input(label="URL", value=row.url_text)
                    .props(f"dense maxlength={LINK_URL_MAX_LENGTH}")
                    .classes("w-full")
                )
                return
            for key in template_placeholders(template.url_template):
                row.value_inputs[key] = (
                    ui.input(label=key, value=row.values.get(key, ""))
                    .props(f"dense maxlength={LINK_VALUE_MAX_LENGTH}")
                    .classes("w-full")
                )
