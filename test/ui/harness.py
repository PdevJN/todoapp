"""画面テストの共通部品(保存先の用意・データ作成・グローバルキー操作の擬似入力)。"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from todoapp.domain.models import AppData, Category, ExecutionRecord, ScheduleType, TodoItem
from todoapp.repository.json_repository import JsonTodoRepository

_KEY_CODES = {"Escape": "Escape", "Enter": "Enter", "Delete": "Delete", "Backspace": "Backspace"} | {
    name: name for name in ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight")
}


@dataclass
class AppEnv:
    """画面テストの保存先。`seed`で起動前のデータを用意し、`todos`で操作後の保存内容を確認する。"""

    directory: Path

    @property
    def todos_repository(self) -> JsonTodoRepository:
        return JsonTodoRepository(self.directory / "todos.json")

    def seed(
        self,
        items: list[TodoItem] | None = None,
        records: list[ExecutionRecord] | None = None,
        categories: list[Category] | None = None,
    ) -> None:
        self.todos_repository.save(AppData(items=items or [], records=records or [], categories=categories or []))

    def todos(self) -> AppData:
        return self.todos_repository.load()


def make_item(name: str, schedule_type: ScheduleType = ScheduleType.DAILY, **kwargs: Any) -> TodoItem:
    kwargs.setdefault("anchor_date", date.today())
    return TodoItem(name=name, schedule_type=schedule_type, **kwargs)


def make_record(item: TodoItem, start: datetime, end: datetime | None) -> ExecutionRecord:
    return ExecutionRecord(item_id=item.id, item_name=item.name, start_time=start, end_time=end)


async def press(user: User, key: str, *, shift: bool = False, ctrl: bool = False, meta: bool = False) -> None:
    """`ui.keyboard`(グローバルキー)へ、キーダウンを擬似的に送る。"""
    code = _KEY_CODES.get(key, f"Key{key.upper()}" if len(key) == 1 else key)
    user.find(kind=ui.keyboard).trigger(
        "key",
        {
            "action": "keydown",
            "repeat": False,
            "altKey": False,
            "ctrlKey": ctrl,
            "metaKey": meta,
            "shiftKey": shift,
            "key": key,
            "code": code,
            "location": 0,
        },
    )


def _row_of(user: User, text: str) -> ui.element:
    """テキストを持つ要素から、クリック処理(`click`リスナー)を持つ最も近い祖先の行を返す。

    同じ名前のラベルが複数ある(実行中は画面下部のフローティング表示にも出る)ため、
    一致した全ての要素を調べ、クリックできる行を持つものを選ぶ。
    """
    candidates: list[ui.element] = []
    for label in user.find(text).elements:
        element: ui.element | None = label
        while element is not None:
            if any(listener.type == "click" for listener in element._event_listeners.values()):  # noqa: SLF001
                if is_displayed(element):
                    candidates.append(element)
                break
            element = element.parent_slot.parent if element.parent_slot else None
    if not candidates:
        raise AssertionError(f"クリックできる行が見つかりません: {text}")
    return min(candidates, key=lambda e: e.id)


def click_row(user: User, text: str, *, ctrl: bool = False, shift: bool = False) -> None:
    """行をクリックして選択する(子ラベルではなく行へ`click`を送る。ブラウザのバブリング相当)。"""
    row = _row_of(user, text)
    UserInteraction(user, {row}, None).trigger("click", {"ctrlKey": ctrl, "metaKey": False, "shiftKey": shift})


def double_click_row(user: User, text: str) -> None:
    row = _row_of(user, text)
    UserInteraction(user, {row}, None).trigger("dblclick")


# --- 表示の判定 ---------------------------------------------------------------------------
# NiceGUIの`user.should_see`は、閉じているダイアログの中身や、非表示の祖先の下にある要素も
# 「見える」と判定する(要素自身の`visible`しか見ない)。そのため、実際に画面へ表示されているかは
# 祖先をたどって、閉じたダイアログ・非表示の要素が無いことまで確かめる。


def is_displayed(element: ui.element) -> bool:
    node: ui.element | None = element
    while node is not None:
        if not node.visible:
            return False
        if isinstance(node, ui.dialog) and not node.value:
            return False
        node = node.parent_slot.parent if node.parent_slot else None
    return True


def displayed_elements(user: User, text: str) -> list[ui.element]:
    try:
        elements = user.find(text).elements
    except AssertionError:  # 該当する要素がそもそも無い場合、`find`は例外を出す
        return []
    return [element for element in elements if is_displayed(element)]


async def _wait_until(condition: Callable[[], bool], message: str, timeout: float = 2.0) -> None:
    # 画面の更新(refreshableの再描画・バインディング)は非同期のため、少しの間は待って確かめる
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(message)
        await asyncio.sleep(0.02)


async def shows(user: User, text: str) -> None:
    await _wait_until(lambda: bool(displayed_elements(user, text)), f"画面に表示されていません: {text}")


async def hides(user: User, text: str) -> None:
    await _wait_until(lambda: not displayed_elements(user, text), f"画面に表示されたままです: {text}")


def click_displayed(user: User, text: str) -> None:
    """画面に表示されている要素だけを対象にクリックする(複数のダイアログに同名のボタンがあるため)。"""
    elements = displayed_elements(user, text)
    assert elements, f"クリックできる表示中の要素がありません: {text}"
    UserInteraction(user, {min(elements, key=lambda e: e.id)}, text).click()


def select_toggle(user: User, option_label: str) -> None:
    """`ui.toggle`の選択肢を選ぶ(`user`のクリックはトグルに対応していないため、値を直接設定する)。"""
    for toggle in user.find(kind=ui.toggle).elements:
        options = toggle.options
        if is_displayed(toggle) and isinstance(options, dict) and option_label in options.values():
            assert user.client is not None
            with user.client:
                toggle.value = next(key for key, label in options.items() if label == option_label)
            return
    raise AssertionError(f"トグルの選択肢が見つかりません: {option_label}")


def input_value(interaction: UserInteraction[Any]) -> str:
    [element] = interaction.elements
    assert isinstance(element, ui.input)
    return str(element.value)
