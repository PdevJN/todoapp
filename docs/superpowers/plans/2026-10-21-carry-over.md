# 繰越 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 未完了で見積りが残っている`当日`アイテムを、`r`キーで次の日へ持ち越せるようにする(`基準日`の移動と、元の日付を残す連結の記録)。

**Architecture:** ドメインに判定関数`can_carry_over()`・`carry_over_target()`と、`TodoItem.carried_from`、`TodoService.carry_over()`を追加する。UIは`r`キーを`KeyboardController`→`main.py`のコールバックへつなぎ、メインパネル・編集一覧のアイテム名の隣に`繰越 MM/DD〜`バッジを出す。見積りと累積は`基準日`を移すだけで続くので、残り時間の計算は変更しない。

**Tech Stack:** Python 3.13, NiceGUI, pytest(`uv run pytest`), mypy(`uv run mypy`)

**Spec:** `docs/superpowers/specs/2026-10-21-carry-over-design.md`

## Global Constraints

- 対象は`ScheduleType.ONE_TIME`(`当日`)のみ。`毎日`・`週次`・`月次`・`未定`は対象外
- 判定は`domain/models.py`の`can_carry_over()`に集約し、UIから直接条件を書かない
- 見積りちょうど(`remaining_seconds == 0`)は対象外。未完了判定は`is_done()`を通す
- 繰越先は`基準日`が今日より前なら今日、今日なら翌日。`基準日`が未来なら対象外
- `carried_from`は初回の繰越時の元の`基準日`のまま保持し、2回目以降は上書きしない
- スキーマの`version`は上げない(`carried_from`は任意項目で、無ければ`None`)
- サービス層は検証しない方針だが、`carry_over()`は対象外を無視する(UIは`can_carry_over()`で絞る必要はなく、`carry_over()`の戻り値で判断する)
- キー操作を追加したら`ui/keyboard.py`の`SHORTCUT_KEYS`・`ui/help_dialog.py`・`README.md`・`CLAUDE.md`を更新する
- コミットは必ずユーザーに確認してから行う(`git commit`を実行する前に確認を取る)。ブランチは`feature/carry-over`

## Review Focus

- 見積りを使い切った(`remaining == 0`)アイテムは繰り越さない(Task 1の境界テスト)
- 完了済みのアイテムは繰り越さない(Task 1)
- `r`を続けて押しても、2回目は動かない(繰越先は`基準日`が未来になり対象外。Task 2のサービステストとTask 4のUIテスト)
- 実行中のアイテムを繰り越すと停止し、実行記録は残る(Task 2)
- 複数選択に対象外が混ざっても、対象のものだけ移動する(Task 2)
- 繰越後に`毎日`などへスケジュールを変えたアイテムには、バッジを出さない(Task 3)

---

## File Structure

- `src/todoapp/domain/models.py`: `TodoItem.carried_from`、`can_carry_over()`、`carry_over_target()`
- `src/todoapp/domain/service.py`: `TodoService.carry_over()`
- `src/todoapp/ui/keyboard.py`: `r`キーの振り分けと`SHORTCUT_KEYS`
- `src/todoapp/main.py`: `carry_over_selected_items()`の定義と配線
- `src/todoapp/ui/formatting.py`: `carried_badge_text()`
- `src/todoapp/ui/main_view.py`・`src/todoapp/ui/list_view.py`: バッジの表示
- `src/todoapp/ui/help_dialog.py`・`README.md`・`CLAUDE.md`: キー一覧と仕様の更新
- テスト: `test/domain/test_models.py`・`test/domain/test_service.py`・`test/ui/test_keyboard_controller.py`・`test/ui/test_formatting.py`・`test/ui/test_app_flows.py`

---

### Task 1: ドメインの判定とデータ項目

**Files:**
- Modify: `src/todoapp/domain/models.py`(`TodoItem`と`today_estimate_seconds()`の近く)
- Test: `test/domain/test_models.py`

**Interfaces:**
- Produces:
  - `TodoItem.carried_from: date | None = None`
  - `can_carry_over(item: TodoItem, today: date, remaining_seconds: float) -> bool`
  - `carry_over_target(item: TodoItem, today: date) -> date`

