# 作業状況メモ

最終更新: 2026-09-30(実行履歴カレンダー機能を追加。FullCalendarのベンダリング・週開始曜日設定・土日/祝日の色分け・祝日データ取得・当日/週/月のビュー切替を実装。コミットは保留中)

## 現在のブランチ

`develop`(`feature/todo-app-mvp`は`9ead194`で一度`develop`へマージ済みだったが、その後両ブランチが個別に進んだため、今回`feature/todo-app-mvp`の↑/↓・j/kキー選択切替とシステム警告音修正を`develop`へ再マージした)

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
  - 追加要望: カテゴリ削除時、紐づくアイテムがある場合は「未定」に戻る旨の確認ダイアログを挟むよう`CategoryEditDialog`に確認用の`ui.dialog()`を追加(`_confirm_delete`で紐付き件数を数え、0件なら即削除・1件以上なら確認ダイアログ経由)。ユーザー確認済み。コミット済み(`f2a2afc`)

- ユーザー要望により、メインパネル・編集一覧・作業ログ・カテゴリ一覧の4画面すべてで全選択(`Cmd+A`)・複数選択・`DEL`キー削除に対応(計画は同じ`tranquil-petting-squirrel.md`を上書きして保存、EnterPlanMode経由で操作方法を事前確認)。要件確認事項:
  - メインパネル・作業ログ(自作の行一覧)は`Cmd/Ctrl+click`で個別トグル、`Shift+click`で範囲選択
  - 編集一覧・カテゴリ一覧(QTable)は`selection="multiple"`に変更し、チェックボックス・ヘッダーの全選択チェックボックスを使う
  - 既存の単一選択フィールド(`selected_item_id`等、Enter/e/cが参照)はそのまま維持し、新たに複数選択マーク用の`set`フィールド(`selected_item_ids`等)を`AppState`に追加。プレーンクリックはこの集合を`{そのid}`にリセットするため、修飾キーを使わない操作でも`DEL`削除は違和感なく機能する
  - メインパネルと編集一覧は同じ`TodoItem`集合の選択状態を共有するため、`delete_items`(アイテム)/`delete_records`(記録)/`delete_categories`(カテゴリ、`linked_item_count`で紐付き件数を事前取得)を`TodoService`に追加し、削除ロジックは`main.py`のクロージャに一本化
  - 共通の`ConfirmDialog`(`ui/confirm_dialog.py`)を新設し、複数選択削除(2件以上)とカテゴリ編集フォームの既存の単一削除確認の両方で再利用するようリファクタリング
  - ブラウザ既定のCmd/Ctrl+A(ページ全体のテキスト選択)を`ui.add_body_html`の小さなスクリプトで`preventDefault`し、見た目のちらつきを防止
  - 追加要望: メインパネルの`Cmd+A`全選択状態のときのみ`ESC`で選択解除できるようにした(通常のクリック選択やLIST/ログ/カテゴリ画面のESC挙動は変更せず)。`MainView`に`_select_all_active`フラグを追加し、`keyboard.py`のESC処理で分岐
  - **不具合修正**: `DEL`キーが効かない不具合を発見。原因はmacOSキーボードの主要な「delete」キー(Backspace位置)がDOM上では`event.key === "Backspace"`として送られ、`"Delete"`(Fn+Delete、フォワードデリート)とは別物であること。`keyboard.py`で`e.key.delete`のみを見ていたため反応していなかった。`e.key.delete or e.key.backspace`に修正
  - ドメイン層テストを追加(`delete_items`/`delete_records`/`linked_item_count`/`delete_categories`)。`uv run pytest` 41件全パス、`uv run mypy src test`通過
  - ユーザーが実機で全機能(Cmd/Ctrl+click個別トグル、Shift+click範囲選択、チェックボックス複数選択、Cmd+A全選択、DEL単一/複数削除、確認ダイアログ、ESC全選択解除、カテゴリ複数削除の紐付き復帰)を確認済み。コミット済み(`9d872cf`)

