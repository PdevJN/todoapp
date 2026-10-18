from __future__ import annotations

import webbrowser
from collections.abc import Callable, Iterable
from typing import NamedTuple

from nicegui import ui

from todoapp.domain.models import LinkTemplate, TodoItem, resolve_link_url

_LABEL_MAX_LENGTH = 60
UNOPENABLE_MESSAGE = "リンクを開けません(未入力の項目があるか、テンプレートが削除されています)"


class LinkEntry(NamedTuple):
    link_id: str
    name: str
    url: str | None  # 開けない場合はNone

    @property
    def label(self) -> str:
        """一覧に出す名前。表示名を省略した場合は、組み立てたURL(長い場合は省略)を使う。"""
        if self.url is None:
            return f"{self.name}(未入力)" if self.name else "(未入力)"
        if self.name:
            return self.name
        return self.url if len(self.url) <= _LABEL_MAX_LENGTH else self.url[: _LABEL_MAX_LENGTH - 1] + "…"


def build_link_entries(item: TodoItem, templates: Iterable[LinkTemplate]) -> list[LinkEntry]:
    registered = list(templates)
    return [LinkEntry(link.id, link.name, resolve_link_url(link, registered)) for link in item.links]


def open_link_url(url: str | None, opener: Callable[[str], object]) -> bool:
    if url is None:
        return False
    opener(url)
    return True


def open_link(url: str | None) -> None:
    # ネイティブウィンドウ(WKWebView)では新規タブ遷移が動かないため、サーバー側で既定のブラウザを開く
    if not open_link_url(url, webbrowser.open):
        ui.notify(UNOPENABLE_MESSAGE, type="warning")


def render_link_button(entries: list[LinkEntry]) -> None:
    """アイテム名の隣のリンクアイコン。1件はクリックで直接、2件以上はメニューで選んで開く。"""
    if not entries:
        return
    # 行のクリック(選択)・ダブルクリック(実行)へ伝えないよう、ラッパーで止める
    wrapper = ui.element("div").classes("inline-flex")
    wrapper.on("click.stop", lambda: None)
    wrapper.on("dblclick.stop", lambda: None)
    with wrapper:
        if len(entries) == 1:
            button = ui.button(icon="link", on_click=lambda u=entries[0].url: open_link(u))
        else:
            button = ui.button(icon="link")
            with button, ui.menu():
                for entry in entries:
                    ui.menu_item(entry.label, on_click=lambda u=entry.url: open_link(u)).props("dense").classes(
                        "text-sm"
                    )
        button.props("flat dense round size=sm")
        button.tooltip(" / ".join(entry.label for entry in entries))
