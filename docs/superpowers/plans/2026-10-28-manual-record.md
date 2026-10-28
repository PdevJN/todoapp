# 実行記録の手動追加 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 実行履歴(カレンダー)から、アイテムを持たない実行記録を手動で追加でき、集計・作業ログに反映され、右クリックメニューでカテゴリを変更できるようにする。

**Architecture:** `ExecutionRecord`に任意項目`manual`・`category_id`を足し、手動記録の`item_id`は`manual:<記録ID>`の合成キーにする。カテゴリの解決は`TodoService.category_for_record()`に一本化し、集計は記録単位でカテゴリを引く。UIは追加フォーム(新規ダイアログ)・カレンダーの薄い赤表示・FullCalendarラッパーに右クリック通知を足す。

**Tech Stack:** Python 3.13、NiceGUI(Quasar)、FullCalendar、pytest(`uv run pytest`)

**Spec:** `docs/superpowers/specs/2026-10-28-manual-record-design.md`

## Global Constraints

- 言語は日本語。コメント・メッセージ・テスト名のdocstringも日本語(既存コードに合わせる)。
- スキーマ`version`は上げない(任意項目のため)。`manual`でない記録は、`to_dict`の出力を従来と変えない。
- 手動記録の追加・カテゴリ変更に`@undoable`は付けない(記録の編集は Undo 対象外)。
- 検証は保存時に行い、`domain/models.py`に集約する。サービス層(`add_manual_record`等)自体は検証しない。
- タスク名は任意・最大50文字・制御文字禁止(`validate_item_name()`を通す)。
- 手動記録の色: 背景`#ef9a9a`、枠線`#c62828`、文字`#7f0000`。
- キー操作の追加は無いため`SHORTCUT_KEYS`は変更しない。
- コミットはタスクごと。コミット前にユーザーへ確認する(プロジェクトの方針)。メッセージ末尾に`Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`を付ける。
- GUIの動作確認はユーザーが手動で行う。画面の自動操作(AppleScript・全画面スクリーンショット)はしない。

## Review Focus

- 実行中の記録がある日に、その実行中の区間と重なる時刻を追加する → 警告して保存しない(現在時刻までを区間とみなす)。
- 終了時刻が開始時刻と同じ・前 → 警告して保存しない。
- 他の記録の終了ちょうどから始まる記録 → 重なりではないので保存できる。
- 手動記録のカテゴリを後から削除する → 集計は`未定`、カレンダーはグレー扱いで、記録は残る。
- 旧データ(`manual`なし)の`todos.json`を読み込む → 従来どおり開ける。`manual`が無い記録は書き出し時も項目が増えない。
- 通常の記録に対して`set_record_category`を呼ぶ → `ValueError`で拒否する。

## File Structure

- Modify `src/todoapp/domain/models.py`: `ExecutionRecord`の項目、`MANUAL_ITEM_ID_PREFIX`、`validate_manual_record()`
- Modify `src/todoapp/domain/service.py`: `category_for_record`・`add_manual_record`・`set_record_category`、集計4メソッドの修正
- Modify `src/todoapp/ui/calendar_view.py`: 手動記録の描画、`追加`ボタン、右クリックメニュー
- Create `src/todoapp/ui/manual_record_dialog.py`: 追加フォーム
- Modify `src/todoapp/ui/log_view.py`・`src/todoapp/ui/record_timeline_dialog.py`: `category_for_record`化、`手動`印
- Modify `src/todoapp/ui/vendor/fullcalendar/fullcalendar.js`・`fullcalendar.py`: 右クリック通知
- Modify `src/todoapp/main.py`: ダイアログの組み立て
- Modify `CLAUDE.md`(todoapp配下)・`README.md`・`docs/development.md`
- Create `test/domain/test_manual_record.py`・`test/ui/test_manual_record_ui.py`

---

### Task 1: データモデルと検証

**Files:**
- Modify: `src/todoapp/domain/models.py`(`ExecutionRecord`と`validate_item_name`の後)
- Test: `test/domain/test_manual_record.py`(新規)

**Interfaces:**
- Produces: `MANUAL_ITEM_ID_PREFIX: str = "manual:"`、`ExecutionRecord.manual: bool`、`ExecutionRecord.category_id: str | None`、`validate_manual_record(name: str, start: datetime, end: datetime, others: Iterable[tuple[datetime, datetime]]) -> str | None`

- [ ] **Step 1: 失敗するテストを書く**

`test/domain/test_manual_record.py`を新規作成する。

