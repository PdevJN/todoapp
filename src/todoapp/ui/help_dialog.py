from __future__ import annotations

from nicegui import ui

from todoapp.ui.dialog_base import DialogMixin

_SHORTCUTS: list[tuple[str, str]] = [
    ("最下部入力欄 + Enter", "アイテム(カテゴリ一覧では新しいカテゴリ)の新規登録"),
    ("最下部入力欄 + Shift+Enter", "登録直後にカテゴリ選択(カテゴリ一覧では種別入力)を続けて表示"),
    ("Enter / ダブルクリック", "選択中アイテムの実行・停止トグル"),
    ("クリック", "アイテム・記録・カテゴリの選択"),
    ("↑ / ↓ (j / k)", "アイテム・記録・カテゴリの選択を前後に切り替え"),
    ("Cmd/Ctrl + クリック", "選択の個別トグル(複数選択)"),
    ("Shift + クリック", "選択の範囲選択"),
    ("Cmd/Ctrl + A", "表示中の一覧を全選択"),
    ("DEL / Backspace", "選択中のアイテム・記録・カテゴリを削除"),
    ("e", "選択中のアイテム・記録・カテゴリの編集フォーム表示"),
    ("c", "選択中アイテムの実行キャンセル"),
    ("l", "本日の作業ログ表示(上部のトグルで実行順・カテゴリ別を切り替え。カテゴリにマウスオーバーで当日のタスクを表示)"),
    ("Shift + L", "実行履歴のカレンダー表示(当日/週/月)"),
    ("g", "カテゴリ一覧表示(メイン画面のみ)"),
    ("Shift + T", "カテゴリ別集計表示(メイン画面・編集一覧)"),
    ("ESC", "選択解除。未選択ならメイン画面⇔編集一覧の切り替え、またはダイアログを閉じる"),
]


class HelpDialog(DialogMixin):
    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[32rem] gap-2"):
            ui.label("キー操作ヘルプ").classes("text-lg font-bold")
            with ui.column().classes("w-full gap-1"):
                for keys, description in _SHORTCUTS:
                    with ui.row().classes("w-full items-start gap-3 flex-nowrap"):
                        ui.label(keys).classes("font-mono text-sm whitespace-nowrap shrink-0 w-52")
                        ui.label(description).classes("text-sm text-gray-600")
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")

    def open(self) -> None:
        self.dialog.open()
