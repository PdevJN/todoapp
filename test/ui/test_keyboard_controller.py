"""`KeyboardController`のキー振り分けを、画面状態ごとの判断表で網羅する。

NiceGUIの画面は立ち上げず、本物の`KeyEventArguments`を`_on_key`へ直接渡して検証する。
"""

import inspect
from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from nicegui.events import KeyboardAction, KeyboardKey, KeyboardModifiers, KeyEventArguments

from todoapp.ui.app_state import AppState, Screen
from todoapp.ui.keyboard import KeyboardController

_CODES = {"ArrowUp": "ArrowUp", "ArrowDown": "ArrowDown", "ArrowLeft": "ArrowLeft", "ArrowRight": "ArrowRight"}

# 引数が無い状態問い合わせ(is_*/has_*)は既定でFalseを返す
_PREDICATES = {
    "is_dialog_open",
    "is_log_open",
    "is_category_list_open",
    "is_main_select_all_active",
    "has_list_selection",
    "has_category_selection",
}


class Harness:
    def __init__(self) -> None:
        self.service = MagicMock()
        self.state = AppState()
        parameters = inspect.signature(KeyboardController.__init__).parameters
        callback_names = [name for name in parameters if name not in ("self", "service", "state")]
        self.cb: dict[str, MagicMock] = {
            name: MagicMock(return_value=False if name in _PREDICATES else None) for name in callback_names
        }
        self.controller = KeyboardController(self.service, self.state, **self.cb)

    def press(
        self,
        name: str,
        *,
        shift: bool = False,
        ctrl: bool = False,
        meta: bool = False,
        keydown: bool = True,
        repeat: bool = False,
    ) -> None:
        event = KeyEventArguments(
            sender=MagicMock(),
            client=MagicMock(),
            action=KeyboardAction(keydown=keydown, keyup=not keydown, repeat=repeat),
            key=KeyboardKey(name=name, code=_CODES.get(name, name), location=0),
            modifiers=KeyboardModifiers(alt=False, ctrl=ctrl, meta=meta, shift=shift),
        )
        self.controller._on_key(event)  # noqa: SLF001

    def set_true(self, *names: str) -> None:
        for name in names:
            self.cb[name].return_value = True

    def called(self, name: str) -> bool:
        return self.cb[name].called


@pytest.fixture
def h() -> Harness:
    return Harness()


# --- 共通: キーダウン以外は無視 -----------------------------------------------------------


@pytest.mark.parametrize(("keydown", "repeat"), [(False, False), (True, True)])
def test_keyup_and_repeated_keydown_are_ignored(h: Harness, keydown: bool, repeat: bool) -> None:
    h.state.select("a")
    h.press("Enter", keydown=keydown, repeat=repeat)
    h.press("l", keydown=keydown, repeat=repeat)

    h.service.toggle_execution.assert_not_called()
    assert not h.called("open_log_dialog")


# --- Escape -------------------------------------------------------------------------------


def test_escape_with_category_selection_clears_it_and_refreshes(h: Harness) -> None:
    h.set_true("is_category_list_open", "has_category_selection")
    h.press("Escape")

    assert h.called("clear_category_selection") and h.called("refresh_all")
    assert not h.called("close_category_list")


def test_escape_in_category_list_without_selection_closes_it(h: Harness) -> None:
    h.set_true("is_category_list_open")
    h.press("Escape")

    assert h.called("close_category_list")
    assert h.state.screen is Screen.MAIN


def test_escape_with_other_dialog_open_does_nothing(h: Harness) -> None:
    h.set_true("is_dialog_open")
    h.state.select("a")
    h.press("Escape")

    assert h.state.selected_item_id == "a"
    assert h.state.screen is Screen.MAIN
    assert not h.called("refresh_all")


def test_escape_on_main_with_select_all_clears_select_all_only(h: Harness) -> None:
    h.set_true("is_main_select_all_active")
    h.state.select("a")
    h.press("Escape")

    assert h.called("clear_main_select_all")
    assert h.state.selected_item_id == "a"


@pytest.mark.parametrize(("item_id", "item_ids"), [("a", set()), (None, {"a", "b"}), ("a", {"a", "b"})])
def test_escape_on_main_with_selection_clears_selection_and_stays(
    h: Harness, item_id: str | None, item_ids: set[str]
) -> None:
    h.state.select(item_id)
    h.state.select_items(item_ids)
    h.press("Escape")

    assert h.state.selected_item_id is None
    assert h.state.selected_item_ids == set()
    assert h.state.screen is Screen.MAIN
    assert h.called("refresh_all")


def test_escape_on_main_without_selection_switches_to_list(h: Harness) -> None:
    h.press("Escape")

    assert h.state.screen is Screen.LIST
    assert h.called("refresh_all")


def test_escape_on_list_with_selection_clears_it_and_stays(h: Harness) -> None:
    h.state.screen = Screen.LIST
    h.set_true("has_list_selection")
    h.press("Escape")

    assert h.called("clear_list_selection")
    assert h.state.screen is Screen.LIST