- ユーザー要望により、カテゴリ一覧(`category_list_dialog.py`)でカテゴリ名にマウスオーバーすると、そのカテゴリに属する本日のアイテム名一覧を`q-tooltip`で表示するよう追加(0件のときは「本日のアイテムはありません」と表示)。`body-cell-name`スロットに`<q-tooltip>`を追加し、`refresh()`で`self._service.items_due_today(date.today())`を`category_id`でフィルタして各行に`today_items`(名前のリスト)を持たせた。新規のTodoServiceメソッドは追加せず、UI層でのフィルタのみで対応。ユーザー確認済み

- ユーザー要望により、カテゴリ一覧の先頭に実体を持たない「未定」の擬似行(`id="__uncategorized__"`)を追加表示(本日の未分類アイテムのホバー表示も同様に対応)。ユーザーから追加で「編集もできないことを期待している」との指摘があり、`_on_select`/`_on_row_click`で`UNCATEGORIZED_ID`を明示的に除外することで選択自体をブロックし、`e`キー編集・`DEL`削除のどちらも一切トリガーされないようにした(`select_all`用の`_rendered_ids`からも除外)。ユーザーが実機で「未定」の表示・編集不可・削除不可を確認済み。コミットはこれから

## 今回(2026-08-30 再々開分)の作業

- 前回セッション終了時点で作業ツリーはクリーン、直前コミット(`c9ba578`)まで反映済みであることを確認(MEMORY.mdには「コミットはこれから」と書かれていたが実際は反映済みだった)。`uv run pytest`(41件)・`uv run mypy`とも問題なし
- 「未実施・今後の検討事項」にあった、Enter/ダブルクリック/`c`/`l`キー操作の実機手動確認を再開。`manual-gui-verification-preferred`メモリの方針どおりアプリを起動しユーザーに手動確認を依頼したところ、**メインパネルでアイテムをクリックしても選択状態にならない**不具合を報告受領
  - 原因調査: アプリのターミナルログに`KeyError: 0`の例外が出ていた。`main_view.py`の`_on_row_click`で`modifiers = e.args[0]`としていたが、NiceGUI 3.16.0では`row.on("click", handler, args=["ctrlKey","metaKey","shiftKey"])`のように単一のイベント引数グループしか指定しない場合、サーバー側で受け取る`e.args`は`client.py`の`if len(msg['args']) == 1: msg['args'] = msg['args'][0]`により自動的に`[dict]`ではなく`dict`そのものへ展開される。そのため`e.args[0]`は存在しないキー`0`へのアクセスとなり例外が発生し、クリックによる選択処理(`_on_row_click`)が実行されていなかった(ダブルクリックによる実行・停止トグルは別ハンドラのため影響なし)
  - 同一パターンの不具合が`log_view.py`(作業ログの記録クリック)にも存在したため、両方とも`modifiers = e.args[0]` → `modifiers = e.args`に修正。コミット済み(`224ea14`)
  - 教訓: NiceGUIで`.on(..., args=[...])`を使う際、リクエストする引数グループが1つだけの場合は`e.args`がその中身そのもの(list展開されない)になる点に注意。今後同様のクリックハンドラを追加する際は同じ罠に注意する
