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
├── domain/        # NiceGUIに依存しないドメインロジック(TodoItem, TodoService等)
├── repository/     # JSON永続化(~/.todoapp/todos.json, ~/.todoapp/config.json)
├── ui/              # NiceGUI画面(main_view/edit_dialog/list_view/log_view/keyboard等)
└── main.py          # エントリーポイント
```

## 保存先ファイル

| ファイル | 内容 |
|---|---|
| `~/.todoapp/todos.json` | アイテム・実行記録・カテゴリ |
| `~/.todoapp/config.json` | テーマ設定(`auto`/`light`/`dark`) |

## 規約

- `.claude/RULE.md` を参照
