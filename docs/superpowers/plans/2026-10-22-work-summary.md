# 稼働集計 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 集計画面に`稼働集計`タブを追加し、月・指定期間の稼働日数/合計/実績/残業時間/見積りGAPを数字と日別グラフで見られるようにする。

**Architecture:** 計算は純粋関数(`domain/work_summary.py`)に集め、`TodoService`が履歴・実行記録から入力を作って呼ぶ。日ごとの見積り履歴(`estimate_history`)と稼働日の上書き(`workday_overrides`)は`todos.json`(スキーマ`version`3)に保存する。画面は`ui/work_summary_panel.py`の`WorkSummaryPanel`に切り出し、`CategorySummaryDialog`のタブとして組み込む。`残業時間の目標`は`config.json`と設定ダイアログに追加する。

**Tech Stack:** Python 3.13、NiceGUI(`ui.echart`・`ui.toggle`・`ui.grid`)、pytest(NiceGUIの`user`シミュレーション)、mypy strict。

**Spec:** `docs/superpowers/specs/2026-10-22-work-summary-design.md`

## Global Constraints

- コミットは、実行前に必ずユーザーへ確認を取る(各タスクの`Commit`ステップに到達したら、確認してから実行する)。`main`へのPRは指示があるまで作らない
- 画面の言語は日本語。コードの識別子は英語、コメント・UI文言は日本語(既存コードに合わせ、コメントは「なぜ」を書く)
- 時間の書式は既存の`format_duration`(`HH:MM:SS`)・`format_hhmm`(`HH:MM`)に合わせ、新しい書式は`format_signed_hhmm`(符号付き`HH:MM`)だけを追加する
- `残業時間 = 実績(期間内)− 今日以前の稼働日数 × 標準労働時間`。`稼働日数`・`合計`は期間全体(未来日を含む)
- `見積りGAP = 見積りのある日の (実績 − 見積り) の合計`。符号は超過が`+`、余りが`-`
- 残業時間の文字色は、`残業 > 目標`(秒に丸めて比較。ちょうどは含まない)で赤(`text-red-600`)、そうでなければ緑(`text-green-600`)
- 期間は`開始 <= 終了`、最大366日(`MAX_PERIOD_DAYS`)
- 残業時間の目標: 既定20.0時間、設定の範囲は0以上744以下
- スキーマ`version`は3。`MIGRATIONS[2]`を追加し、適用前の内容は既存の仕組みで`todos.json.v2.bak`に残る
- 稼働日の上書きはUndoの対象外、`estimate_history`はUndoの対象(`Snapshot`に含める)
- 実行は`uv run pytest`・`uv run mypy src`。各タスクの最後に、そのタスクの範囲のテストを実行する

## Review Focus

- 月の途中(期間の後半が未来)でも、`残業時間`が未来の稼働日分だけ大きなマイナスにならない(今日以前の稼働日で計算する) → Task 2
- 稼働日でない日(土日・祝日)に記録があっても、実績に含まれ`残業時間`に加わる → Task 2
- 期間が1日だけ・366日ちょうど・367日・開始が終了より後 → Task 2
- `v2`のデータを開いたとき、導入日の`本日の見積り`が履歴に入り、移行前の内容が`.v2.bak`に残る → Task 1
- `本日の見積り`を0で解除すると履歴の当日分が消え、アイテムを削除しても過去日の履歴は残り、Undoで履歴も戻る → Task 3
- 実行中の記録が実績に含まれる(現在時刻まで)。0:00で分割された記録が日ごとに振り分けられる → Task 3
- `config.json`の`overtime_target_hours`が不正値(負数・上限超過・真偽値・文字列)のとき既定値に戻る → Task 4
- 祝日データが空でも、土日だけを除いた稼働日で動く → Task 2

---

## File Structure

| ファイル | 役割 |
|---|---|
| `src/todoapp/domain/models.py`(変更) | `DailyEstimate`の追加、`AppData`に`estimate_history`・`workday_overrides`を追加 |
| `src/todoapp/repository/json_repository.py`(変更) | 保存・読み込み、スキーマ`version`3への移行 |
| `src/todoapp/domain/work_summary.py`(新規) | 稼働日判定・期間検証・集計の純粋関数 |
| `src/todoapp/domain/undo.py`(変更) | `Snapshot`に`estimate_history`を追加 |
| `src/todoapp/domain/service.py`(変更) | 見積り履歴の記録、`work_summary()`、`set_workday()` |
| `src/todoapp/repository/config_repository.py`(変更) | `overtime_target_hours` |
| `src/todoapp/ui/settings_dialog.py`(変更) | 残業時間の目標の入力欄 |
| `src/todoapp/ui/formatting.py`(変更) | `format_signed_hhmm` |
| `src/todoapp/ui/work_summary_panel.py`(新規) | `work_chart_options()`と`WorkSummaryPanel` |
| `src/todoapp/ui/category_summary_dialog.py`(変更) | `稼働集計`タブの組み込み、グラフ切り替えボタンの対応 |
| `src/todoapp/main.py`(変更) | 設定・集計画面への配線 |
| `test/ui/harness.py`(変更) | `seed`の引数追加、`select_tab`・`set_value` |
| `CLAUDE.md`・`README.md`・`docs/development.md`(変更) | 仕様・機能一覧・構成図 |

---

### Task 1: データモデルと保存(スキーマ version 3)

**Files:**
- Modify: `src/todoapp/domain/models.py`(`AppData`の直前に`DailyEstimate`を追加、`AppData`にフィールド追加)
- Modify: `src/todoapp/repository/json_repository.py`
- Modify: `test/ui/harness.py`(`AppEnv.seed`)
- Test: `test/repository/test_json_repository.py`

**Interfaces:**
- Produces:
  - `DailyEstimate(day: date, item_id: str, seconds: int)`、`to_dict()`/`from_dict()`
  - `AppData.estimate_history: list[DailyEstimate]`(既定は空)、`AppData.workday_overrides: dict[date, bool]`(既定は空)
  - `SCHEMA_VERSION == 3`、`MIGRATIONS[2]`
  - `AppEnv.seed(..., estimate_history=None, workday_overrides=None)`

- [ ] **Step 1: 失敗するテストを書く**

`test/repository/test_json_repository.py`の先頭のimportを次のようにする。

```python
from todoapp.domain.models import (
    AppData,
    DailyEstimate,
    ExecutionRecord,
    ItemLink,
    LinkTemplate,
    ScheduleType,
    TodoItem,
)
```

ファイル末尾に追加する。

```python
def test_save_then_load_roundtrips_estimate_history_and_workday_overrides(tmp_path: Path) -> None:
    repository = JsonTodoRepository(path=tmp_path / "todos.json")
    data = AppData(
        items=[],
        records=[],
        estimate_history=[DailyEstimate(date(2026, 10, 22), "i1", 5400)],
        workday_overrides={date(2026, 10, 12): True, date(2026, 10, 13): False},
    )

    repository.save(data)

    assert repository.load() == data
    raw = json.loads((tmp_path / "todos.json").read_text(encoding="utf-8"))
    assert raw["version"] == 3
    assert raw["workday_overrides"] == {"2026-10-12": True, "2026-10-13": False}


def _v2_item(item_id: str, name: str, **extra: Any) -> dict[str, Any]:
    base = {
        "id": item_id,
        "name": name,
        "schedule_type": "daily",
        "anchor_date": "2026-10-22",
        "estimate_hours": 0.0,
        "links": [],
    }
    return {**base, **extra}


def test_load_migrates_v2_file_and_seeds_history_from_todays_estimates(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    items = [
        _v2_item("i1", "設計", today_estimate_hours=1.5, today_estimate_date="2026-10-22"),
        _v2_item("i2", "見積りなし"),
        _v2_item("i3", "0時間", today_estimate_hours=0.0, today_estimate_date="2026-10-22"),
    ]
    path.write_text(
        json.dumps(
            {"version": 2, "items": items, "records": [], "categories": [], "link_templates": []},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    original = path.read_text(encoding="utf-8")

    loaded = JsonTodoRepository(path=path).load()

    assert loaded.estimate_history == [DailyEstimate(date(2026, 10, 22), "i1", 5400)]
    assert loaded.workday_overrides == {}
    assert (tmp_path / "todos.json.v2.bak").read_text(encoding="utf-8") == original
```

既存テストの`assert json.loads(...)["version"] == 2`(`test_save_then_load_roundtrips`系、198行付近)を`== SCHEMA_VERSION`に直す。

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/repository/test_json_repository.py -q`
Expected: FAIL(`DailyEstimate`が未定義でImportError)

- [ ] **Step 3: モデルを実装する**

`src/todoapp/domain/models.py`の`AppData`の直前に追加し、`AppData`を更新する。

```python
@dataclass
class DailyEstimate:
    """ある日に設定した`本日の見積り`の履歴(日付×アイテム×秒)。

    `TodoItem`の`本日の見積り`は最後に設定した1日分しか持たないため、過去日の集計用に残す。
    """

    day: date
    item_id: str
    seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {"date": self.day.isoformat(), "item_id": self.item_id, "seconds": self.seconds}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyEstimate:
        return cls(day=date.fromisoformat(data["date"]), item_id=data["item_id"], seconds=int(data["seconds"]))


@dataclass
class AppData:
    items: list[TodoItem]
    records: list[ExecutionRecord]
    categories: list[Category] = field(default_factory=list)
    link_templates: list[LinkTemplate] = field(default_factory=list)
    estimate_history: list[DailyEstimate] = field(default_factory=list)
    workday_overrides: dict[date, bool] = field(default_factory=dict)  # 既定(平日・祝日以外)と違う稼働日の指定
