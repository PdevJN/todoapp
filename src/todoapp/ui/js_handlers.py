from __future__ import annotations

# 日本語IME変換確定のEnterキーダウンでも`keydown.enter`が発火してしまうため、
# 変換中(isComposing)かIME確定用のkeyCode(229)の場合はサーバーに送信しない
IME_SAFE_ENTER_HANDLER = "(...args) => { if (!args[0].isComposing && args[0].keyCode !== 229) emit(...args); }"

# WebKitはサーバー往復後のクリップボード書き込みを拒否するため、クリック直後にクライアント側で書き込む。
# コピー対象はボタンの`data-copy-text`属性から読み、成否だけをサーバーへ送る
CLIPBOARD_COPY_HANDLER = (
    "(e) => { const el = e.target.closest('[data-copy-text]');"
    " navigator.clipboard.writeText(el.dataset.copyText).then(() => emit(true), () => emit(false)); }"
)
