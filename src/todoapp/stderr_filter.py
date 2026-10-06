from __future__ import annotations

import os
import threading
from collections.abc import Iterable

# 日本語IMEの変換中にmacOS(AppKit)がNSLogで出す無害な警告。アプリの動作には影響しない
SUPPRESSED_MESSAGES = (
    "Text input context does not respond to _valueForTIProperty",
    "_TIPropertyValueIsValid called with",
    "imkxpc_getApplicationProperty:reply: called with incorrect property value",
)


def filter_lines(lines: Iterable[bytes], suppressed: tuple[str, ...] = SUPPRESSED_MESSAGES) -> Iterable[bytes]:
    needles = tuple(s.encode() for s in suppressed)
    return (line for line in lines if not any(n in line for n in needles))


def install_stderr_filter() -> None:
    """fd 2をパイプに差し替え、抑制対象の行を除いて元のstderrへ流す(子プロセスにも継承される)"""
    original_fd = os.dup(2)
    read_fd, write_fd = os.pipe()
    os.dup2(write_fd, 2)
    os.close(write_fd)

    def pump() -> None:
        with os.fdopen(read_fd, "rb") as src:
            for line in filter_lines(src):
                os.write(original_fd, line)

    threading.Thread(target=pump, name="stderr-filter", daemon=True).start()