```

- [ ] **Step 4: リポジトリを実装する**

`src/todoapp/repository/json_repository.py`を変更する。

```python
from datetime import date
```
をimportに追加し、`from todoapp.domain.models import AppData, Category, DailyEstimate, ExecutionRecord, LinkTemplate, TodoItem`に直す。`SCHEMA_VERSION = 3`にし、`MIGRATIONS`の前に関数を追加する。

```python
def _migrate_v2_to_v3(raw: dict[str, Any]) -> dict[str, Any]:
    """v3で日ごとの見積り履歴(`estimate_history`)と稼働日の上書き(`workday_overrides`)を追加した。

    移行時点で有効な`本日の見積り`は、導入日の見積りを失わないよう履歴へ入れる。
    """
    history = []
    for item in raw["items"]:
        seconds = round(item.get("today_estimate_hours", 0.0) * 3600)
        if item.get("today_estimate_date") and seconds > 0:
            history.append({"date": item["today_estimate_date"], "item_id": item["id"], "seconds": seconds})
    return {**raw, "version": 3, "estimate_history": history, "workday_overrides": {}}


MIGRATIONS: dict[int, Migration] = {1: _migrate_v1_to_v2, 2: _migrate_v2_to_v3}
```
(元の`MIGRATIONS = {1: ...}`の行は置き換える。)

`_read`の末尾を次のようにする。

```python
        link_templates = [LinkTemplate.from_dict(template) for template in raw.get("link_templates", [])]
        estimate_history = [DailyEstimate.from_dict(entry) for entry in raw.get("estimate_history", [])]
        workday_overrides = {
            date.fromisoformat(day): bool(workday) for day, workday in raw.get("workday_overrides", {}).items()
        }
        return AppData(
            items=items,
            records=records,
            categories=categories,
            link_templates=link_templates,
            estimate_history=estimate_history,
            workday_overrides=workday_overrides,
        )
```

`save`のpayloadに追加する。

```python
            "link_templates": [template.to_dict() for template in data.link_templates],
            "estimate_history": [entry.to_dict() for entry in data.estimate_history],
            "workday_overrides": {day.isoformat(): workday for day, workday in sorted(data.workday_overrides.items())},
```

- [ ] **Step 5: テスト用`seed`を拡張する**

`test/ui/harness.py`のimportに`DailyEstimate`を加え、`AppEnv.seed`を次のようにする。

```python
    def seed(
        self,
        items: list[TodoItem] | None = None,
        records: list[ExecutionRecord] | None = None,
        categories: list[Category] | None = None,
        estimate_history: list[DailyEstimate] | None = None,
        workday_overrides: dict[date, bool] | None = None,
    ) -> None:
        self.todos_repository.save(
            AppData(
                items=items or [],
                records=records or [],
                categories=categories or [],
                estimate_history=estimate_history or [],
                workday_overrides=workday_overrides or {},
            )
        )
```

- [ ] **Step 6: 成功を確認する**

Run: `uv run pytest test/repository test/ui/test_app_smoke.py -q && uv run mypy src`
Expected: PASS

- [ ] **Step 7: Commit(ユーザー確認後)**

```bash
git add src/todoapp/domain/models.py src/todoapp/repository/json_repository.py test/repository/test_json_repository.py test/ui/harness.py
git commit -m "feat: 見積り履歴と稼働日の上書きを保存しスキーマをv3へ移行"
```

---

### Task 2: 稼働集計の純粋関数(`domain/work_summary.py`)

**Files:**
- Create: `src/todoapp/domain/work_summary.py`
- Test: `test/domain/test_work_summary.py`

**Interfaces:**
- Produces:
  - `MAX_PERIOD_DAYS = 366`
  - `is_workday(day: date, overrides: Mapping[date, bool], holidays: Mapping[date, str]) -> bool`
  - `validate_period(start: date, end: date) -> str | None`(問題があれば警告文言、無ければ`None`)
  - `month_bounds(year: int, month: int) -> tuple[date, date]`
  - `WorkDayRow(day, is_workday, estimate_seconds: int | None, actual_seconds: float)`
  - `WorkSummary(start, end, rows, workday_count, total_seconds, actual_seconds, overtime_seconds, estimate_seconds, estimate_day_count, gap_seconds)`
  - `build_work_summary(*, start, end, today, standard_seconds: int, overrides, holidays, estimates: Mapping[date, int], actuals: Mapping[date, float]) -> WorkSummary`(不正な期間は`ValueError`)
  - `overtime_exceeds_target(overtime_seconds: float, target_hours: float) -> bool`

- [ ] **Step 1: 失敗するテストを書く**

`test/domain/test_work_summary.py`:

```python
from datetime import date, timedelta

import pytest

from todoapp.domain.work_summary import (
    MAX_PERIOD_DAYS,
    build_work_summary,
    is_workday,
    month_bounds,
    overtime_exceeds_target,
    validate_period,
)

STANDARD = 8 * 3600
MON = date(2026, 9, 7)  # 2026-09-07は月曜


def _build(start: date, end: date, today: date, **kwargs):  # type: ignore[no-untyped-def]
    params = {"overrides": {}, "holidays": {}, "estimates": {}, "actuals": {}}
    params.update(kwargs)
    return build_work_summary(start=start, end=end, today=today, standard_seconds=STANDARD, **params)


def test_is_workday_defaults_to_weekdays_without_holidays() -> None:
    assert is_workday(MON, {}, {})
    assert not is_workday(date(2026, 9, 12), {}, {})  # 土曜
    assert not is_workday(date(2026, 9, 13), {}, {})  # 日曜


def test_is_workday_excludes_holiday_on_weekday() -> None:
    assert not is_workday(date(2026, 9, 21), {}, {date(2026, 9, 21): "敬老の日"})


def test_is_workday_uses_override_over_defaults() -> None:
    saturday = date(2026, 9, 12)
    assert is_workday(saturday, {saturday: True}, {})
    assert not is_workday(MON, {MON: False}, {})
    assert is_workday(date(2026, 9, 21), {date(2026, 9, 21): True}, {date(2026, 9, 21): "敬老の日"})


def test_month_bounds_handles_leap_february() -> None:
    assert month_bounds(2028, 2) == (date(2028, 2, 1), date(2028, 2, 29))
    assert month_bounds(2026, 12) == (date(2026, 12, 1), date(2026, 12, 31))


def test_validate_period_boundaries() -> None:
    assert validate_period(MON, MON) is None  # 1日だけ
    assert validate_period(MON, MON + timedelta(days=MAX_PERIOD_DAYS - 1)) is None  # 366日ちょうど
    assert validate_period(MON, MON + timedelta(days=MAX_PERIOD_DAYS)) == "期間は366日以内にしてください"
    assert validate_period(MON + timedelta(days=1), MON) == "開始日は終了日以前にしてください"


def test_build_work_summary_rejects_invalid_period() -> None:
    with pytest.raises(ValueError):
        _build(MON + timedelta(days=1), MON, today=MON)


def test_build_work_summary_totals_a_past_week() -> None:
    saturday = date(2026, 9, 12)
    summary = _build(
        MON,
        date(2026, 9, 13),
        today=date(2026, 9, 30),
        estimates={MON: 28800, MON + timedelta(days=1): 7200},
        actuals={MON: 30000.0, saturday: 3600.0},
    )

    assert summary.workday_count == 5
    assert summary.total_seconds == 5 * STANDARD
    assert summary.actual_seconds == 33600
    assert summary.overtime_seconds == 33600 - 5 * STANDARD  # 休日出勤の実績も含む
    assert summary.estimate_seconds == 36000
    assert summary.estimate_day_count == 2
    # 見積りのある日だけ: (30000-28800) + (0-7200)
    assert summary.gap_seconds == -6000
    assert [row.is_workday for row in summary.rows] == [True] * 5 + [False] * 2
    assert summary.rows[1].actual_seconds == 0.0
    assert summary.rows[2].estimate_seconds is None


def test_overtime_counts_only_workdays_up_to_today() -> None:
    summary = _build(MON, date(2026, 9, 13), today=date(2026, 9, 9))  # 水曜まで

    assert summary.workday_count == 5
    assert summary.total_seconds == 5 * STANDARD  # 合計は期間全体
    assert summary.overtime_seconds == -3 * STANDARD  # 残業時間は月・火・水だけ


def test_overtime_with_period_entirely_in_the_future_is_just_actual() -> None:
    summary = _build(MON, date(2026, 9, 11), today=date(2026, 9, 1), actuals={MON: 600.0})

    assert summary.overtime_seconds == 600


def test_summary_without_estimates_has_zero_estimate_days() -> None:
    summary = _build(MON, MON, today=MON, actuals={MON: 100.0})

    assert summary.estimate_day_count == 0
    assert summary.gap_seconds == 0


def test_single_day_period_and_max_period_are_accepted() -> None:
    assert len(_build(MON, MON, today=MON).rows) == 1
    assert len(_build(MON, MON + timedelta(days=MAX_PERIOD_DAYS - 1), today=MON).rows) == MAX_PERIOD_DAYS


def test_holidays_reduce_workday_count() -> None:
    summary = _build(MON, date(2026, 9, 11), today=date(2026, 9, 30), holidays={date(2026, 9, 9): "臨時"})

    assert summary.workday_count == 4


@pytest.mark.parametrize(
    ("overtime", "target_hours", "expected"),
    [(72000, 20, False), (72001, 20, True), (71999, 20, False), (0, 0, False), (1, 0, True), (-5, 0, False)],
)
def test_overtime_exceeds_target_is_strictly_greater(overtime: float, target_hours: float, expected: bool) -> None:
    assert overtime_exceeds_target(overtime, target_hours) is expected
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_work_summary.py -q`
Expected: FAIL(モジュールが無い)

- [ ] **Step 3: 実装する**

`src/todoapp/domain/work_summary.py`:

```python
from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