```python
from datetime import datetime

from todoapp.domain.models import (
    MANUAL_ITEM_ID_PREFIX,
    ExecutionRecord,
    validate_manual_record,
)

_D = datetime(2026, 8, 30)


def _t(hour: int, minute: int = 0) -> datetime:
    return _D.replace(hour=hour, minute=minute)


def test_manual_record_round_trips_through_dict() -> None:
    record = ExecutionRecord(
        item_id=f"{MANUAL_ITEM_ID_PREFIX}x",
        item_name="打合せ",
        start_time=_t(9),
        end_time=_t(10),
        manual=True,
        category_id="c1",
    )

    restored = ExecutionRecord.from_dict(record.to_dict())

    assert restored.manual is True
    assert restored.category_id == "c1"
    assert restored == record


def test_normal_record_dict_has_no_manual_keys() -> None:
    record = ExecutionRecord(item_id="i", item_name="散歩", start_time=_t(9), end_time=_t(10))

    data = record.to_dict()

    assert "manual" not in data
    assert "category_id" not in data


def test_old_record_dict_loads_as_normal_record() -> None:
    data = {"id": "r", "item_id": "i", "item_name": "散歩", "start_time": _t(9).isoformat(), "end_time": None}

    record = ExecutionRecord.from_dict(data)

    assert record.manual is False
    assert record.category_id is None


def test_validate_manual_record_accepts_valid_input() -> None:
    assert validate_manual_record("打合せ", _t(9), _t(10), []) is None


def test_validate_manual_record_accepts_empty_name() -> None:
    assert validate_manual_record("", _t(9), _t(10), []) is None


def test_validate_manual_record_rejects_bad_name() -> None:
    assert validate_manual_record("a\tb", _t(9), _t(10), []) is not None
    assert validate_manual_record("あ" * 51, _t(9), _t(10), []) is not None


def test_validate_manual_record_rejects_end_not_after_start() -> None:
    assert validate_manual_record("", _t(10), _t(10), []) is not None
    assert validate_manual_record("", _t(10), _t(9), []) is not None


def test_validate_manual_record_rejects_crossing_midnight() -> None:
    next_day = datetime(2026, 8, 31, 1, 0)
    assert validate_manual_record("", _t(23), next_day, []) is not None


def test_validate_manual_record_rejects_overlap() -> None:
    others = [(_t(9, 30), _t(10, 30))]
    assert validate_manual_record("", _t(9), _t(10), others) is not None
    assert validate_manual_record("", _t(10), _t(11), others) is not None
    assert validate_manual_record("", _t(9, 45), _t(10), others) is not None


def test_validate_manual_record_allows_touching_boundary() -> None:
    others = [(_t(9), _t(10))]
    assert validate_manual_record("", _t(10), _t(11), others) is None
    assert validate_manual_record("", _t(8), _t(9), others) is None
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_manual_record.py -v`
Expected: FAIL(`ImportError: cannot import name 'MANUAL_ITEM_ID_PREFIX'`)

- [ ] **Step 3: 実装する**

`domain/models.py`で、定数を`UNCATEGORIZED_NAME`の近くに足す。

```python
MANUAL_ITEM_ID_PREFIX = "manual:"  # 手動記録の`item_id`の接頭辞(アイテムを持たない記録の合成キー)
```

`ExecutionRecord`の`id`の下に項目を足す。

```python
    manual: bool = False  # 手動で追加した記録(アイテムを持たない)
    category_id: str | None = None  # 手動記録のカテゴリ。通常の記録はアイテムのカテゴリを使う
```

`to_dict`を、手動記録のときだけ項目を足す形に変える。

```python
    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }
        if self.manual:
            data["manual"] = True
            data["category_id"] = self.category_id
        return data
```

`from_dict`の`ExecutionRecord(...)`に次を足す。

```python
            manual=bool(data.get("manual", False)),
            category_id=data.get("category_id"),
```

`validate_item_name`の後に検証関数を足す(ファイル先頭の`from collections.abc import Iterable`は既にある)。

```python
def validate_manual_record(
    name: str, start: datetime, end: datetime, others: Iterable[tuple[datetime, datetime]]
) -> str | None:
    """手動で追加する記録を検証する。`others`は同日の既存記録の区間(実行中は現在時刻まで)。"""
    error = validate_item_name(name)
    if error is not None:
        return error
    if end <= start:
        return "終了時刻は開始時刻より後にしてください"
    if start.date() != end.date():
        return "0:00をまたぐ記録は追加できません"
    for other_start, other_end in others:
        if start < other_end and other_start < end:
            return "同じ日の他の記録と時間が重なっています"
    return None
```

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test/domain/test_manual_record.py test/domain test/repository -q`
Expected: PASS(既存テストも通る)

- [ ] **Step 5: コミット(ユーザー確認後)**

```bash
git add src/todoapp/domain/models.py test/domain/test_manual_record.py
git commit -m "feat: 手動記録のデータモデルと検証を追加"
```

---

### Task 2: サービス(追加・カテゴリ解決・カテゴリ変更)

**Files:**
- Modify: `src/todoapp/domain/service.py`(`category_for_item`の近く、`delete_records`の後)
- Test: `test/domain/test_manual_record.py`(追記)

**Interfaces:**
- Consumes: Task 1の`ExecutionRecord.manual`/`category_id`、`MANUAL_ITEM_ID_PREFIX`
- Produces:
  - `TodoService.category_for_record(record: ExecutionRecord) -> Category | None`
  - `TodoService.add_manual_record(category_id: str | None, name: str, start: datetime, end: datetime) -> ExecutionRecord`
  - `TodoService.set_record_category(record_id: str, category_id: str | None) -> None`(通常記録は`ValueError`、未登録カテゴリは`KeyError`)

- [ ] **Step 1: 失敗するテストを書く**

`test/domain/test_manual_record.py`に追記する(先頭のimportに`pytest`・`date`・`TodoService`等を足す)。

```python
from datetime import date, timedelta

import pytest

from todoapp.domain.models import AppData, ScheduleType
from todoapp.domain.service import TodoService


class _Repo:
    def __init__(self) -> None:
        self.saved: AppData | None = None

    def load(self) -> AppData:
        return AppData(items=[], records=[])

    def save(self, data: AppData) -> None:
        self.saved = data


