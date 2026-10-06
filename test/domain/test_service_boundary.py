"""`domain/service.py`のユースケースを、同値クラスと境界値で網羅する(ドメイン分析)。"""

from datetime import date, datetime, timedelta

import pytest

from todoapp.domain.models import AppData, DoneFilter, ScheduleType
from todoapp.domain.service import TodoService

TODAY = date(2026, 8, 30)


class _Repository:
    def load(self) -> AppData:
        return AppData(items=[], records=[])

    def save(self, data: AppData) -> None:
        pass


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 30, 9, 0, 0)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _service() -> tuple[TodoService, _Clock]:
    clock = _Clock()
    return TodoService(_Repository(), clock=clock), clock


def _run(service: TodoService, clock: _Clock, item_id: str, seconds: float) -> None:
    service.start(item_id)
    clock.advance(seconds)
    service.stop_running()


# --- 見積りと超過判定 ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("estimate_hours", "elapsed", "over", "remaining"),
    [
        (1.0, 3599, False, 1),  # 見積りの1秒前
        (1.0, 3600, False, 0),  # ちょうど(超過扱いにしない)
        (1.0, 3601, True, 0),  # 1秒超過(残りは0で止まる)
        (1 / 6, 599, False, 1),  # 10分=0.1666…時間でも秒に丸めて比べる
        (1 / 6, 600, False, 0),
        (1 / 6, 601, True, 0),
        (0.0, 0, False, 0),  # 見積り未設定は常に超過ではない
        (0.0, 10_000, False, 0),
    ],
)
def test_over_estimate_and_remaining_boundaries(
    estimate_hours: float, elapsed: int, over: bool, remaining: int
) -> None:
    service, clock = _service()
    item = service.add_item("A", ScheduleType.DAILY, TODAY, estimate_hours=estimate_hours)
    _run(service, clock, item.id, elapsed)

    assert service.is_over_estimate(item.id) is over
    assert service.remaining_seconds(item.id) == pytest.approx(remaining, abs=0.5)


def test_running_record_counts_toward_cumulative_and_over_estimate() -> None:
    # 実行中の記録も、現在時刻までの経過時間として累積に含まれる
    service, clock = _service()
    item = service.add_item("A", ScheduleType.DAILY, TODAY, estimate_hours=1.0)
    service.start(item.id)
    clock.advance(3600)
    assert not service.is_over_estimate(item.id)
    clock.advance(1)
    assert service.is_over_estimate(item.id)


# --- 本日の見積り -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [(0, 1800), (1799, 1), (1800, 0), (1801, 0)],
)
def test_today_remaining_seconds_boundaries(elapsed: int, expected: int) -> None:
    service, clock = _service()
    item = service.add_item("A", ScheduleType.DAILY, TODAY)
    service.edit_item(item.id, today_estimate_hours=0.5)
    _run(service, clock, item.id, elapsed)

    assert service.today_remaining_seconds(item.id, TODAY) == expected


def test_today_remaining_seconds_ignores_executions_of_other_days() -> None:
    service, clock = _service()
    item = service.add_item("A", ScheduleType.DAILY, TODAY)
    _run(service, clock, item.id, 600)  # 前日分として扱うため、記録の日付をずらす
    clock.advance(24 * 3600)
    service.edit_item(item.id, today_estimate_hours=1.0)
    next_day = TODAY + timedelta(days=1)

    assert service.today_remaining_seconds(item.id, next_day) == 3600


def test_today_estimate_is_invalid_the_day_after_it_was_set() -> None:
    service, clock = _service()
    item = service.add_item("A", ScheduleType.DAILY, TODAY)
    service.edit_item(item.id, today_estimate_hours=1.0)

    assert service.today_remaining_seconds(item.id, TODAY) == 3600
    assert service.today_remaining_seconds(item.id, TODAY + timedelta(days=1)) is None
    assert service.today_remaining_seconds(item.id, TODAY - timedelta(days=1)) is None


@pytest.mark.parametrize(
    ("hours", "expected_date"),
    [(0.0, None), (-1.0, None), (1 / 3600, TODAY), (1.0, TODAY)],
)
def test_edit_item_today_estimate_sets_or_clears_the_date(hours: float, expected_date: date | None) -> None:
    service, _ = _service()
    item = service.add_item("A", ScheduleType.DAILY, TODAY)
    service.edit_item(item.id, today_estimate_hours=1.0)  # 一度設定してから境界値で上書きする

    service.edit_item(item.id, today_estimate_hours=hours)

    assert item.today_estimate_date == expected_date


def test_today_estimate_total_excludes_items_not_due_today() -> None:
    service, _ = _service()
    due = service.add_item("due", ScheduleType.DAILY, TODAY)
    not_due = service.add_item("not due", ScheduleType.ONE_TIME, TODAY + timedelta(days=1))
    for item in (due, not_due):
        service.edit_item(item.id, today_estimate_hours=1.0)

    assert service.today_estimate_total_seconds(TODAY) == 3600


def test_today_estimate_total_is_zero_without_items() -> None:
    service, _ = _service()
    assert service.today_estimate_total_seconds(TODAY) == 0


# --- edit_item(None=変更なしの同値クラス) -------------------------------------------------


def test_edit_item_without_arguments_changes_nothing() -> None:
    service, _ = _service()
    item = service.add_item("A", ScheduleType.WEEKLY, TODAY, estimate_hours=2.0)

    service.edit_item(item.id)

    assert (item.name, item.schedule_type, item.anchor_date, item.estimate_hours) == (
        "A",
        ScheduleType.WEEKLY,
        TODAY,
        2.0,
    )