MAX_PERIOD_DAYS = 366


@dataclass(frozen=True)
class WorkDayRow:
    day: date
    is_workday: bool
    estimate_seconds: int | None  # 履歴に1件も無い日は`None`
    actual_seconds: float


@dataclass(frozen=True)
class WorkSummary:
    start: date
    end: date
    rows: list[WorkDayRow]
    workday_count: int  # 期間全体の稼働日数
    total_seconds: float  # 稼働日数 × 標準労働時間
    actual_seconds: float  # 期間内の実績の合計
    overtime_seconds: float  # 実績 − (今日以前の稼働日数 × 標準労働時間)。マイナスあり
    estimate_seconds: int  # 期間内の見積りの合計
    estimate_day_count: int  # 見積りが記録された日の数(0なら見積り・GAPは`-`表示)
    gap_seconds: float  # 見積りのある日の (実績 − 見積り) の合計


def is_workday(day: date, overrides: Mapping[date, bool], holidays: Mapping[date, str]) -> bool:
    """稼働日か。上書きがあればその値、無ければ平日(月〜金)かつ祝日でない日。"""
    if day in overrides:
        return overrides[day]
    return day.weekday() < 5 and day not in holidays


def validate_period(start: date, end: date) -> str | None:
    """期間の問題を警告文言で返す。問題が無ければ`None`。"""
    if start > end:
        return "開始日は終了日以前にしてください"
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        return f"期間は{MAX_PERIOD_DAYS}日以内にしてください"
    return None


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def build_work_summary(
    *,
    start: date,
    end: date,
    today: date,
    standard_seconds: int,
    overrides: Mapping[date, bool],
    holidays: Mapping[date, str],
    estimates: Mapping[date, int],
    actuals: Mapping[date, float],
) -> WorkSummary:
    message = validate_period(start, end)
    if message is not None:
        raise ValueError(message)
    rows = [
        WorkDayRow(
            day=day,
            is_workday=is_workday(day, overrides, holidays),
            estimate_seconds=estimates.get(day),
            actual_seconds=actuals.get(day, 0.0),
        )
        for day in (start + timedelta(days=offset) for offset in range((end - start).days + 1))
    ]
    workday_count = sum(row.is_workday for row in rows)
    # 月の途中でも目標と比べられるよう、残業時間は今日までの稼働日で計算する(未来の稼働日分は引かない)
    elapsed_workdays = sum(row.is_workday and row.day <= today for row in rows)
    actual_seconds = sum(row.actual_seconds for row in rows)
    estimated = [row for row in rows if row.estimate_seconds is not None]
    return WorkSummary(
        start=start,
        end=end,
        rows=rows,
        workday_count=workday_count,
        total_seconds=workday_count * standard_seconds,
        actual_seconds=actual_seconds,
        overtime_seconds=actual_seconds - elapsed_workdays * standard_seconds,
        estimate_seconds=sum(row.estimate_seconds or 0 for row in rows),
        estimate_day_count=len(estimated),
        gap_seconds=sum(row.actual_seconds - (row.estimate_seconds or 0) for row in estimated),
    )


def overtime_exceeds_target(overtime_seconds: float, target_hours: float) -> bool:
    """残業時間が目標を上回ったか(秒に丸めて比べ、ちょうどは上回りにしない)。"""
    return round(overtime_seconds) > round(target_hours * 3600)
```

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test/domain/test_work_summary.py -q && uv run mypy src`
Expected: PASS

- [ ] **Step 5: Commit(ユーザー確認後)**

```bash
git add src/todoapp/domain/work_summary.py test/domain/test_work_summary.py
git commit -m "feat: 稼働集計の純粋関数(稼働日判定・期間検証・集計)を追加"
```

---

### Task 3: サービス(見積り履歴・稼働集計・稼働日の設定)

**Files:**
- Modify: `src/todoapp/domain/undo.py`(`Snapshot`)
- Modify: `src/todoapp/domain/service.py`
- Test: `test/domain/test_service.py`(末尾に追加)

**Interfaces:**
- Consumes: Task 1の`DailyEstimate`・`AppData`、Task 2の`build_work_summary`・`is_workday`・`WorkSummary`
- Produces:
  - `TodoService.estimate_history -> list[DailyEstimate]`、`TodoService.workday_overrides -> dict[date, bool]`
  - `TodoService.work_summary(start: date, end: date, holidays: Mapping[date, str], standard_hours: float) -> WorkSummary`
  - `TodoService.set_workday(day: date, workday: bool, holidays: Mapping[date, str]) -> None`
  - `edit_item(..., today_estimate_hours=...)`が当日の履歴を記録・更新・削除する

- [ ] **Step 1: 失敗するテストを書く**

`test/domain/test_service.py`の先頭importに`DailyEstimate`を足す(`from todoapp.domain.models import AppData, DailyEstimate, DoneFilter, ...`)。末尾に追加する。

```python
# --- 稼働集計(見積り履歴・work_summary・set_workday) ----------------------------------------


def test_edit_item_records_daily_estimate_history() -> None:
    service, _, _ = _service()
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))

    service.edit_item(item.id, today_estimate_hours=1.5)

    assert service.estimate_history == [DailyEstimate(date(2026, 8, 30), item.id, 5400)]


def test_edit_item_updates_the_same_day_history_instead_of_adding() -> None:
    service, _, _ = _service()
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.edit_item(item.id, today_estimate_hours=1.0)

    service.edit_item(item.id, today_estimate_hours=2.0)

    assert service.estimate_history == [DailyEstimate(date(2026, 8, 30), item.id, 7200)]


def test_edit_item_with_zero_removes_only_todays_history() -> None:
    service, _, clock = _service()
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.edit_item(item.id, today_estimate_hours=1.0)
    clock.advance(86400)  # 翌日
    service.edit_item(item.id, today_estimate_hours=2.0)

    service.edit_item(item.id, today_estimate_hours=0.0)

    assert service.estimate_history == [DailyEstimate(date(2026, 8, 30), item.id, 3600)]


def test_history_survives_item_deletion() -> None:
    service, _, _ = _service()
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.edit_item(item.id, today_estimate_hours=1.0)

    service.delete_item(item.id)

    assert len(service.estimate_history) == 1


def test_undo_restores_estimate_history_together_with_the_item() -> None:
    service, _, _ = _service()
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.edit_item(item.id, today_estimate_hours=1.0)

    service.undo()

    assert service.estimate_history == []
    assert service.items[0].today_estimate_hours == 0.0


def test_edit_item_without_today_estimate_leaves_history_untouched() -> None:
    service, _, _ = _service()
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.edit_item(item.id, today_estimate_hours=1.0)

    service.edit_item(item.id, name="設計2")

    assert len(service.estimate_history) == 1


def test_set_workday_stores_only_differences_from_default() -> None:
    service, repository, _ = _service()
    sunday, monday = date(2026, 8, 30), date(2026, 8, 31)

    service.set_workday(sunday, True, {})  # 日曜を稼働日に
    service.set_workday(monday, False, {})  # 月曜を非稼働日に
    assert service.workday_overrides == {sunday: True, monday: False}
    assert repository.saved is not None and repository.saved.workday_overrides == {sunday: True, monday: False}

    service.set_workday(sunday, False, {})  # 既定(非稼働)に戻す
    service.set_workday(monday, True, {})
    assert service.workday_overrides == {}


def test_set_workday_default_considers_holidays() -> None:
    service, _, _ = _service()
    holiday = date(2026, 8, 31)

    service.set_workday(holiday, True, {holiday: "臨時休業"})  # 祝日を稼働日に → 既定(非稼働)と違う
    assert service.workday_overrides == {holiday: True}
    service.set_workday(holiday, False, {holiday: "臨時休業"})
    assert service.workday_overrides == {}


def test_work_summary_combines_estimates_and_records() -> None:
    service, _, clock = _service()  # 2026-08-30(日曜) 09:00
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.edit_item(item.id, today_estimate_hours=2.0)
    service.start(item.id)
    clock.advance(600)
    service.stop_running()

    summary = service.work_summary(date(2026, 8, 30), date(2026, 8, 30), {}, 8.0)

    assert summary.workday_count == 0  # 日曜は既定で非稼働
    assert summary.actual_seconds == 600
    assert summary.overtime_seconds == 600  # 休日出勤の実績
    assert summary.estimate_seconds == 7200
    assert summary.gap_seconds == 600 - 7200


def test_work_summary_includes_running_record_up_to_now() -> None:
    service, _, clock = _service()
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(300)

    summary = service.work_summary(date(2026, 8, 30), date(2026, 8, 30), {}, 8.0)

    assert summary.actual_seconds == 300


def test_work_summary_assigns_records_to_their_own_day() -> None:
    service, _, clock = _service()
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(600)
    service.stop_running()
    clock.advance(86400)
    service.start(item.id)
    clock.advance(1200)
    service.stop_running()

    summary = service.work_summary(date(2026, 8, 30), date(2026, 8, 31), {}, 8.0)

    assert [row.actual_seconds for row in summary.rows] == [600, 1200]
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_service.py -q -k "estimate or workday or work_summary or history"`
Expected: FAIL(`estimate_history`などが未定義)

- [ ] **Step 3: `Snapshot`を拡張する**

`src/todoapp/domain/undo.py`:

```python
from dataclasses import dataclass, field

from todoapp.domain.models import Category, DailyEstimate, LinkTemplate, TodoItem
```
```python
    items: list[TodoItem]
    categories: list[Category]
    link_templates: list[LinkTemplate]
    estimate_history: list[DailyEstimate] = field(default_factory=list)  # アイテムの編集と食い違わないよう一緒に戻す
```