- ユーザー要望により、メインパネルでアイテム選択中に`ESC`キーで選択解除できるよう追加(`keyboard.py`)。編集一覧・ログ・カテゴリ一覧画面のESC挙動(画面切り替え/ダイアログ)は、以前ユーザーからの指示で変更しない方針だったため今回も維持し、メインパネルのみのスコープとした。README.mdのキー操作表も更新。ユーザー確認済み。コミット済み(`7a0d3c4`)
- Enter/ダブルクリック/`c`/`l`の一部キー操作について、ユーザーが実機で手動確認し問題ないことを確認済み(前述のクリック選択不具合修正・ESC選択解除追加後の状態で確認)
- ユーザー要望により、ESCキーによる選択解除の対象を編集一覧・カテゴリ一覧にも拡大
  - 編集一覧(`list_view.py`)・カテゴリ一覧(`category_list_dialog.py`)はQTableの`selected`プロパティで選択の見た目を管理しており、`AppState`側の集合をクリアするだけでは画面に反映されない(`render()`/`refresh()`は`table.update_rows(rows, clear_selection=False)`を使っているため)。そのため両クラスに`has_selection()`/`clear_selection()`を追加し、`table.selected = []`も明示的にリセットするようにした
  - カテゴリ一覧は`ui.dialog()`で、素のESCキーはQuasarの既定動作でダイアログ自体を閉じてしまう。「選択があれば選択解除、なければ閉じる」の2段階挙動にするため、ダイアログに`.props("persistent")`を付けてESCでの自動クローズを止め、`close()`メソッドを追加して`keyboard.py`側で明示的に制御するようにした
  - `keyboard.py`のESC分岐は「カテゴリ一覧が開いていれば最優先で処理→他のダイアログが開いていれば何もしない(既存どおり)→メイン画面/編集一覧それぞれで選択があれば解除、なければ画面切り替え」の順に整理
  - README.mdのESCキーの説明も更新。ユーザーが実機で編集一覧・カテゴリ一覧それぞれの選択解除とダイアログクローズの2段階挙動を確認済み。コミット済み(`189caaf`)

- ユーザーから「メインパネルでのダブルクリックによる実行が動かないことがある」と報告受領
  - 最初にSortableJS(`make_sortable`)の既定`delay: 0`により、素早いクリック時のわずかなカーソルのブレがドラッグ開始と誤判定されclick/dblclickイベントが奪われる可能性を疑い、`options={"delay": 150}`を設定したが改善せず
  - ユーザーから「選択状態にしたことでダブルクリックが効かなくなったのでは」との指摘を受け再調査。真因は、`main_view.py`の`_on_row_click`(単一クリックのハンドラ)が選択のたびに`self.render.refresh()`でリスト全体を作り直していたこと。ダブルクリックの1回目のクリックでこの全体再描画(サーバーとの非同期往復を伴う)が走り、対象行のDOM要素が入れ替わってしまうため、2回目のクリックとの間でブラウザの`dblclick`判定が成立するかどうかがタイミング依存になっていた
  - 修正: クリックによる選択変更は行のDOM要素を作り直さず、選択状態が変化した行だけ`row.classes(add=..., remove=...)`でCSSクラスを差分更新するように変更(`_update_selection_classes`を新設、`_row_elements`で`item_id`→行要素のマッピングを保持)。ダブルクリック(`_toggle`)による実行トグルは従来通り`_refresh_all()`で全体再描画するが、これは2回のクリックが確定した後のアクションなので競合しない
  - 教訓: NiceGUIで単一クリックのたびに`@ui.refreshable_method`の全体再描画を呼ぶと、同じ要素への連続クリック(ダブルクリック等)が再描画のタイミングと競合してイベントを取りこぼすことがある。選択状態のような軽微な見た目の変化は、全体再描画ではなくクラスの差分更新で済ませる方が安全
  - ユーザーが実機で改善を確認済み。コミット済み(`620aba2`)。なお`make_sortable`の`delay: 150`は根本原因ではなかったが、ドラッグ誤判定対策として有用なため残している

- ユーザー要望により、ログ表示時に`Enter`キーでメインパネルの選択中アイテムが実行トグルされてしまう不具合を修正
  - 原因: 作業ログダイアログはフォーカス可能な入力欄を持たない行クリック選択のため、`Enter`キーがどこにもフォーカスされず`keyboard.py`のグローバル`Enter`ハンドラまで届いていた
  - 修正: `Enter`ハンドラに既存の`_is_dialog_open()`(ESCキーで使っているのと同じ判定)によるガードを追加。この判定は作業ログに限らずアイテム編集・カテゴリ一覧・カテゴリ集計など全ダイアログを含むため、いずれかのダイアログが開いている間はメインパネルのアイテム実行トグルが抑制されるようになった(ユーザーには「ログのときだけで良いか」を確認した上でこの範囲で実施)
  - ユーザー確認済み。コミット済み(`ac1dc0f`)

