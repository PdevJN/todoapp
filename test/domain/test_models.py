from datetime import date

from todoapp.domain.models import ScheduleType, TodoItem, is_due_today


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