- [ ] **Step 4: サービスを実装する**

`src/todoapp/domain/service.py`:

importに追加する。

```python
from collections.abc import Callable, Iterable, Iterator, Mapping
```
```python
    AppData,
    Category,
    DailyEstimate,
```
```python
from todoapp.domain.work_summary import WorkSummary, build_work_summary, is_workday
```

プロパティを`link_templates`の後に追加する。

```python
    @property
    def estimate_history(self) -> list[DailyEstimate]:
        return self._data.estimate_history

    @property
    def workday_overrides(self) -> dict[date, bool]:
        return self._data.workday_overrides
```

`_snapshot`・`_restore`に追加する。

```python
            link_templates=copy.deepcopy(self._data.link_templates),
            estimate_history=copy.deepcopy(self._data.estimate_history),
        )
```
```python
        self._data.link_templates = copy.deepcopy(snapshot.link_templates)
        self._data.estimate_history = copy.deepcopy(snapshot.estimate_history)
```

`edit_item`の`today_estimate_hours`ブロックを次のようにする。

```python
        if today_estimate_hours is not None:
            # 限定見積りは設定した日だけ有効。0で解除する
            item.today_estimate_hours = today_estimate_hours
            today = self._clock().date()
            item.today_estimate_date = today if today_estimate_hours > 0 else None
            self._record_daily_estimate(item_id, today, round(today_estimate_hours * 3600))
        self._save()
```

`edit_item`の直後(`running_record`の前)にメソッドを追加する。

```python
    def _record_daily_estimate(self, item_id: str, day: date, seconds: int) -> None:
        """日ごとの見積り履歴を更新する(同じ日・アイテムは1件だけ。0秒は削除)。"""
        history = [e for e in self._data.estimate_history if not (e.day == day and e.item_id == item_id)]
        if seconds > 0:
            history.append(DailyEstimate(day, item_id, seconds))
        self._data.estimate_history = history
```

稼働集計のメソッドを`today_estimate_total_seconds`の後に追加する。

```python
    def work_summary(
        self, start: date, end: date, holidays: Mapping[date, str], standard_hours: float
    ) -> WorkSummary:
        """期間の稼働集計。実績は実行記録を開始日ごとに合計する(実行中の記録は現在時刻まで)。"""
        now = self._clock()
        estimates: dict[date, int] = {}
        for entry in self._data.estimate_history:
            if start <= entry.day <= end:
                estimates[entry.day] = estimates.get(entry.day, 0) + entry.seconds
        actuals: dict[date, float] = {}
        for record in self._data.records:
            day = record.start_time.date()
            if start <= day <= end:
                actuals[day] = actuals.get(day, 0.0) + record.elapsed_seconds(now)
        return build_work_summary(
            start=start,
            end=end,
            today=now.date(),
            standard_seconds=round(standard_hours * 3600),
            overrides=self._data.workday_overrides,
            holidays=holidays,
            estimates=estimates,
            actuals=actuals,
        )

    def set_workday(self, day: date, workday: bool, holidays: Mapping[date, str]) -> None:
        """日ごとの稼働日の指定を保存する。既定(平日かつ祝日でない)と同じ値なら上書きを削除する。

        Undoの対象外(編集系ではなく、カレンダーでの頻繁な切り替えのため)なので`@undoable`は付けない。
        """
        if workday == is_workday(day, {}, holidays):
            self._data.workday_overrides.pop(day, None)
        else:
            self._data.workday_overrides[day] = workday
        self._save()
```

- [ ] **Step 5: 成功を確認する**

Run: `uv run pytest test/domain -q && uv run mypy src`
Expected: PASS(既存の`test_undo*.py`は`Snapshot`の新フィールドが既定値付きのため通る)

- [ ] **Step 6: Commit(ユーザー確認後)**

```bash
git add src/todoapp/domain/undo.py src/todoapp/domain/service.py test/domain/test_service.py
git commit -m "feat: 見積り履歴の記録と稼働集計・稼働日設定をサービスに追加"
```

---

### Task 4: 残業時間の目標(設定とconfig)

**Files:**
- Modify: `src/todoapp/repository/config_repository.py`
- Modify: `src/todoapp/ui/settings_dialog.py`
- Modify: `src/todoapp/main.py`
- Modify: `test/ui/harness.py`(`set_value`を追加)
- Test: `test/repository/test_config_repository.py`、`test/ui/test_app_flows.py`

**Interfaces:**
- Produces:
  - `DEFAULT_OVERTIME_TARGET_HOURS = 20.0`、`MAX_OVERTIME_TARGET_HOURS = 744.0`、`AppConfig.overtime_target_hours: float`
  - `SettingsDialog(get_standard_work_hours, get_overtime_target_hours, get_suspend_detection, on_save: Callable[[float, float, bool], None])`
  - `set_value(user: User, marker: str, value: Any) -> None`(テスト用。`marker`の要素の値を直接設定する)

- [ ] **Step 1: 失敗するテストを書く(config)**

`test/repository/test_config_repository.py`の末尾に追加する。

```python
def test_overtime_target_hours_defaults_to_twenty(tmp_path: Path) -> None:
    assert ConfigRepository(path=tmp_path / "config.json").load().overtime_target_hours == 20.0


def test_save_then_load_roundtrips_overtime_target_hours(tmp_path: Path) -> None:
    repository = ConfigRepository(path=tmp_path / "config.json")
    repository.save(AppConfig(overtime_target_hours=30.5))

    assert repository.load().overtime_target_hours == 30.5


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, 0.0), (20, 20.0), (744, 744.0), (744.1, 20.0), (-0.1, 20.0), ("30", 20.0), (None, 20.0), (True, 20.0)],
)
def test_load_overtime_target_hours_boundaries(tmp_path: Path, raw: object, expected: float) -> None:
    # 0は「残業なし」を目標にする有効な値。範囲外・数値以外・真偽値は既定値に戻す
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"overtime_target_hours": raw}), encoding="utf-8")

    assert ConfigRepository(path=path).load().overtime_target_hours == expected
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/repository/test_config_repository.py -q -k overtime`
Expected: FAIL

- [ ] **Step 3: configを実装する**

`src/todoapp/repository/config_repository.py`:

```python
DEFAULT_STANDARD_WORK_HOURS = 8.0
DEFAULT_OVERTIME_TARGET_HOURS = 20.0
MAX_OVERTIME_TARGET_HOURS = 744.0  # 31日×24時間
```
`_parse_standard_work_hours`の後に追加する。

```python
def _parse_overtime_target_hours(value: Any) -> float:
    # boolはintのサブクラスのため、数値として扱わないよう先に除外する。0は有効(残業なしを目標にする)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return DEFAULT_OVERTIME_TARGET_HOURS
    if not 0 <= value <= MAX_OVERTIME_TARGET_HOURS:
        return DEFAULT_OVERTIME_TARGET_HOURS
    return float(value)
```
`AppConfig`に`overtime_target_hours: float = DEFAULT_OVERTIME_TARGET_HOURS  # 月の残業時間の目標(時間)`を`standard_work_hours`の次に追加し、`load`に`overtime_target_hours=_parse_overtime_target_hours(raw.get("overtime_target_hours")),`、`save`のpayloadに`"overtime_target_hours": config.overtime_target_hours,`を加える。

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test/repository/test_config_repository.py -q`
Expected: PASS

- [ ] **Step 5: 失敗するテストを書く(設定ダイアログ)**

`test/ui/harness.py`に追加する。

```python
def set_value(user: User, marker: str, value: Any) -> None:
    """マーカーを付けた要素(入力欄など)の値を直接設定する(`user.type`が数値入力に対応していないため)。"""
    [element] = user.find(marker=marker).elements
    assert user.client is not None
    with user.client:
        element.value = value
```
`test/ui/test_app_flows.py`の`from test.ui.harness import (...)`に`set_value`を足し、「設定」節の末尾に追加する。

```python
async def test_settings_dialog_saves_overtime_target_hours(app_user: User, app_env: AppEnv) -> None:
    config_path = app_env.directory / "config.json"
    await app_user.open("/")

    await press(app_user, "o")
    await shows(app_user, "残業時間の目標(時間)")
    set_value(app_user, "settings-overtime", 30.0)
    click_displayed(app_user, "保存")

    assert json.loads(config_path.read_text(encoding="utf-8"))["overtime_target_hours"] == 30.0


async def test_settings_dialog_rejects_out_of_range_overtime_target(app_user: User, app_env: AppEnv) -> None:
    config_path = app_env.directory / "config.json"
    await app_user.open("/")

    await press(app_user, "o")
    await shows(app_user, "残業時間の目標(時間)")
    set_value(app_user, "settings-overtime", 745.0)
    click_displayed(app_user, "保存")

    await app_user.should_see("0以上744以下で入力してください")
    assert not config_path.exists()
```

- [ ] **Step 6: 失敗を確認する**

Run: `uv run pytest test/ui/test_app_flows.py -q -k overtime`
Expected: FAIL

- [ ] **Step 7: 設定ダイアログとmainを実装する**

`src/todoapp/ui/settings_dialog.py`全体を次のようにする。

```python
from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from todoapp.repository.config_repository import MAX_OVERTIME_TARGET_HOURS
from todoapp.ui.dialog_base import DialogMixin

_MAX_WORK_HOURS = 24.0


