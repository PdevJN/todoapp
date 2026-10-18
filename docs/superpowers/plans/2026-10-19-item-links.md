# アイテムのリンク機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** アイテムに複数のリンクを付け、URL雛形(テンプレート)の置換項目を入力して、一覧のアイコンから開けるようにする。

**Architecture:** ドメイン(`models.py`)にリンク型・URL組み立て・検証を純粋関数として置き、`TodoService`がテンプレートとアイテムのリンクを保存する。保存はスキーマv2(`MIGRATIONS[1]`)。UIは、一覧のリンクアイコン(`ui/item_links.py`)、編集フォームのリンク欄(`ui/link_rows_editor.py`)、`u`キーのテンプレート管理ダイアログ(`ui/link_template_dialog.py`)を追加する。

**Tech Stack:** Python 3.13、NiceGUI、pytest、mypy(strict)、uv。

**Spec:** `docs/superpowers/specs/2026-10-19-item-links-design.md`

## Global Constraints

- コマンドは`uv run pytest`・`uv run mypy src test`(作業ディレクトリは`/Users/jun/Documents/opt/work/todoapp`)。
- すべての関数に型ヒントを付ける(`.claude/RULE.md`)。コメントは多くても3行以内。コード中のコメントは日本語で、周囲と同じ密度にする。
- 置換項目は`{名前}`(名前は半角英数字と`_`)、1テンプレート1〜5個。
- 入力上限: テンプレート名30、URL雛形500、リンクの表示名30、直接入力のURL500、置換項目の値200、組み立てたURL2000(Pythonの`len`)。
- URL雛形・直接入力のURLは、ASCII文字のみ・空白不可・`http://`か`https://`で始まる。全角の`｛``｝`を含む場合は専用メッセージで警告する。
- 制御文字の判定は`has_control_chars()`を使う。保存済みデータは読み込み時に検証しない。サービス層は検証せず、画面側で検証してから呼ぶ。
- スキーマは`SCHEMA_VERSION = 2`、`MIGRATIONS[1]`で`link_templates: []`と各アイテムの`links: []`を補う。
- キー`u`はメイン画面のみ・ダイアログ表示中は無効。`SHORTCUT_KEYS`・ヘルプ・`README.md`に追加する。
- リンクは`webbrowser.open()`(サーバー側)で開く。開く直前に必ず`resolve_link_url()`を通し、`None`なら開かず警告する。
- **コミット前にユーザーへ確認する**(このプロジェクトの規約)。各Taskの「Commit」ステップは、確認を取ってから実行する。`main`へのPRは作らない。
- GUIの動作確認はユーザーが手動で行う(Task 7のチェックリスト)。AppleScript等の自動操作はしない。

## Review Focus

- 値に`/ ? # & 空白 日本語 {id}`を含む → URLエンコードされ、パスやクエリを壊さず、`{id}`が再展開されない(Task 1)。
- 直接入力URLが`javascript:`・`file:`など`http(s)`以外 → 保存できず、手編集した`todos.json`に混ざっていても開けない(Task 1・4)。
- テンプレートの置換項目を後から変えた → 既存リンクは未入力として扱われ、落ちずに警告だけ出る(Task 1・4)。
- 200文字の日本語を置換項目に入れて組み立てたURLが2000文字を超える → エラーで保存されず、落ちない(Task 1)。
- テンプレートを使うリンクがあるまま削除 → 確認のうえリンクごと消え、アイテム側に壊れたリンクが残らない(Task 3・6)。

---

### Task 1: ドメイン: リンクの型・URL組み立て・検証

**Files:**
- Modify: `src/todoapp/domain/models.py`
- Test: `test/domain/test_link_models.py`(新規)

**Interfaces:**
- Produces(後続Taskが使う。名前と型は固定):
  - `LinkTemplate(name: str, url_template: str, id: str)` / `.to_dict()` / `.from_dict(data)`
  - `ItemLink(name: str, template_id: str | None = None, url: str = "", values: dict[str, str], id: str)` / `.to_dict()` / `.from_dict(data)`
  - `template_placeholders(url_template: str) -> list[str]`
  - `resolve_link_url(link: ItemLink, templates: Iterable[LinkTemplate]) -> str | None`
  - `validate_link_template_fields(name: str, url_template: str) -> str | None`
  - `validate_item_link_fields(name: str, template: LinkTemplate | None, url: str, values: dict[str, str]) -> str | None`
  - 定数: `LINK_TEMPLATE_NAME_MAX_LENGTH=30`・`LINK_NAME_MAX_LENGTH=30`・`LINK_URL_MAX_LENGTH=500`・`LINK_VALUE_MAX_LENGTH=200`・`LINK_RESOLVED_URL_MAX_LENGTH=2000`・`LINK_MAX_PLACEHOLDERS=5`

- [ ] **Step 1: 失敗するテストを書く**

`test/domain/test_link_models.py`を新規作成:

```python
import pytest

from todoapp.domain.models import (
    ItemLink,
    LinkTemplate,
    resolve_link_url,
    template_placeholders,
    validate_item_link_fields,
    validate_link_template_fields,
)

JIRA = LinkTemplate(name="Jira", url_template="https://example.com/{project}/issues/{id}")


def test_template_placeholders_are_unique_in_first_appearance_order() -> None:
    assert template_placeholders("https://x/{b}/{a}/{b}?q={a}") == ["b", "a"]


def test_template_placeholders_ignore_invalid_names() -> None:
    assert template_placeholders("https://x/{a b}/{}/{id}") == ["id"]


def test_link_template_roundtrips_through_dict() -> None:
    assert LinkTemplate.from_dict(JIRA.to_dict()) == JIRA


def test_item_link_roundtrips_through_dict() -> None:
    link = ItemLink(name="チケット", template_id=JIRA.id, values={"project": "P", "id": "1"})
    assert ItemLink.from_dict(link.to_dict()) == link


def test_resolve_direct_url() -> None:
    link = ItemLink(name="資料", url="https://example.com/doc")
    assert resolve_link_url(link, []) == "https://example.com/doc"


def test_resolve_fills_all_placeholders() -> None:
    link = ItemLink(name="t", template_id=JIRA.id, values={"project": "PRJ", "id": "12"})
    assert resolve_link_url(link, [JIRA]) == "https://example.com/PRJ/issues/12"


def test_resolve_replaces_repeated_placeholder_everywhere() -> None:
    template = LinkTemplate(name="t", url_template="https://x/{id}/edit?ref={id}")
    link = ItemLink(name="t", template_id=template.id, values={"id": "7"})
    assert resolve_link_url(link, [template]) == "https://x/7/edit?ref=7"


def test_resolve_url_encodes_special_characters() -> None:
    link = ItemLink(name="t", template_id=JIRA.id, values={"project": "P", "id": "a/b?c#d&e 日本"})
    url = resolve_link_url(link, [JIRA])
    assert url == "https://example.com/P/issues/a%2Fb%3Fc%23d%26e%20%E6%97%A5%E6%9C%AC"


def test_resolve_does_not_expand_placeholder_inside_a_value() -> None:
    link = ItemLink(name="t", template_id=JIRA.id, values={"project": "{id}", "id": "1"})
    assert resolve_link_url(link, [JIRA]) == "https://example.com/%7Bid%7D/issues/1"


@pytest.mark.parametrize("values", [{"project": "P"}, {"project": "P", "id": ""}, {"project": "P", "id": "  "}])
def test_resolve_returns_none_when_a_value_is_missing_or_blank(values: dict[str, str]) -> None:
    link = ItemLink(name="t", template_id=JIRA.id, values=values)
    assert resolve_link_url(link, [JIRA]) is None


def test_resolve_returns_none_when_template_is_missing() -> None:
    link = ItemLink(name="t", template_id="gone", values={"project": "P", "id": "1"})
    assert resolve_link_url(link, [JIRA]) is None


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "ftp://example.com", ""])
def test_resolve_rejects_non_http_schemes(url: str) -> None:
    assert resolve_link_url(ItemLink(name="t", url=url), []) is None


def test_resolve_accepts_uppercase_scheme() -> None:
    assert resolve_link_url(ItemLink(name="t", url="HTTPS://example.com"), []) == "HTTPS://example.com"


def test_validate_template_accepts_valid_input() -> None:
    assert validate_link_template_fields("Jira", "https://example.com/{project}/{id}") is None


@pytest.mark.parametrize(
    ("name", "url_template", "expected"),
    [
        ("", "https://x/{id}", "テンプレート名"),
        ("a\tb", "https://x/{id}", "制御文字"),
        ("a" * 31, "https://x/{id}", "30文字以内"),
        ("n", "https://x/｛id｝", "全角の｛ ｝"),
        ("n", "https://x/日本/{id}", "ASCII以外"),
        ("n", "https://x/ {id}", "空白"),
        ("n", "https://x/{id}" + "a" * 500, "500文字以内"),
        ("n", "ftp://x/{id}", "http://"),
        ("n", "https://x/", "1つ以上"),
        ("n", "https://x/{id", "書いてください"),
        ("n", "https://x/{}", "書いてください"),
        ("n", "https://x/{a-b}", "書いてください"),
        ("n", "https://x/{a}{b}{c}{d}{e}{f}", "5個まで"),
    ],
)
def test_validate_template_rejects_invalid_input(name: str, url_template: str, expected: str) -> None:
    error = validate_link_template_fields(name, url_template)
    assert error is not None
    assert expected in error


def test_validate_template_accepts_five_placeholders() -> None:
    assert validate_link_template_fields("n", "https://x/{a}/{b}/{c}/{d}/{e}") is None


def test_validate_link_accepts_direct_url_and_template_values() -> None:
    assert validate_item_link_fields("資料", None, "https://example.com/doc", {}) is None
    assert validate_item_link_fields("t", JIRA, "", {"project": "P", "id": "1"}) is None


@pytest.mark.parametrize(
    ("name", "url", "expected"),
    [
        ("", "https://example.com", "表示名"),
        ("a\nb", "https://example.com", "制御文字"),
        ("a" * 31, "https://example.com", "30文字以内"),
        ("n", "", "URL"),
        ("n", "javascript:alert(1)", "http://"),
        ("n", "https://example.com/日本", "ASCII以外"),
    ],
)
def test_validate_direct_link_rejects_invalid_input(name: str, url: str, expected: str) -> None:
    error = validate_item_link_fields(name, None, url, {})
    assert error is not None
    assert expected in error


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"project": "P"}, "id"),
        ({"project": "P", "id": "a\tb"}, "制御文字"),
        ({"project": "P", "id": "a" * 201}, "200文字以内"),
    ],
)
def test_validate_template_link_rejects_invalid_values(values: dict[str, str], expected: str) -> None:
    error = validate_item_link_fields("t", JIRA, "", values)
    assert error is not None
    assert expected in error


def test_validate_template_link_rejects_too_long_resolved_url() -> None:
    template = LinkTemplate(name="t", url_template="https://x/{a}/{b}")
    values = {"a": "あ" * 200, "b": "あ" * 200}
    error = validate_item_link_fields("t", template, "", values)
    assert error is not None
    assert "2000" in error
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_link_models.py -q`
Expected: FAIL(`ImportError: cannot import name 'ItemLink'`)

- [ ] **Step 3: 実装する**

`src/todoapp/domain/models.py`の先頭のimportを次のように変える:

```python
import calendar
import random
import re
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any
from urllib.parse import quote
```

`_PRJ_CODE_PATTERN`の定義の直後に定数を追加:

```python
LINK_TEMPLATE_NAME_MAX_LENGTH = 30
LINK_NAME_MAX_LENGTH = 30
LINK_URL_MAX_LENGTH = 500
LINK_VALUE_MAX_LENGTH = 200
LINK_RESOLVED_URL_MAX_LENGTH = 2000
LINK_MAX_PLACEHOLDERS = 5
_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_]+)\}")
_URL_SCHEMES = ("http://", "https://")
```

`Category`クラスの直後(`def has_control_chars`の前)に追加:

```python
@dataclass
class LinkTemplate:
    name: str
    url_template: str  # 例: https://example.com/{project}/issues/{id}
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "url_template": self.url_template}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> LinkTemplate:
        return LinkTemplate(
            id=data.get("id") or uuid.uuid4().hex, name=data["name"], url_template=data["url_template"]
        )


@dataclass
class ItemLink:
    name: str
    template_id: str | None = None  # Noneはテンプレートを使わず、`url`を直接開く
    url: str = ""
    values: dict[str, str] = field(default_factory=dict)  # テンプレート使用時の{置換項目名: 値}
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "template_id": self.template_id,
            "url": self.url,
            "values": dict(self.values),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ItemLink:
        return ItemLink(
            id=data.get("id") or uuid.uuid4().hex,
            name=data["name"],
            template_id=data.get("template_id"),
            url=data.get("url", ""),
            values=dict(data.get("values", {})),
        )
```

`is_category_expired`の直後に追加:

```python
def template_placeholders(url_template: str) -> list[str]:
    """URL雛形の置換項目名を、最初に現れた順に重複なく返す。"""
    return list(dict.fromkeys(_PLACEHOLDER_PATTERN.findall(url_template)))


def _is_http_url(url: str) -> bool:
    return url.lower().startswith(_URL_SCHEMES)


def resolve_link_url(link: ItemLink, templates: Iterable[LinkTemplate]) -> str | None:
    """リンクを開くURLを返す。置換項目が未入力・テンプレートが無い・http(s)以外の場合は`None`。"""
    if link.template_id is None:
        url = link.url
    else:
        template = next((t for t in templates if t.id == link.template_id), None)
        if template is None:
            return None
        names = template_placeholders(template.url_template)
        if any(not link.values.get(name, "").strip() for name in names):
            return None
        url = _PLACEHOLDER_PATTERN.sub(lambda m: quote(link.values[m.group(1)], safe=""), template.url_template)
    return url if _is_http_url(url) else None


def _validate_url_text(label: str, url: str) -> str | None:
    if not url:
        return f"{label}を入力してください"
    if has_control_chars(url):
        return f"{label}に制御文字は使えません"
    if "｛" in url or "｝" in url:
        return f"{label}に全角の｛ ｝は使えません。半角の {{ }} を使ってください"
    if not url.isascii():
        return f"{label}に全角などASCII以外の文字は使えません(日本語はエンコード済みの形で入力してください)"
    if any(ch.isspace() for ch in url):
        return f"{label}に空白は使えません"
    if len(url) > LINK_URL_MAX_LENGTH:
        return f"{label}は{LINK_URL_MAX_LENGTH}文字以内で入力してください"
    if not _is_http_url(url):
        return f"{label}は http:// または https:// で始めてください"
    return None


def _validate_label_text(label: str, text: str, limit: int) -> str | None:
    if not text:
        return f"{label}を入力してください"
    if has_control_chars(text):
        return f"{label}に制御文字は使えません"
    if len(text) > limit:
        return f"{label}は{limit}文字以内で入力してください"
    return None


def validate_link_template_fields(name: str, url_template: str) -> str | None:
    """リンクテンプレートの入力値を検証する。問題があればその内容(表示用メッセージ)を、無ければNoneを返す。"""
    error = _validate_label_text("テンプレート名", name, LINK_TEMPLATE_NAME_MAX_LENGTH)
    if error is not None:
        return error
    error = _validate_url_text("URL雛形", url_template)
    if error is not None:
        return error
    leftover = _PLACEHOLDER_PATTERN.sub("", url_template)
    if "{" in leftover or "}" in leftover:
        return "置換項目は {名前}(名前は半角英数字と _ のみ)の形で書いてください"
    count = len(template_placeholders(url_template))
    if count == 0:
        return "置換項目 {名前} を1つ以上入れてください"
    if count > LINK_MAX_PLACEHOLDERS:
        return f"置換項目は{LINK_MAX_PLACEHOLDERS}個までです"
    return None


def validate_item_link_fields(
    name: str, template: LinkTemplate | None, url: str, values: dict[str, str]
) -> str | None:
    """アイテムのリンクの入力値を検証する。呼び出し側で前後の空白を除いた値を渡す。"""
    error = _validate_label_text("リンクの表示名", name, LINK_NAME_MAX_LENGTH)
    if error is not None:
        return error
    if template is None:
        return _validate_url_text("URL", url)
    for placeholder in template_placeholders(template.url_template):
        error = _validate_label_text(placeholder, values.get(placeholder, ""), LINK_VALUE_MAX_LENGTH)
        if error is not None:
            return error
    resolved = resolve_link_url(ItemLink(name=name, template_id=template.id, values=values), [template])
    if resolved is None:
        return "URLを組み立てられません。テンプレートのURL雛形を確認してください"
    if len(resolved) > LINK_RESOLVED_URL_MAX_LENGTH:
        return f"組み立てたURLは{LINK_RESOLVED_URL_MAX_LENGTH}文字以内にしてください"
    return None
```