- ユーザー要望により、カテゴリ一覧のカテゴリ編集フォーム(`category_edit_dialog.py`)でカラーも編集できるように追加
  - `TodoService.edit_category`に`color`パラメータを追加(キーワード専用、必須)
  - フォームに`CATEGORY_COLORS`(固定パレット)の丸いスウォッチボタンを並べ、クリックで選択(選択中は黒枠でハイライト、上部バッジでプレビュー)。既存の色はランダム割当のみだったが、これで手動変更が可能になった
  - `test/domain/test_service.py`の`test_edit_category_updates_fields`に`color`引数と検証を追加
  - ユーザー確認済み。コミット済み(`65b3907`)

- ユーザーより、`edit_dialog.py`で「当日(ONE_TIME)」もスケジュール変更時に基準日を編集可能にした拡張(元プランでは週次/月次のみ言及だったが、当日も基準日が必須なため実装時に拡張していたもの)について承認を受け、CLAUDE.mdの「機能の詳細」に`基準日`の概念(週次=同じ曜日、月次=同じ日で月末調整あり、当日=基準日そのものの日付が対象日になること、`毎日`以外は編集フォームで設定・変更できること)を追記した

## 今回(2026-08-30 三度目の再開分)の作業

- ユーザー要望により、カテゴリ一覧画面(`category_list_dialog.py`)にカテゴリ登録機能を追加
  - 最下部にカテゴリ名のみの入力欄を追加(メインパネルの新規アイテム登録欄と同じ`keydown.enter.exact`/`keydown.enter.shift`の2リスナー分離+IME`isComposing`/`keyCode===229`ガードのパターンを踏襲)
  - プレーン`Enter`で種別なし(`kind=""`)のカテゴリを即登録
  - `Shift+Enter`で登録後、新規`CategoryKindDialog`(`ui/category_kind_dialog.py`)を開き、種別のみを入力するフォームを表示。保存時は`TodoService.edit_category`に既存の`name`/`expiry_date`/`color`をそのまま渡し`kind`だけを更新する(既存カテゴリ編集フォームとは別の軽量ダイアログとして新設)
  - `main.py`に`category_kind_dialog`を配線し、`KeyboardController`の`is_dialog_open`判定にも追加(開いている間は他のグローバルキー操作を抑制)
  - ドメイン層(`add_category`/`edit_category`)は既存のものをそのまま利用したため、新規のドメインテストは追加していない。`uv run pytest`(41件)・`uv run mypy src test`とも問題なし
  - ユーザーが実機で「Enter即登録」「Shift+Enterでの種別入力フォーム表示・保存反映」「IME変換中のEnter無反応」を確認済み

## 今回(2026-08-30 四度目の再開分)の作業

- セッション冒頭で`.claude/MEMORY.md`の記述が古いことに気づき整理。実際には`feature/todo-app-mvp`は既に`develop`へマージ済み(`9ead194`)で、その後もテスト拡充・ダークモードFAB・カテゴリ登録機能などが追加されていた。`uv run pytest`(79件)・`uv run mypy`とも問題なし

