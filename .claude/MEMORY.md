# 作業状況メモ

最終更新: 2026-08-30(カテゴリ機能を追加)

## 現在のブランチ

`feature/todo-app-mvp`(`develop`から分岐、git-flow運用)

## これまでの作業

CLAUDE.mdの機能仕様(TODOリスト表示・タイマー計測・キー操作)に基づき、コア機能のMVP実装を完了した。`develop`ブランチとの差分は以下5コミット:

1. `chore`: srcレイアウトへの再構成とnicegui依存の追加(RULE.md準拠のディレクトリ構成整備)
2. `feat`: TODOドメインモデル(`TodoItem`/`ExecutionRecord`/`TodoService`)とJSON永続化リポジトリを追加(NiceGUI非依存、独自JSONファイル永続化を採用)
3. `feat`: NiceGUIによるUI層(メイン画面/編集フォーム/編集一覧/ログ画面/キーボード操作)とpywebviewによるネイティブウィンドウ化を実装
4. `docs`: README整備
5. `fix`: 編集一覧の「残りの完了時間」が実質変化しない表示不具合を修正(時間の丸め誤差が原因。HH:MM:SS形式に変更し、定期再描画も追加)

## モジュール構成

```
src/todoapp/
├── domain/        # NiceGUI非依存のドメインロジック(models.py, service.py)
├── repository/     # JSON永続化(~/.todoapp/todos.json)
├── ui/              # NiceGUI画面(main_view/edit_dialog/list_view/log_view/keyboard/app_state/formatting)
└── main.py          # エントリーポイント(pywebviewネイティブウィンドウ)
```

## 動作確認状況

- `uv run pytest --cov=todoapp` : 22件全パス
- `uv run mypy src test` : strict型チェック通過
- `uv run todoapp`を実機で起動し、ネイティブウィンドウの表示・アイテム追加・実行計測・編集一覧の表示を目視確認済み(画面2/セカンダリモニターでのスクリーンショットで確認。ユーザーの個人的な画面を写さないよう`screencapture -x -D2`を使用すること)

## 今回(2026-08-30 再開分)の作業

- 実機でのキー操作確認を実施しようとしたが、`ui.keyboard`(NiceGUI)は入力欄/select/button/textareaがフォーカスされている間はグローバルキー(`e`/`c`/`l`/`ESC`/`Enter`)を無視する仕様であり、AppleScript(System Events)からの合成クリックでは確実にフォーカスを外せず自動化検証が不安定だったため、ユーザーによる手動検証に切り替えた
- ユーザーの手動検証で発見: 新規アイテム登録時、日本語IME変換確定のEnterでもアイテムが登録されてしまう不具合を報告受領
  - 原因: `main_view.py`の`ui.input.on("keydown.enter", self._add_item)`がVueの`withKeys`(`event.key === 'Enter'`のみ判定)を使っており、IME変換確定時のEnterキーダウンでも`isComposing`を無視して発火していた
  - 修正: `js_handler`で`event.isComposing`および`event.keyCode === 229`をチェックし、IME変換中のEnterはサーバーに送信しない(`emit`しない)ように変更(`src/todoapp/ui/main_view.py`)
  - ユーザーが実機で再現しないことを確認済み
  - 修正前に発生した重複データ(「新規アイテム」2件)は、ユーザーの指示で当面`~/.todoapp/todos.json`に残したまま運用中

- 編集一覧(`list_view.py`)に「実行の曜日」「基準日」列を追加(基準日はMM/DD表記)。列増加でネイティブウィンドウ幅(480px)から溢れたため、`main.py`のウィンドウ幅を620pxに拡大
- ユーザーの手動検証で発見: 編集一覧でテーブルの行をクリックしても選択されず(QTableは既定でチェックボックスクリックでしか`selection`イベントが発火しない)、その結果一度もメインパネルで選択していない状態だと編集一覧で`e`キーを押しても何も表示されない不具合を報告受領
  - 修正: `self.table.on("rowClick", self._on_row_click, ...)`を追加し、行のどこをクリックしても`state.selected_item_id`と`table.selected`(チェックボックス見た目)の両方を更新するようにした(`list_view.py`)
  - ユーザーが実機で選択・`e`キーとも動作することを確認済み
- ユーザー要望により、編集一覧の「実行の曜日」列を削除し、代わりにメインパネルと同じ`q-badge outline`スタイルでアイテム名の右にスケジュール種別を併記するよう変更(QTableの`body-cell-name`スロットをカスタムテンプレートで上書き)。ユーザー確認済み