class SettingsDialog(DialogMixin):
    """アプリの設定ダイアログ。設定項目は`標準労働時間`・`残業時間の目標`・`スリープ検知`。"""

    def __init__(
        self,
        get_standard_work_hours: Callable[[], float],
        get_overtime_target_hours: Callable[[], float],
        get_suspend_detection: Callable[[], bool],
        on_save: Callable[[float, float, bool], None],
    ) -> None:
        self._get_standard_work_hours = get_standard_work_hours
        self._get_overtime_target_hours = get_overtime_target_hours
        self._get_suspend_detection = get_suspend_detection
        self._on_save = on_save

    def build(self) -> None:
        with ui.dialog() as self.dialog, ui.card().classes("w-80 gap-2"):
            ui.label("設定").classes("text-lg font-bold")
            self._hours_input = ui.number(
                label="標準労働時間(時間)", min=0.1, max=_MAX_WORK_HOURS, step=0.1, format="%.1f"
            ).classes("w-full")
            self._overtime_input = (
                ui.number(label="残業時間の目標(時間)", min=0, max=MAX_OVERTIME_TARGET_HOURS, step=1, format="%.1f")
                .classes("w-full")
                .mark("settings-overtime")
            )
            self._suspend_checkbox = ui.checkbox("スリープ検知(処理が長く止まったら実行を停止)")
            with ui.row().classes("w-full justify-end mt-2 gap-2"):
                ui.button("キャンセル", on_click=self.dialog.close).props("flat")
                ui.button("保存", on_click=self._save)

    def open(self) -> None:
        self._hours_input.value = self._get_standard_work_hours()
        self._overtime_input.value = self._get_overtime_target_hours()
        self._suspend_checkbox.value = self._get_suspend_detection()
        self.dialog.open()

    def _save(self) -> None:
        value = self._hours_input.value
        if value is None or not 0 < value <= _MAX_WORK_HOURS:
            ui.notify(f"0より大きく{_MAX_WORK_HOURS:g}以下で入力してください", type="warning")
            return
        overtime = self._overtime_input.value
        if overtime is None or not 0 <= overtime <= MAX_OVERTIME_TARGET_HOURS:
            ui.notify(f"0以上{MAX_OVERTIME_TARGET_HOURS:g}以下で入力してください", type="warning")
            return
        self._on_save(float(value), float(overtime), bool(self._suspend_checkbox.value))
        self.dialog.close()
```

`src/todoapp/main.py`:

```python
    def _on_settings_save(hours: float, overtime_target: float, suspend_detection: bool) -> None:
        config.standard_work_hours = hours
        config.overtime_target_hours = overtime_target
        config.suspend_detection = suspend_detection
        config_repository.save(config)
        refresh_all()
```
```python
    settings_dialog = SettingsDialog(
        lambda: config.standard_work_hours,
        lambda: config.overtime_target_hours,
        lambda: config.suspend_detection,
        _on_settings_save,
    )
```

- [ ] **Step 8: 成功を確認する**

Run: `uv run pytest test/repository test/ui/test_app_flows.py -q && uv run mypy src`
Expected: PASS

- [ ] **Step 9: Commit(ユーザー確認後)**

```bash
git add src/todoapp/repository/config_repository.py src/todoapp/ui/settings_dialog.py src/todoapp/main.py test/repository/test_config_repository.py test/ui/harness.py test/ui/test_app_flows.py
git commit -m "feat: 設定に残業時間の目標を追加"
```

---

### Task 5: 符号付き時分の書式

**Files:**
- Modify: `src/todoapp/ui/formatting.py`
- Test: `test/ui/test_formatting.py`

**Interfaces:**
- Produces: `format_signed_hhmm(seconds: float) -> str`

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_formatting.py`の末尾に追加し、import文に`format_signed_hhmm`を足す。

```python
@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(5400, "+01:30"), (-2700, "-00:45"), (0, "00:00"), (10, "00:00"), (-20, "00:00"), (90, "+00:02"), (-73800, "-20:30")],
)
def test_format_signed_hhmm(seconds: float, expected: str) -> None:
    # 秒は四捨五入して分にし、分に丸めて0なら符号を付けない
    assert format_signed_hhmm(seconds) == expected
```
(`pytest`が未importなら`import pytest`を足す。)

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_formatting.py -q`
Expected: FAIL(ImportError)

- [ ] **Step 3: 実装する**

`format_hhmm`の直後に追加する。

```python
def format_signed_hhmm(seconds: float) -> str:
    """符号付きの時分(`+01:30`/`-00:45`)。分に丸めて0なら符号を付けない。"""
    total_minutes = (abs(round(seconds)) + 30) // 60
    if total_minutes == 0:
        return "00:00"
    hours, minutes = divmod(total_minutes, 60)
    return f"{'+' if seconds > 0 else '-'}{hours:02d}:{minutes:02d}"
```

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test/ui/test_formatting.py -q && uv run mypy src`
Expected: PASS

- [ ] **Step 5: Commit(ユーザー確認後)**

```bash
git add src/todoapp/ui/formatting.py test/ui/test_formatting.py
git commit -m "feat: 符号付き時分の書式を追加"
```

---

### Task 6: 日別グラフのオプション(`work_chart_options`)

**Files:**
- Create: `src/todoapp/ui/work_summary_panel.py`(この時点ではグラフのオプション関数のみ)
- Test: `test/ui/test_work_summary_panel.py`

**Interfaces:**
- Consumes: Task 2の`WorkDayRow`
- Produces: `work_chart_options(rows: list[WorkDayRow]) -> dict[str, Any]`。系列は`見積り`(棒)・`実績`(棒)・`GAP`(折れ線)。データ点は`{"value": 時間, "seconds": 秒}`、見積りのない日は`None`。見積りが1件も無い場合は`見積り`・`GAP`の系列を出さない

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_work_summary_panel.py`:

```python
from datetime import date

from todoapp.domain.work_summary import WorkDayRow
from todoapp.ui.work_summary_panel import work_chart_options

MON = date(2026, 9, 7)


def _series(options: dict, name: str) -> dict:  # type: ignore[type-arg]
    return next(s for s in options["series"] if s["name"] == name)


def test_chart_has_estimate_actual_and_gap_series_per_day() -> None:
    rows = [
        WorkDayRow(MON, True, 28800, 30600.0),
        WorkDayRow(date(2026, 9, 8), True, None, 3600.0),
    ]

    options = work_chart_options(rows)

    assert options["xAxis"]["data"] == ["9/7", "9/8"]
    assert [s["name"] for s in options["series"]] == ["見積り", "実績", "GAP"]
    assert _series(options, "見積り")["data"] == [{"value": 8.0, "seconds": 28800}, None]
    assert _series(options, "実績")["data"] == [
        {"value": 8.5, "seconds": 30600.0},
        {"value": 1.0, "seconds": 3600.0},
    ]
    # GAPは見積りのある日だけ(実績 − 見積り)
    assert _series(options, "GAP")["data"] == [{"value": 0.5, "seconds": 1800.0}, None]
    assert _series(options, "GAP")["type"] == "line"


def test_chart_omits_estimate_and_gap_series_without_any_estimate() -> None:
    options = work_chart_options([WorkDayRow(MON, True, None, 3600.0)])

    assert [s["name"] for s in options["series"]] == ["実績"]


def test_chart_gap_value_can_be_negative() -> None:
    options = work_chart_options([WorkDayRow(MON, True, 7200, 0.0)])

    assert _series(options, "GAP")["data"] == [{"value": -2.0, "seconds": -7200.0}]


def test_chart_includes_non_workday_with_actual() -> None:
    options = work_chart_options([WorkDayRow(date(2026, 9, 12), False, None, 600.0)])

    assert _series(options, "実績")["data"][0]["seconds"] == 600.0
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_work_summary_panel.py -q`
Expected: FAIL(モジュールが無い)

- [ ] **Step 3: 実装する**

`src/todoapp/ui/work_summary_panel.py`:

```python
from __future__ import annotations

from typing import Any

from todoapp.domain.work_summary import WorkDayRow

# 系列データのsecondsを`HH:MM:SS`で表示する。値の無い日(null)は行を出さない
_CHART_TOOLTIP_FORMATTER = (
    "params => { const f = s => { const a = Math.abs(Math.round(s)); const p = n => String(n).padStart(2, '0');"
    " return `${s < 0 ? '-' : ''}${p(Math.floor(a / 3600))}:${p(Math.floor(a % 3600 / 60))}:${p(a % 60)}`; };"
    " const lines = params.filter(x => x.data).map(x => `${x.marker}${x.seriesName} `"
    " + `${x.seriesName === 'GAP' && x.data.seconds > 0 ? '+' : ''}${f(x.data.seconds)}`);"
    " return [params[0].axisValue, ...lines].join('<br>'); }"
)


def _point(seconds: float) -> dict[str, float]:
    return {"value": round(seconds / 3600, 2), "seconds": seconds}


def work_chart_options(rows: list[WorkDayRow]) -> dict[str, Any]:
    """日別の棒グラフ(見積り・実績)と、見積りのある日のGAP(実績 − 見積り)の折れ線のオプション。"""
    has_estimate = any(row.estimate_seconds is not None for row in rows)
    series: list[dict[str, Any]] = []
    if has_estimate:
        series.append(
            {
                "name": "見積り",
                "type": "bar",
                "data": [_point(row.estimate_seconds) if row.estimate_seconds is not None else None for row in rows],
            }
        )
    series.append({"name": "実績", "type": "bar", "data": [_point(row.actual_seconds) for row in rows]})
    if has_estimate:
        series.append(
            {
                "name": "GAP",
                "type": "line",
                "data": [
                    _point(row.actual_seconds - row.estimate_seconds) if row.estimate_seconds is not None else None
                    for row in rows
                ],
            }
        )
    return {
        "tooltip": {"trigger": "axis", ":formatter": _CHART_TOOLTIP_FORMATTER, "confine": True},
        "legend": {"data": [s["name"] for s in series], "top": 0},
        "grid": {"left": 48, "right": 16, "top": 40, "bottom": 28},
        "xAxis": {"type": "category", "data": [f"{row.day.month}/{row.day.day}" for row in rows]},
        "yAxis": {"type": "value", "name": "時間", "axisLabel": {"formatter": "{value}h"}},
        "series": series,
    }