- ユーザー要望により、`カテゴリ`の概念に`PRJコード`(自由入力の文字列)を追加。要件確認事項:
  - カテゴリ一覧画面はテーブルに列を追加し、カテゴリ編集フォームにも入力欄を追加
  - カテゴリ一覧最下部の新規登録欄(Enter/Shift+Enter)では登録時は空のまま、後から編集フォームで設定
  - `Category`(`domain/models.py`)に`prj_code: str = ""`を追加(to_dict/from_dict・永続化も対応)、`TodoService.edit_category`に`prj_code`を必須キーワードとして追加(`category_kind_dialog.py`など既存の呼び出し元もすべて追随)
  - `category_edit_dialog.py`に「PRJコード」入力欄を追加、`category_list_dialog.py`のテーブルに「PRJコード」列を追加(未定行は「-」)
  - `category_summary_dialog.py`(カテゴリ別集計、Shift+T)の各カテゴリ行で、カテゴリ名の横にPRJコードを`q-badge`表示(未設定時は非表示)
  - ドメイン層テストを追加。`uv run pytest`(79件)・`uv run mypy`とも問題なし。ユーザー確認済み。コミット済み(`48af499`)
  - 余談: このやり取りの中で、`uv run todoapp`実行時に出る`_valueForTIProperty`/`imkxpc_getApplicationProperty`ログについて質問を受けた。調査の結果、macOSのIMKit(日本語入力システム)と`pywebview`が使う`WKWebView`間の既知の相互作用によるもので、他の多数のmacOSアプリ(Flutter・Java Swing・scrcpyなど)でも同様の報告がある無害なシステムログと判断(アプリのバグではなく対応不要)

- ユーザー要望により、メインパネル・編集一覧どちらの`e`キー編集からも共通で開くアイテム編集フォーム(`edit_dialog.py`)の「カテゴリ」選択欄(`ui.select`)で、その選択肢自体(ドロップダウンの各項目)にPRJコード→種別の順でバッジ表示するよう追加(値が空のカテゴリは非表示)。要件確認の経緯:
  - 当初、ダイアログ内の別行にバッジを表示する実装をしたが、ユーザーから「編集画面の中ではなく、カテゴリの選択アイテムに表示する」と指摘を受け、`ui.select`の`option`スロット(ドロップダウンの各選択肢)自体にバッジを出す方式に作り直した
  - 最初の`option`スロット実装は、NiceGUI内部の`_props["options"]`に`prj_code`/`kind`を直接追加する方式だったが、ユーザーが実機で「1回目は表示されるが2回目は表示されないことがある」を発見。原因はNiceGUIの`ChoiceElement.update()`(`ui.select`の内部実装)が`_props["options"]`を毎回`{value,label}`のみへ再構築してしまうことで、`suspend_updates()`+ベースクラスの`Element.update()`直接呼び出しでこれを回避する応急処置をいったん入れたが、非同期の更新処理と競合しうる不安定な実装だった
  - 最終的に、カテゴリ名・PRJコード・種別を1つのラベル文字列に区切り文字(`\x1f`)で埋め込み、`option`スロット・`selected-item`スロットの両方でラベルを分解して表示する方式に変更。NiceGUI標準の`set_options()`フローにそのまま乗るため、内部実装への介入が不要になり安定した
  - 教訓: NiceGUIの`ui.select`で選択肢にカスタムメタデータ(バッジ表示用の追加情報など)を持たせたい場合、`_props["options"]`への直接介入は`ChoiceElement.update()`と競合し不安定になる。ラベル文字列に区切り文字で埋め込みスロット側で分解する方式の方が安全
  - `nicegui.testing.User`を使った一時テストで、同一ダイアログに`open_for()`を複数回連続で呼んでも毎回正しくラベルにメタデータが含まれることを検証(検証用の一時ファイルは削除済み)
  - `uv run pytest`(79件)・`uv run mypy`とも問題なし。ユーザーが実機で複数回の表示安定性を確認済み

- ユーザー要望により、`編集一覧`画面に3種類のフィルタを追加(表示位置は「編集一覧」タイトルと一覧テーブルの間)。要件確認事項:
  - `実行の曜日`フィルタは複数選択可能(未選択なら全種別表示)
  - `基準日`フィルタはデフォルトで本日の日付が入っており、変更すればその日付で絞り込む(空にすれば絞り込みなし)
  - `list_view.py`の`ListView.build()`にフィルタ用の`ui.input`(アイテム名、部分一致)・`ui.select(multiple=True)`(実行の曜日)・`ui.input(type=date)`(基準日、初期値は本日)を追加し、いずれの値変更でも`render.refresh()`を呼んで再描画するようにした。`render()`内で3条件をAND評価してから行を構築する
  - `nicegui.testing.User`を使った一時テストで検証。その過程で「`view.render.refresh()`を呼んだ直後に`_rendered_ids`を読むと、まだ再描画が完了しておらず古い値が見える」という`@ui.refreshable_method`の非同期な挙動に気づいた。これはテストコード側で`await`を挟む必要があるだけで、実装自体のバグではなかった(実際のブラウザ操作では問題にならない)。教訓として、NiceGUIの`refreshable`メソッドの効果をテストで確認する際は、`refresh()`呼び出し直後に同期的に結果を読まず、`asyncio.sleep(0)`を数回挟むなどして完了を待つ必要がある
  - `uv run pytest`(79件)・`uv run mypy`とも問題なし。ユーザーが実機で3種類のフィルタの動作を確認済み