def test_edit_item_rename_only_updates_records_of_that_item() -> None:
    service, clock = _service()
    renamed = service.add_item("old", ScheduleType.DAILY, TODAY)
    other = service.add_item("other", ScheduleType.DAILY, TODAY)
    _run(service, clock, renamed.id, 60)
    _run(service, clock, other.id, 60)

    service.edit_item(renamed.id, name="new")

    assert [r.item_name for r in service.records] == ["new", "other"]


def test_edit_item_unknown_id_raises_key_error() -> None:
    service, _ = _service()
    with pytest.raises(KeyError):
        service.edit_item("missing", name="x")


# --- 完了(set_done / toggle_done) -------------------------------------------------------


def test_toggle_done_with_no_matching_items_marks_nothing() -> None:
    # 空集合・存在しないIDは「全て完了済み」とは扱わない(items空のためall_done=False)
    service, _ = _service()
    item = service.add_item("A", ScheduleType.ONE_TIME, TODAY)

    service.toggle_done([], TODAY)
    service.toggle_done(["missing"], TODAY)

    assert item.done_date is None


@pytest.mark.parametrize(
    ("done_flags", "expected_all_done"),
    [
        ([False], True),  # 1件・未完了 -> 完了
        ([True], False),  # 1件・完了済み -> 未完了
        ([False, False], True),  # 全て未完了 -> 全て完了
        ([True, True], False),  # 全て完了済み -> 全て未完了
        ([True, False], True),  # 混在 -> 全て完了
        ([False, True], True),
    ],
)
def test_toggle_done_decision_table(done_flags: list[bool], expected_all_done: bool) -> None:
    service, _ = _service()
    items = []
    for index, done in enumerate(done_flags):
        item = service.add_item(f"item{index}", ScheduleType.ONE_TIME, TODAY)
        if done:
            service.set_done([item.id], True, TODAY)
        items.append(item)

    service.toggle_done([item.id for item in items], TODAY)

    assert all((item.done_date == TODAY) is expected_all_done for item in items)


def test_set_done_stops_running_item_only_when_it_is_in_the_target_and_done_is_true() -> None:
    service, clock = _service()
    running = service.add_item("running", ScheduleType.ONE_TIME, TODAY)
    other = service.add_item("other", ScheduleType.ONE_TIME, TODAY)
    service.start(running.id)

    service.set_done([other.id], True, TODAY)  # 対象外 -> 実行は継続
    assert service.running_record() is not None
    service.set_done([running.id], False, TODAY)  # 未完了へ戻す -> 実行は継続
    assert service.running_record() is not None
    clock.advance(10)
    service.set_done([running.id], True, TODAY)  # 対象かつ完了 -> 停止
    assert service.running_record() is None
    assert service.cumulative_seconds(running.id) == 10


# --- 並び替え -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (0, 0, "ABC"),  # 同じ位置
        (0, 2, "BCA"),  # 先頭 -> 末尾
        (2, 0, "CAB"),  # 末尾 -> 先頭
        (1, 2, "ACB"),  # 隣へ
    ],
)
def test_reorder_boundaries(old: int, new: int, expected: str) -> None:
    service, _ = _service()
    for name in "ABC":
        service.add_item(name, ScheduleType.DAILY, TODAY)

    service.reorder(old, new)

    assert "".join(item.name for item in service.items) == expected


@pytest.mark.parametrize(
    ("moved", "target", "expected"),
    [
        ("A", "A", "ABCD"),  # 自分自身へ
        ("A", "D", "BCDA"),  # 先頭 -> 末尾の位置
        ("D", "A", "DABC"),  # 末尾 -> 先頭の位置
        ("B", "C", "ACBD"),  # 隣へ(フィルタで間が非表示でも全体の位置へ寄せる)
    ],
)
def test_move_item_to_boundaries(moved: str, target: str, expected: str) -> None:
    service, _ = _service()
    ids = {name: service.add_item(name, ScheduleType.DAILY, TODAY).id for name in "ABCD"}

    service.move_item_to(ids[moved], ids[target])

    assert "".join(item.name for item in service.items) == expected


# --- 入力補完の候補 -----------------------------------------------------------------------


def test_item_name_candidates_empty_when_no_items_or_records() -> None:
    service, _ = _service()
    assert service.item_name_candidates() == []


def test_item_name_candidates_orders_items_newest_first_then_records_newest_first() -> None:
    service, clock = _service()
    old = service.add_item("old", ScheduleType.DAILY, TODAY)
    service.add_item("new", ScheduleType.DAILY, TODAY)
    _run(service, clock, old.id, 60)
    service.delete_item(old.id)  # 削除済みアイテムの名前も、実行記録から候補に残る

    assert service.item_name_candidates() == ["new", "old"]


def test_item_name_candidates_dedupes_and_skips_empty_names() -> None:
    service, clock = _service()
    item = service.add_item("same", ScheduleType.DAILY, TODAY)
    service.add_item("", ScheduleType.DAILY, TODAY)
    _run(service, clock, item.id, 60)

    assert service.item_name_candidates() == ["same"]


# --- 絞り込み -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("done_filter", "expected"),
    [(DoneFilter.ACTIVE, ["open"]), (DoneFilter.DONE, ["done"]), (DoneFilter.ALL, ["open", "done"])],
)
def test_items_due_today_applies_the_done_filter(done_filter: DoneFilter, expected: list[str]) -> None:
    service, _ = _service()
    service.add_item("open", ScheduleType.DAILY, TODAY)
    done = service.add_item("done", ScheduleType.DAILY, TODAY)
    service.set_done([done.id], True, TODAY)

    assert [item.name for item in service.items_due_today(TODAY, done_filter)] == expected
