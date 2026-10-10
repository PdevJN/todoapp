"""実行中にアプリが終了・中断した場合と、日跨ぎの場合のサービスの振る舞い。"""

from datetime import datetime, timedelta

from todoapp.domain.models import AppData, ExecutionRecord, ScheduleType
from todoapp.domain.service import TodoService


class FakeRepository:
    def __init__(self, data: AppData | None = None) -> None:
        self.data = data or AppData(items=[], records=[])

    def load(self) -> AppData:
        return self.data

    def save(self, data: AppData) -> None:
        self.data = data


class FakeAliveStore:
    def __init__(self, value: datetime | None = None) -> None:
        self.value = value
        self.save_count = 0

    def load(self) -> datetime | None:
        return self.value

    def save(self, value: datetime) -> None:
        self.value = value
        self.save_count += 1


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)

    def __call__(self) -> datetime:
        return self.now


DAY1 = datetime(2026, 10, 10)
DAY2 = datetime(2026, 10, 11)
DAY3 = datetime(2026, 10, 12)


def _at(day: datetime, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return day.replace(hour=hour, minute=minute, second=second)


def _restart(
    running_start: datetime,
    *,
    now: datetime,
    alive: datetime | None,
    running_end: datetime | None = None,
) -> tuple[TodoService, FakeAliveStore]:
    """実行中(`running_end`未指定)の記録が残った状態で、アプリが再起動した場面を作る。"""
    seed = TodoService(FakeRepository(), clock=lambda: running_start)
    item = seed.add_item("作業", ScheduleType.DAILY, running_start.date())
    record = ExecutionRecord(item_id=item.id, item_name=item.name, start_time=running_start, end_time=running_end)
    data = AppData(items=[item], records=[record])
    store = FakeAliveStore(alive)
    return TodoService(FakeRepository(data), clock=lambda: now, alive_store=store), store


def _spans(service: TodoService) -> list[tuple[datetime, datetime | None]]:
    return [(r.start_time, r.end_time) for r in sorted(service.records, key=lambda r: r.start_time)]


# --- 起動時の復旧 --------------------------------------------------------------------------


def test_recover_stops_running_record_at_last_alive_time() -> None:
    service, _ = _restart(_at(DAY1, 9), now=_at(DAY1, 15), alive=_at(DAY1, 10, 30))

    service.recover_interrupted()

    assert service.running_record() is None
    assert _spans(service) == [(_at(DAY1, 9), _at(DAY1, 10, 30))]


def test_recover_closes_at_start_when_last_alive_is_before_start() -> None:
    # 前回の生存時刻が古い(記録の開始より前)場合は、開始より前に閉じないよう開始時刻で閉じる
    service, _ = _restart(_at(DAY1, 9), now=_at(DAY1, 15), alive=_at(DAY1, 8))

    service.recover_interrupted()

    assert _spans(service) == [(_at(DAY1, 9), _at(DAY1, 9))]


def test_recover_closes_at_start_without_alive_time() -> None:
    service, _ = _restart(_at(DAY1, 9), now=_at(DAY1, 15), alive=None)

    service.recover_interrupted()

    assert _spans(service) == [(_at(DAY1, 9), _at(DAY1, 9))]


def test_recover_does_not_close_after_now_when_alive_time_is_in_the_future() -> None:
    service, _ = _restart(_at(DAY1, 9), now=_at(DAY1, 10), alive=_at(DAY1, 12))

    service.recover_interrupted()

    assert _spans(service) == [(_at(DAY1, 9), _at(DAY1, 10))]


def test_recover_splits_record_that_spans_midnight() -> None:
    service, _ = _restart(_at(DAY1, 23), now=_at(DAY2, 8), alive=_at(DAY2, 1))

    service.recover_interrupted()

    assert service.running_record() is None
    assert _spans(service) == [(_at(DAY1, 23), DAY2), (DAY2, _at(DAY2, 1))]


def test_recover_splits_record_that_spans_several_midnights() -> None:
    service, _ = _restart(_at(DAY1, 22), now=_at(DAY3, 9), alive=_at(DAY3, 2))

    service.recover_interrupted()

    assert _spans(service) == [(_at(DAY1, 22), DAY2), (DAY2, DAY3), (DAY3, _at(DAY3, 2))]


def test_recover_keeps_item_identity_in_split_records() -> None:
    service, _ = _restart(_at(DAY1, 23), now=_at(DAY2, 8), alive=_at(DAY2, 1))

    service.recover_interrupted()

    assert {r.item_id for r in service.records} == {service.items[0].id}
    assert {r.item_name for r in service.records} == {"作業"}


def test_recover_changes_nothing_without_running_record() -> None:
    service, _ = _restart(_at(DAY1, 9), now=_at(DAY1, 15), alive=_at(DAY1, 12), running_end=_at(DAY1, 10))

    service.recover_interrupted()

    assert _spans(service) == [(_at(DAY1, 9), _at(DAY1, 10))]


# --- 実行中の日跨ぎ ------------------------------------------------------------------------


def _running(start: datetime) -> tuple[TodoService, FakeClock, FakeAliveStore, str]:
    clock = FakeClock(start)
    store = FakeAliveStore()
    service = TodoService(FakeRepository(), clock=clock, alive_store=store)
    item = service.add_item("作業", ScheduleType.DAILY, start.date())
    service.start(item.id)
    return service, clock, store, item.id


def _run_until(service: TodoService, clock: FakeClock, target: datetime) -> None:
    """実際の1秒タイマーのように、時計を細かく進めながら見守りを呼ぶ(30秒刻みで中断扱いにならない)。"""
    while clock.now < target:
        clock.now = min(clock.now + timedelta(seconds=30), target)
        assert not service.keep_alive()


def test_keep_alive_splits_running_record_at_midnight_and_continues() -> None:
    service, clock, _, item_id = _running(_at(DAY1, 23, 30))

    _run_until(service, clock, _at(DAY2, 0, 10))

    running = service.running_record()
    assert running is not None
    assert (running.item_id, running.start_time) == (item_id, DAY2)
    assert _spans(service) == [(_at(DAY1, 23, 30), DAY2), (DAY2, None)]


def test_keep_alive_leaves_running_record_within_the_same_day() -> None:
    service, clock, _, _ = _running(_at(DAY1, 9))

    clock.advance(30)
    service.keep_alive()

    assert _spans(service) == [(_at(DAY1, 9), None)]


def test_split_at_midnight_keeps_daily_totals_correct() -> None:
    service, clock, _, item_id = _running(_at(DAY1, 23, 30))

    _run_until(service, clock, _at(DAY2, 0, 10))

    assert service.today_total_seconds(item_id, DAY1.date()) == 30 * 60
    assert service.today_total_seconds(item_id, DAY2.date()) == 10 * 60


# --- スリープ等による中断の検出 ----------------------------------------------------------------


def test_keep_alive_stops_at_last_tick_when_a_long_gap_is_detected() -> None:
    service, clock, _, _ = _running(_at(DAY1, 9))
    _run_until(service, clock, _at(DAY1, 9, 10))  # 9:10 まで動作していた

    clock.advance(3600)  # スリープ: 1時間タイマーが止まる
    stopped_by_suspend = service.keep_alive()

    assert stopped_by_suspend
    assert service.running_record() is None
    assert _spans(service) == [(_at(DAY1, 9), _at(DAY1, 9, 10))]


def test_keep_alive_does_not_treat_a_short_gap_as_suspend() -> None:
    service, clock, _, _ = _running(_at(DAY1, 9))

    clock.advance(5)
    stopped_by_suspend = service.keep_alive()

    assert not stopped_by_suspend
    assert service.running_record() is not None


def test_suspend_across_midnight_stops_at_last_tick_without_splitting() -> None:
    service, clock, _, _ = _running(_at(DAY1, 23, 50))
    _run_until(service, clock, _at(DAY1, 23, 50, 10))  # 直前まで動作

    clock.now = _at(DAY2, 7)  # 一晩スリープ
    service.keep_alive()

    assert _spans(service) == [(_at(DAY1, 23, 50), _at(DAY1, 23, 50, 10))]


def test_start_after_idle_gap_is_not_mistaken_for_suspend() -> None:
    clock = FakeClock(_at(DAY1, 9))
    service = TodoService(FakeRepository(), clock=clock, alive_store=FakeAliveStore())
    item = service.add_item("作業", ScheduleType.DAILY, DAY1.date())
    service.keep_alive()  # 実行中でなければ何もしない

    clock.advance(7200)  # 2時間操作なし(スリープ含む)
    service.start(item.id)
    clock.advance(1)
    stopped_by_suspend = service.keep_alive()

    assert not stopped_by_suspend
    assert service.running_record() is not None


def test_keep_alive_without_running_record_does_nothing() -> None:
    clock = FakeClock(_at(DAY1, 9))
    store = FakeAliveStore()
    service = TodoService(FakeRepository(), clock=clock, alive_store=store)

    clock.advance(7200)

    assert not service.keep_alive()
    assert store.save_count == 0


# --- 生存時刻の保存 --------------------------------------------------------------------------


def test_start_saves_alive_time_immediately() -> None:
    _, _, store, _ = _running(_at(DAY1, 9))

    assert store.value == _at(DAY1, 9)


def test_keep_alive_saves_alive_time_every_ten_seconds_only() -> None:
    service, clock, store, _ = _running(_at(DAY1, 9))

    clock.advance(5)
    service.keep_alive()
    assert store.value == _at(DAY1, 9)  # 10秒未満は書き込まない

    clock.advance(6)
    service.keep_alive()
    assert store.value == _at(DAY1, 9, 0, 11)


def test_service_works_without_alive_store() -> None:
    clock = FakeClock(_at(DAY1, 9))
    service = TodoService(FakeRepository(), clock=clock)
    item = service.add_item("作業", ScheduleType.DAILY, DAY1.date())
    service.start(item.id)

    clock.advance(5)

    assert not service.keep_alive()
