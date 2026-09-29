import re
from pathlib import Path

from todoapp.ui import keyboard
from todoapp.ui.keyboard import SHORTCUT_KEYS


def test_every_key_handled_by_keyboard_controller_is_registered_as_shortcut_key() -> None:
    # 登録漏れがあると、WKWebViewでそのキーを押したときにシステム警告音が鳴る
    source = Path(keyboard.__file__).read_text(encoding="utf-8")
    handled = set(re.findall(r'e\.key == "(\w)"', source))
    # Cmd/Ctrl+Aは修飾キー付きの操作で、main.pyのJSが別に(常に)preventDefaultしている
    handled.discard("a")

    assert handled
    assert handled <= set(SHORTCUT_KEYS)


def test_shortcut_keys_include_the_special_keys_used_by_the_controller() -> None:
    for key in ("Escape", "Enter", "Backspace", "Delete", "ArrowUp", "ArrowDown"):
        assert key in SHORTCUT_KEYS