- 上記2件をユーザー確認後、意味のある単位で2つに分けてコミット済み: カテゴリ選択バッジ修正(`9f15d51`)、編集一覧フィルタ追加(`1d86044`)

## 今回(2026-09-02、feature/todo-app-mvpブランチでの作業とdevelopへの再マージ)

- (`feature/todo-app-mvp`ブランチ側で実施。上記の`develop`側の作業とは別セッションで並行して進んでいたため、両ブランチが分岐していた)
- ユーザー要望により、メインパネル・編集一覧・作業ログ・カテゴリ一覧の4画面すべてで`↑`/`↓`キーによる単一選択の切り替えに対応
  - `MainView`/`ListView`/`LogView`/`CategoryListDialog`それぞれに`move_selection(delta: int)`を追加。表示順リスト(`_rendered_item_ids`等)の中で現在の単一選択の位置を求め、±1した位置(先頭・末尾でクランプ、範囲外に出ない)の1件のみを新たな単一選択にする。未選択の状態から`↓`を押すと先頭、`↑`を押すと末尾を選択する
  - `MainView.move_selection`は既存の`_on_row_click`と同様、選択中の`_select_all_active`解除・`_select_anchor_index`更新・`_update_selection_classes`によるCSSクラス差分更新(全体再描画を避けてダブルクリック等との競合を防ぐ既存パターン)を踏襲
  - `KeyboardController`に`e.key.arrow_up`/`arrow_down`の分岐を新設。ESCキーと同じ優先順位(カテゴリ一覧が開いていれば最優先→作業ログが開いていれば次→他のダイアログが開いていれば何もしない→編集一覧/メイン画面)で呼び分ける
  - `NiceGUI`の`ui.keyboard`は入力欄・select・button・textareaにフォーカスがある間グローバルキーを無視する既存仕様により、最下部の新規登録入力欄にフォーカス中は矢印キーがこのハンドラに届かず、テキストカーソル移動と衝突しない
  - `help_dialog.py`・`README.md`・`CLAUDE.md`(todoapp直下、`複数選択・削除`節)にも操作を追記。`uv run pytest`(79件)・`uv run mypy src test`とも問題なし。ドメイン層のロジックは変更していないため新規のドメインテストは追加していない
  - ユーザー要望により、`j`(下)/`k`(上)キーでも同じ選択切り替えができるよう追加(`e.key == "j"`/`"k"`を矢印キー分岐に合流)。`help_dialog.py`・`README.md`・`CLAUDE.md`も追記。`uv run pytest`(79件)・`uv run mypy src test`とも問題なし
  - ユーザーから「`j`/`k`キーを押すと音が鳴る」との報告受領
    - 原因: NiceGUIの`ui.keyboard`(`keyboard.js`)はキーイベントをサーバーに転送するのみで`preventDefault()`を呼ばない。pywebviewのネイティブウィンドウ(WKWebView)ではフォーカス先が無い状態で`j`/`k`等の文字キーを押すと、ブラウザ側の既定動作(テキスト挿入)が処理先を見つけられず、AppKit側でシステム警告音(NSBeep)が鳴ると見られる。矢印キーはカーソル移動系のコマンドとして扱われるため鳴らない
    - 修正: `main.py`の既存のCmd/Ctrl+A抑止スクリプト(`ui.add_body_html`)に、`j`/`k`キー用の`preventDefault()`を追加。`ui.keyboard`がグローバルキーを無視する対象(`input`/`select`/`button`/`textarea`)と同じ判定で、フォーカスが無い間だけ抑止するようにした(テキスト入力欄内での`j`/`k`の通常入力は妨げない)
    - `uv run pytest`(79件)・`uv run mypy src test`とも問題なし
  - ユーザーから続けて「メインパネルの上下キー入力でも音が鳴る」との報告受領。`j`/`k`と同じ原因(WKWebViewでフォーカス先が無い未処理キーがOS側の警告音を鳴らす)と判断し、`main.py`の抑止対象キー(`beepKeys`)に`ArrowUp`/`ArrowDown`を追加
  - ユーザーから「全ての画面でショートカットされているキー入力(`ESC`/`e`/`T`/`DEL`等)で音が鳴らないようにしてほしい」との要望を受け、その場しのぎの追加ではなく`main.py`のpreventDefault対象を`KeyboardController`(`keyboard.py`)がグローバルに処理する全キー(`Escape`/`Enter`/`Backspace`/`Delete`/`ArrowUp`/`ArrowDown`/`e`/`c`/`l`/`g`/`T`/`j`/`k`)に揃えて一元管理するよう整理。あわせて`Cmd/Ctrl+A`以外はmeta/ctrl/altキー併用時を除外する条件を追加(他の修飾キー併用のブラウザ標準ショートカットを誤って奪わないため)
  - ユーザーの実機確認・コミット(`35e8063`)まで完了

