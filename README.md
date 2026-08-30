# todoapp

シンプルなTODOリストとタイマー計測ができるネイティブアプリ。詳細な機能仕様は [CLAUDE.md](./CLAUDE.md) を参照。

## セットアップ

```bash
uv sync
```

## 起動

```bash
uv run todoapp
```

pywebviewによるネイティブウィンドウが起動する。

## キーボード操作

| キー / 操作 | 機能 |
|---|---|
| 最下部入力欄 + `Enter` | アイテムの新規登録 |
| `Enter` / ダブルクリック | 選択中アイテムの実行・停止トグル |
| `e` | 選択中アイテムの編集フォーム表示 |
| `c` | 選択中アイテムの実行キャンセル |
| `l` | 本日の作業ログ表示 |
| `ESC` | 選択中は選択解除(メイン画面・編集一覧・カテゴリ一覧)。未選択ならメイン画面⇔編集一覧の切り替え、またはカテゴリ一覧を閉じる |

## 開発

```bash
uv run pytest --cov=todoapp   # テスト + カバレッジ
uv run mypy src test           # 型チェック(strict)
```

## 構成

```
src/todoapp/
├── domain/        # NiceGUIに依存しないドメインロジック(TodoItem, TodoService等)
├── repository/     # JSON永続化(~/.todoapp/todos.json)
├── ui/              # NiceGUI画面(main_view/edit_dialog/list_view/log_view/keyboard)
└── main.py          # エントリーポイント
```