```

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test/ui/test_work_summary_panel.py -q && uv run mypy src`
Expected: PASS

- [ ] **Step 5: Commit(ユーザー確認後)**

```bash
git add src/todoapp/ui/work_summary_panel.py test/ui/test_work_summary_panel.py
git commit -m "feat: 稼働集計の日別グラフのオプションを追加"
```

---

### Task 7: 稼働集計タブ(月・期間・数字・グラフ)

**Files:**
- Modify: `src/todoapp/ui/work_summary_panel.py`(`WorkSummaryPanel`を追加)
- Modify: `src/todoapp/ui/category_summary_dialog.py`
- Modify: `src/todoapp/main.py`
- Modify: `test/ui/harness.py`(`select_tab`)
- Test: `test/ui/test_work_summary.py`

**Interfaces:**
- Consumes: Task 2〜6の成果物(`TodoService.work_summary`・`overtime_exceeds_target`・`validate_period`・`month_bounds`・`format_signed_hhmm`・`work_chart_options`)
- Produces:
  - `WorkSummaryPanel(service, get_standard_work_hours, get_overtime_target_hours, holidays)`: `build()`・`reset()`・`refresh()`、属性`chart_container: ui.column`
  - `CategorySummaryDialog(service, get_standard_work_hours, get_overtime_target_hours, holidays)`
  - マーカー: `work-prev-month`・`work-next-month`・`work-start`・`work-end`・`work-overtime`(残業時間の値ラベル)・`work-chart`(グラフの入れ物)・`summary-chart-toggle`(グラフ切り替えボタン)
  - `select_tab(user, label)`(テスト用)

- [ ] **Step 1: テスト用ヘルパーを追加する**

`test/ui/harness.py`に追加する。

```python
def select_tab(user: User, label: str) -> None:
    """表示中の`ui.tabs`の選択を切り替える(`user`のクリックはタブに対応していないため、値を直接設定する)。"""
    for tabs in user.find(kind=ui.tabs).elements:
        if is_displayed(tabs):
            assert user.client is not None
            with user.client:
                tabs.value = label
            return
    raise AssertionError(f"タブが見つかりません: {label}")
```

- [ ] **Step 2: 失敗するテストを書く**

`test/ui/test_work_summary.py`:

```python
"""集計画面の`稼働集計`タブを、ブラウザ無し(NiceGUIの`user`)で操作する画面テスト。

期間は過去の固定日(2026-09-07〜)にして、今日の日付に依存させない。
"""

from datetime import date, datetime, timedelta

from nicegui import ui
from nicegui.testing import User

from test.ui.harness import (
    AppEnv,
    click_displayed,
    is_displayed,
    make_item,
    make_record,
    press,
    select_tab,
    select_toggle,
    set_value,
    shows,
)
from todoapp.domain.models import DailyEstimate, ScheduleType

MON = date(2026, 9, 7)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute)


async def _open_period(user: User, start: date, end: date) -> None:
    await user.open("/")
    await press(user, "T", shift=True)
    await shows(user, "集計画面")
    select_tab(user, "稼働集計")
    select_toggle(user, "期間")
    set_value(user, "work-start", start.isoformat())
    set_value(user, "work-end", end.isoformat())


def _overtime_label(user: User) -> ui.label:
    [label] = user.find(marker="work-overtime").elements
    return label  # type: ignore[return-value]


async def test_period_shows_workdays_total_actual_and_overtime(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    app_env.seed(
        items=[item],
        records=[
            make_record(item, _at(MON, 9), _at(MON, 18)),  # 9時間
            make_record(item, _at(MON + timedelta(days=1), 9), _at(MON + timedelta(days=1), 17, 30)),  # 8.5時間
        ],
    )

    await _open_period(app_user, MON, MON + timedelta(days=4))

    await shows(app_user, "5日")
    await shows(app_user, "40:00")  # 合計 = 5日 × 8時間
    await shows(app_user, "17:30")  # 実績
    await shows(app_user, "-22:30")  # 残業時間 = 17:30 - 40:00
    await shows(app_user, "残業時間(合計)")


async def test_estimate_and_gap_are_shown_from_history(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    app_env.seed(
        items=[item],
        records=[make_record(item, _at(MON, 9), _at(MON, 18))],
        estimate_history=[DailyEstimate(MON, item.id, 8 * 3600)],
    )

    await _open_period(app_user, MON, MON + timedelta(days=4))

    await shows(app_user, "08:00")  # 見積り
    await shows(app_user, "+01:00")  # 見積りGAP = 9時間 - 8時間


async def test_overtime_is_green_at_exactly_the_target_and_red_above_it(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    records = [
        make_record(item, _at(MON + timedelta(days=offset), 8), _at(MON + timedelta(days=offset), 20))
        for offset in range(5)
    ]  # 12時間 × 5日 = 60時間 → 残業 = 60 - 40 = 20:00(目標20時間ちょうど)
    saturday = MON + timedelta(days=5)
    app_env.seed(items=[item], records=records + [make_record(item, _at(saturday, 10), _at(saturday, 10, 1))])

    await _open_period(app_user, MON, MON + timedelta(days=4))
    await shows(app_user, "+20:00")
    assert "text-green-600" in _overtime_label(app_user).classes
    assert "text-red-600" not in _overtime_label(app_user).classes

    set_value(app_user, "work-end", saturday.isoformat())  # 土曜の1分を含める → +20:01
    await shows(app_user, "+20:01")
    assert "text-red-600" in _overtime_label(app_user).classes


async def test_invalid_period_warns_and_keeps_the_previous_summary(app_user: User, app_env: AppEnv) -> None:
    await _open_period(app_user, MON, MON + timedelta(days=4))
    await shows(app_user, "5日")

    set_value(app_user, "work-start", (MON + timedelta(days=10)).isoformat())

    await app_user.should_see("開始日は終了日以前にしてください")
    await shows(app_user, "5日")


async def test_month_mode_starts_from_this_month_and_moves_with_arrows(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "T", shift=True)
    select_tab(app_user, "稼働集計")
    today = date.today()
    await shows(app_user, f"{today.year}年{today.month}月")

    app_user.find(marker="work-prev-month").click()

    previous = (today.replace(day=1) - timedelta(days=1))
    await shows(app_user, f"{previous.year}年{previous.month}月")


async def test_month_mode_labels_overtime_without_total_suffix(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "T", shift=True)
    select_tab(app_user, "稼働集計")

    await shows(app_user, "残業時間")
```

- [ ] **Step 3: 失敗を確認する**

Run: `uv run pytest test/ui/test_work_summary.py -q`
Expected: FAIL(`稼働集計`タブが無い)

- [ ] **Step 4: `WorkSummaryPanel`を実装する**

`src/todoapp/ui/work_summary_panel.py`の先頭importを次のように置き換え、`work_chart_options`の後にクラスを追加する。

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from todoapp.domain.service import TodoService
from todoapp.domain.work_summary import (
    WorkDayRow,
    WorkSummary,
    month_bounds,
    overtime_exceeds_target,
    validate_period,
)
from todoapp.ui.formatting import format_hhmm, format_signed_hhmm

_MODE_MONTH = "month"
_MODE_PERIOD = "period"
_MODE_LABELS = {_MODE_MONTH: "月", _MODE_PERIOD: "期間"}
_OVER_CLASS = "text-red-600"
_UNDER_CLASS = "text-green-600"
```

```python
def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        return None


