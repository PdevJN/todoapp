from datetime import date, datetime, timedelta

from todoapp.domain.models import (
    Category,
    DoneFilter,
    ExecutionRecord,
    ScheduleType,
    TodoItem,
    is_category_expired,
    is_done,
    is_due_today,
    matches_done_filter,
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


def test_monthly_is_not_due_the_day_after_the_clamped_day() -> None:
    # 境界値分析: 月末調整される側の上限境界(調整後の月末日の翌日=翌月1日)は対象外
    anchor = date(2026, 1, 31)
    item = _item(ScheduleType.MONTHLY, anchor)
    assert not is_due_today(item, date(2026, 3, 1))


def test_monthly_clamps_to_leap_day_in_leap_year() -> None:
    # 境界値分析: 基準日30日が閏年2月は29日(閏日)にクランプされ、
    # 平年のクランプ先(28日)とは異なる境界になることを確認する
    anchor = date(2026, 1, 30)
    item = _item(ScheduleType.MONTHLY, anchor)
    assert is_due_today(item, date(2028, 2, 29))
    assert not is_due_today(item, date(2028, 2, 28))


def test_weekly_is_due_exactly_one_week_later_across_year_boundary() -> None:
    # 境界値分析: 年またぎでも「同じ曜日」の判定が7日後の境界で成立することを確認する
    anchor = date(2025, 12, 29)
    item = _item(ScheduleType.WEEKLY, anchor)
    one_week_later = anchor + timedelta(days=7)
    assert one_week_later.year != anchor.year
    assert is_due_today(item, anchor)  # 基準日そのものも対象日になる
    assert is_due_today(item, one_week_later)
    assert not is_due_today(item, anchor + timedelta(days=1))
    assert not is_due_today(item, anchor + timedelta(days=6))


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
    category = Category(name="仕事", kind="業務", expiry_date=date(2026, 12, 31), prj_code="PRJ-001")
    restored = Category.from_dict(category.to_dict())
    assert restored == category


def test_category_from_dict_assigns_id_when_missing() -> None:
    data = {"name": "仕事", "kind": "", "expiry_date": None}
    restored = Category.from_dict(data)
    assert restored.id
    assert restored.color
    assert restored.prj_code == ""


def test_is_category_expired_when_past_expiry_date() -> None:
    category = Category(name="仕事", expiry_date=date(2026, 1, 1))
    assert is_category_expired(category, date(2026, 1, 2))
    assert not is_category_expired(category, date(2025, 12, 31))


def test_is_category_expired_when_no_expiry_date() -> None:
    category = Category(name="仕事")
    assert not is_category_expired(category, date(2099, 1, 1))


def test_is_category_expired_on_the_expiry_date_itself_is_not_expired() -> None:
    # 境界値分析: 判定は`expiry_date < today`(厳密未満)のため、
    # 有効期限日当日はまだ「期限切れ」とはみなされない
    category = Category(name="仕事", expiry_date=date(2026, 1, 1))
    assert not is_category_expired(category, date(2026, 1, 1))


def test_todo_item_done_date_roundtrip() -> None:
    item = _item(ScheduleType.DAILY, date(2026, 8, 24))
    item.done_date = date(2026, 8, 30)

    assert TodoItem.from_dict(item.to_dict()) == item


def test_todo_item_from_dict_without_done_date_is_not_done() -> None:
    data = _item(ScheduleType.DAILY, date(2026, 8, 24)).to_dict()
    del data["done_date"]

    assert TodoItem.from_dict(data).done_date is None


def test_item_without_done_date_is_not_done() -> None:
    for schedule_type in ScheduleType:
        assert is_done(_item(schedule_type, date(2026, 8, 30)), date(2026, 8, 30)) is False


def test_repeating_item_is_done_only_on_the_day_it_was_completed() -> None:
    for schedule_type in (ScheduleType.DAILY, ScheduleType.WEEKLY, ScheduleType.MONTHLY):
        item = _item(schedule_type, date(2026, 8, 30))
        item.done_date = date(2026, 8, 30)

        assert is_done(item, date(2026, 8, 30)) is True
        assert is_done(item, date(2026, 8, 31)) is False
        assert is_done(item, date(2026, 9, 6)) is False


def test_one_time_item_stays_done() -> None:
    item = _item(ScheduleType.ONE_TIME, date(2026, 8, 30))
    item.done_date = date(2026, 8, 30)

    assert is_done(item, date(2026, 8, 30)) is True
    assert is_done(item, date(2026, 9, 30)) is True


def test_matches_done_filter() -> None:
    today = date(2026, 8, 30)
    done_item = _item(ScheduleType.DAILY, today)
    done_item.done_date = today
    open_item = _item(ScheduleType.DAILY, today)

    assert matches_done_filter(open_item, today, DoneFilter.ACTIVE) is True
    assert matches_done_filter(done_item, today, DoneFilter.ACTIVE) is False
    assert matches_done_filter(open_item, today, DoneFilter.DONE) is False
    assert matches_done_filter(done_item, today, DoneFilter.DONE) is True
    assert matches_done_filter(open_item, today, DoneFilter.ALL) is True
    assert matches_done_filter(done_item, today, DoneFilter.ALL) is True


def test_weekly_is_not_due_before_anchor_date() -> None:
    # 境界値分析: 基準日当日は対象、基準日の1週間前(同じ曜日)は対象外
    anchor = date(2026, 8, 24)  # Monday
    item = _item(ScheduleType.WEEKLY, anchor)
    assert is_due_today(item, anchor)
    assert not is_due_today(item, date(2026, 8, 17))
    assert is_due_today(item, date(2026, 8, 31))


def test_monthly_is_not_due_before_anchor_date() -> None:
    # 境界値分析: 基準日当日は対象、基準日の前月の同じ日は対象外
    anchor = date(2026, 8, 15)
    item = _item(ScheduleType.MONTHLY, anchor)
    assert is_due_today(item, anchor)
    assert not is_due_today(item, date(2026, 7, 15))
    assert is_due_today(item, date(2026, 9, 15))


def test_monthly_clamped_day_before_anchor_date_is_not_due() -> None:
    # 月末調整でも、基準日より前の月は対象外(2/28は基準日1/31より後なので対象)
    anchor = date(2026, 3, 31)
    item = _item(ScheduleType.MONTHLY, anchor)
    assert not is_due_today(item, date(2026, 2, 28))
    assert is_due_today(item, date(2026, 4, 30))


def test_daily_is_due_even_before_anchor_date() -> None:
    # 毎日は基準日を使わない(編集フォームでも設定できない)
    item = _item(ScheduleType.DAILY, date(2026, 8, 30))
    assert is_due_today(item, date(2026, 1, 1))