- [ ] **Step 0: ブランチを切る**

```bash
cd /Users/jun/Documents/opt/work/todoapp
git switch -c feature/carry-over
```

(未コミットの設計書・本計画は、そのままこのブランチに持ち越す。)

- [ ] **Step 1: 失敗するテストを書く**

`test/domain/test_models.py`の末尾に追加する。先頭のimportに`can_carry_over`・`carry_over_target`を足す(既存の`from todoapp.domain.models import (...)`の括弧内、`is_skipped`と同じ並び)。`timedelta`のimportが無ければ`from datetime import date, timedelta`にする。

```python
_TODAY = date(2026, 8, 30)


def _carry_item(**kwargs: Any) -> TodoItem:
    kwargs.setdefault("schedule_type", ScheduleType.ONE_TIME)
    kwargs.setdefault("anchor_date", _TODAY)
    kwargs.setdefault("estimate_hours", 2.0)
    return TodoItem(name="資料作成", **kwargs)


def test_can_carry_over_for_unfinished_one_time_item_with_remaining_estimate() -> None:
    assert can_carry_over(_carry_item(), _TODAY, remaining_seconds=600) is True


def test_can_carry_over_is_false_when_estimate_is_used_up_or_unset() -> None:
    assert can_carry_over(_carry_item(), _TODAY, remaining_seconds=0) is False
    assert can_carry_over(_carry_item(estimate_hours=0.0), _TODAY, remaining_seconds=0) is False


def test_can_carry_over_is_false_when_done() -> None:
    assert can_carry_over(_carry_item(done_date=_TODAY), _TODAY, remaining_seconds=600) is False


@pytest.mark.parametrize(
    "schedule_type",
    [ScheduleType.DAILY, ScheduleType.WEEKLY, ScheduleType.MONTHLY, ScheduleType.UNDECIDED],
)
def test_can_carry_over_is_false_for_other_schedules(schedule_type: ScheduleType) -> None:
    assert can_carry_over(_carry_item(schedule_type=schedule_type), _TODAY, remaining_seconds=600) is False


def test_can_carry_over_is_false_for_future_anchor_and_true_for_past_anchor() -> None:
    assert can_carry_over(_carry_item(anchor_date=_TODAY + timedelta(days=1)), _TODAY, 600) is False
    assert can_carry_over(_carry_item(anchor_date=_TODAY - timedelta(days=1)), _TODAY, 600) is True


def test_carry_over_target_is_today_for_past_anchor_and_tomorrow_for_today_anchor() -> None:
    assert carry_over_target(_carry_item(anchor_date=_TODAY - timedelta(days=3)), _TODAY) == _TODAY
    assert carry_over_target(_carry_item(anchor_date=_TODAY), _TODAY) == _TODAY + timedelta(days=1)


def test_carried_from_round_trips_and_defaults_to_none_for_legacy_data() -> None:
    item = _carry_item(carried_from=date(2026, 8, 28))
    assert TodoItem.from_dict(item.to_dict()) == item
    assert item.to_dict()["carried_from"] == "2026-08-28"
    legacy = {k: v for k, v in item.to_dict().items() if k != "carried_from"}
    assert TodoItem.from_dict(legacy).carried_from is None
    assert _carry_item().to_dict()["carried_from"] is None
```

`Any`・`pytest`がimport済みか確認し、無ければ足す。

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_models.py -q`
Expected: FAIL(`can_carry_over`のimportエラー)

- [ ] **Step 3: 実装する**

`models.py`の`TodoItem`に項目を追加する(`skip_date`の次の行)。

```python
    carried_from: date | None = None  # 初めて繰り越したときの元の基準日(当日のアイテムのみ有効)
```

`to_dict`の`"skip_date"`行の次に追加する。

```python
            "carried_from": self.carried_from.isoformat() if self.carried_from else None,
```

`from_dict`の`skip_date = data.get("skip_date")`の次に`carried_from = data.get("carried_from")`、`TodoItem(...)`の`skip_date=...`行の次に追加する。

```python
            carried_from=date.fromisoformat(carried_from) if carried_from else None,