def test_escape_on_list_without_selection_switches_back_to_main(h: Harness) -> None:
    h.state.screen = Screen.LIST
    h.press("Escape")

    assert h.state.screen is Screen.MAIN


# --- 上下移動(↑↓・j/k) -----------------------------------------------------------------


@pytest.mark.parametrize(("key", "delta"), [("ArrowDown", 1), ("j", 1), ("ArrowUp", -1), ("k", -1)])
def test_move_keys_route_to_main_selection_by_default(h: Harness, key: str, delta: int) -> None:
    h.press(key)

    h.cb["move_main_selection"].assert_called_once_with(delta)


@pytest.mark.parametrize(
    ("flags", "screen", "target"),
    [
        (("is_category_list_open",), Screen.MAIN, "move_category_selection"),
        (("is_log_open",), Screen.MAIN, "move_log_selection"),
        ((), Screen.LIST, "move_list_selection"),
        # 優先順位: カテゴリ一覧 > 作業ログ(両方開いている場合)
        (("is_category_list_open", "is_log_open"), Screen.MAIN, "move_category_selection"),
        # 作業ログが開いていれば、ダイアログ判定より優先される
        (("is_log_open", "is_dialog_open"), Screen.MAIN, "move_log_selection"),
    ],
)
def test_move_keys_route_by_open_surface(h: Harness, flags: tuple[str, ...], screen: Screen, target: str) -> None:
    h.state.screen = screen
    h.set_true(*flags)
    h.press("ArrowDown")

    h.cb[target].assert_called_once_with(1)
    others = [n for n in h.cb if n.startswith("move_") and n != target]
    assert not any(h.called(n) for n in others)


def test_move_keys_are_ignored_while_other_dialog_is_open(h: Harness) -> None:
    h.set_true("is_dialog_open")
    h.press("ArrowDown")

    assert not any(h.called(n) for n in h.cb if n.startswith("move_"))


# --- Shift+←/→(表示日の移動) ------------------------------------------------------------


@pytest.mark.parametrize(("key", "delta"), [("ArrowRight", 1), ("ArrowLeft", -1)])
def test_shift_arrow_moves_view_date_on_main(h: Harness, key: str, delta: int) -> None:
    h.press(key, shift=True)

    h.cb["shift_view_date"].assert_called_once_with(delta)


@pytest.mark.parametrize(
    ("screen", "dialog_open", "shift"),
    [(Screen.LIST, False, True), (Screen.MAIN, True, True), (Screen.MAIN, False, False)],
)
def test_shift_arrow_is_ignored_on_list_with_dialog_or_without_shift(
    h: Harness, screen: Screen, dialog_open: bool, shift: bool
) -> None:
    h.state.screen = screen
    if dialog_open:
        h.set_true("is_dialog_open")
    h.press("ArrowRight", shift=shift)

    assert not h.called("shift_view_date")


# --- Enter(実行・停止) ------------------------------------------------------------------


def test_enter_toggles_execution_of_selected_item_and_refreshes(h: Harness) -> None:
    h.state.select("a")
    h.press("Enter")

    h.service.toggle_execution.assert_called_once_with("a")
    assert h.called("refresh_all")


@pytest.mark.parametrize("case", ["no_selection", "dialog_open", "read_only_view"])
def test_enter_does_not_toggle_execution_in_guarded_states(h: Harness, case: str) -> None:
    if case != "no_selection":
        h.state.select("a")
    if case == "dialog_open":
        h.set_true("is_dialog_open")
    if case == "read_only_view":
        h.state.view_date = date.today() + timedelta(days=1)
    h.press("Enter")

    h.service.toggle_execution.assert_not_called()


# --- e(編集) ----------------------------------------------------------------------------


def test_e_opens_item_edit_for_selected_item(h: Harness) -> None:
    h.state.select("a")
    h.press("e")

    h.cb["open_edit_dialog"].assert_called_once_with("a")


def test_e_opens_category_edit_in_category_list(h: Harness) -> None:
    h.set_true("is_category_list_open")
    h.state.select_category("c1")
    h.state.select("a")
    h.press("e")

    h.cb["open_category_edit_dialog"].assert_called_once_with("c1")
    assert not h.called("open_edit_dialog")


def test_e_opens_record_edit_in_log(h: Harness) -> None:
    h.set_true("is_log_open")
    h.state.select_record("r1")
    h.press("e")

    h.cb["open_record_edit_dialog"].assert_called_once_with("r1")


@pytest.mark.parametrize("case", ["nothing_selected", "dialog_open", "log_open_without_record"])
def test_e_does_nothing_in_guarded_states(h: Harness, case: str) -> None:
    if case == "dialog_open":
        h.state.select("a")
        h.set_true("is_dialog_open")
    if case == "log_open_without_record":
        h.state.select("a")
        h.set_true("is_log_open", "is_dialog_open")
    h.press("e")

    assert not (h.called("open_edit_dialog") or h.called("open_record_edit_dialog") or h.called("open_category_edit_dialog"))


