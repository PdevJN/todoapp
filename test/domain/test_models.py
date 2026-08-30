from datetime import date, datetime

from todoapp.domain.models import (
    Category,
    ExecutionRecord,
    ScheduleType,
    TodoItem,
    is_category_expired,
    is_due_today,
)


def _item(schedule_type: ScheduleType, anchor_date: date) -> TodoItem:
    return TodoItem(name="test", schedule_type=schedule_type, anchor_date=anchor_date)


def test_daily_is_always_due() -> None:
    item = _item(ScheduleType.DAILY, date(2026, 1, 1))
    assert is_due_today(item, date(2026, 8, 30))


def test_weekly_is_due_on_same_weekday_only() -> None:
    anchor = date(2026, 8, 24)  # Monday
    item = _item(ScheduleType.WEEKLY, anchor)
    assert is_due_today(item, date(2026, 8, 31))  # next Monday
    assert not is_due_today(item, date(2026, 8, 30))  # Sunday


def test_monthly_is_due_on_same_day_only() -> None:
    anchor = date(2026, 1, 15)
    item = _item(ScheduleType.MONTHLY, anchor)
    assert is_due_today(item, date(2026, 8, 15))
    assert not is_due_today(item, date(2026, 8, 14))


def test_monthly_clamps_to_last_day_of_short_month() -> None:
    anchor = date(2026, 1, 31)
    item = _item(ScheduleType.MONTHLY, anchor)
    assert is_due_today(item, date(2026, 2, 28))


def test_one_time_is_due_only_on_anchor_date() -> None:
    anchor = date(2026, 8, 30)
    item = _item(ScheduleType.ONE_TIME, anchor)
    assert is_due_today(item, anchor)
    assert not is_due_today(item, date(2026, 8, 29))
    assert not is_due_today(item, date(2026, 8, 31))


def test_todo_item_dict_roundtrip() -> None:
    item = _item(ScheduleType.WEEKLY, date(2026, 8, 24))
    restored = TodoItem.from_dict(item.to_dict())
    assert restored == item


def test_execution_record_dict_roundtrip_preserves_id() -> None:
    record = ExecutionRecord(
        item_id="item-1",
        item_name="散歩",
        start_time=datetime(2026, 8, 30, 9, 0, 0),
        end_time=datetime(2026, 8, 30, 9, 10, 0),
    )
    restored = ExecutionRecord.from_dict(record.to_dict())
    assert restored == record


def test_execution_record_from_dict_assigns_id_when_missing() -> None:
    data = {
        "item_id": "item-1",
        "item_name": "散歩",
        "start_time": "2026-08-30T09:00:00",
        "end_time": None,
    }
    restored = ExecutionRecord.from_dict(data)
    assert restored.id


def test_category_dict_roundtrip() -> None:
    category = Category(name="仕事", kind="業務", expiry_date=date(2026, 12, 31))
    restored = Category.from_dict(category.to_dict())
    assert restored == category


def test_category_from_dict_assigns_id_when_missing() -> None:
    data = {"name": "仕事", "kind": "", "expiry_date": None}
    restored = Category.from_dict(data)
    assert restored.id
    assert restored.color


def test_is_category_expired_when_past_expiry_date() -> None:
    category = Category(name="仕事", expiry_date=date(2026, 1, 1))
    assert is_category_expired(category, date(2026, 1, 2))
    assert not is_category_expired(category, date(2025, 12, 31))


def test_is_category_expired_when_no_expiry_date() -> None:
    category = Category(name="仕事")
    assert not is_category_expired(category, date(2099, 1, 1))
