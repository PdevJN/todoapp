from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def atomic_write_text(path: Path, text: str, *, backup: bool = False) -> None:
    """一時ファイルへ書いてから置き換える。書き込み途中で落ちても元のファイルは壊れない。

    backup=Trueのときは、置き換える直前に現在のファイルを`.bak`へ1世代だけ残す。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        if backup and path.exists():
            shutil.copy2(path, backup_path(path))
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def quarantine(path: Path) -> Path:
    """壊れたファイルを`.corrupt-<日時>`へ退避する(上書き・削除はしない)。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = path.with_name(f"{path.name}.corrupt-{stamp}")
    os.replace(path, target)
    return target