def _service() -> TodoService:
    return TodoService(_Repo(), clock=lambda: datetime(2026, 8, 30, 18, 0, 0))


def test_add_manual_record_uses_given_name_and_category() -> None:
    service = _service()
    work = service.add_category("仕事")

    record = service.add_manual_record(work.id, "打合せ", _t(9), _t(10))

    assert record in service.records
    assert record.manual is True
    assert record.item_name == "打合せ"
    assert record.item_id == f"{MANUAL_ITEM_ID_PREFIX}{record.id}"
    assert service.category_for_record(record) is work


def test_add_manual_record_blank_name_uses_category_name() -> None:
    service = _service()
    work = service.add_category("仕事")

    assert service.add_manual_record(work.id, "", _t(9), _t(10)).item_name == "仕事"
    assert service.add_manual_record(None, "", _t(11), _t(12)).item_name == "未定"


def test_add_manual_record_is_not_undoable() -> None:
    service = _service()
    service.add_manual_record(None, "", _t(9), _t(10))

    assert service.undo() is None


def test_category_for_record_of_normal_record_follows_item() -> None:
    service = _service()
    work = service.add_category("仕事")
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item.id, work.id)
    service.start(item.id)
    service.stop_running()

    assert service.category_for_record(service.records[0]) is work


def test_category_for_record_is_none_after_category_deleted() -> None:
    service = _service()
    work = service.add_category("仕事")
    record = service.add_manual_record(work.id, "", _t(9), _t(10))

    service.delete_category(work.id)

    assert service.category_for_record(record) is None


def test_set_record_category_changes_category() -> None:
    service = _service()
    work = service.add_category("仕事")
    hobby = service.add_category("趣味")
    record = service.add_manual_record(work.id, "打合せ", _t(9), _t(10))

    service.set_record_category(record.id, hobby.id)

    assert record.category_id == hobby.id
    assert record.item_name == "打合せ"


def test_set_record_category_renames_when_name_followed_category() -> None:
    service = _service()
    work = service.add_category("仕事")
    hobby = service.add_category("趣味")
    record = service.add_manual_record(work.id, "", _t(9), _t(10))

    service.set_record_category(record.id, hobby.id)
    assert record.item_name == "趣味"

    service.set_record_category(record.id, None)
    assert record.item_name == "未定"


def test_set_record_category_rejects_normal_record() -> None:
    service = _service()
    work = service.add_category("仕事")
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    service.stop_running()

    with pytest.raises(ValueError):
        service.set_record_category(service.records[0].id, work.id)


def test_set_record_category_rejects_unknown_category() -> None:
    service = _service()
    record = service.add_manual_record(None, "", _t(9), _t(10))

    with pytest.raises(KeyError):
        service.set_record_category(record.id, "no-such-category")
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_manual_record.py -v`
Expected: FAIL(`AttributeError: 'TodoService' object has no attribute 'add_manual_record'`)

- [ ] **Step 3: 実装する**

`service.py`のimportに`MANUAL_ITEM_ID_PREFIX`を足す。`category_for_item`の後に次を足す。

```python
    def category_for_record(self, record: ExecutionRecord) -> Category | None:
        """記録のカテゴリ。手動記録は記録自身の、通常の記録はアイテムのカテゴリ(未設定・削除済みはNone)。"""
        if not record.manual:
            return self.category_for_item(record.item_id)
        return next((c for c in self._data.categories if c.id == record.category_id), None)
```

`delete_records`の後に次を足す。

```python
    def add_manual_record(
        self, category_id: str | None, name: str, start: datetime, end: datetime
    ) -> ExecutionRecord:
        """アイテムを持たない記録を手動で追加する。名前が空ならカテゴリ名(未設定は`未定`)にする。

        記録の編集はUndoの対象外なので`@undoable`は付けない。検証は画面側で行う。
        """
        category = self._find_category(category_id) if category_id is not None else None
        record = ExecutionRecord(
            item_id="",
            item_name=name or (category.name if category is not None else UNCATEGORIZED_NAME),
            start_time=start,
            end_time=end,
            manual=True,
            category_id=category_id,
        )
        record.item_id = f"{MANUAL_ITEM_ID_PREFIX}{record.id}"
        self._data.records.append(record)
        self._save()
        return record

    def set_record_category(self, record_id: str, category_id: str | None) -> None:
        """手動記録のカテゴリを変更する。名前がこれまでのカテゴリ名のままなら、新しいカテゴリ名へ揃える。"""
        record = self._find_record(record_id)
        if not record.manual:
            raise ValueError("手動で追加した記録のみカテゴリを変更できます")
        new_category = self._find_category(category_id) if category_id is not None else None
        old_category = self.category_for_record(record)
        old_name = old_category.name if old_category is not None else UNCATEGORIZED_NAME
        if record.item_name == old_name:
            record.item_name = new_category.name if new_category is not None else UNCATEGORIZED_NAME
        record.category_id = category_id
        self._save()
```

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test/domain -q`
Expected: PASS

- [ ] **Step 5: コミット(ユーザー確認後)**

```bash
git add src/todoapp/domain/service.py test/domain/test_manual_record.py
git commit -m "feat: 手動記録の追加とカテゴリ変更をサービスに追加"
```

---

### Task 3: 集計への反映

**Files:**
- Modify: `src/todoapp/domain/service.py`の`category_today_totals`・`category_today_item_totals`
- Test: `test/domain/test_manual_record.py`(追記)

