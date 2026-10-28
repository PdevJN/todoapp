from datetime import date, datetime

import pytest

from todoapp.domain.models import (
    MANUAL_ITEM_ID_PREFIX,
    AppData,
    ExecutionRecord,
    ScheduleType,
    validate_manual_record,
)
from todoapp.domain.service import ItemGapRow, TodoService

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