- 未追跡だった`.DS_Store`を`.gitignore`に追加(`82a3d21`)

- `develop`側で先行していたPRJコード機能・編集一覧フィルタ(上記「四度目の再開分」まで)と、`feature/todo-app-mvp`側の↑/↓・j/kキー選択切替+ショートカットキーのシステム警告音修正が別々に進んでいたため、`develop`へ`feature/todo-app-mvp`を再マージ。競合したのは本ファイル(`.claude/MEMORY.md`、両ブランチのセッション記録が同じ節に追記されていたため)のみで、コード側(`category_list_dialog.py`・`list_view.py`)はPRJコード列/フィルタ機能行と`move_selection`追加が別箇所のため自動マージされた

## 今回(2026-09-29〜09-30、実行履歴カレンダー機能の追加)の作業

- ユーザー要望により、実行履歴を週次カレンダー表示できる機能を新規追加。NiceGUIには標準のカレンダー要素が無いため、公式リポジトリの`examples/fullcalendar/`(FullCalendarライブラリのVueラッパー)を`src/todoapp/ui/vendor/fullcalendar/`に無改変でベンダリングし(pipパッケージ化はされていないため)、`calendar_view.py`(新規)から利用する方式を採用。`main.py`に`CalendarView`を配線し、`Shift+L`キーでダイアログとして開く
- 開いた直後だけ週7日分のうち1日分しか正しく描画されない不具合が繰り返し発生し、複数回の当てずっぽうなタイミング調整(requestAnimationFrame・ResizeObserver等)では再現性なく解消しなかった。ユーザーから「遅延を微調整という仕様でよいのか」との指摘を受け、方針を転換して`fullcalendar.js`に一時的な計測ログ(要素の幅・クラス名・経過時間等)を仕込み、実測データから原因を特定
  - 真因は2つの独立した非同期処理の競合(レースコンディション): (1)FullCalendar本体(280KB)のロード完了と、(2)NiceGUIのダイアログ(Quasarの`QDialog`)を開いた際の表示アニメーション完了(祖先要素に`transform: scale(0)`相当の`q-dialog__inner--minimized`クラスが一時的に付与される)。カレンダーの構築をダイアログを開いた直後の`on_open`メソッドに一本化し、ライブラリのロード完了と、ダイアログの`transitionend`(アニメーション完了、保険として500msのタイムアウトも用意)の両方を確実に待ってから構築するよう修正して解消した
  - 教訓は`.claude/memory`(auto-memory)の`diagnose-before-guessing-timing-fixes.md`に記録済み