- [ ] **Step 4: 通ることを確認する**

Run: `uv run pytest test/domain/test_link_models.py -q && uv run mypy src test`
Expected: PASS / `Success: no issues found`

(`test_validate_link...`のうち`{"project": "P"}`の期待`id`は、`id を入力してください`に含まれる。)

- [ ] **Step 5: Commit(確認を取ってから)**

```bash
git add src/todoapp/domain/models.py test/domain/test_link_models.py
git commit -m "feat: リンクテンプレート・アイテムのリンクの型とURL組み立て・検証を追加"
```

---

### Task 2: 保存データ: シリアライズとスキーマv2の移行

**Files:**
- Modify: `src/todoapp/domain/models.py`(`TodoItem`・`AppData`)
- Modify: `src/todoapp/repository/json_repository.py`
- Modify: `test/repository/test_json_repository.py`
- Test: `test/repository/test_json_repository.py`

**Interfaces:**
- Consumes: Task 1の`ItemLink`・`LinkTemplate`。
- Produces: `TodoItem.links: list[ItemLink]`、`AppData.link_templates: list[LinkTemplate]`、`SCHEMA_VERSION == 2`。

- [ ] **Step 1: 失敗するテストを書く**

`test/repository/test_json_repository.py`のimportを`from todoapp.domain.models import AppData, ExecutionRecord, ItemLink, LinkTemplate, ScheduleType, TodoItem`と`from todoapp.repository.json_repository import SCHEMA_VERSION, JsonTodoRepository, UnsupportedSchemaVersionError`に直し、末尾に追加:

```python
def test_save_then_load_roundtrips_links_and_templates(tmp_path: Path) -> None:
    repository = JsonTodoRepository(path=tmp_path / "todos.json")
    template = LinkTemplate(name="Jira", url_template="https://example.com/{project}/{id}")
    item = TodoItem(
        name="散歩",
        schedule_type=ScheduleType.DAILY,
        anchor_date=date(2026, 8, 24),
        links=[
            ItemLink(name="チケット", template_id=template.id, values={"project": "P", "id": "1"}),
            ItemLink(name="資料", url="https://example.com/doc"),
        ],
    )
    data = AppData(items=[item], records=[], link_templates=[template])
    repository.save(data)

    assert repository.load() == data
    assert json.loads((tmp_path / "todos.json").read_text(encoding="utf-8"))["version"] == 2


def test_load_migrates_v1_file_and_keeps_pre_migration_copy(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    item = {"id": "i1", "name": "散歩", "schedule_type": "daily", "anchor_date": "2026-08-24", "estimate_hours": 0.0}
    path.write_text(
        json.dumps({"version": 1, "items": [item], "records": [], "categories": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    original = path.read_text(encoding="utf-8")

    loaded = JsonTodoRepository(path=path).load()

    assert loaded.items[0].name == "散歩"
    assert loaded.items[0].links == []
    assert loaded.link_templates == []
    assert (tmp_path / "todos.json.v1.bak").read_text(encoding="utf-8") == original
```

既存テストが新しい版(SCHEMA_VERSION=2)に合うよう、次の2か所を直す:

```python
# _rename_legacy_name の最終行
    return {**raw, "version": SCHEMA_VERSION, "items": items}
```
```python
# test_load_rejects_newer_version_without_touching_file 内
    _write_raw(path, version=SCHEMA_VERSION + 1)
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/repository/test_json_repository.py -q`
Expected: FAIL(`TypeError: ... unexpected keyword argument 'links'` など)

- [ ] **Step 3: 実装する**

`TodoItem`のフィールドに`skip_date`の次の行で追加(`id`の前):

```python
    links: list[ItemLink] = field(default_factory=list)
```
`to_dict`の辞書の末尾(`"skip_date"`の次)に`"links": [link.to_dict() for link in self.links],`、`from_dict`の`TodoItem(...)`の引数末尾に`links=[ItemLink.from_dict(link) for link in data.get("links", [])],`を追加。

`AppData`に追加:

```python
    link_templates: list[LinkTemplate] = field(default_factory=list)
```

`src/todoapp/repository/json_repository.py`:

```python
from todoapp.domain.models import AppData, Category, ExecutionRecord, LinkTemplate, TodoItem

SCHEMA_VERSION = 2
```
`MIGRATIONS`の定義の前に移行関数を置き、辞書を書き換える:

```python
def _migrate_v1_to_v2(raw: dict[str, Any]) -> dict[str, Any]:
    """v2でリンクテンプレート(`link_templates`)とアイテムのリンク(`links`)を追加した。"""
    items = [{**item, "links": []} for item in raw["items"]]
    return {**raw, "version": 2, "items": items, "link_templates": []}


MIGRATIONS: dict[int, Migration] = {1: _migrate_v1_to_v2}
```
`_read`の末尾を:

```python
        categories = [Category.from_dict(category) for category in raw.get("categories", [])]
        link_templates = [LinkTemplate.from_dict(template) for template in raw.get("link_templates", [])]
        return AppData(items=items, records=records, categories=categories, link_templates=link_templates)
```
`save`のpayloadに`"link_templates": [template.to_dict() for template in data.link_templates],`を追加。

- [ ] **Step 4: 全体が通ることを確認する**

Run: `uv run pytest -q -x && uv run mypy src test`
Expected: PASS。`to_dict`の完全一致を比較している既存テストが落ちた場合は、期待値に`"links": []`を足して直す。

- [ ] **Step 5: Commit(確認を取ってから)**

```bash
git add src/todoapp/domain/models.py src/todoapp/repository/json_repository.py test/repository/test_json_repository.py
git commit -m "feat: リンクを保存データ(スキーマv2)に追加し、v1からの移行を用意"
```

---

### Task 3: サービス: テンプレートの管理とアイテムのリンク設定

**Files:**
- Modify: `src/todoapp/domain/service.py`
- Test: `test/domain/test_service.py`

**Interfaces:**
- Consumes: Task 1・2の型。
- Produces(`TodoService`のメソッド):
  - `link_templates -> list[LinkTemplate]`(プロパティ)
  - `add_link_template(name: str, url_template: str) -> LinkTemplate`
  - `edit_link_template(template_id: str, *, name: str, url_template: str) -> None`
  - `linked_link_count(template_ids: Iterable[str]) -> int`
  - `delete_link_templates(template_ids: Iterable[str]) -> None`(使うリンクもアイテムから削除する)
  - `set_item_links(item_id: str, links: list[ItemLink]) -> None`
  - `link_url(link: ItemLink) -> str | None`

- [ ] **Step 1: 失敗するテストを書く**

`test/domain/test_service.py`のimportに`ItemLink`を足し(`from todoapp.domain.models import AppData, DoneFilter, ItemLink, ScheduleType`)、末尾に追加:

```python
def test_add_and_edit_link_template_saves() -> None:
    service, repository, _ = _service()
    template = service.add_link_template("Jira", "https://example.com/{id}")
    assert service.link_templates == [template]
    service.edit_link_template(template.id, name="Jira2", url_template="https://example.com/{project}/{id}")
    assert (template.name, template.url_template) == ("Jira2", "https://example.com/{project}/{id}")
    assert repository.saved is not None
    assert repository.saved.link_templates == [template]


def test_set_item_links_replaces_links_and_saves() -> None:
    service, repository, _ = _service()
    item = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    links = [ItemLink(name="資料", url="https://example.com/doc")]
    service.set_item_links(item.id, links)
    assert item.links == links
    assert repository.saved is not None
    assert repository.saved.items[0].links == links


def test_link_url_resolves_through_registered_templates() -> None:
    service, _, _ = _service()
    template = service.add_link_template("Jira", "https://example.com/{id}")
    link = ItemLink(name="t", template_id=template.id, values={"id": "9"})
    assert service.link_url(link) == "https://example.com/9"


def test_delete_link_templates_removes_links_that_use_them() -> None:
    service, _, _ = _service()
    jira = service.add_link_template("Jira", "https://example.com/{id}")
    wiki = service.add_link_template("Wiki", "https://wiki.example.com/{id}")
    item = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    other = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    keep = ItemLink(name="資料", url="https://example.com/doc")
    service.set_item_links(item.id, [ItemLink(name="j", template_id=jira.id, values={"id": "1"}), keep])
    service.set_item_links(other.id, [ItemLink(name="w", template_id=wiki.id, values={"id": "2"})])

    assert service.linked_link_count([jira.id]) == 1
    assert service.linked_link_count([jira.id, wiki.id]) == 2

    service.delete_link_templates([jira.id])

    assert service.link_templates == [wiki]
    assert item.links == [keep]
    assert len(other.links) == 1
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_service.py -q -k link`
Expected: FAIL(`AttributeError: 'TodoService' object has no attribute 'add_link_template'`)

- [ ] **Step 3: 実装する**

`service.py`のimportの`models`ブロックに`ItemLink`・`LinkTemplate`・`resolve_link_url`を追加。`categories`プロパティの後に:

```python
    @property
    def link_templates(self) -> list[LinkTemplate]:
        return self._data.link_templates
```
`_find_category`の後に:

```python
    def _find_link_template(self, template_id: str) -> LinkTemplate:
        for template in self._data.link_templates:
            if template.id == template_id:
                return template
        raise KeyError(template_id)
```
`category_for_item`の近く(カテゴリ操作の並び)に:

```python
    def add_link_template(self, name: str, url_template: str) -> LinkTemplate:
        template = LinkTemplate(name=name, url_template=url_template)
        self._data.link_templates.append(template)
        self._save()
        return template

    def edit_link_template(self, template_id: str, *, name: str, url_template: str) -> None:
        template = self._find_link_template(template_id)
        template.name = name
        template.url_template = url_template
        self._save()

    def linked_link_count(self, template_ids: Iterable[str]) -> int:
        ids = set(template_ids)
        return sum(1 for item in self._data.items for link in item.links if link.template_id in ids)

    def delete_link_templates(self, template_ids: Iterable[str]) -> None:
        """テンプレートを削除する。それを使うリンクも、値だけでは開けないためアイテムから削除する。"""
        ids = set(template_ids)
        self._data.link_templates = [t for t in self._data.link_templates if t.id not in ids]
        for item in self._data.items:
            item.links = [link for link in item.links if link.template_id not in ids]
        self._save()

    def set_item_links(self, item_id: str, links: list[ItemLink]) -> None:
        self._find_item(item_id).links = links
        self._save()

    def link_url(self, link: ItemLink) -> str | None:
        return resolve_link_url(link, self._data.link_templates)
```

- [ ] **Step 4: 通ることを確認する**

Run: `uv run pytest test/domain -q && uv run mypy src test`
Expected: PASS

- [ ] **Step 5: Commit(確認を取ってから)**

```bash
git add src/todoapp/domain/service.py test/domain/test_service.py
git commit -m "feat: リンクテンプレートの管理とアイテムのリンク設定をサービスに追加"
```

---

### Task 4: 一覧のリンクアイコン(メインパネル・編集一覧)

**Files:**
- Create: `src/todoapp/ui/item_links.py`
- Modify: `src/todoapp/ui/main_view.py:394`(アイテム名ラベルの直後)
- Modify: `src/todoapp/ui/list_view.py`(`COLUMNS`の下のslot・`render`の行・イベント)
- Test: `test/ui/test_item_links.py`(新規)

**Interfaces:**
- Consumes: Task 1・3の`resolve_link_url`・`TodoService.link_url`・`link_templates`。
- Produces:
  - `LinkEntry(link_id: str, name: str, url: str | None)`(NamedTuple、`.label`プロパティ。開けない場合は`名前(未入力)`)
  - `build_link_entries(item: TodoItem, templates: Iterable[LinkTemplate]) -> list[LinkEntry]`
  - `open_link_url(url: str | None, opener: Callable[[str], object]) -> bool`
  - `open_link(url: str | None) -> None`(開けなければ警告を表示)
  - `render_link_button(entries: list[LinkEntry]) -> None`

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_item_links.py`を新規作成:

```python
import webbrowser

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from test.ui.harness import AppEnv, make_item, press
from todoapp.domain.models import ItemLink, LinkTemplate
from todoapp.ui.item_links import build_link_entries, open_link_url

JIRA = LinkTemplate(name="Jira", url_template="https://example.com/{id}")


def test_build_link_entries_marks_unopenable_links() -> None:
    item = make_item(
        "A",
        links=[
            ItemLink(name="チケット", template_id=JIRA.id, values={"id": "1"}),
            ItemLink(name="空", template_id=JIRA.id, values={}),
            ItemLink(name="危険", url="javascript:alert(1)"),
        ],
    )
    entries = build_link_entries(item, [JIRA])
    assert [e.url for e in entries] == ["https://example.com/1", None, None]
    assert [e.label for e in entries] == ["チケット", "空(未入力)", "危険(未入力)"]


def test_open_link_url_calls_opener_only_for_a_url() -> None:
    opened: list[str] = []
    assert open_link_url("https://example.com", opened.append) is True
    assert open_link_url(None, opened.append) is False
    assert opened == ["https://example.com"]


def _link_buttons(user: User) -> list[ui.button]:
    return [b for b in user.find(kind=ui.button).elements if b.props.get("icon") == "link"]