**Interfaces:**
- Consumes: Task 2の`add_manual_record`、`category_for_record`
- Produces: 手動記録が`category_today_totals`・`category_today_all_totals`・`category_today_item_totals`・`kind_today_totals`・`item_gap_rows`・`work_summary`に反映される(`_today_item_order`と`item_gap_rows`は`item_id`キーのまま動くため変更しない)

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_manual_record_counts_in_category_totals() -> None:
    service = _service()
    work = service.add_category("仕事", kind="業務")
    service.add_manual_record(work.id, "打合せ", _t(9), _t(10))

    assert service.category_today_totals(date(2026, 8, 30)) == {work.id: 3600}
    assert service.kind_today_totals(date(2026, 8, 30)) == {"業務": 3600}
    all_totals = service.category_today_all_totals(date(2026, 8, 30))
    assert all_totals[0] == (work, 3600)
    assert all_totals[-1] == (None, 0.0)


def test_manual_record_without_category_counts_as_uncategorized() -> None:
    service = _service()
    service.add_manual_record(None, "雑務", _t(9), _t(9, 30))

    assert service.category_today_totals(date(2026, 8, 30)) == {None: 1800}
    assert service.category_today_all_totals(date(2026, 8, 30))[-1] == (None, 1800)


def test_manual_record_of_deleted_category_counts_as_uncategorized() -> None:
    service = _service()
    work = service.add_category("仕事")
    service.add_manual_record(work.id, "", _t(9), _t(10))

    service.delete_category(work.id)

    assert service.category_today_all_totals(date(2026, 8, 30))[-1] == (None, 3600)


def test_manual_record_listed_per_record_in_item_totals() -> None:
    service = _service()
    work = service.add_category("仕事")
    service.add_manual_record(work.id, "打合せ", _t(9), _t(10))
    service.add_manual_record(work.id, "打合せ", _t(11), _t(11, 30))

    result = service.category_today_item_totals(date(2026, 8, 30))

    assert result == {work.id: [("打合せ", 3600, False), ("打合せ", 1800, False)]}


def test_manual_record_row_in_item_gap_rows_has_no_estimate() -> None:
    service = _service()
    service.add_manual_record(None, "雑務", _t(9), _t(9, 30))

    rows = service.item_gap_rows(date(2026, 8, 30))

    assert rows == [ItemGapRow("雑務", 1800, None, None, None)]


def test_manual_record_counts_in_work_summary_actual() -> None:
    service = _service()
    service.add_manual_record(None, "雑務", _t(9), _t(10))

    summary = service.work_summary(date(2026, 8, 30), date(2026, 8, 30), {}, 8.0)

    assert summary.actual_seconds == 3600
```

import に`from todoapp.domain.service import ItemGapRow, TodoService`を使う(Task 2で`TodoService`をimport済みなので`ItemGapRow`を足す)。

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_manual_record.py -v`
Expected: FAIL(カテゴリ別の集計が`{None: 3600}`になり、`category_today_item_totals`は`None`キーに入る)。`item_gap_rows`・`work_summary`のテストは既に通ってよい。

- [ ] **Step 3: 実装する**

`category_today_totals`のループ内を、記録ごとにカテゴリを引く形にする。

```python
        for record in self._data.records:
            if record.start_time.date() != today:
                continue
            if record.manual:
                category_id = record.category_id
            else:
                item = items_by_id.get(record.item_id)
                category_id = item.category_id if item is not None else None
            totals[category_id] = totals.get(category_id, 0.0) + record.elapsed_seconds(now)
```

`category_today_item_totals`は、`order, seconds_by_item, names = ...`の直後に手動記録のカテゴリ表を作り、ループ内で使う。`item`が`None`のときの`category_id`を置き換える。

```python
        manual_category_ids = {r.item_id: r.category_id for r in self.today_records(today) if r.manual}
        ...
            item = items_by_id.get(item_id)
            category_id = item.category_id if item is not None else manual_category_ids.get(item_id)
```

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test -q`
Expected: PASS(全体)

- [ ] **Step 5: コミット(ユーザー確認後)**

```bash
git add src/todoapp/domain/service.py test/domain/test_manual_record.py
git commit -m "feat: 手動記録をカテゴリ別・アイテム別の集計に反映"
```

---

### Task 4: カレンダー・作業ログの表示

**Files:**
- Modify: `src/todoapp/ui/calendar_view.py`(`_build_events`)
- Modify: `src/todoapp/ui/log_view.py:218`(`_render_row`)
- Modify: `src/todoapp/ui/record_timeline_dialog.py:116`
- Test: `test/ui/test_manual_record_ui.py`(新規)

**Interfaces:**
- Consumes: `TodoService.category_for_record`
- Produces: `CalendarView._build_events()`が手動記録に`color`・`borderColor`・`textColor`と`manual`ツールチップを付ける

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_manual_record_ui.py`を新規作成する。

