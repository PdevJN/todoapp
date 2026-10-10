# 開発者向け情報

エンドユーザー向けの説明は [README.md](../README.md) を参照。ここには開発時にしか使わない情報のみをまとめる。

## テスト・型チェック

```bash
uv run pytest --cov=todoapp   # テスト + カバレッジ
uv run mypy src test           # 型チェック(strict)
```

## モジュール構成

```
src/todoapp/
├── domain/        # NiceGUIに依存しないドメインロジック
│   ├── models.py            # TodoItem(完了日done_dateを含む)・Category・ExecutionRecord・is_done()/DoneFilter等
│   ├── service.py           # TodoService(実行・完了・集計・GAP等のユースケース)
│   └── record_layout.py     # 作業ログの時間編集の吸着ロジック(1分単位・隣接記録の境界へ密着)の純粋関数
├── repository/     # JSON永続化(json_repository.py: todos.json / config_repository.py: config.json / holiday_repository.py: holidays.json・祝日CSV取得 / alive_repository.py: alive.json・実行中の生存時刻)
├── ui/              # NiceGUI画面
│   ├── settings_dialog.py       # 設定ダイアログ(`o`キー。現在は標準労働時間のみ)
│   ├── main_view.py             # メインパネル(一覧・完了状態の絞り込み・新規登録・テーマFAB・実行中フローティング表示)
│   ├── list_view.py             # 編集一覧
│   ├── log_view.py              # 本日の作業ログ(実行順/カテゴリ別)
│   ├── record_timeline_dialog.py # 作業ログの時間編集(日表示カレンダー上のドラッグ&ドロップ)
│   ├── calendar_view.py         # 実行履歴のカレンダー表示(当日/週/月、FullCalendar)
│   ├── vendor/fullcalendar/     # FullCalendarのベンダリング(NiceGUI公式exampleを元に、ドラッグ&ドロップの通知・祝日ツールチップ・密着ガイド線などを追加。`lib/ja.global.min.js`は日本語locale)
│   ├── category_summary_dialog.py # 集計画面(カテゴリ別/アイテム別、円グラフ・GAP)
│   ├── category_*.py            # カテゴリ一覧/編集/種別入力/選択の各ダイアログ
│   ├── edit_dialog.py           # アイテム編集フォーム
│   ├── record_edit_dialog.py    # 記録編集フォーム
│   ├── help_dialog.py           # キー操作ヘルプ
│   ├── confirm_dialog.py        # 共通の削除確認ダイアログ
│   ├── keyboard.py              # グローバルキー操作の振り分け(SHORTCUT_KEYSもここ)
│   ├── js_handlers.py           # クライアント側(JS)で処理するイベントハンドラの文字列
│   ├── dialog_base.py           # ダイアログ共通(DialogMixin)
│   └── app_state.py / formatting.py
└── main.py          # エントリーポイント(画面・ダイアログの組み立て、警告音対策のJS)
```

テストは`test/`配下に`src/todoapp/`と同じ構成(`domain`・`repository`・`ui`)で置く。UI部品は、NiceGUIに依存しない純粋関数(系列データの組み立て・色や書式の計算など)に切り出してテストする。

## 保存先ファイル

| ファイル | 内容 |
|---|---|
| `~/.todoapp/todos.json` | アイテム(完了日を含む)・実行記録・カテゴリ |
| `~/.todoapp/config.json` | テーマ設定(`auto`/`light`/`dark`)・週次カレンダーの週の開始曜日・標準労働時間 |
| `~/.todoapp/holidays.json` | 祝日データのキャッシュ(内閣府CSVから取得) |
| `~/.todoapp/alive.json` | 実行中の最後に動作していた時刻(約10秒ごとに更新。再起動時の停止時刻に使う) |

## キー操作を追加するとき

1. `ui/keyboard.py`の`KeyboardController`に処理を追加する
2. `ui/keyboard.py`の`SHORTCUT_KEYS`にそのキーを追加する(`main.py`がこれをJSへ埋め込み、フォーカスが無い間のキーを`preventDefault()`する。漏れると、ネイティブウィンドウ(WKWebView)でシステム警告音が鳴る。`test/ui/test_keyboard.py`が単一文字キーの登録漏れを検出する)
3. `ui/help_dialog.py`のキー一覧と、`README.md`のキー操作表、`CLAUDE.md`の仕様を更新する

## 規約

- `.claude/RULE.md` を参照