```

`today_estimate_seconds()`の直後に追加する(`timedelta`が未importなら`from datetime import ... timedelta`に足す)。

```python
def can_carry_over(item: TodoItem, today: date, remaining_seconds: float) -> bool:
    """未完了で見積りが残っている当日のアイテムを、次の日へ繰り越せるか。見積りちょうど使い切った場合は対象外。"""
    return (
        item.schedule_type is ScheduleType.ONE_TIME
        and not is_done(item, today)
        and item.estimate_hours > 0
        and remaining_seconds > 0
        and item.anchor_date <= today
    )


def carry_over_target(item: TodoItem, today: date) -> date:
    """繰越先の日。基準日が過去なら今日、今日なら翌日。"""
    return today if item.anchor_date < today else today + timedelta(days=1)
```

- [ ] **Step 4: 通ることを確認する**

Run: `uv run pytest test/domain/test_models.py -q && uv run mypy`
Expected: PASS

- [ ] **Step 5: コミット(ユーザーに確認してから)**

```bash
git add docs/superpowers/specs/2026-10-21-carry-over-design.md docs/superpowers/plans/2026-10-21-carry-over.md src/todoapp/domain/models.py test/domain/test_models.py
git commit -m "feat: 繰越の判定とcarried_fromを追加"
```

---

### Task 2: `TodoService.carry_over()`

**Files:**
- Modify: `src/todoapp/domain/service.py`(`toggle_skipped`の直後。importに`can_carry_over`・`carry_over_target`を追加)
- Test: `test/domain/test_service.py`

**Interfaces:**
- Consumes: Task 1の`can_carry_over(item, today, remaining_seconds)`・`carry_over_target(item, today)`・`TodoItem.carried_from`
- Produces: `TodoService.carry_over(item_ids: Iterable[str], today: date) -> list[str]`(繰り越したidを返す。対象外は無視する)

- [ ] **Step 1: 失敗するテストを書く**

`test/domain/test_service.py`の末尾に追加する(`_service()`は2026-08-30 09:00のクロック)。

```python
def test_carry_over_moves_anchor_to_tomorrow_and_keeps_remaining_estimate() -> None:
    service, repository, clock = _service()
    item = service.add_item("資料作成", ScheduleType.ONE_TIME, date(2026, 8, 30), estimate_hours=2.0)
    service.start(item.id)
    clock.advance(1800)
    service.stop_running()
    before = service.remaining_seconds(item.id)

    carried = service.carry_over([item.id], date(2026, 8, 30))

    assert carried == [item.id]
    assert item.anchor_date == date(2026, 8, 31)
    assert item.carried_from == date(2026, 8, 30)
    assert service.remaining_seconds(item.id) == before == 5400
    assert repository.saved is not None


def test_carry_over_from_past_anchor_moves_to_today() -> None:
    service, _, _ = _service()
    item = service.add_item("資料作成", ScheduleType.ONE_TIME, date(2026, 8, 28), estimate_hours=2.0)

    service.carry_over([item.id], date(2026, 8, 30))

    assert item.anchor_date == date(2026, 8, 30)
    assert item.carried_from == date(2026, 8, 28)


def test_carry_over_keeps_the_first_carried_from() -> None:
    service, _, _ = _service()
    item = service.add_item("資料作成", ScheduleType.ONE_TIME, date(2026, 8, 28), estimate_hours=2.0)
    service.carry_over([item.id], date(2026, 8, 30))  # 8/28 -> 8/30

    service.carry_over([item.id], date(2026, 8, 30))  # 8/30 -> 8/31

    assert item.anchor_date == date(2026, 8, 31)
    assert item.carried_from == date(2026, 8, 28)


def test_carry_over_twice_in_a_row_does_not_move_a_future_anchor_again() -> None:
    service, _, _ = _service()
    item = service.add_item("資料作成", ScheduleType.ONE_TIME, date(2026, 8, 30), estimate_hours=2.0)
    service.carry_over([item.id], date(2026, 8, 30))

    carried = service.carry_over([item.id], date(2026, 8, 30))

    assert carried == []
    assert item.anchor_date == date(2026, 8, 31)