def test_e_is_allowed_in_read_only_view(h: Harness) -> None:
    # 閲覧用の日でも、編集(e)は受け付ける
    h.state.view_date = date.today() + timedelta(days=1)
    h.state.select("a")
    h.press("e")

    h.cb["open_edit_dialog"].assert_called_once_with("a")


# --- d(完了)・c(キャンセル) -------------------------------------------------------------


def test_d_toggles_done_on_selected_items(h: Harness) -> None:
    h.press("d")

    assert h.called("toggle_done_selected_items")


@pytest.mark.parametrize("case", ["dialog_open", "read_only_view"])
def test_d_is_ignored_in_guarded_states(h: Harness, case: str) -> None:
    if case == "dialog_open":
        h.set_true("is_dialog_open")
    else:
        h.state.view_date = date.today() - timedelta(days=1)
    h.press("d")

    assert not h.called("toggle_done_selected_items")


def test_c_cancels_running_of_selected_item(h: Harness) -> None:
    h.state.select("a")
    h.press("c")

    h.service.cancel_running.assert_called_once_with("a")
    assert h.called("refresh_all")


@pytest.mark.parametrize("case", ["no_selection", "dialog_open", "read_only_view"])
def test_c_is_ignored_in_guarded_states(h: Harness, case: str) -> None:
    if case != "no_selection":
        h.state.select("a")
    if case == "dialog_open":
        h.set_true("is_dialog_open")
    if case == "read_only_view":
        h.state.view_date = date.today() + timedelta(days=1)
    h.press("c")

    h.service.cancel_running.assert_not_called()


# --- 画面を開くキー(l・L・g・T・o) ------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "callback"),
    [("l", "open_log_dialog"), ("L", "open_calendar_view"), ("g", "open_category_list"),
     ("T", "open_category_summary"), ("o", "open_settings")],
)  # fmt: skip
def test_open_keys_on_main(h: Harness, key: str, callback: str) -> None:
    h.press(key)

    assert h.called(callback)


@pytest.mark.parametrize(
    ("key", "callback", "opens_on_list"),
    [("l", "open_log_dialog", True), ("L", "open_calendar_view", True), ("g", "open_category_list", False),
     ("T", "open_category_summary", True), ("o", "open_settings", False)],
)  # fmt: skip
def test_open_keys_on_list_screen(h: Harness, key: str, callback: str, opens_on_list: bool) -> None:
    # g(カテゴリ一覧)・o(設定)はメイン画面のみ。l・L・Tは編集一覧でも開ける
    h.state.screen = Screen.LIST
    h.press(key)

    assert h.called(callback) is opens_on_list


def test_o_is_ignored_while_dialog_is_open(h: Harness) -> None:
    h.set_true("is_dialog_open")
    h.press("o")

    assert not h.called("open_settings")


# --- Delete / Backspace(削除の振り分け) ---------------------------------------------------


@pytest.mark.parametrize("key", ["Delete", "Backspace"])
@pytest.mark.parametrize(
    ("flags", "target"),
    [
        ((), "delete_selected_items"),
        (("is_log_open",), "delete_selected_records"),
        (("is_category_list_open",), "delete_selected_categories"),
        (("is_category_list_open", "is_log_open"), "delete_selected_categories"),
    ],
)
def test_delete_keys_route_by_open_surface(h: Harness, key: str, flags: tuple[str, ...], target: str) -> None:
    h.set_true(*flags)
    h.press(key)

    deletes = [n for n in h.cb if n.startswith("delete_selected_")]
    assert [n for n in deletes if h.called(n)] == [target]


# --- Cmd/Ctrl+A(全選択の振り分け) -------------------------------------------------------


@pytest.mark.parametrize("modifier", ["ctrl", "meta"])
@pytest.mark.parametrize(
    ("flags", "screen", "target"),
    [
        ((), Screen.MAIN, "select_all_main_items"),
        ((), Screen.LIST, "select_all_list_items"),
        (("is_log_open",), Screen.MAIN, "select_all_records"),
        (("is_category_list_open",), Screen.MAIN, "select_all_categories"),
        (("is_category_list_open", "is_log_open"), Screen.LIST, "select_all_categories"),
    ],
)
def test_select_all_routes_by_open_surface(
    h: Harness, modifier: str, flags: tuple[str, ...], screen: Screen, target: str
) -> None:
    h.state.screen = screen
    h.set_true(*flags)
    modifiers: dict[str, Any] = {modifier: True}
    h.press("a", **modifiers)

    selects = [n for n in h.cb if n.startswith("select_all_")]
    assert [n for n in selects if h.called(n)] == [target]


def test_a_without_modifier_does_nothing(h: Harness) -> None:
    h.press("a")

    assert not any(h.called(n) for n in h.cb if n.startswith("select_all_"))
