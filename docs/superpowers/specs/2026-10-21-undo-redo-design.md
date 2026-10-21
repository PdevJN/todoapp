# Undo/Redo(編集系操作の取り消しとやり直し) 設計

## 目的

誤操作(削除・完了・スキップ・繰越・並び替えなど)を`Cmd/Ctrl+Z`で元に戻し、`Shift+Cmd/Ctrl+Z`でやり直せるようにする。

## 要件(ユーザー指示)

- Undo/Redoを実装する
- 対象は、アイテム・カテゴリ・リンクテンプレートの編集系。実行の開始/停止/キャンセルと実行記録の編集・削除は対象外(時間計測は実時間なので巻き戻さない)
- 方式はスナップショット方式(変更の直前の状態を履歴に積み、Undo/Redoで入れ替える)

## 前提(現状の仕組み)

- 変更はすべて`TodoService`のメソッドを通り、毎回`_save()`が呼ばれる。状態は`AppData`(`items`・`records`・`categories`・`link_templates`)に集まっている
- `TodoService`はアプリ全体で1つを共有する(`main.py`の`_shared_service`)
- 実行記録(`ExecutionRecord`)はアイテムidと名前を持つ。アイテムを削除しても記録は残り、名前を変更すると既存の記録の名前も揃える(`edit_item`)
- `ui.keyboard`は、入力欄にフォーカスがある間のキーを既定で無視する

## ドメイン(`domain/undo.py`・`domain/service.py`)

### スナップショットと履歴(`domain/undo.py`、新規)

- `Snapshot`: `items`・`categories`・`link_templates`のディープコピーと、`{記録id: アイテム名}`の対応表を持つ。`records`本体は持たない(Undoのたびに、その後の計測時間が消えるのを避けるため)
- `UndoHistory`: UndoスタックとRedoスタック(上限は各50件。超えたら古いものから捨てる)を持つ
  - `push(label, before)`: Undoスタックへ積み、Redoスタックを空にする
  - `pop_undo(current)`・`pop_redo(current)`: 反対側のスタックへ`current`を退避して、戻す先のスナップショットとラベルを返す。空なら`None`
- 履歴はメモリのみで、起動のたびに空から始まる(保存しない)

### サービス(`domain/service.py`)

- `@undoable("操作名")`デコレータを、対象メソッドに付ける
  1. 一番外側の呼び出しの直前にスナップショットを取る(入れ子の呼び出しは深さカウンタで見分け、内側では取らない)
  2. 呼び出しの後に、スナップショットの対象部分(`items`・`categories`・`link_templates`・記録の名前)が変わっていれば履歴へ積む。変わっていなければ積まない(繰越の対象が無い場合など)
- 対象メソッド
  - アイテム: `add_item`・`edit_item`・`delete_item`・`delete_items`・`reorder`・`move_item_to`・`set_done`・`set_skipped`・`carry_over`・`set_item_category`・`set_item_links`
  - カテゴリ: `add_category`・`edit_category`・`delete_category`・`delete_categories`・`move_category_to`
  - リンクテンプレート: `add_link_template`・`edit_link_template`・`delete_link_templates`
  - `toggle_done`・`toggle_skipped`は`set_done`・`set_skipped`へ委譲するため、デコレータは付けない
- 対象外: `start`・`stop_running`・`toggle_execution`・`cancel_running`・`edit_record`・`delete_record(s)`・`recover_interrupted`・`stop_on_shutdown`・`keep_alive`(日跨ぎの分割を含む)
- `TodoService.undo() -> str | None`・`redo() -> str | None`: 復元した操作のラベルを返す。履歴が空なら`None`
- 復元は`items`・`categories`・`link_templates`をスナップショットのコピーで置き換え、記録の名前は対応表にあるidの分だけ戻す(その後に削除された記録は無視する)。その後`_save()`を1回呼ぶ
- 復元後に実行中の記録のアイテムが存在しない場合は、`delete_item`と同じく記録を停止する(記録は残す)。たとえば、追加したアイテムを実行した後に、追加を取り消した場合
- 完了・スキップ・繰越で止めた計測は、Undoしても再開しない(停止した記録はそのまま残る)

## 画面(`ui/keyboard.py`・`main.py`・各ビュー)

- キー: Undoは`Cmd/Ctrl+Z`、Redoは`Shift+Cmd/Ctrl+Z`または`Ctrl+Y`
- 有効なのは、メイン画面と編集一覧。ダイアログ表示中は無効だが、カテゴリ一覧の表示中は有効とする。当日以外の日を表示している閲覧用でも有効(登録・編集・削除が使えるため)
- 実行後に`元に戻しました: 〇〇`・`やり直しました: 〇〇`を通知する。履歴が空なら`元に戻す操作がありません`・`やり直す操作がありません`の警告を出す
- 復元後は全画面を再描画し、存在しなくなったアイテム・カテゴリの選択を外す
- 他の画面(別のウィンドウ・タブ)には自動では反映されない(既存の共有サービスの制約と同じ)
- `SHORTCUT_KEYS`に`z`・`Z`・`y`を追加する。ヘルプ(`ui/help_dialog.py`)・`README.md`のキー一覧・`CLAUDE.md`も更新する

## テスト

- `test/domain/test_undo.py`
  - 対象の各メソッドのUndo/Redo
  - 変化が無い操作を積まないこと
  - 入れ子の呼び出しが1件になること
  - 新しい操作でRedoが消えること
  - 50件の上限
  - 名前変更後のUndoで記録の名前が戻ること
  - 削除のUndoで、残っていた記録と再び結びつくこと
  - 実行中の記録のアイテムを追加の取り消しで失った場合に停止すること
  - 対象外の操作(実行の開始・停止、記録の編集・削除)が履歴を積まないこと
- `test/ui`
  - キー操作と通知(Undo・Redo・履歴が空)
  - ダイアログ表示中は無効なこと(カテゴリ一覧では有効なこと)
  - 復元後の選択の整理
  - `test_keyboard.py`の登録漏れ検出が通ること
- 進め方はTDD。全体のpytestとmypyが通ること

## スコープ外

- 履歴の保存(再起動をまたぐUndo)
- 実行の開始/停止・実行記録の編集・削除のUndo
- 画面をまたぐ履歴の同期
- 履歴の一覧表示
