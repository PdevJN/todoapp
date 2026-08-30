# 作業状況メモ

最終更新: 2026-08-30(カテゴリ一覧にカテゴリ登録機能を追加)

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

## 未実施・今後の検討事項

- `develop`や`main`へのマージはまだ行っていない

## 運用ルール(このセッションで確定した方針)

- **コミットは実行前に必ずユーザーへ確認を取ること**(以前はタスクの区切りごとに自律的にコミットしていたが、ユーザーからの指示によりこの方針に変更)
- GUIアプリの動作確認スクリーンショットは、デスクトップ全体ではなく`screencapture -x -D2`でセカンダリモニター(画面2)のみを撮影すること
