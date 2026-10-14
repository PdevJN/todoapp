from collections.abc import Callable
from typing import Any

from nicegui import ui
from nicegui.elements import sortable as _sortable  # noqa: F401  SortableJS(`nicegui-sortable`)の読み込み設定を有効にする


class SortableTable(ui.element, component='sortable_table.js'):
    """`ui.table`の行をドラッグ&ドロップで並べ替えられるようにする(表の直後に置く)。

    `on_reorder(old_index, new_index)`は、表示上の行の添字(先頭の`fixed_rows`行を含む)で呼ばれる。
    ドロップした行は画面上では元の位置へ戻るため、呼び出し側が`rows`を更新して再描画すること。
    """

    def __init__(
        self,
        table: ui.table,
        on_reorder: Callable[[int, int], Any],
        *,
        fixed_rows: int = 0,
        delay: int = 150,
    ) -> None:
        super().__init__()
        self._props['table-id'] = table.id
        self._props['fixed-rows'] = fixed_rows
        self._props['delay'] = delay
        self.on('reorder', lambda e: on_reorder(e.args['old_index'], e.args['new_index']))