```python
from datetime import date, datetime
from pathlib import Path

from todoapp.domain.service import TodoService
from todoapp.repository.json_repository import JsonTodoRepository
from todoapp.ui.calendar_view import CalendarView


def _view(tmp_path: Path) -> tuple[CalendarView, TodoService]:
    service = TodoService(JsonTodoRepository(tmp_path / "todos.json"))
    view = CalendarView(
        service,
        open_record_edit_dialog=lambda _record_id: None,
        initial_week_start="sunday",
        on_week_start_change=lambda _week_start: None,
        holidays={},
        refresh_holidays=lambda: True,
    )
    return view, service


def test_manual_record_event_is_drawn_in_light_red(tmp_path: Path) -> None:
    view, service = _view(tmp_path)
    work = service.add_category("仕事")
    start = datetime(2026, 8, 30, 9)
    service.add_manual_record(work.id, "打合せ", start, start.replace(hour=10))

    (event,) = view._build_events()

    assert event["color"] == "#ef9a9a"
    assert event["borderColor"] == "#c62828"
    assert event["textColor"] == "#7f0000"
    assert "手動追加" in event["extendedProps"]["tooltip"]
    assert event["extendedProps"]["manual"] is True
    assert "仕事" in event["extendedProps"]["tooltip"]


def test_normal_record_event_keeps_category_color(tmp_path: Path) -> None:
    from todoapp.domain.models import ScheduleType

    view, service = _view(tmp_path)
    work = service.add_category("仕事")
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item.id, work.id)
    service.start(item.id)
    service.stop_running()

    (event,) = view._build_events()

    assert event["color"] == work.color
    assert event["extendedProps"]["manual"] is False
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_manual_record_ui.py -v`
Expected: FAIL(`KeyError: 'borderColor'`)

- [ ] **Step 3: 実装する**

`calendar_view.py`に定数を足し、`_build_events`を次の形にする。

```python
_MANUAL_COLORS = {"color": "#ef9a9a", "borderColor": "#c62828", "textColor": "#7f0000"}
```

```python
        for record in self._service.records:
            category = self._service.category_for_record(record)
            end = record.end_time or now
            start_label = record.start_time.strftime("%H:%M:%S")
            end_label = end.strftime("%H:%M:%S") if record.end_time else "実行中"
            elapsed_label = format_duration(record.elapsed_seconds(now))
            tooltip = f"開始 {start_label} / 終了 {end_label} / 経過 {elapsed_label}"
            event: dict[str, Any] = {
                "id": record.id,
                "title": record.item_name,
                "start": record.start_time.isoformat(),
                "end": end.isoformat(),
                "color": category.color if category is not None else _UNCATEGORIZED_COLOR,
                "extendedProps": {"tooltip": tooltip, "manual": record.manual},
            }
            if record.manual:
                # 手動追加の記録は、カテゴリ色ではなく薄い赤で他の記録と見分ける
                event.update(_MANUAL_COLORS)
                category_name = category.name if category is not None else "未定"
                event["extendedProps"]["tooltip"] = f"手動追加 / カテゴリ {category_name} / {tooltip}"
            events.append(event)
```

`log_view.py`の`_render_row`で`category_for_item(record.item_id)`を`category_for_record(record)`に替え、タスク名のラベルの直前に手動の印を足す。

```python
            category = self._service.category_for_record(record)
```

```python
                if record.manual:
                    ui.badge("手動").props("color=red-2 text-color=red-10").classes("shrink-0")
                with ui.label(record.item_name).classes("font-medium truncate min-w-0"):
```

`record_timeline_dialog.py`の`category = self._service.category_for_item(record.item_id)`を`category_for_record(record)`に替える。

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test -q`
Expected: PASS

- [ ] **Step 5: コミット(ユーザー確認後)**

```bash
git add src/todoapp/ui/calendar_view.py src/todoapp/ui/log_view.py src/todoapp/ui/record_timeline_dialog.py test/ui/test_manual_record_ui.py
git commit -m "feat: 手動記録を薄い赤で表示し、作業ログに手動印を付ける"
```

---

### Task 5: 追加フォームと「追加」ボタン

**Files:**
- Create: `src/todoapp/ui/manual_record_dialog.py`
- Modify: `src/todoapp/ui/calendar_view.py`(コンストラクタ引数とヘッダー)
- Modify: `src/todoapp/main.py:288-306`
- Test: `test/ui/test_manual_record_ui.py`(追記)

**Interfaces:**
- Consumes: `validate_manual_record`、`TodoService.add_manual_record`、`TodoService.today_records(day)`
- Produces: `ManualRecordDialog(service, refresh_all)`、`ManualRecordDialog.build()`、`ManualRecordDialog.open_for(day: date) -> None`、`ManualRecordDialog.submit() -> bool`(検証してから追加し、成功で`True`)、`CalendarView(..., open_manual_record_dialog: Callable[[date], None])`

- [ ] **Step 1: 失敗するテストを書く**

フォームの入力値の取り込みを`submit()`に切り出して、UIを描画せずに検証できるようにする。入力をプレーンな値で受け取る純関数`build_manual_record(...)`をダイアログ側に置く。

```python
from todoapp.ui.manual_record_dialog import parse_manual_record


def test_parse_manual_record_returns_datetimes() -> None:
    parsed = parse_manual_record("2026-08-30", "09:00:00", "10:30:15")

    assert parsed == (datetime(2026, 8, 30, 9), datetime(2026, 8, 30, 10, 30, 15))


