from __future__ import annotations

# 日本語IME変換確定のEnterキーダウンでも`keydown.enter`が発火してしまうため、
# 変換中(isComposing)かIME確定用のkeyCode(229)の場合はサーバーに送信しない
IME_SAFE_ENTER_HANDLER = "(...args) => { if (!args[0].isComposing && args[0].keyCode !== 229) emit(...args); }"