class WorkSummaryPanel:
    """集計画面の`稼働集計`タブ。月または指定期間の稼働日数・合計・実績・残業時間・見積りGAPと日別グラフを表示する。"""

    def __init__(
        self,
        service: TodoService,
        get_standard_work_hours: Callable[[], float],
        get_overtime_target_hours: Callable[[], float],
        holidays: dict[date, str],
    ) -> None:
        self._service = service
        self._get_standard_work_hours = get_standard_work_hours
        self._get_overtime_target_hours = get_overtime_target_hours
        self._holidays = holidays
        self._built = False
        self._suppress_events = False
        self._mode = _MODE_MONTH
        self._month_start = date.today().replace(day=1)
        self._period = month_bounds(self._month_start.year, self._month_start.month)

    def build(self) -> None:
        with ui.column().classes("w-full gap-2"):
            self._mode_toggle = ui.toggle(_MODE_LABELS, value=self._mode, on_change=self._on_mode_change).props(
                "dense"
            )
            with ui.row().classes("items-center gap-1") as self._month_row:
                ui.button(icon="chevron_left", on_click=lambda: self._shift_month(-1)).props(
                    "flat dense round"
                ).mark("work-prev-month")
                self._month_label = ui.label().classes("font-medium")
                ui.button(icon="chevron_right", on_click=lambda: self._shift_month(1)).props(
                    "flat dense round"
                ).mark("work-next-month")
            with ui.row().classes("items-center gap-2") as self._period_row:
                self._start_input = (
                    ui.input(label="開始日", on_change=self._on_period_change).props("type=date dense").mark("work-start")
                )
                self._end_input = (
                    ui.input(label="終了日", on_change=self._on_period_change).props("type=date dense").mark("work-end")
                )
            self.chart_container = ui.column().classes("w-full items-center").mark("work-chart")
            with self.chart_container:
                self._chart = ui.echart(work_chart_options([])).classes("w-full h-64")
                self._chart_empty_label = ui.label("この期間の記録はありません").classes("text-gray-400 italic")
            self._summary_container = ui.column().classes("w-full gap-0")
        self._built = True

    def reset(self) -> None:
        """集計画面を開くたびに、今月の月表示から始める(保存しない)。"""
        self._mode = _MODE_MONTH
        self._month_start = date.today().replace(day=1)
        self._period = month_bounds(self._month_start.year, self._month_start.month)
        self._suppress_events = True
        try:
            self._mode_toggle.set_value(_MODE_MONTH)
        finally:
            self._suppress_events = False
        self.refresh()

    def refresh(self) -> None:
        if not self._built:
            return
        start, end = self._range()
        self._month_row.set_visibility(self._mode == _MODE_MONTH)
        self._period_row.set_visibility(self._mode == _MODE_PERIOD)
        self._month_label.set_text(f"{self._month_start.year}年{self._month_start.month}月")
        self._suppress_events = True
        try:
            self._start_input.set_value(self._period[0].isoformat())
            self._end_input.set_value(self._period[1].isoformat())
        finally:
            self._suppress_events = False
        summary = self._service.work_summary(start, end, self._holidays, self._get_standard_work_hours())
        self._render_summary(summary)
        self._update_chart(summary)

    def _range(self) -> tuple[date, date]:
        if self._mode == _MODE_MONTH:
            return month_bounds(self._month_start.year, self._month_start.month)
        return self._period

    def _on_mode_change(self, e: ValueChangeEventArguments[str]) -> None:
        if self._suppress_events:
            return
        self._mode = e.value
        self.refresh()

    def _shift_month(self, months: int) -> None:
        # 月初の日付から1か月ずらす(月初に31日を足して月初へ戻す方法で、月ごとの日数差を避ける)
        base = self._month_start
        if months > 0:
            self._month_start = (base + timedelta(days=31)).replace(day=1)
        else:
            self._month_start = (base - timedelta(days=1)).replace(day=1)
        self.refresh()

    def _on_period_change(self, _: ValueChangeEventArguments[str | None]) -> None:
        if self._suppress_events:
            return
        start = _parse_date(self._start_input.value)
        end = _parse_date(self._end_input.value)
        if start is None or end is None:
            return
        message = validate_period(start, end)
        if message is not None:
            ui.notify(message, type="warning")
            return
        self._period = (start, end)
        self.refresh()

    def _render_summary(self, summary: WorkSummary) -> None:
        target_hours = self._get_overtime_target_hours()
        over = overtime_exceeds_target(summary.overtime_seconds, target_hours)
        has_estimate = summary.estimate_day_count > 0
        overtime_title = "残業時間" if self._mode == _MODE_MONTH else "残業時間(合計)"
        self._summary_container.clear()
        with self._summary_container:
            self._summary_row("稼働日数", f"{summary.workday_count}日")
            self._summary_row("合計", format_hhmm(summary.total_seconds))
            self._summary_row("実績", format_hhmm(summary.actual_seconds))
            value_label = self._summary_row(
                overtime_title,
                format_signed_hhmm(summary.overtime_seconds),
                color_class=_OVER_CLASS if over else _UNDER_CLASS,
            )
            value_label.mark("work-overtime")
            with value_label:
                ui.tooltip(f"目標 {target_hours:g}時間")
            self._summary_row("見積り", format_hhmm(summary.estimate_seconds) if has_estimate else "-")
            self._summary_row("見積りGAP", format_signed_hhmm(summary.gap_seconds) if has_estimate else "-")

    @staticmethod
    def _summary_row(name: str, value: str, color_class: str = "") -> ui.label:
        with ui.row().classes("w-full justify-between items-center border-b py-1 px-1"):
            ui.label(name).classes(f"text-gray-600 {color_class}".strip())
            return ui.label(value).classes(f"font-mono font-medium {color_class}".strip())

    def _update_chart(self, summary: WorkSummary) -> None:
        has_data = any(row.actual_seconds > 0 or row.estimate_seconds for row in summary.rows)
        self._chart.options.update(work_chart_options(summary.rows))
        self._chart.update()
        self._chart.set_visibility(has_data)
        self._chart_empty_label.set_visibility(not has_data)
```

mypy対策: `_summary_row`はwithブロック内でreturnするため、関数末尾の到達性は問題ない。`chart.options`は`dict`なので`update`でキーを置き換える(`series`も丸ごと置換される)。

- [ ] **Step 5: ダイアログにタブを組み込む**

`src/todoapp/ui/category_summary_dialog.py`:

importに追加する。
```python
from collections.abc import Callable
```
```python
from todoapp.ui.work_summary_panel import WorkSummaryPanel
```
定数を追加する。
```python
_TAB_WORK = "稼働集計"
```
`__init__`を次のようにする。
```python
    def __init__(
        self,
        service: TodoService,
        get_standard_work_hours: Callable[[], float],
        get_overtime_target_hours: Callable[[], float],
        holidays: dict[date, str],
    ) -> None:
        self._service = service
        self._selected_key: str | None = None
        self._built = False
        # グラフの表示状態はタブごとに独立して持つ
        self._pie_visible = {_TAB_CATEGORY: False, _TAB_ITEM: False, _TAB_WORK: False}
        self.work_panel = WorkSummaryPanel(service, get_standard_work_hours, get_overtime_target_hours, holidays)
```
`build`の変更:
- ボタンを `self.pie_button = ui.button(icon="pie_chart", on_click=self._toggle_pie).props("flat dense round").mark("summary-chart-toggle")` にし、ツールチップを `"グラフの表示を切り替え"` に直す。
- タブに追加: `self.work_tab = ui.tab(_TAB_WORK)`(`item_tab`の次)。
- タブパネルに追加(`item_tab`のパネルの後):
```python
                with ui.tab_panel(self.work_tab).classes("p-0 gap-2"):
                    self.work_panel.build()
```
`open`の`_pie_visible`初期化を3キーにし、`self.tabs.set_value(_TAB_CATEGORY)`の後に`self.work_panel.reset()`を呼ぶ(`self.refresh()`の前)。
`refresh`の先頭付近(`self._refresh_items(...)`の後)に追加する。
```python
        if self.is_open():
            self.work_panel.refresh()
```
`_apply_pie_visibility`に追加する。
```python
        self.work_panel.chart_container.set_visibility(self._pie_visible[_TAB_WORK])
```

- [ ] **Step 6: mainを配線する**

`src/todoapp/main.py`の`category_summary_dialog = CategorySummaryDialog(service)`を次に置き換える(`holidays`は89行付近で定義済み、`config`も同様)。

```python
    category_summary_dialog = CategorySummaryDialog(
        service,
        lambda: config.standard_work_hours,
        lambda: config.overtime_target_hours,
        holidays,
    )
```
`holidays`の定義(`holidays: dict[date, str] = holiday_repository.load()`)より後ろに置かれていることを確認する(`category_summary_dialog`の生成は256行付近で、後ろにある)。

- [ ] **Step 7: 成功を確認する**

Run: `uv run pytest test/ui -q && uv run mypy src`
Expected: PASS。失敗した場合は、`shows`が期待どおりの文言を見つけているか(例: `5日`が他の要素と重ならないか)をテストの出力で確認して直す。

- [ ] **Step 8: Commit(ユーザー確認後)**

```bash
git add src/todoapp/ui/work_summary_panel.py src/todoapp/ui/category_summary_dialog.py src/todoapp/main.py test/ui/harness.py test/ui/test_work_summary.py
git commit -m "feat: 集計画面に稼働集計タブ(月・期間・数字・グラフ)を追加"
```

---

### Task 8: 稼働日の選択カレンダーとグラフ切り替え

**Files:**
- Modify: `src/todoapp/ui/work_summary_panel.py`
- Test: `test/ui/test_work_summary.py`(末尾に追加)

**Interfaces:**
- Consumes: Task 7の`WorkSummaryPanel`、Task 3の`TodoService.set_workday`・`workday_overrides`
- Produces: 日のボタンのマーカー`work-day-<YYYY-MM-DD>`、折りたたみ`稼働日を選ぶ`

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_work_summary.py`の末尾に追加する。

```python
async def test_clicking_a_day_toggles_workday_and_saves_override(app_user: User, app_env: AppEnv) -> None:
    saturday = MON + timedelta(days=5)
    await _open_period(app_user, MON, MON + timedelta(days=6))
    await shows(app_user, "5日")

    app_user.find(marker=f"work-day-{saturday.isoformat()}").click()

    await shows(app_user, "6日")
    assert app_env.todos().workday_overrides == {saturday: True}

    app_user.find(marker=f"work-day-{saturday.isoformat()}").click()  # 既定に戻すと上書きが消える

    await shows(app_user, "5日")
    assert app_env.todos().workday_overrides == {}


async def test_saved_override_is_applied_when_reopened(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(workday_overrides={MON: False})  # 月曜を非稼働日に

    await _open_period(app_user, MON, MON + timedelta(days=4))

    await shows(app_user, "4日")


async def test_chart_is_hidden_until_the_toggle_button_is_pressed(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    app_env.seed(items=[item], records=[make_record(item, _at(MON, 9), _at(MON, 10))])
    await _open_period(app_user, MON, MON + timedelta(days=4))
    [chart] = app_user.find(marker="work-chart").elements

    assert not is_displayed(chart)

    app_user.find(marker="summary-chart-toggle").click()

    assert is_displayed(chart)
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_work_summary.py -q -k "clicking or override or chart"`
Expected: FAIL(`work-day-…`のマーカーが無い)

- [ ] **Step 3: 実装する**

`src/todoapp/ui/work_summary_panel.py`のimportに追加する。

```python
from todoapp.ui.formatting import WEEKDAY_LABELS, format_hhmm, format_signed_hhmm
```
(既存の`from todoapp.ui.formatting import format_hhmm, format_signed_hhmm`を置き換える。)