def test_parse_manual_record_returns_none_for_bad_input() -> None:
    assert parse_manual_record("", "09:00:00", "10:00:00") is None
    assert parse_manual_record("2026-08-30", "", "10:00:00") is None
    assert parse_manual_record("2026-08-30", "9時", "10:00:00") is None
    assert parse_manual_record("2026-13-40", "09:00:00", "10:00:00") is None
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_manual_record_ui.py -v`
Expected: FAIL(`ModuleNotFoundError: todoapp.ui.manual_record_dialog`)

- [ ] **Step 3: 実装する**

`src/todoapp/ui/manual_record_dialog.py`を新規作成する。

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time

from nicegui import ui

from todoapp.domain.models import ITEM_NAME_MAX_LENGTH, UNCATEGORIZED_NAME, validate_manual_record
from todoapp.domain.service import TodoService
from todoapp.ui.dialog_base import DialogMixin


def parse_manual_record(day: str, start: str, end: str) -> tuple[datetime, datetime] | None:
    """入力欄の文字列(日付・HH:MM:SS)を開始・終了のdatetimeへ変換する。不正なら`None`。"""
    try:
        record_date = date.fromisoformat(day)
        return (
            datetime.combine(record_date, time.fromisoformat(start)),
            datetime.combine(record_date, time.fromisoformat(end)),
        )
    except ValueError:
        return None


class ManualRecordDialog(DialogMixin):
    """実行履歴に、アイテムを持たない記録を手動で追加するフォーム。"""

    def __init__(self, service: TodoService, refresh_all: Callable[[], None]) -> None:
        self._service = service
        self._refresh_all = refresh_all

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            ui.label("実行記録の追加").classes("text-lg font-bold")
            self._date_input = ui.input(label="日付").props("type=date dense").classes("w-full")
            self._category_select = ui.select({}, label="カテゴリ").props("dense").classes("w-full")
            self._name_input = (
                ui.input(label="タスク名(省略するとカテゴリ名)")
                .props(f"maxlength={ITEM_NAME_MAX_LENGTH} dense")
                .classes("w-full")
            )
            self._start_input = ui.time_input(label="開始時刻").classes("w-full")
            self._start_input.picker.props("mask=HH:mm:ss with-seconds")
            self._end_input = ui.time_input(label="終了時刻").classes("w-full")
            self._end_input.picker.props("mask=HH:mm:ss with-seconds")
            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                ui.button("追加", on_click=self.submit)

    def open_for(self, day: date) -> None:
        """`day`を日付の初期値にしてフォームを開く。"""
        options: dict[str, str] = {"": UNCATEGORIZED_NAME}
        for category in self._service.categories:
            label = f"{category.name}({category.prj_code})" if category.prj_code else category.name
            options[category.id] = label
        self._category_select.set_options(options, value="")
        self._date_input.value = day.isoformat()
        self._name_input.value = ""
        self._start_input.value = ""
        self._end_input.value = ""
        self.dialog.open()

    def submit(self) -> bool:
        """入力を検証して記録を追加する。問題があれば警告を表示して追加せず、ダイアログは開いたままにする。"""
        parsed = parse_manual_record(self._date_input.value, self._start_input.value, self._end_input.value)
        if parsed is None:
            ui.notify("日付・開始時刻・終了時刻を正しく入力してください", type="warning")
            return False
        start, end = parsed
        name = self._name_input.value.strip()
        now = datetime.now()
        others = [
            (record.start_time, record.end_time or now) for record in self._service.today_records(start.date())
        ]
        error = validate_manual_record(name, start, end, others)
        if error is not None:
            ui.notify(error, type="warning")
            return False
        self._service.add_manual_record(self._category_select.value or None, name, start, end)
        self.dialog.close()
        self._refresh_all()
        return True
```

`calendar_view.py`: コンストラクタに`open_manual_record_dialog: Callable[[date], None]`を足して保持し、ヘッダーの`event_available`ボタンの手前に追加ボタンを置く。

```python
                    ui.button(icon="add", on_click=self._on_add_click).props("flat dense round").tooltip(
                        "実行記録を追加"
                    )
```

```python
    def _on_add_click(self) -> None:
        self._open_manual_record_dialog(date.today())
```

`CalendarView`のテスト用コンストラクタ(Task 4の`_view`)には`open_manual_record_dialog=lambda _day: None`を足す。

`main.py`: `record_edit_dialog`の後でダイアログを作り、`CalendarView`へ渡し、他のダイアログと同様に`build()`する。

```python
from todoapp.ui.manual_record_dialog import ManualRecordDialog
...
    manual_record_dialog = ManualRecordDialog(service, refresh_all=refresh_all)
    calendar_view = CalendarView(
        service,
        open_record_edit_dialog=record_edit_dialog.open_for,
        open_manual_record_dialog=manual_record_dialog.open_for,
        ...
```

```python
    manual_record_dialog.build()
```

(`build()`は`calendar_view.build()`の前後どちらでもよい。`record_edit_dialog.build()`の隣に置く。)

- [ ] **Step 4: 成功を確認し、手動確認を依頼する**

Run: `uv run pytest test -q`
Expected: PASS

ユーザー確認項目(手動): `Shift+L`→`+`ボタン→フォームでカテゴリ・時刻を入力して追加。薄い赤で表示される / 重なる時刻・終了≦開始・空の時刻は警告が出てダイアログが開いたまま。

- [ ] **Step 5: コミット(ユーザー確認後)**

```bash
git add src/todoapp/ui/manual_record_dialog.py src/todoapp/ui/calendar_view.py src/todoapp/main.py test/ui/test_manual_record_ui.py
git commit -m "feat: 実行履歴に記録を手動で追加するフォームを追加"
```

---