- ユーザー要望により「本日の作業ログ」画面に、記録の選択・編集・削除機能を追加
  - `ExecutionRecord`(`domain/models.py`)にUUID採番の`id`フィールドを追加(既存データとの後方互換のため`from_dict`は`id`欠落時に新規採番)
  - `TodoService`(`domain/service.py`)に`edit_record(record_id, *, start_time, end_time)`と`delete_record(record_id)`を追加
  - `AppState`(`ui/app_state.py`)に`selected_record_id`とその選択メソッドを追加(アイテム選択とは独立)
  - `LogView`(`ui/log_view.py`)の各記録行をクリックで選択・ハイライトできるようにし、新規`RecordEditDialog`(`ui/record_edit_dialog.py`)で開始時刻・終了時刻の編集と記録の削除ができるようにした
  - `KeyboardController`(`ui/keyboard.py`)の`e`キー処理を拡張し、作業ログが開いていて記録が選択されている場合はアイテム編集ではなく記録編集ダイアログを開くよう分岐
  - ドメイン層のテストを追加(`test/domain/test_service.py`の`edit_record`/`delete_record`、`test/domain/test_models.py`の`id`ラウンドトリップ・後方互換)。`uv run pytest` 26件全パス、`uv run mypy src test`通過
  - ユーザーの手動検証で選択ハイライトが薄いとの指摘を受け`bg-blue-50`→`bg-blue-200`に強調。また時刻入力を`ui.input(type=time)`から`ui.time_input`(ピッカー付き、`with-seconds`で秒まで選択可)に変更
  - ユーザー確認済み。コミット済み(`a658443`)

- ユーザー要望により「カテゴリ」機能を追加(計画は`/Users/jun/.claude/plans/tranquil-petting-squirrel.md`に保存、EnterPlanMode経由で要件を事前確認)。要件確認事項:
  - 「種別」はカテゴリ自身が持つ自由入力の分類項目(選択式ではない)
  - 新規アイテム登録(最下部入力欄+`Enter`)は従来どおり「未定」カテゴリで即登録。`Shift+Enter`の場合のみ登録直後にカテゴリ選択フォームが続けて開く
  - 「カテゴリ一覧」「カテゴリ別集計」は本日の作業ログと同じ`ui.dialog()`形式で表示
  - `Category`(`domain/models.py`): `name`/`kind`(種別)/`expiry_date`/`color`(作成時に固定パレットからランダム割当)。`TodoItem`に`category_id`を追加(`None`=「未定」)。`AppData`に`categories`を追加、JSON永続化も後方互換で対応
  - `TodoService`に`add_category`/`edit_category`/`delete_category`(削除時は紐づくアイテムの`category_id`を`None`に戻す)/`set_item_category`/`category_for_item`/`category_today_totals`/`kind_today_totals`を追加
  - 新規ダイアログ4つ: `CategoryListDialog`(`g`キー、メインパネルのみ、行クリック選択+`e`で編集)、`CategoryEditDialog`(名前/種別/有効期限日+削除ボタン)、`CategorySummaryDialog`(`T`=Shift+Tキー、メインパネル・編集一覧両方、本日のカテゴリ別累積時間+種別ごとの集計ラベル)、`CategoryPickDialog`(Shift+Enter登録時の軽量カテゴリ選択/新規作成ピッカー)
  - `list_view.py`の`body-cell-name`スロットにカテゴリバッジを追加(期限切れは`❗️`付き)。メインパネルには要件どおりカテゴリバッジを表示しない
  - `main_view.py`の新規登録入力欄は、プレーン`Enter`用(`keydown.enter.exact`)とShift+Enter用(`keydown.enter.shift`)の2リスナーに分離(Vueの`.exact`修飾子で同時発火を防止)。既存のIME`isComposing`ガードは両方に適用
  - `keyboard.py`の`e`キー分岐にカテゴリ一覧の優先順位を追加、`g`(メイン画面限定)・`T`(メイン/編集一覧)を新設
  - ドメイン層テストを追加(`Category`のラウンドトリップ・期限切れ判定、カテゴリCRUD、集計関数)。`uv run pytest` 37件全パス、`uv run mypy src test`通過
  - ユーザーが実機で全機能(Shift+Enter登録、カテゴリ一覧/編集/削除、カテゴリ別集計、編集一覧バッジ、メインパネル非表示)を確認済み
  - 追加要望: カテゴリ削除時、紐づくアイテムがある場合は「未定」に戻る旨の確認ダイアログを挟むよう`CategoryEditDialog`に確認用の`ui.dialog()`を追加(`_confirm_delete`で紐付き件数を数え、0件なら即削除・1件以上なら確認ダイアログ経由)。ユーザー確認済み。コミットはこれから

## 未実施・今後の検討事項

- Enter/ダブルクリック/`c`/`l`の一部キー操作について、実機での網羅的な手動確認はまだ行っていない(自動化は不安定なため断念し、ユーザーの手動確認に依存する方針。詳細は`manual-gui-verification-preferred`メモリ参照)
- `edit_dialog.py`では「当日(ONE_TIME)」もスケジュール変更時に基準日を編集可能にしている(元プランでは週次/月次のみ言及だったが、当日も基準日が必須なため拡張した)
- `develop`や`main`へのマージはまだ行っていない

## 運用ルール(このセッションで確定した方針)

- **コミットは実行前に必ずユーザーへ確認を取ること**(以前はタスクの区切りごとに自律的にコミットしていたが、ユーザーからの指示によりこの方針に変更)
- GUIアプリの動作確認スクリーンショットは、デスクトップ全体ではなく`screencapture -x -D2`でセカンダリモニター(画面2)のみを撮影すること
