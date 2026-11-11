"""一覧の表を、ウィンドウ(ブラウザ・ネイティブとも)の幅に収めるための共通部品。

`table-layout: fixed`にして、幅を固定しない列(アイテム名・カテゴリ名)が残りの幅を取る。
収まらない文字は`ellipsis`で「...」と省略し、呼び出し側でマウスオーバーのチップを付けて全文を見せる。
"""

from __future__ import annotations

# 表(`ui.table`)に付けるクラス
FIT_TABLE_CLASS = "fit-table"

# `table-layout: fixed`は内側の<table>に指定する(QTableの`table-style`は外枠に付くため効かない)。
# 固定レイアウトでは、選択用チェックボックスの列(Quasar既定は幅1px)に幅を与える必要がある
FIT_TABLE_CSS = """
.fit-table table { table-layout: fixed; }
.fit-table .q-table--col-auto-width { width: 2.5rem !important; max-width: 2.5rem; }
"""


def fixed_width(column: dict[str, str], rem: float, *, ellipsis: bool = False) -> dict[str, str]:
    """列の幅を`rem`に固定する(`ellipsis`なら、収まらない文字を「...」で省略する)。"""
    width = f"width: {rem}rem; max-width: {rem}rem"
    column = {**column, "style": width, "headerStyle": width}
    if ellipsis:
        column["classes"] = "ellipsis"
    return column