### Task 6: 右クリックメニューでカテゴリを変更

**Files:**
- Modify: `src/todoapp/ui/vendor/fullcalendar/fullcalendar.js`(`eventDidMount`)
- Modify: `src/todoapp/ui/vendor/fullcalendar/fullcalendar.py`(`on_contextmenu`)
- Modify: `src/todoapp/ui/calendar_view.py`
- Test: `test/ui/test_manual_record_ui.py`(追記)

**Interfaces:**
- Consumes: `TodoService.set_record_category`、`category_for_record`
- Produces: `FullCalendar(..., on_contextmenu=...)`(`e.args = {"id": str, "x": float, "y": float}`)、`CalendarView.category_menu_entries(record_id: str) -> list[CategoryMenuEntry]`、`CategoryMenuEntry(category_id: str | None, label: str, color: str, current: bool)`

- [ ] **Step 1: 失敗するテストを書く**

```python
from todoapp.ui.calendar_view import CategoryMenuEntry


def test_category_menu_entries_list_uncategorized_then_categories(tmp_path: Path) -> None:
    view, service = _view(tmp_path)
    work = service.add_category("仕事")
    hobby = service.add_category("趣味")
    record = service.add_manual_record(work.id, "", datetime(2026, 8, 30, 9), datetime(2026, 8, 30, 10))

    entries = view.category_menu_entries(record.id)

    assert [e.label for e in entries] == ["未定", "仕事", "趣味"]
    assert [e.category_id for e in entries] == [None, work.id, hobby.id]
    assert [e.current for e in entries] == [False, True, False]


def test_category_menu_entries_show_prj_code_and_expired_mark(tmp_path: Path) -> None:
    view, service = _view(tmp_path)
    service.add_category("案件", expiry_date=date(2000, 1, 1))
    service.categories[0].prj_code = "P-1"
    record = service.add_manual_record(None, "", datetime(2026, 8, 30, 9), datetime(2026, 8, 30, 10))

    entries = view.category_menu_entries(record.id)

    assert entries[1].label == "❗️案件(P-1)"


def test_category_menu_entries_empty_for_normal_record(tmp_path: Path) -> None:
    from todoapp.domain.models import ScheduleType

    view, service = _view(tmp_path)
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    service.stop_running()

    assert view.category_menu_entries(service.records[0].id) == []
```

有効期限切れの判定は既存の`domain/models.py`の`is_category_expired(category, today)`を使う(新しい判定は作らない。`calendar_view.py`のimportに足す)。

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_manual_record_ui.py -v`
Expected: FAIL(`ImportError: cannot import name 'CategoryMenuEntry'`)

- [ ] **Step 3: 実装する**

`fullcalendar.js`の`eventDidMount`を次のように拡張する。手動記録(`extendedProps.manual`)でだけ、標準メニューを抑止して通知する。

```js
    this.options.eventDidMount = (info) => {
      const props = info.event.extendedProps || {};
      info.el.title = props.tooltip || info.event.title || "";
      if (props.manual) {
        info.el.addEventListener("contextmenu", (event) => {
          event.preventDefault();
          this.$emit("event_contextmenu", {
            id: info.event.id,
            x: event.clientX,
            y: event.clientY,
          });
        });
      }
    };
```

`fullcalendar.py`に引数とハンドラを足す(docstringにも`e.args`を書く)。

```python
        on_contextmenu: Callable | None = None,
...
        if on_contextmenu:
            self.on('event_contextmenu', lambda e: events.handle_event(on_contextmenu, e))
```

`calendar_view.py`にエントリ型と構築を足す。

```python
from dataclasses import dataclass
from todoapp.domain.models import UNCATEGORIZED_NAME


@dataclass(frozen=True)
class CategoryMenuEntry:
    category_id: str | None
    label: str
    color: str
    current: bool
```

```python
    def category_menu_entries(self, record_id: str) -> list[CategoryMenuEntry]:
        """手動記録の右クリックメニューに並べる、`未定`+登録済みカテゴリ。通常の記録は空。"""
        record = next((r for r in self._service.records if r.id == record_id), None)
        if record is None or not record.manual:
            return []
        current = self._service.category_for_record(record)
        entries = [CategoryMenuEntry(None, UNCATEGORIZED_NAME, _UNCATEGORIZED_COLOR, current is None)]
        for category in self._service.categories:
            label = f"❗️{category.name}" if is_category_expired(category, date.today()) else category.name
            if category.prj_code:
                label += f"({category.prj_code})"
            entries.append(CategoryMenuEntry(category.id, label, category.color, current is category))
        return entries
```

`build()`で`FullCalendar(..., on_contextmenu=self._on_event_contextmenu)`を渡し、ダイアログ内に`QMenu`を1つ作る(`context-menu`プロップで、`show(evt)`がクリック位置に開くようにする)。

```python
            self._category_menu = ui.menu().props("context-menu")
```

```python
    def _on_event_contextmenu(self, e: GenericEventArguments) -> None:
        record_id = e.args.get("id")
        entries = self.category_menu_entries(record_id) if record_id else []
        if not entries:
            return
        self._category_menu.clear()
        with self._category_menu:
            ui.item_label("カテゴリを変更").props("header").classes("text-xs text-gray-500 px-3 pt-1")
            for entry in entries:
                item = ui.menu_item(
                    entry.label, on_click=lambda cid=entry.category_id: self._change_category(record_id, cid)
                ).props("dense" + (" disable" if entry.current else ""))
                with item:
                    ui.icon("circle", color=entry.color).classes("text-xs")
        self._category_menu.run_method("show", {"clientX": e.args["x"], "clientY": e.args["y"]})

    def _change_category(self, record_id: str, category_id: str | None) -> None:
        self._service.set_record_category(record_id, category_id)
        self.refresh()