- ダイアログ幅を当初`w-[56rem]`にしていたが、ネイティブウィンドウ(`window_size=(620, 720)`)に対して大きすぎ列が見切れる不具合が発生。他のダイアログと同程度の`w-[36rem]`に修正
- 曜日ヘッダーの折り返しが列ごとに不揃いだったため、`.fc-col-header-cell-cushion`に`white-space: nowrap`を追加して統一
- ユーザー要望により、週次カレンダーに「日曜始まり」「月曜始まり」を切り替えるトグルを追加。`config_repository.py`の`AppConfig`に`week_start`を追加し`~/.todoapp/config.json`に永続化。この際、既存の`_on_theme_change`がconfig全体を毎回新規生成して保存しており、他の設定を上書き消去してしまう潜在バグを発見・修正(共有の`config`オブジェクトを直接書き換える方式に変更)
- ユーザー要望により、土曜を薄い青・日曜を薄いピンクの背景で表示(FullCalendar既定の`fc-day-sat`/`fc-day-sun`クラスを使ったCSS)
- ユーザー要望により、内閣府配布の祝日CSV(`https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv`)から祝日情報を取得し薄い緑の背景(背景イベント)で表示する機能を追加(`holiday_repository.py`新規)。キャッシュ(`~/.todoapp/holidays.json`)が無い初回起動時のみ自動取得、以降はカレンダーダイアログのボタンで手動更新
  - 実装当初`urllib`を使ったところ、この実行環境(uv管理のCPython)ではOSのCA証明書ストアを参照できずSSL証明書検証エラーが発生。`certifi`を明示指定して解消した後、ユーザーからの提案で`httpx`(証明書に`certifi`を既定で使う)に切り替え、手動のssl/certifi配線を削除してシンプルにした(`pyproject.toml`の依存も`httpx`に変更)
- ユーザー要望により、祝日の日付にマウスオーバーすると祝日名をツールチップ表示。当初は日付ヘッダーへの常時テキスト追記だったが、フォントが小さく視認性が悪いとの指摘で撤回し、ホバー時のみのネイティブツールチップ(title属性)に変更
- ユーザー要望により、カレンダーを`当日`/`週`/`月`の3形式で切り替えられるようFullCalendarのheaderToolbarにビュー切替ボタンを追加(`timeGridDay`/`timeGridWeek`/`dayGridMonth`)。月表示で日付をクリックするとその日の当日表示に切り替わる`navLinks`も有効化(クリックした日付が基準になるのが標準動作)
- ユーザー要望により、カレンダー上のブロックはタスク名のみ表示(`displayEventTime: false`)とし、マウスオーバーで「開始/終了/経過時間」をツールチップ表示するよう変更(`format_duration`を再利用、カテゴリの色付けは変更せず維持)
- ユーザー要望により、祝日名ツールチップの表示範囲を統一。当初は日付ヘッダーの文字部分のみに`title`を設定していたため、週表示・日表示では色付き列の大部分でホバーしても出ず月表示と不一致だった。FullCalendarが日付を表す全要素に付与する`data-date`属性を目印に、`datesSet`イベント発火のたびに一括で`title`を反映する方式に統一し、月表示と同じ体験になるよう修正
- `pytest`(90件)・`mypy src test`とも問題なし。ユーザーが実機で各機能を確認済み。コミットは未実施(ユーザー指示により保留中)

## 未実施・今後の検討事項

- `main`へのマージはまだ行っていない

## 運用ルール(このセッションで確定した方針)

- **コミットは実行前に必ずユーザーへ確認を取ること**(以前はタスクの区切りごとに自律的にコミットしていたが、ユーザーからの指示によりこの方針に変更)
- GUIアプリの動作確認スクリーンショットは、デスクトップ全体ではなく`screencapture -x -D2`でセカンダリモニター(画面2)のみを撮影すること