def test_carry_over_only_moves_eligible_items_in_a_mixed_selection() -> None:
    service, _, _ = _service()
    ok = service.add_item("対象", ScheduleType.ONE_TIME, date(2026, 8, 30), estimate_hours=1.0)
    no_estimate = service.add_item("見積りなし", ScheduleType.ONE_TIME, date(2026, 8, 30))
    daily = service.add_item("毎日", ScheduleType.DAILY, date(2026, 8, 30), estimate_hours=1.0)
    done = service.add_item("完了", ScheduleType.ONE_TIME, date(2026, 8, 30), estimate_hours=1.0)
    service.set_done([done.id], True, date(2026, 8, 30))

    carried = service.carry_over([ok.id, no_estimate.id, daily.id, done.id], date(2026, 8, 30))

    assert carried == [ok.id]
    assert [i.anchor_date for i in (ok, no_estimate, daily, done)] == [date(2026, 8, 31)] + [date(2026, 8, 30)] * 3
    assert no_estimate.carried_from is None


def test_carry_over_returns_empty_and_does_not_save_when_nothing_is_eligible() -> None:
    service, repository, _ = _service()
    item = service.add_item("見積りなし", ScheduleType.ONE_TIME, date(2026, 8, 30))
    repository.saved = None

    assert service.carry_over([item.id], date(2026, 8, 30)) == []
    assert repository.saved is None


def test_carry_over_stops_running_item_and_keeps_its_record() -> None:
    service, _, clock = _service()
    item = service.add_item("資料作成", ScheduleType.ONE_TIME, date(2026, 8, 30), estimate_hours=2.0)
    service.start(item.id)
    clock.advance(600)

    service.carry_over([item.id], date(2026, 8, 30))

    assert service.running_record() is None
    assert service.cumulative_seconds(item.id) == 600


def test_carry_over_does_not_carry_the_today_estimate_to_the_next_day() -> None:
    service, _, _ = _service()
    item = service.add_item("資料作成", ScheduleType.ONE_TIME, date(2026, 8, 30), estimate_hours=2.0)
    service.edit_item(item.id, today_estimate_hours=1.0)

    service.carry_over([item.id], date(2026, 8, 30))

    assert today_estimate_seconds(item, date(2026, 8, 31)) is None
```

先頭のimportに`from todoapp.domain.models import ... today_estimate_seconds`を足す。`add_item`の引数名は`estimate_hours`(`service.py:113-127`で確認済み。位置引数は`name, schedule_type, anchor_date`)。

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/domain/test_service.py -q -k carry_over`
Expected: FAIL(`carry_over`が未定義)

- [ ] **Step 3: 実装する**

`service.py`の`toggle_skipped()`の直後に追加する。importに`can_carry_over`・`carry_over_target`を足す(`is_skipped`のある`from todoapp.domain.models import (...)`ブロック)。

```python
    def carry_over(self, item_ids: Iterable[str], today: date) -> list[str]:
        """未完了で見積りが残っている当日のアイテムを次の日へ繰り越し、繰り越したidを返す(対象外は変更しない)。

        見積りと累積はそのままなので、残り時間は繰越先でも続く。実行中なら停止する(記録は残す)。
        """
        ids = set(item_ids)
        carried: list[str] = []
        for item in self._data.items:
            if item.id not in ids or not can_carry_over(item, today, self.remaining_seconds(item.id)):
                continue
            if item.carried_from is None:
                item.carried_from = item.anchor_date
            item.anchor_date = carry_over_target(item, today)
            carried.append(item.id)
        if not carried:
            return []
        running = self.running_record()
        if running is not None and running.item_id in carried:
            self.stop_running()
        else:
            self._save()
        return carried
```

(`stop_running()`は保存まで行う。`set_done`・`set_skipped`と同じ扱い。)

- [ ] **Step 4: 通ることを確認する**

Run: `uv run pytest test/domain -q && uv run mypy`
Expected: PASS

- [ ] **Step 5: コミット(ユーザーに確認してから)**

```bash
git add src/todoapp/domain/service.py test/domain/test_service.py
git commit -m "feat: TodoService.carry_overを追加"
```

---

### Task 3: バッジ表示(メインパネル・編集一覧)