```

実装の最初に、`run_method("show", {clientX, clientY})`でメニューがクリック位置に開くかをネイティブウィンドウ(`uv run todoapp`)とWebモード(`--mode web`)の両方で確認する(WKWebViewで位置指定が効くかが未検証)。開かない場合は、`ui.run_javascript`で`getElement(<menu id>).show(new MouseEvent("contextmenu", {clientX, clientY}))`を呼ぶ形に切り替える。それでも駄目なら、メニューを`position: fixed`の空のdivへ結び付けて`target`で指定する。選んだ方法をコミットメッセージに書く。

- [ ] **Step 4: 成功を確認し、手動確認を依頼する**

Run: `uv run pytest test -q`
Expected: PASS

ユーザー確認項目(手動): 手動記録のバーを右クリック→`カテゴリを変更`のメニューがクリック位置に出る / 現在のカテゴリは選べない / 選ぶとバーのツールチップ・作業ログ・集計が変わる / 通常の記録では独自メニューが出ない / 左クリックは従来どおり時刻編集が開く。

- [ ] **Step 5: コミット(ユーザー確認後)**

```bash
git add src/todoapp/ui/vendor/fullcalendar src/todoapp/ui/calendar_view.py test/ui/test_manual_record_ui.py
git commit -m "feat: 手動記録を右クリックしてカテゴリを変更できるメニューを追加"
```

---

### Task 7: ドキュメント更新

**Files:**
- Modify: `CLAUDE.md`(todoapp配下。`### 実行履歴(カレンダー)`の節に追記し、`集計画面`・`作業ログ`・`データの保存先`の関連箇所に一文ずつ)
- Modify: `README.md`(`実行履歴カレンダー`の行と`Shift + L`の行)
- Modify: `docs/development.md`(ファイル構成に`manual_record_dialog.py`)
- Modify: `src/todoapp/ui/help_dialog.py`(`Shift + L`の説明)

- [ ] **Step 1: CLAUDE.mdに仕様を追記する**

`### 実行履歴(カレンダー)`の末尾に次を足す。

```markdown
- 実行履歴ダイアログのヘッダーの`+`ボタンから、アイテムを持たない実行記録を手動で追加できる。入力は`日付`・`カテゴリ`(`未定`を含む)・`タスク名`(任意。空ならカテゴリ名)・`開始時刻`・`終了時刻`で、見積りは持たない。保存時に検証し(`domain/models.py`の`validate_manual_record()`)、`開始 < 終了`・同じ日の内・同日の他の記録(実行中を含む)と重ならないことを求める(境界で接するのは可)。問題があれば警告を表示して追加せず、ダイアログは開いたままにする
- 手動追加の記録は、カレンダーで薄い赤(背景`#ef9a9a`・枠線`#c62828`)で表示し、ツールチップに`手動追加`とカテゴリを表示する。作業ログの`実行順`ではカテゴリバッジの隣に`手動`の印を付ける。カテゴリ別・種別別・`アイテム別`(1件1行、`累積`・`見積り`・`GAP`は`-`)・稼働集計の実績に、通常の記録と同じく反映する
- 手動記録を右クリックすると、`カテゴリを変更`のメニュー(`未定`と登録済みカテゴリ)が開き、カテゴリを変更できる。名前がそれまでのカテゴリ名のままなら、新しいカテゴリ名へ揃える。時刻の編集・削除は左クリックの記録編集ダイアログで行う。通常の記録では右クリックメニューを出さない
- 手動記録は`ExecutionRecord.manual`・`category_id`を持ち、`item_id`は`manual:<記録ID>`の合成キーとする(任意項目のためスキーマ`version`は上げない)。カテゴリの解決は`TodoService.category_for_record()`に集約する。追加・カテゴリ変更はUndoの対象外。カテゴリを削除した場合、手動記録は`未定`として集計する
```

- [ ] **Step 2: README・ヘルプ・development.mdを更新する**

`README.md`の`実行履歴カレンダー`の行に`、`+`ボタンで実行記録を手動追加(薄い赤で表示)でき、右クリックでカテゴリを変更できる`を足す。`Shift + L`の行は`(当日・週・月。記録をクリックで編集、+で手動追加)`にする。`help_dialog.py`の`Shift + L`の説明を`実行履歴のカレンダー表示(当日/週/月。+で記録を手動追加、手動記録の右クリックでカテゴリ変更)`にする。`docs/development.md`のui一覧に次を足す。

```
│   ├── manual_record_dialog.py  # 実行記録の手動追加フォーム(実行履歴カレンダーの+ボタン)
```

- [ ] **Step 3: 全体の確認**

Run: `uv run pytest test -q`
Expected: PASS(キー一覧の登録漏れ検出`test/ui/test_keyboard.py`も通る)

- [ ] **Step 4: コミット(ユーザー確認後)**

```bash
git add CLAUDE.md README.md docs/development.md src/todoapp/ui/help_dialog.py
git commit -m "docs: 実行記録の手動追加の仕様・README・ヘルプを更新"
```
