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
├── domain/        # NiceGUIに依存しないドメインロジック(TodoItem, Category, TodoService等)
├── repository/     # JSON永続化(json_repository.py: todos.json / config_repository.py: config.json)
├── ui/              # NiceGUI画面
│   ├── main_view.py             # メインパネル(一覧・新規登録・テーマFAB・実行中フローティング表示)
│   ├── list_view.py             # 編集一覧
│   ├── log_view.py              # 本日の作業ログ
│   ├── category_*.py            # カテゴリ一覧/編集/種別入力/選択/集計の各ダイアログ
│   ├── edit_dialog.py           # アイテム編集フォーム
│   ├── record_edit_dialog.py    # 記録編集フォーム
│   ├── help_dialog.py           # キー操作ヘルプ
│   ├── confirm_dialog.py        # 共通の削除確認ダイアログ
│   ├── keyboard.py              # グローバルキー操作の振り分け
│   └── app_state.py / formatting.py
└── main.py          # エントリーポイント(画面・ダイアログの組み立て)
```

## 保存先ファイル

| ファイル | 内容 |
|---|---|
| `~/.todoapp/todos.json` | アイテム・実行記録・カテゴリ |
| `~/.todoapp/config.json` | テーマ設定(`auto`/`light`/`dark`) |

## 規約

- `.claude/RULE.md` を参照