**Files:**
- Modify: `src/todoapp/ui/formatting.py`、`src/todoapp/ui/main_view.py`(`_render_row`のスキップバッジの次)、`src/todoapp/ui/list_view.py`(行データと`body-cell-name`スロット)
- Test: `test/ui/test_formatting.py`

**Interfaces:**
- Consumes: `TodoItem.carried_from`(Task 1)
- Produces: `carried_badge_text(item: TodoItem) -> str | None`(`繰越 10/20〜`。`当日`以外・未繰越は`None`)

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_formatting.py`の末尾に追加する(importに`carried_badge_text`、`TodoItem`・`ScheduleType`・`date`が無ければ足す)。

```python
def test_carried_badge_text_shows_original_date_for_one_time_items() -> None:
    item = TodoItem(
        name="資料作成", schedule_type=ScheduleType.ONE_TIME, anchor_date=date(2026, 10, 21),
        carried_from=date(2026, 10, 20),
    )  # fmt: skip

    assert carried_badge_text(item) == "繰越 10/20〜"


def test_carried_badge_text_is_none_when_not_carried_or_not_one_time() -> None:
    plain = TodoItem(name="a", schedule_type=ScheduleType.ONE_TIME, anchor_date=date(2026, 10, 21))
    changed = TodoItem(
        name="b", schedule_type=ScheduleType.DAILY, anchor_date=date(2026, 10, 21),
        carried_from=date(2026, 10, 20),
    )  # fmt: skip

    assert carried_badge_text(plain) is None
    assert carried_badge_text(changed) is None
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_formatting.py -q`
Expected: FAIL(importエラー)

- [ ] **Step 3: 実装する**

`formatting.py`に追加する(`TodoItem`・`ScheduleType`のimportが無ければ`from todoapp.domain.models import ...`に足す)。

```python
def carried_badge_text(item: TodoItem) -> str | None:
    """繰り越したアイテムのバッジ文言。当日以外(繰越後にスケジュールを変えた場合)は表示しない。"""
    if item.carried_from is None or item.schedule_type is not ScheduleType.ONE_TIME:
        return None
    return f"繰越 {item.carried_from.strftime('%m/%d')}〜"
```

`main_view.py`の`_render_row`で、`ui.badge(SCHEDULE_LABELS[item.schedule_type.value]).props("outline")`の直前に追加する(importに`carried_badge_text`を足す)。

```python
            carried_text = carried_badge_text(item)
            if carried_text is not None:
                ui.badge(carried_text).props("outline color=orange")
```

`list_view.py`の行データに`"carried": carried_badge_text(item) or "",`を`"skipped"`の次の行へ追加し、`body-cell-name`スロットの`スキップ`バッジの次の行に追加する。

```
                        <q-badge v-if="props.row.carried" outline color="orange">{{ props.row.carried }}</q-badge>
```

- [ ] **Step 4: 通ることを確認する**

Run: `uv run pytest test/ui -q && uv run mypy`
Expected: PASS(既存の画面テストも通ること)

- [ ] **Step 5: コミット(ユーザーに確認してから)**

```bash
git add src/todoapp/ui/formatting.py src/todoapp/ui/main_view.py src/todoapp/ui/list_view.py test/ui/test_formatting.py
git commit -m "feat: 繰越バッジをメインパネルと編集一覧に表示"
```

---

### Task 4: `r`キーの配線とドキュメント

**Files:**
- Modify: `src/todoapp/ui/keyboard.py`(`SHORTCUT_KEYS`・`__init__`引数・`_on_key`)、`src/todoapp/main.py`(`skip_selected_items`の直後と`KeyboardController(...)`の引数)、`src/todoapp/ui/help_dialog.py`、`README.md`、`CLAUDE.md`
- Test: `test/ui/test_keyboard_controller.py`、`test/ui/test_app_flows.py`

**Interfaces:**
- Consumes: `TodoService.carry_over(item_ids, today) -> list[str]`(Task 2)
- Produces: `KeyboardController(..., carry_over_selected_items: Callable[[], None], ...)`

- [ ] **Step 1: 失敗するテストを書く**

`test/ui/test_keyboard_controller.py`の`test_shift_s_is_ignored_in_guarded_states`の直後に追加する(Harnessは`__init__`の引数名からコールバックを自動で作る)。

```python
def test_r_carries_over_selected_items(h: Harness) -> None:
    h.press("r")

    assert h.called("carry_over_selected_items")