async def test_main_panel_shows_one_link_icon_per_item_with_links(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(
        items=[
            make_item("リンクあり", links=[ItemLink(name="資料", url="https://example.com/doc")]),
            make_item("リンクなし"),
        ]
    )
    await app_user.open("/")
    assert len(_link_buttons(app_user)) == 1


async def test_clicking_a_single_link_opens_it_in_the_browser(
    app_user: User, app_env: AppEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    app_env.seed(items=[make_item("A", links=[ItemLink(name="資料", url="https://example.com/doc")])])
    await app_user.open("/")

    UserInteraction(app_user, set(_link_buttons(app_user)), None).trigger("click")

    assert opened == ["https://example.com/doc"]


async def test_multiple_links_show_a_menu_entry_for_each_link(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(
        items=[
            make_item(
                "A",
                links=[
                    ItemLink(name="資料1", url="https://example.com/1"),
                    ItemLink(name="資料2", url="https://example.com/2"),
                ],
            )
        ]
    )
    await app_user.open("/")
    menu_items = [m for m in app_user.find(kind=ui.menu_item).elements]
    assert sorted(m.text for m in menu_items) == ["資料1", "資料2"]


async def test_list_view_rows_carry_link_entries(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("A", links=[ItemLink(name="資料", url="https://example.com/doc")])])
    await app_user.open("/")
    await press(app_user, "Escape")  # 編集一覧へ切り替え

    tables = [t for t in app_user.find(kind=ui.table).elements if any("links" in row for row in t.rows)]
    assert len(tables) == 1
    assert tables[0].rows[0]["links"] == [{"id": tables[0].rows[0]["links"][0]["id"], "label": "資料"}]
```


- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_item_links.py -q`
Expected: FAIL(`ModuleNotFoundError: No module named 'todoapp.ui.item_links'`)

- [ ] **Step 3: `ui/item_links.py`を実装する**

```python
from __future__ import annotations

import webbrowser
from collections.abc import Callable, Iterable
from typing import NamedTuple

from nicegui import ui

from todoapp.domain.models import LinkTemplate, TodoItem, resolve_link_url

UNOPENABLE_MESSAGE = "リンクを開けません(未入力の項目があるか、テンプレートが削除されています)"


class LinkEntry(NamedTuple):
    link_id: str
    name: str
    url: str | None  # 開けない場合はNone

    @property
    def label(self) -> str:
        return self.name if self.url is not None else f"{self.name}(未入力)"


def build_link_entries(item: TodoItem, templates: Iterable[LinkTemplate]) -> list[LinkEntry]:
    registered = list(templates)
    return [LinkEntry(link.id, link.name, resolve_link_url(link, registered)) for link in item.links]


def open_link_url(url: str | None, opener: Callable[[str], object]) -> bool:
    if url is None:
        return False
    opener(url)
    return True


def open_link(url: str | None) -> None:
    # ネイティブウィンドウ(WKWebView)では新規タブ遷移が動かないため、サーバー側で既定のブラウザを開く
    if not open_link_url(url, webbrowser.open):
        ui.notify(UNOPENABLE_MESSAGE, type="warning")


def render_link_button(entries: list[LinkEntry]) -> None:
    """アイテム名の隣のリンクアイコン。1件はクリックで直接、2件以上はメニューで選んで開く。"""
    if not entries:
        return
    # 行のクリック(選択)・ダブルクリック(実行)へ伝えないよう、ラッパーで止める
    wrapper = ui.element("div").classes("inline-flex")
    wrapper.on("click.stop", lambda: None)
    wrapper.on("dblclick.stop", lambda: None)
    with wrapper:
        if len(entries) == 1:
            button = ui.button(icon="link", on_click=lambda u=entries[0].url: open_link(u))
        else:
            button = ui.button(icon="link")
            with button, ui.menu():
                for entry in entries:
                    ui.menu_item(entry.label, on_click=lambda u=entry.url: open_link(u))
        button.props("flat dense round size=sm")
        button.tooltip(" / ".join(entry.label for entry in entries))
```

- [ ] **Step 4: メインパネルに組み込む**

`main_view.py`のimportに`from todoapp.ui.item_links import build_link_entries, render_link_button`を足し、`_render_row`の`ui.label(item.name).classes(name_classes)`の直後に追加:

```python
            render_link_button(build_link_entries(item, self._service.link_templates))
```

- [ ] **Step 5: 編集一覧に組み込む**

`list_view.py`のimportに`from todoapp.ui.item_links import build_link_entries, open_link`を足す。

`body-cell-name`のslotを、アイテム名のバッジ群の末尾(`</q-badge>`の後、`</div>`の前)にボタンを足した形へ変える:

```html
                        <q-btn v-if="props.row.links.length" flat dense round size="sm" icon="link"
                               @click.stop="props.row.links.length === 1 && $parent.$emit('openLink', {id: props.row.id, link: props.row.links[0].id})">
                            <q-tooltip>{{ props.row.links.map(l => l.label).join(' / ') }}</q-tooltip>
                            <q-menu v-if="props.row.links.length > 1">
                                <q-list dense style="min-width: 8rem">
                                    <q-item v-for="l in props.row.links" :key="l.id" clickable v-close-popup
                                            @click.stop="$parent.$emit('openLink', {id: props.row.id, link: l.id})">
                                        <q-item-section>{{ l.label }}</q-item-section>
                                    </q-item>
                                </q-list>
                            </q-menu>
                        </q-btn>
```

`self.table.on("rowClick", ...)`の次の行に`self.table.on("openLink", self._on_open_link)`を追加し、メソッドを追加:

```python
    def _on_open_link(self, e: GenericEventArguments) -> None:
        item = next((i for i in self._service.items if i.id == e.args["id"]), None)
        link = next((link for link in item.links if link.id == e.args["link"]), None) if item else None
        if link is not None:
            open_link(self._service.link_url(link))
```
`render`の`rows.append({...})`に追加:

```python
                    "links": [
                        {"id": entry.link_id, "label": entry.label}
                        for entry in build_link_entries(item, self._service.link_templates)
                    ],
```

- [ ] **Step 6: 通ることを確認する**

Run: `uv run pytest -q -x && uv run mypy src test`
Expected: PASS。画面テストの要素の取り方(`menu_item`の`text`など)がNiceGUIの版と合わない場合は、テスト側を実際の属性に合わせて直す(挙動は変えない)。

- [ ] **Step 7: Commit(確認を取ってから)**

```bash
git add src/todoapp/ui/item_links.py src/todoapp/ui/main_view.py src/todoapp/ui/list_view.py test/ui/test_item_links.py
git commit -m "feat: メインパネル・編集一覧にリンクアイコンを表示し、クリックで開く"
```

---

### Task 5: アイテム編集フォームのリンク欄

**Files:**
- Create: `src/todoapp/ui/link_rows_editor.py`
- Modify: `src/todoapp/ui/edit_dialog.py`
- Test: `test/ui/test_link_rows_editor.py`(新規)

**Interfaces:**
- Consumes: Task 1の`ItemLink`・`LinkTemplate`・`template_placeholders`・`validate_item_link_fields`・長さ定数、Task 3の`set_item_links`。
- Produces:
  - `LinkRowsEditor`: `build() -> None`(リンク欄の見出し・行の入れ物・`リンクを追加`ボタンを現在のコンテナ内に作る)、`load(links: list[ItemLink], templates: list[LinkTemplate]) -> None`、`collect() -> list[ItemLink] | None`(検証に失敗したら警告を出して`None`)
  - `NO_TEMPLATE_LABEL = "なし(URLを直接入力)"`

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_link_rows_editor.py`を新規作成:

```python
from nicegui import ui
from nicegui.testing import User

from test.ui.harness import AppEnv, make_item, press, shows
from todoapp.domain.models import AppData, ItemLink, LinkTemplate
from todoapp.ui.link_rows_editor import LinkRowsEditor

JIRA = LinkTemplate(name="Jira", url_template="https://example.com/{project}/issues/{id}")


async def _open_edit(user: User, name: str) -> None:
    await user.open("/")
    user.find(name).click()
    await press(user, "e")


def test_collect_without_rows_returns_empty_list() -> None:
    assert LinkRowsEditor().collect() == []


async def test_edit_form_shows_inputs_for_the_selected_templates_placeholders(
    app_user: User, app_env: AppEnv
) -> None:
    item = make_item(
        "A", links=[ItemLink(name="チケット", template_id=JIRA.id, values={"project": "P", "id": "1"})]
    )
    app_env.todos_repository.save(AppData(items=[item], records=[], link_templates=[JIRA]))

    await _open_edit(app_user, "A")

    await shows(app_user, "project")
    await shows(app_user, "id")


async def test_saving_the_edit_form_persists_links(app_user: User, app_env: AppEnv) -> None:
    item = make_item("A", links=[ItemLink(name="資料", url="https://example.com/doc")])
    app_env.todos_repository.save(AppData(items=[item], records=[], link_templates=[JIRA]))

    await _open_edit(app_user, "A")
    app_user.find(kind=ui.button, content="保存").click()

    saved = app_env.todos().items[0]
    assert [(link.name, link.url) for link in saved.links] == [("資料", "https://example.com/doc")]
```

(`_open_edit`の操作手順は、既存の`test/ui/test_app_flows.py`の編集フォームのテストに合わせて調整する。`user.find(...).click()`で行を選択できない場合は`click_row`(`test/ui/harness.py`)を使う。保存済みの値が空の置換項目を持つリンクを保存しようとすると警告が出て保存されないテストも1本追加する。)

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_link_rows_editor.py -q`
Expected: FAIL(`ModuleNotFoundError: No module named 'todoapp.ui.link_rows_editor'`)

- [ ] **Step 3: `ui/link_rows_editor.py`を実装する**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from nicegui import ui

from todoapp.domain.models import (
    LINK_NAME_MAX_LENGTH,
    LINK_URL_MAX_LENGTH,
    LINK_VALUE_MAX_LENGTH,
    ItemLink,
    LinkTemplate,
    template_placeholders,
    validate_item_link_fields,
)

NO_TEMPLATE_LABEL = "なし(URLを直接入力)"


@dataclass
class _LinkRow:
    link_id: str
    card: ui.element
    name_input: ui.input
    template_select: ui.select
    fields: ui.element
    url_text: str = ""
    values: dict[str, str] = field(default_factory=dict)  # 入力済みの値。テンプレートを切り替えても同名の項目へ引き継ぐ
    url_input: ui.input | None = None
    value_inputs: dict[str, ui.input] = field(default_factory=dict)


class LinkRowsEditor:
    """アイテム編集フォームのリンク欄。選んだテンプレートの置換項目ごとに入力欄を表示する。"""

    def __init__(self) -> None:
        self._templates: dict[str, LinkTemplate] = {}
        self._rows: list[_LinkRow] = []

    def build(self) -> None:
        ui.label("リンク").classes("text-gray-600")
        self._container = ui.column().classes("w-full gap-2")
        ui.button("リンクを追加", icon="add", on_click=lambda: self._add_row(ItemLink(name=""))).props("flat dense")

    def load(self, links: list[ItemLink], templates: list[LinkTemplate]) -> None:
        self._templates = {template.id: template for template in templates}
        self._rows = []
        self._container.clear()
        for link in links:
            self._add_row(link)

    def collect(self) -> list[ItemLink] | None:
        """入力中のリンクを検証して返す。問題があれば警告を表示して`None`を返す。"""
        links: list[ItemLink] = []
        for row in self._rows:
            template = self._templates.get(row.template_select.value)
            name = (row.name_input.value or "").strip()
            url = ""
            values: dict[str, str] = {}
            if template is None:
                url = ((row.url_input.value if row.url_input else "") or "").strip()
            else:
                values = {key: (inp.value or "").strip() for key, inp in row.value_inputs.items()}
            error = validate_item_link_fields(name, template, url, values)
            if error is not None:
                ui.notify(f"リンク「{name or '(表示名なし)'}」: {error}", type="warning")
                return None
            links.append(
                ItemLink(
                    id=row.link_id,
                    name=name,
                    template_id=template.id if template else None,
                    url=url,
                    values=values,
                )
            )
        return links

    def _add_row(self, link: ItemLink) -> None:
        options: dict[str | None, str] = {None: NO_TEMPLATE_LABEL}
        options.update({template_id: template.name for template_id, template in self._templates.items()})
        selected = link.template_id if link.template_id in options else None
        with self._container, ui.column().classes("w-full gap-1 p-2 border rounded") as card:
            with ui.row().classes("w-full items-center no-wrap"):
                name_input = (
                    ui.input(label="表示名", value=link.name)
                    .props(f"dense maxlength={LINK_NAME_MAX_LENGTH}")
                    .classes("flex-grow")
                )
                remove_button = ui.button(icon="delete").props("flat dense round color=negative")
            template_select = ui.select(options, label="テンプレート", value=selected).props("dense").classes("w-full")
            fields = ui.column().classes("w-full gap-1")
        row = _LinkRow(link.id, card, name_input, template_select, fields, url_text=link.url, values=dict(link.values))
        self._rows.append(row)
        remove_button.on_click(lambda r=row: self._remove_row(r))
        template_select.on_value_change(lambda _e, r=row: self._rebuild_fields(r))
        self._rebuild_fields(row)

    def _remove_row(self, row: _LinkRow) -> None:
        self._rows.remove(row)
        row.card.delete()

    def _rebuild_fields(self, row: _LinkRow) -> None:
        if row.url_input is not None:
            row.url_text = row.url_input.value or ""
        row.values.update({key: inp.value or "" for key, inp in row.value_inputs.items()})
        row.fields.clear()
        row.url_input = None
        row.value_inputs = {}
        template = self._templates.get(row.template_select.value)
        with row.fields:
            if template is None:
                row.url_input = (
                    ui.input(label="URL", value=row.url_text)
                    .props(f"dense maxlength={LINK_URL_MAX_LENGTH}")
                    .classes("w-full")
                )
                return
            for key in template_placeholders(template.url_template):
                row.value_inputs[key] = (
                    ui.input(label=key, value=row.values.get(key, ""))
                    .props(f"dense maxlength={LINK_VALUE_MAX_LENGTH}")
                    .classes("w-full")
                )
```

- [ ] **Step 4: 編集フォームに組み込む**

`edit_dialog.py`:
- import: `from todoapp.ui.link_rows_editor import LinkRowsEditor`
- `__init__`に`self._link_editor = LinkRowsEditor()`
- `build`で、`_category_select`の`selected-item`スロット追加(`add_slot(...)`)の直後、保存ボタン行(`with ui.row().classes("w-full justify-between mt-2")`)の前に`self._link_editor.build()`
- `open_for`の`self._category_select.set_options(...)`の次に`self._link_editor.load(item.links, self._service.link_templates)`
- `_save`の`schedule_type = ScheduleType(...)`の前(アイテム名の検証の直後)に:

```python
        links = self._link_editor.collect()
        if links is None:
            return
```
- `self._service.set_item_category(...)`の次の行に`self._service.set_item_links(self._item_id, links)`

- [ ] **Step 5: 通ることを確認する**

Run: `uv run pytest -q -x && uv run mypy src test`
Expected: PASS

- [ ] **Step 6: Commit(確認を取ってから)**

```bash
git add src/todoapp/ui/link_rows_editor.py src/todoapp/ui/edit_dialog.py test/ui/test_link_rows_editor.py
git commit -m "feat: アイテム編集フォームにリンク欄を追加(テンプレートの置換項目ごとに入力欄を表示)"
```

---

### Task 6: テンプレート管理ダイアログと`u`キー

**Files:**
- Create: `src/todoapp/ui/link_template_dialog.py`
- Modify: `src/todoapp/ui/keyboard.py`(`SHORTCUT_KEYS`・コンストラクタ・`_on_key`)
- Modify: `src/todoapp/ui/help_dialog.py`
- Modify: `src/todoapp/main.py`
- Test: `test/ui/test_keyboard_controller.py`、`test/ui/test_link_template_dialog.py`(新規)

**Interfaces:**
- Consumes: Task 1の`validate_link_template_fields`・長さ定数、Task 3のサービス、`ConfirmDialog.open(message, on_confirm)`。
- Produces: `LinkTemplateDialog(service, refresh_all, confirm_dialog)`(`build()`・`open()`・`refresh()`・`is_open()`)、`KeyboardController`の新しい引数`open_link_templates: Callable[[], None]`。

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_keyboard_controller.py`の末尾に追加(`Screen`は既にimport済み):

```python
def test_u_opens_link_templates_on_main_screen(h: Harness) -> None:
    h.press("u")
    assert h.called("open_link_templates")


def test_u_is_ignored_on_list_screen_or_with_dialog_open(h: Harness) -> None:
    h.state.screen = Screen.LIST
    h.press("u")
    h.state.screen = Screen.MAIN
    h.set_true("is_dialog_open")
    h.press("u")
    assert not h.called("open_link_templates")
```

`test/ui/test_link_template_dialog.py`を新規作成:

```python
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from test.ui.harness import AppEnv, make_item, press, shows
from todoapp.domain.models import AppData, ItemLink, LinkTemplate


async def test_u_key_opens_the_template_dialog(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "u")
    await shows(app_user, "テンプレートを追加")


async def test_adding_a_template_saves_it(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "u")
    app_user.find("テンプレート名").type("Jira")
    app_user.find("URL雛形").type("https://example.com/{id}")
    app_user.find(kind=ui.button, content="テンプレートを追加").click()

    templates = app_env.todos().link_templates
    assert [(t.name, t.url_template) for t in templates] == [("Jira", "https://example.com/{id}")]


async def test_invalid_template_is_not_saved(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "u")
    app_user.find("テンプレート名").type("Jira")
    app_user.find("URL雛形").type("https://example.com/｛id｝")
    app_user.find(kind=ui.button, content="テンプレートを追加").click()

    assert app_env.todos().link_templates == []


async def test_deleting_a_template_without_links_deletes_immediately(app_user: User, app_env: AppEnv) -> None:
    template = LinkTemplate(name="Jira", url_template="https://example.com/{id}")
    app_env.todos_repository.save(AppData(items=[], records=[], link_templates=[template]))
    await app_user.open("/")
    await press(app_user, "u")

    delete_button = next(b for b in app_user.find(kind=ui.button).elements if b.props.get("icon") == "delete")
    UserInteraction(app_user, {delete_button}, None).trigger("click")

    assert app_env.todos().link_templates == []


async def test_deleting_a_template_with_links_asks_for_confirmation(app_user: User, app_env: AppEnv) -> None:
    template = LinkTemplate(name="Jira", url_template="https://example.com/{id}")
    item = make_item("A", links=[ItemLink(name="t", template_id=template.id, values={"id": "1"})])
    app_env.todos_repository.save(AppData(items=[item], records=[], link_templates=[template]))
    await app_user.open("/")
    await press(app_user, "u")

    delete_button = next(b for b in app_user.find(kind=ui.button).elements if b.props.get("icon") == "delete")
    UserInteraction(app_user, {delete_button}, None).trigger("click")
    await shows(app_user, "そのリンクも削除されます")
    assert app_env.todos().link_templates == [template]  # 確認前は消えない

    app_user.find(kind=ui.button, content="削除する").click()

    saved = app_env.todos()
    assert saved.link_templates == []
    assert saved.items[0].links == []
```

(要素の操作方法は、既存テストで使われているヘルパー(`test/ui/harness.py`の`click_displayed`など)に合わせて調整してよい。)

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_keyboard_controller.py test/ui/test_link_template_dialog.py -q`
Expected: FAIL(`KeyError: 'open_link_templates'` / 画面に`テンプレートを追加`が無い)

- [ ] **Step 3: キー操作を追加する**

`keyboard.py`:
- `SHORTCUT_KEYS`の末尾を`"e", "c", "d", "S", "l", "L", "g", "T", "o", "u", "j", "k",`に変更
- `__init__`の引数に`open_link_templates: Callable[[], None],`(`open_settings`の次)、本体に`self._open_link_templates = open_link_templates`
- `_on_key`の`e.key == "o"`の分岐の直後に追加:

```python
        elif e.key == "u" and self._state.screen is Screen.MAIN and not self._is_dialog_open():
            self._open_link_templates()
```

`help_dialog.py`の`_SHORTCUTS`の`("o", ...)`の次に追加:

```python
    ("u", "リンクテンプレートの管理ダイアログ表示(メイン画面のみ。置換項目{名前}を含むURL雛形を登録)"),
```

- [ ] **Step 4: `ui/link_template_dialog.py`を実装する**

```python
from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from todoapp.domain.models import (
    LINK_TEMPLATE_NAME_MAX_LENGTH,
    LINK_URL_MAX_LENGTH,
    LinkTemplate,
    validate_link_template_fields,
)
from todoapp.domain.service import TodoService
from todoapp.ui.confirm_dialog import ConfirmDialog
from todoapp.ui.dialog_base import DialogMixin


class LinkTemplateDialog(DialogMixin):
    """リンクテンプレートの一覧と、追加・編集・削除。"""

    def __init__(self, service: TodoService, refresh_all: Callable[[], None], confirm_dialog: ConfirmDialog) -> None:
        self._service = service
        self._refresh_all = refresh_all
        self._confirm_dialog = confirm_dialog
        self._editing_id: str | None = None

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-[36rem] gap-2"):
            ui.label("リンクテンプレート").classes("text-lg font-bold")
            self._list = ui.column().classes("w-full gap-1")
            ui.separator()
            self._name_input = (
                ui.input(label="テンプレート名")
                .props(f"maxlength={LINK_TEMPLATE_NAME_MAX_LENGTH}")
                .classes("w-full")
            )
            self._url_input = (
                ui.input(label="URL雛形", placeholder="https://example.com/{project}/issues/{id}")
                .props(f"maxlength={LINK_URL_MAX_LENGTH}")
                .classes("w-full")
            )
            ui.label("{名前}の部分を、アイテムのリンクで入力した値に置き換えます(名前は半角英数字と _、5個まで)").classes(
                "text-xs text-gray-500"
            )
            with ui.row().classes("w-full justify-end gap-2"):
                self._cancel_button = ui.button("編集をやめる", on_click=self._reset_form).props("flat")
                self._submit_button = ui.button("テンプレートを追加", on_click=self._submit)
            ui.button("閉じる", on_click=self.dialog.close).props("flat").classes("self-end")
        self._reset_form()
        self.refresh()

    def open(self) -> None:
        self._reset_form()
        self.refresh()
        self.dialog.open()

    def refresh(self) -> None:
        self._list.clear()
        with self._list:
            if not self._service.link_templates:
                ui.label("テンプレートはまだありません").classes("text-gray-400 italic")
            for template in self._service.link_templates:
                with ui.row().classes("w-full items-center no-wrap gap-2"):
                    with ui.column().classes("flex-grow gap-0"):
                        ui.label(template.name).classes("font-medium")
                        ui.label(template.url_template).classes("text-xs text-gray-500 break-all")
                    ui.button(icon="edit", on_click=lambda t=template: self._start_edit(t)).props("flat dense round")
                    ui.button(icon="delete", on_click=lambda t=template: self._delete(t)).props(
                        "flat dense round color=negative"
                    )

    def _reset_form(self) -> None:
        self._editing_id = None
        self._name_input.value = ""
        self._url_input.value = ""
        self._submit_button.set_text("テンプレートを追加")
        self._cancel_button.set_visibility(False)

    def _start_edit(self, template: LinkTemplate) -> None:
        self._editing_id = template.id
        self._name_input.value = template.name
        self._url_input.value = template.url_template
        self._submit_button.set_text("テンプレートを更新")
        self._cancel_button.set_visibility(True)

    def _submit(self) -> None:
        name = (self._name_input.value or "").strip()
        url_template = (self._url_input.value or "").strip()
        error = validate_link_template_fields(name, url_template)
        if error is not None:
            ui.notify(error, type="warning")
            return
        if self._editing_id is None:
            self._service.add_link_template(name, url_template)
        else:
            self._service.edit_link_template(self._editing_id, name=name, url_template=url_template)
        self._reset_form()
        self._refresh_all()

    def _delete(self, template: LinkTemplate) -> None:
        count = self._service.linked_link_count([template.id])

        def do_delete() -> None:
            self._service.delete_link_templates([template.id])
            if self._editing_id == template.id:
                self._reset_form()
            self._refresh_all()

        if count > 0:
            self._confirm_dialog.open(
                f"このテンプレートを使うリンクが{count}件あり、削除するとそのリンクも削除されます。削除しますか?",
                do_delete,
            )
        else:
            do_delete()
```

- [ ] **Step 5: `main.py`に組み込む**

- import: `from todoapp.ui.link_template_dialog import LinkTemplateDialog`
- `confirm_dialog = ConfirmDialog()`の後に`link_template_dialog = LinkTemplateDialog(service, refresh_all=refresh_all, confirm_dialog=confirm_dialog)`
- `refresh_all`の末尾に`link_template_dialog.refresh()`(`category_summary_dialog.refresh()`の次)
- `settings_dialog.build()`の次に`link_template_dialog.build()`
- `all_dialogs`の末尾に`link_template_dialog,`
- `KeyboardController(...)`の`open_settings=settings_dialog.open,`の次に`open_link_templates=link_template_dialog.open,`

(`refresh_all`が`link_template_dialog`を参照するのは、関数の呼び出し時点なので定義順は問題ない。`build()`前に`refresh_all`が呼ばれないことを確認する。)

- [ ] **Step 6: 通ることを確認する**

Run: `uv run pytest -q -x && uv run mypy src test`
Expected: PASS(`test_keyboard.py`の登録漏れ検出も`u`で通る)

- [ ] **Step 7: Commit(確認を取ってから)**

```bash
git add src/todoapp/ui/link_template_dialog.py src/todoapp/ui/keyboard.py src/todoapp/ui/help_dialog.py src/todoapp/main.py test/ui/test_keyboard_controller.py test/ui/test_link_template_dialog.py
git commit -m "feat: リンクテンプレートの管理ダイアログ(uキー)を追加"
```

---

### Task 7: ドキュメントと最終確認

**Files:**
- Modify: `CLAUDE.md`、`README.md`、`docs/development.md`
- Modify: `docs/superpowers/specs/2026-10-19-item-links-design.md`(開けないリンクの扱いを実装に合わせる)

- [ ] **Step 1: 仕様書を実装に合わせる**

`docs/superpowers/specs/2026-10-19-item-links-design.md`の「テンプレートの変更・削除」の最初の項目の「メニュー項目(1件のみならアイコン)は無効にし、ツールチップで理由を示す」を、次に置き換える:

```
メニュー項目の表示名に`(未入力)`を付け(1件のみの場合はアイコンのツールチップに同様に付ける)、クリックすると開かずに警告を表示する(無効状態のツールチップは表示されないため)
```

- [ ] **Step 2: `CLAUDE.md`を更新する**

`## カテゴリ機能`の節の直前に、次の節を追加:

```markdown
## リンク機能

- アイテムには、複数の`リンク`を設定できる。リンクは`表示名`・`テンプレート`・`URLまたは置換項目の値`を持つ。テンプレートを選ばない場合は、`URL`をそのまま開く
- `リンクテンプレート`はURLの雛形で、`{名前}`(名前は半角英数字と`_`、1テンプレート1〜5個)の部分を、アイテムのリンクで入力した値に置き換える。例: `https://example.com/{project}/issues/{id}`。値はURLエンコードして埋め込む。テンプレートは複数登録でき、`u`キー(メイン画面のみ)の専用ダイアログで追加・編集・削除する
- アイテム編集フォームのリンク欄で、`リンクを追加`から行を増やす。テンプレートを選ぶと、その置換項目ごとに入力欄を表示する(切り替えても同名の項目の値は引き継ぐ)
- メインパネルと編集一覧のアイテム名の隣にリンクのアイコンを表示する。リンクが1件ならクリックで直接、2件以上ならメニューで選んで、既定のブラウザで開く(サーバー側の`webbrowser.open()`)。アイコンのクリックは行の選択・実行に伝えない。閲覧用の過去日表示でも使える
- 置換項目が未入力のリンク(テンプレートの置換項目を後から変えた場合など)は、`(未入力)`を付けて表示し、クリックすると開かずに警告を表示する
- テンプレートを削除すると、それを使うリンクもアイテムから削除する(使うリンクがある場合は確認ダイアログを表示する)
- URLの組み立ては`domain/models.py`の`resolve_link_url()`に集約し、`http`・`https`以外のスキーム、未入力の項目、削除済みのテンプレートは`None`(開かない)とする。開く直前に必ずこれを通すこと
```

`## 入力規則`の表の下の箇条書きの前に、表の行を追加:

```markdown
| リンクテンプレート名 | 30 | 制御文字は禁止、それ以外は自由 | 不可 | 制限なし |
| URL雛形・リンクのURL | 500 | ASCII文字のみ・空白不可・`http(s)://`で始まる(雛形は`{名前}`を1〜5個含む。全角の`｛``｝`は警告) | 不可 | 制限なし |
| リンクの表示名 | 30 | 制御文字は禁止、それ以外は自由 | 不可 | 制限なし |
| 置換項目の値 | 200 | 制御文字は禁止、それ以外は自由(URLエンコードして埋め込み、組み立てたURLは2000文字以内) | 不可 | 制限なし |
```
「検証は`domain/models.py`の…」の行に`validate_link_template_fields()`・`validate_item_link_fields()`を追記する。

`## データの保存先`の最初の項目を`アイテム(完了日・リンクを含む)・実行記録・カテゴリ・リンクテンプレートは`~/.todoapp/todos.json`に保存する`に直し、`## 実装上の注意`の最初の項目に「`u`キー」の追加を反映する(`SHORTCUT_KEYS`・ヘルプ・README)。

- [ ] **Step 3: `README.md`を更新する**

機能一覧の`- **カテゴリ**: ...`の行の次に追加:

```markdown
- **リンク**: アイテムに複数のリンクを付けられる。URLの雛形(`{id}`などの置換項目を含むテンプレート)を登録しておくと、アイテムごとにidなどの値を入力するだけでリンクを作れる。一覧のアイコンから既定のブラウザで開ける(複数ならメニューで選ぶ)
```
キー操作表の`| \`o\` | ...`の行の次に追加:

```markdown
| `u` | リンクテンプレートの管理ダイアログ表示(メイン画面のみ) |
```

- [ ] **Step 4: `docs/development.md`を更新する**

モジュール構成の`models.py`の説明を`TodoItem(完了日done_dateを含む)・Category・LinkTemplate・ItemLink(URL組み立てresolve_link_url()・検証)・ExecutionRecord・is_done()/DoneFilter等`に直し、`ui/`に次の3行を追加:

```
│   ├── item_links.py            # 一覧のリンクアイコン(1件は直接、2件以上はメニューで開く。webbrowser.open)
│   ├── link_rows_editor.py      # アイテム編集フォームのリンク欄(テンプレートの置換項目ごとの入力欄)
│   ├── link_template_dialog.py  # リンクテンプレートの管理ダイアログ(`u`キー)
```
保存先の表の`todos.json`の行を`アイテム(完了日・リンクを含む)・実行記録・カテゴリ・リンクテンプレート(スキーマ`version` 2)`に直す。

- [ ] **Step 5: 最終検証**

Run: `uv run pytest --cov=todoapp -q && uv run mypy src test`
Expected: 全テストPASS、`Success: no issues found`。件数とカバレッジを報告に含める。

- [ ] **Step 6: ユーザーによる手動確認(実装者は依頼して結果を待つ)**

ユーザーに次の確認を依頼する(`uv run python -m todoapp.main`で起動):
1. `u`でテンプレートダイアログが開く。`https://example.com/{project}/issues/{id}`を登録できる。全角の`｛id｝`・日本語入りURL・`{id`は警告で保存されない。
2. アイテムを選んで`e`。リンクを追加し、テンプレートを選ぶと`project`・`id`の入力欄が出る。テンプレートを`なし`に切り替えるとURL欄に変わる。保存後に再度開くと値が復元される。
3. メインパネルと編集一覧のアイテム名の隣にリンクアイコンが出る。1件はクリックで既定のブラウザが開く。2件以上はメニューが出て、選んだリンクが開く。
4. アイコンのクリック・ダブルクリックで、行の選択や実行の開始が起きない。
5. テンプレートの置換項目を後から増やすと、既存リンクが`(未入力)`表示になり、クリックで警告が出る。
6. 使われているテンプレートを削除すると確認が出て、リンクも消える。
7. 既存の`~/.todoapp/todos.json`(v1)でも起動でき、`todos.json.v1.bak`が作られる。
8. 編集フォームにリンクを多数入れても、ダイアログがウィンドウに収まりスクロールできる(収まらない場合は`edit_dialog.py`のカードに`max-h-[90vh] overflow-auto`を追加する)。

- [ ] **Step 7: Commit(確認を取ってから)**

```bash
git add CLAUDE.md README.md docs/development.md docs/superpowers/specs/2026-10-19-item-links-design.md
git commit -m "docs: アイテムのリンク機能を仕様・README・開発者向け資料に反映"
```
