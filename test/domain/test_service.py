from datetime import date, datetime, timedelta

from todoapp.domain.models import AppData, ScheduleType
from todoapp.domain.service import TodoService


class FakeRepository:
    def __init__(self) -> None:
        self.saved: AppData | None = None

    def load(self) -> AppData:
        return AppData(items=[], records=[])

    def save(self, data: AppData) -> None:
        self.saved = data


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)

    def __call__(self) -> datetime:
        return self._now


def _service() -> tuple[TodoService, FakeRepository, FakeClock]:
    repository = FakeRepository()
    clock = FakeClock(datetime(2026, 8, 30, 9, 0, 0))
    service = TodoService(repository, clock=clock)
    return service, repository, clock


def test_add_item_appends_and_saves() -> None:
    service, repository, _ = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    assert item in service.items
    assert repository.saved is not None
    assert repository.saved.items == [item]


def test_start_then_stop_records_elapsed_time() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(600)
    service.stop_running()
    assert service.running_record() is None
    assert service.cumulative_seconds(item.id) == 600


def test_starting_another_item_stops_the_running_one() -> None:
    service, _, clock = _service()
    item_a = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    item_b = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))

    service.start(item_a.id)
    clock.advance(300)
    service.start(item_b.id)

    running = service.running_record()
    assert running is not None
    assert running.item_id == item_b.id
    assert service.cumulative_seconds(item_a.id) == 300


def test_toggle_execution_starts_and_stops() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))

    service.toggle_execution(item.id)
    assert service.running_record() is not None

    clock.advance(120)
    service.toggle_execution(item.id)
    assert service.running_record() is None
    assert service.cumulative_seconds(item.id) == 120


def test_cancel_running_removes_the_open_record() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(60)

    service.cancel_running(item.id)

    assert service.running_record() is None
    assert service.records == []


def test_cancel_running_does_nothing_when_item_is_not_running() -> None:
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))

    service.cancel_running(item.id)

    assert service.records == []


def test_delete_item_stops_running_record_then_removes_item_but_keeps_records() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(90)

    service.delete_item(item.id)

    assert service.items == []
    assert len(service.records) == 1
    assert service.records[0].end_time is not None
    assert service.records[0].item_name == "散歩"


def test_reorder_moves_item_to_new_index() -> None:
    service, _, _ = _service()
    item_a = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    item_b = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    service.add_item("C", ScheduleType.DAILY, date(2026, 8, 30))

    service.reorder(0, 2)

    assert [item.name for item in service.items] == ["B", "C", "A"]
    assert service.items[2] is item_a
    assert service.items[0] is item_b


def test_today_total_seconds_excludes_other_days() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))

    service.start(item.id)
    clock.advance(600)
    service.stop_running()

    yesterday_record = service.records[0]
    yesterday_record.start_time = datetime(2026, 8, 29, 9, 0, 0)
    yesterday_record.end_time = datetime(2026, 8, 29, 9, 10, 0)

    service.start(item.id)
    clock.advance(300)
    service.stop_running()

    assert service.today_total_seconds(item.id, date(2026, 8, 30)) == 300
    assert service.cumulative_seconds(item.id) == 900


def test_remaining_hours_decreases_as_execution_accumulates() -> None:
    service, _, clock = _service()
    item = service.add_item(
        "散歩", ScheduleType.DAILY, date(2026, 8, 30), estimate_hours=2.0
    )
    assert service.remaining_hours(item.id) == 2.0

    service.start(item.id)
    clock.advance(3600)
    service.stop_running()

    assert service.remaining_hours(item.id) == 1.0


def test_remaining_hours_does_not_go_below_zero() -> None:
    service, _, clock = _service()
    item = service.add_item(
        "散歩", ScheduleType.DAILY, date(2026, 8, 30), estimate_hours=1.0
    )

    service.start(item.id)
    clock.advance(7200)
    service.stop_running()

    assert service.remaining_hours(item.id) == 0.0


def test_edit_record_updates_start_and_end_time() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(600)
    service.stop_running()
    record = service.records[0]

    new_start = datetime(2026, 8, 30, 8, 0, 0)
    new_end = datetime(2026, 8, 30, 8, 30, 0)
    service.edit_record(record.id, start_time=new_start, end_time=new_end)

    assert service.records[0].start_time == new_start
    assert service.records[0].end_time == new_end
    assert service.cumulative_seconds(item.id) == 1800


def test_delete_record_removes_it() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(60)
    service.stop_running()
    record = service.records[0]

    service.delete_record(record.id)

    assert service.records == []


def test_remaining_seconds_reflects_small_amounts_of_execution() -> None:
    service, _, clock = _service()
    item = service.add_item(
        "散歩", ScheduleType.DAILY, date(2026, 8, 30), estimate_hours=3.0
    )

    service.start(item.id)
    clock.advance(60)
    service.stop_running()

    assert service.remaining_seconds(item.id) == 3 * 3600 - 60