def test_r_works_in_read_only_view_because_past_items_are_carried_to_today(h: Harness) -> None:
    h.state.view_date = date.today() - timedelta(days=1)
    h.press("r")

    assert h.called("carry_over_selected_items")


def test_r_is_ignored_while_a_dialog_is_open(h: Harness) -> None:
    h.set_true("is_dialog_open")
    h.press("r")

    assert not h.called("carry_over_selected_items")
```

`test/ui/test_app_flows.py`の`test_shift_s_on_non_repeating_item_warns_and_does_nothing`の直後に追加する(`YESTERDAY = TODAY - timedelta(days=1)`が無ければ`TOMORROW`の次の行に足す)。

```python
async def test_r_carries_item_to_tomorrow_with_badge_and_keeps_remaining(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("資料作成", ScheduleType.ONE_TIME, estimate_hours=2.0)])
    await app_user.open("/")
    click_row(app_user, "資料作成")

    await press(app_user, "r")

    await hides(app_user, "資料作成")
    item = app_env.todos().items[0]
    assert item.anchor_date == TOMORROW
    assert item.carried_from == TODAY
    await press(app_user, "ArrowRight", shift=True)
    await shows(app_user, "資料作成")
    await shows(app_user, f"繰越 {TODAY.strftime('%m/%d')}〜")
    await shows(app_user, "見積り 2時間")


async def test_r_in_past_day_view_carries_item_to_today(app_user: User, app_env: AppEnv) -> None:
    yesterday = TODAY - timedelta(days=1)
    app_env.seed(items=[make_item("前日の作業", ScheduleType.ONE_TIME, anchor_date=yesterday, estimate_hours=1.0)])
    await app_user.open("/")
    await press(app_user, "ArrowLeft", shift=True)
    await shows(app_user, "前日の作業")
    click_row(app_user, "前日の作業")

    await press(app_user, "r")

    await hides(app_user, "前日の作業")
    assert app_env.todos().items[0].anchor_date == TODAY
    await press(app_user, "ArrowRight", shift=True)
    await shows(app_user, "前日の作業")


async def test_r_warns_when_nothing_can_be_carried(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("見積りなし", ScheduleType.ONE_TIME)])
    await app_user.open("/")
    click_row(app_user, "見積りなし")

    await press(app_user, "r")

    await app_user.should_see("繰越できるアイテムがありません")
    assert app_env.todos().items[0].anchor_date == TODAY
    await shows(app_user, "見積りなし")


async def test_r_on_a_done_item_does_not_carry(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("終わった", ScheduleType.ONE_TIME, estimate_hours=1.0, done_date=TODAY)])
    await app_user.open("/")
    select_toggle(app_user, "すべて")
    click_row(app_user, "終わった")

    await press(app_user, "r")

    await app_user.should_see("繰越できるアイテムがありません")
    assert app_env.todos().items[0].anchor_date == TODAY
```

- [ ] **Step 2: 失敗を確認する**

Run: `uv run pytest test/ui/test_keyboard_controller.py test/ui/test_app_flows.py test/ui/test_keyboard.py -q -k "r_ or carries or carry"`
Expected: FAIL(`carry_over_selected_items`が未定義、`r`が`SHORTCUT_KEYS`に無い)

- [ ] **Step 3: 実装する**

`keyboard.py`:
- `SHORTCUT_KEYS`の`"S"`の次に`"r"`を足す。
- `__init__`の引数`skip_selected_items: Callable[[], None],`の次に`carry_over_selected_items: Callable[[], None],`を足し、本体の`self._skip_selected_items = skip_selected_items`の次に`self._carry_over_selected_items = carry_over_selected_items`を足す。
- `_on_key`の`elif e.key == "S" ...`ブロックの次に追加する(閲覧用の過去日でも使えるよう`is_read_only_view`は見ない)。

```python
        elif e.key == "r" and not self._is_dialog_open():
            self._carry_over_selected_items()