`build`の`self._summary_container = ...`の直後に追加する。

```python
            with ui.expansion("稼働日を選ぶ").classes("w-full"):
                self._calendar_container = ui.column().classes("w-full gap-2")
```
`refresh`の`self._update_chart(summary)`の後に`self._render_calendar(summary)`を追加し、メソッドを追加する。

```python
    def _render_calendar(self, summary: WorkSummary) -> None:
        """期間内の日を月ごとの格子で並べる。クリックで稼働/非稼働を切り替える。"""
        months: dict[tuple[int, int], list[WorkDayRow]] = {}
        for row in summary.rows:
            months.setdefault((row.day.year, row.day.month), []).append(row)
        self._calendar_container.clear()
        with self._calendar_container:
            for (year, month), rows in months.items():
                ui.label(f"{year}年{month}月").classes("text-sm font-bold text-gray-600")
                with ui.grid(columns=7).classes("gap-1"):
                    for weekday in WEEKDAY_LABELS:
                        ui.label(weekday).classes("text-xs text-center text-gray-500")
                    for _ in range(rows[0].day.weekday()):  # 月曜始まりで、月初の曜日まで空ける
                        ui.label("")
                    for row in rows:
                        self._render_day_button(row)

    def _render_day_button(self, row: WorkDayRow) -> None:
        holiday_name = self._holidays.get(row.day)
        if row.is_workday:
            props = "color=primary"
        elif holiday_name:
            props = "color=green-2 text-color=green-9"
        else:
            props = "color=grey-4 text-color=grey-8"
        button = (
            ui.button(str(row.day.day), on_click=lambda day=row.day, workday=row.is_workday: self._toggle(day, not workday))
            .props(f"dense unelevated size=sm {props}")
            .classes("w-8")
            .mark(f"work-day-{row.day.isoformat()}")
        )
        if row.day in self._service.workday_overrides:
            button.classes("outline outline-2 outline-orange-400")  # 既定から変更した日
        state = "稼働日" if row.is_workday else "非稼働日"
        with button:
            ui.tooltip(f"{holiday_name}・{state}" if holiday_name else state)

    def _toggle(self, day: date, workday: bool) -> None:
        self._service.set_workday(day, workday, self._holidays)
        self.refresh()
```

- [ ] **Step 4: 成功を確認する**

Run: `uv run pytest test/ui/test_work_summary.py -q && uv run mypy src`
Expected: PASS。`outline`系のクラスがTailwind未対応で効かない場合は、`style("outline: 2px solid #fb923c")`に差し替える(見た目の確認はGUIで行う)。

- [ ] **Step 5: 全体を確認する**

Run: `uv run pytest -q && uv run mypy src`
Expected: 全件PASS(0時前後の実行は日付跨ぎで一時的に失敗することがあるため、その場合は再実行する)

- [ ] **Step 6: Commit(ユーザー確認後)**

```bash
git add src/todoapp/ui/work_summary_panel.py test/ui/test_work_summary.py
git commit -m "feat: 稼働集計に稼働日の選択カレンダーを追加"
```

---

### Task 9: ドキュメント

**Files:**
- Modify: `CLAUDE.md`、`README.md`、`docs/development.md`

- [ ] **Step 1: `CLAUDE.md`を更新する**

「## 集計画面」の節の末尾に、次の見出しと内容を追加する(キー操作の追加は無いため`SHORTCUT_KEYS`は変更しない)。

```markdown
### 稼働集計

- `集計画面`に`稼働集計`タブを置く。上部のトグルで`月`(`◀`・`2026年10月`・`▶`で移動)と`期間`(`開始日`・`終了日`)を切り替える。開くたびに今月の月表示から始め、保存はしない。期間は開始が終了以前で最大366日(範囲外は警告を表示して更新しない)
- 数字は、`稼働日数`・`合計`(稼働日数 × 標準労働時間)・`実績`(期間内の実行時間の合計)・`残業時間`・`見積り`・`見積りGAP`。期間指定では`残業時間(合計)`と表示する。判定・集計は`domain/work_summary.py`に集約する(`build_work_summary()`)
- `残業時間`は`実績 − 今日以前の稼働日数 × 標準労働時間`(月の途中でも目標と比べられるよう、未来の稼働日は引かない。`稼働日数`・`合計`は期間全体)。稼働日でない日の実績も含む。符号付きの`HH:MM`で表示し、設定の`残業時間の目標`を上回ったとき(ちょうどは含まない)は赤、そうでなければ緑の文字にする。月表示・期間指定とも、表示中の値をそのまま目標と比べる
- `見積り`は日ごとの`本日の見積り`の合計、`見積りGAP`は見積りが記録された日の`実績 − 見積り`の合計(超過が`+`)。見積りが記録された日が無い期間は`-`
- 日ごとの`本日の見積り`は`estimate_history`に記録する(`本日の見積り`を設定・変更したとき当日の分を更新し、0で解除すると当日の分を削除する。アイテムを削除しても残す)。導入前の日は見積りなし。Undoの`Snapshot`に含める
- `稼働日`は既定が平日(土日・祝日を除く)。`稼働日を選ぶ`の格子(日のボタン)で日ごとに切り替えられ、既定と違う日だけを`workday_overrides`に保存する(既定に戻すと削除)。Undoの対象外。判定は`is_workday()`に集約する。祝日データが無い場合は土日のみ除外する
- 日別の棒グラフ(`見積り`・`実績`)と`GAP`の折れ線(見積りのある日のみ)を、集計画面右上のグラフボタンで表示/非表示する(他のタブと同じく、開くたびに非表示から始める)。見積りが1件も無い期間は`見積り`・`GAP`の系列を出さず、記録が無い期間は`この期間の記録はありません`を表示する
```

「## 設定」の節を次のように直す(`2つ`→`3つ`、項目を追加)。

```markdown
- `o`キー(メイン画面のみ。ダイアログ表示中は無効)で設定ダイアログを表示する。設定できる項目は`標準労働時間`(1日の作業時間の目安。既定8.0時間、0より大きく24以下)・`残業時間の目標`(`稼働集計`の`残業時間`の色分けの基準。既定20.0時間、0以上744以下)・`スリープ検知`(スリープ等で処理が長く止まった場合に実行を停止するか。既定は無効)の3つ
- `標準労働時間`・`残業時間の目標`・`スリープ検知`は`~/.todoapp/config.json`に保存し、次回起動時に復元する
```

「## データの保存先」に追記する。

```markdown
- 日ごとの見積り履歴(`estimate_history`)・稼働日の上書き(`workday_overrides`)も`~/.todoapp/todos.json`に保存する(スキーマ`version`は3。v2からの移行では、移行時点で有効な`本日の見積り`を履歴へ入れる)
```
既存の「テーマ・週表示の開始曜日・標準労働時間・スリープ検知は`~/.todoapp/config.json`」の行に`残業時間の目標`を加える。

- [ ] **Step 2: `README.md`を更新する**

主な機能の一覧の集計画面の説明に、`稼働集計`(月・期間の稼働日数/合計/残業時間/見積りGAPと日別グラフ。稼働日はカレンダーで選択、残業時間の目標は設定で変更)を追記する。`T`キーの行の説明が集計画面なら、そこにも一言足す。

- [ ] **Step 3: `docs/development.md`を更新する**

モジュール構成の図に、`domain/work_summary.py`(稼働日判定・期間集計の純粋関数)と`ui/work_summary_panel.py`(稼働集計タブ)を追記する。

- [ ] **Step 4: 最終確認**

Run: `uv run pytest -q && uv run mypy src`
Expected: 全件PASS

- [ ] **Step 5: Commit(ユーザー確認後)**

```bash
git add CLAUDE.md README.md docs/development.md
git commit -m "docs: 稼働集計の仕様・機能一覧・構成図を追記"
```

---

## Self-Review

**Spec coverage**
- 稼働日数/合計/残業時間/見積り/GAP の数字 → Task 2(計算)・Task 7(表示)
- 日別グラフ(見積り・GAP・実績) → Task 6・Task 7・Task 8(切り替え)
- 月・指定期間、期間の検証(最大366日) → Task 2・Task 7
- 期間指定の残業時間合計の表示、目標との色分け → Task 2(`overtime_exceeds_target`)・Task 7
- 残業時間の目標(設定・既定20h) → Task 4
- 稼働日のカレンダー選択と日ごとの保存 → Task 3(`set_workday`)・Task 8
- 見積り履歴・スキーマ`version`3・移行 → Task 1・Task 3
- Undo(履歴は対象、上書きは対象外) → Task 3
- ドキュメント → Task 9

**型・名前の整合**: `WorkSummary`の`estimate_day_count`はTask 2で定義し、Task 3(サービスは`build_work_summary`を呼ぶだけ)・Task 7(`has_estimate`)で使う。`SettingsDialog`の引数順(標準労働時間→残業目標→スリープ→保存)はTask 4の定義とmainの呼び出しで一致。`CategorySummaryDialog`の引数順(`service, get_standard_work_hours, get_overtime_target_hours, holidays`)はTask 7の定義とmainで一致。マーカー名はTask 7・8のテストと実装で一致。

**注意点(実装時に確認)**
- Task 7のテストは、`shows`が閉じたダイアログ・非表示の祖先を見るが、非選択のタブパネルの中身は検出できない可能性がある。期待値の文言(`5日`・`-22:30`など)が他の画面の文言と重ならない値になっていることで、空振りを防いでいる
- Task 8のテストの`is_displayed`はグラフの祖先の`visible`を見るため、グラフボタンの切り替えが`chart_container.set_visibility`を通っていることを確認できる
- 見た目(日のボタンの色・枠線、グラフの凡例の重なり)はGUIで確認する(自動テストの対象外)