```

`main.py`の`skip_selected_items()`の直後に追加し、`KeyboardController(...)`の`skip_selected_items=skip_selected_items,`の次に`carry_over_selected_items=carry_over_selected_items,`を足す。

```python
    def carry_over_selected_items() -> None:
        ids = set(state.selected_item_ids) or ({state.selected_item_id} if state.selected_item_id else set())
        if not ids:
            return
        carried = service.carry_over(ids, date.today())
        if not carried:
            ui.notify("繰越できるアイテムがありません(未完了で見積りが残っている当日のアイテムが対象です)", type="warning")
            return
        ui.notify(f"{len(carried)}件を繰り越しました")
        # メインパネルでは繰り越したアイテムが表示日から外れるため、選択も解除する
        if state.screen is Screen.MAIN:
            state.select(None)
            state.select_items(set())
        refresh_all()
```

`help_dialog.py`の`Shift + S`行の次に追加する。

```python
    ("r", "選択中の当日アイテムの繰越(未完了で見積りが残っているものを、基準日が過去なら今日へ、今日なら翌日へ移す。メイン画面・編集一覧。過去日の表示でも使える)"),
```

`README.md`の`Shift+S`行の次に追加し、22行目の機能説明の末尾に1文を足す。

```
| `r` | 選択中の当日アイテムの繰越(未完了で見積りが残っているものを次の日へ。メイン画面・編集一覧) |
```

機能説明の追記文: `未完了で見積りが残っている当日アイテムは、`r`キーで次の日へ繰り越せ、`繰越`バッジと残りの完了時間が続く。`

`CLAUDE.md`(`todoapp/CLAUDE.md`)の`### スキップ`節の次に`### 繰越`節を追加する。内容は設計書(`docs/superpowers/specs/2026-10-21-carry-over-design.md`)の「ドメイン」「画面」の要点を、既存の節と同じ粒度で書く(対象条件・繰越先・`carried_from`・`r`キー・バッジ・判定は`models.py`の`can_carry_over()`に集約)。
あわせて設計書の画面節の「繰り越したアイテムは表示日から外れるため、選択は解除する」を「メインパネルでは…」に直す。

- [ ] **Step 4: 全体で通ることを確認する**

Run: `uv run pytest -q && uv run mypy`
Expected: PASS(既存テスト668件超+新規。`test_keyboard.py`の登録漏れ検出も通ること)

- [ ] **Step 5: GUIの手動確認をユーザーに依頼する**

アプリは`uv run todoapp`で起動する(GUI確認はユーザーが手動で行う)。確認項目:
- 見積りつきの`当日`アイテムを選んで`r`→今日の一覧から消え、`Shift+→`で翌日に`繰越 MM/DD〜`バッジと見積りが出る
- 前日分を`Shift+←`で開いて`r`→今日へ移る
- 見積りなし・完了済みでは警告が出る
- 実行中のアイテムで`r`→停止して移る

- [ ] **Step 6: コミット(ユーザーに確認してから)**

```bash
git add src/todoapp/ui/keyboard.py src/todoapp/main.py src/todoapp/ui/help_dialog.py README.md CLAUDE.md docs/superpowers/specs/2026-10-21-carry-over-design.md test/ui/test_keyboard_controller.py test/ui/test_app_flows.py
git commit -m "feat: rキーでの繰越を追加"
```

---

## Self-Review メモ

- 設計書の対応: 条件・繰越先・`carried_from`・実行中の停止・`本日の見積り`を引き継がない(Task 1・2)、バッジ(Task 3)、`r`キー・警告・過去日の使用・ヘルプ/README/CLAUDE.md(Task 4)、スキーマ`version`据え置き(Task 1の往復テスト)
- 設計書との差分: 選択解除はメインパネルのみ(編集一覧では繰越後もアイテムが残るため)。Task 4でCLAUDE.mdと設計書の文言を合わせる
- 型・名前の一貫性: `can_carry_over(item, today, remaining_seconds)`・`carry_over_target(item, today)`・`TodoService.carry_over(item_ids, today) -> list[str]`・`carried_badge_text(item)`・`carry_over_selected_items`
