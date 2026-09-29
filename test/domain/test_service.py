from datetime import date, datetime, timedelta

import pytest

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


def test_add_category_assigns_random_color() -> None:
    service, _, _ = _service()
    category = service.add_category("仕事", kind="業務")
    assert category in service.categories
    assert category.color


def test_edit_category_updates_fields() -> None:
    service, _, _ = _service()
    category = service.add_category("仕事")

    service.edit_category(
        category.id,
        name="プライベート",
        kind="私用",
        expiry_date=date(2026, 12, 31),
        color="teal",
        prj_code="PRJ-001",
    )

    assert service.categories[0].name == "プライベート"
    assert service.categories[0].kind == "私用"
    assert service.categories[0].expiry_date == date(2026, 12, 31)
    assert service.categories[0].color == "teal"
    assert service.categories[0].prj_code == "PRJ-001"


def test_delete_category_clears_it_from_items() -> None:
    service, _, _ = _service()
    category = service.add_category("仕事")
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item.id, category.id)

    service.delete_category(category.id)

    assert service.categories == []
    assert service.items[0].category_id is None


def test_set_item_category_and_category_for_item() -> None:
    service, _, _ = _service()
    category = service.add_category("仕事")
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))

    service.set_item_category(item.id, category.id)

    assert service.category_for_item(item.id) == category


def test_category_for_item_is_none_when_uncategorized() -> None:
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))

    assert service.category_for_item(item.id) is None


def test_category_for_item_is_none_when_item_no_longer_exists() -> None:
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.delete_item(item.id)

    assert service.category_for_item(item.id) is None


def test_category_today_totals_groups_by_item_category() -> None:
    service, _, clock = _service()
    work = service.add_category("仕事")
    item_a = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    item_b = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item_a.id, work.id)

    service.start(item_a.id)
    clock.advance(600)
    service.stop_running()
    service.start(item_b.id)
    clock.advance(300)
    service.stop_running()

    totals = service.category_today_totals(date(2026, 8, 30))
    assert totals[work.id] == 600
    assert totals[None] == 300


def test_kind_today_totals_groups_by_category_kind() -> None:
    service, _, clock = _service()
    work = service.add_category("仕事", kind="業務")
    hobby = service.add_category("趣味", kind="業務")
    item_work = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    item_hobby = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    item_none = service.add_item("C", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item_work.id, work.id)
    service.set_item_category(item_hobby.id, hobby.id)

    service.start(item_work.id)
    clock.advance(600)
    service.stop_running()
    service.start(item_hobby.id)
    clock.advance(300)
    service.stop_running()
    service.start(item_none.id)
    clock.advance(60)
    service.stop_running()

    totals = service.kind_today_totals(date(2026, 8, 30))
    assert totals["業務"] == 900
    assert totals["未定"] == 60


def test_delete_items_removes_multiple_items_and_stops_running_one() -> None:
    service, _, clock = _service()
    item_a = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    item_b = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    item_c = service.add_item("C", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item_a.id)
    clock.advance(60)

    service.delete_items([item_a.id, item_b.id])

    assert [item.id for item in service.items] == [item_c.id]
    assert service.running_record() is None
    assert len(service.records) == 1
    assert service.records[0].end_time is not None


def test_delete_records_removes_multiple_records() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(60)
    service.stop_running()
    service.start(item.id)
    clock.advance(30)
    service.stop_running()
    record_ids = [r.id for r in service.records]

    service.delete_records(record_ids)

    assert service.records == []


def test_linked_item_count_counts_items_across_categories() -> None:
    service, _, _ = _service()
    work = service.add_category("仕事")
    hobby = service.add_category("趣味")
    item_a = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    item_b = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    service.add_item("C", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item_a.id, work.id)
    service.set_item_category(item_b.id, hobby.id)

    assert service.linked_item_count([work.id, hobby.id]) == 2
    assert service.linked_item_count([work.id]) == 1


def test_delete_categories_removes_multiple_and_resets_linked_items() -> None:
    service, _, _ = _service()
    work = service.add_category("仕事")
    hobby = service.add_category("趣味")
    item_a = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    item_b = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item_a.id, work.id)
    service.set_item_category(item_b.id, hobby.id)

    service.delete_categories([work.id, hobby.id])

    assert service.categories == []
    assert service.items[0].category_id is None
    assert service.items[1].category_id is None


def test_delete_categories_keeps_category_id_of_items_not_in_deleted_set() -> None:
    # 境界値分析: 削除対象IDの集合に「含まれない」アイテムは変更されないことを確認する
    service, _, _ = _service()
    work = service.add_category("仕事")
    hobby = service.add_category("趣味")
    item_work = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    item_hobby = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item_work.id, work.id)
    service.set_item_category(item_hobby.id, hobby.id)

    service.delete_categories([work.id])

    assert item_work.category_id is None
    assert item_hobby.category_id == hobby.id


def test_edit_item_updates_all_given_fields() -> None:
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30), estimate_hours=1.0)

    service.edit_item(
        item.id,
        name="ジョギング",
        schedule_type=ScheduleType.WEEKLY,
        anchor_date=date(2026, 9, 1),
        estimate_hours=2.5,
    )

    assert item.name == "ジョギング"
    assert item.schedule_type == ScheduleType.WEEKLY
    assert item.anchor_date == date(2026, 9, 1)
    assert item.estimate_hours == 2.5


def test_edit_item_with_no_arguments_keeps_existing_values() -> None:
    # 同値分析: 全引数省略(すべてNone)は「変更しない」という同値クラスとして扱われる
    service, _, _ = _service()
    item = service.add_item(
        "散歩", ScheduleType.DAILY, date(2026, 8, 30), estimate_hours=1.0
    )

    service.edit_item(item.id)

    assert item.name == "散歩"
    assert item.schedule_type == ScheduleType.DAILY
    assert item.anchor_date == date(2026, 8, 30)
    assert item.estimate_hours == 1.0


def test_edit_item_estimate_hours_can_be_reset_to_zero_boundary() -> None:
    # 境界値分析: estimate_hoursの下限0.0は「Noneでない有効値」として更新対象になる
    service, _, _ = _service()
    item = service.add_item(
        "散歩", ScheduleType.DAILY, date(2026, 8, 30), estimate_hours=1.0
    )

    service.edit_item(item.id, estimate_hours=0.0)

    assert item.estimate_hours == 0.0


def test_edit_item_unknown_id_raises_key_error() -> None:
    # 異常系(同値分析): 存在しないIDは全メソッド共通でKeyErrorとなる
    service, _, _ = _service()
    service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))

    with pytest.raises(KeyError):
        service.edit_item("unknown-id", name="別名")


def test_edit_record_unknown_id_raises_key_error() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    clock.advance(60)
    service.stop_running()

    with pytest.raises(KeyError):
        service.edit_record(
            "unknown-id",
            start_time=datetime(2026, 8, 30, 8, 0, 0),
            end_time=datetime(2026, 8, 30, 8, 10, 0),
        )


def test_edit_category_unknown_id_raises_key_error() -> None:
    service, _, _ = _service()
    service.add_category("仕事")
    service.add_category("趣味")

    with pytest.raises(KeyError):
        service.edit_category(
            "unknown-id", name="別名", kind="", expiry_date=None, color="teal", prj_code=""
        )


def test_delete_item_does_not_stop_a_different_running_item() -> None:
    # 境界値分析: 削除対象と「実行中のアイテムが一致しない」場合は実行中の記録を止めない
    service, _, clock = _service()
    running_item = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    other_item = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(running_item.id)
    clock.advance(30)

    service.delete_item(other_item.id)

    running = service.running_record()
    assert running is not None
    assert running.item_id == running_item.id
    assert running.end_time is None


def test_delete_items_does_not_stop_running_item_when_not_in_deleted_set() -> None:
    service, _, clock = _service()
    running_item = service.add_item("A", ScheduleType.DAILY, date(2026, 8, 30))
    other_item = service.add_item("B", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(running_item.id)
    clock.advance(30)

    service.delete_items([other_item.id])

    running = service.running_record()
    assert running is not None
    assert running.item_id == running_item.id
    assert running.end_time is None


def test_items_due_today_filters_items_by_schedule() -> None:
    # ドメイン分析: サービス経由でも、実行対象日でないアイテムは一覧から除外される
    service, _, _ = _service()
    today = date(2026, 8, 30)
    daily = service.add_item("毎日", ScheduleType.DAILY, date(2026, 1, 1))
    due_one_time = service.add_item("当日", ScheduleType.ONE_TIME, today)
    service.add_item("別日", ScheduleType.ONE_TIME, date(2026, 8, 31))

    due_items = service.items_due_today(today)

    assert {item.id for item in due_items} == {daily.id, due_one_time.id}


def test_today_records_returns_only_todays_records_sorted_by_start_time() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))

    service.start(item.id)
    clock.advance(60)
    service.stop_running()
    record_a = service.records[0]

    service.start(item.id)
    clock.advance(60)
    service.stop_running()
    record_b = service.records[1]

    # 生成順(records配列の並び)とstart_timeの前後関係をわざと逆転させ、
    # today_recordsが開始時刻の昇順でソートして返すことを確認する
    record_a.start_time, record_b.start_time = record_b.start_time, record_a.start_time

    other_day_item = service.add_item("別件", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(other_day_item.id)
    clock.advance(60)
    service.stop_running()
    # 前日の記録は対象日(today)から除外される境界値
    other_day_record = service.records[2]
    other_day_record.start_time = datetime(2026, 8, 29, 9, 0, 0)
    other_day_record.end_time = datetime(2026, 8, 29, 9, 10, 0)

    result = service.today_records(date(2026, 8, 30))

    assert result == [record_b, record_a]


def test_category_for_item_returns_none_when_linked_category_no_longer_exists() -> None:
    # ドメイン分析: category_idが指すカテゴリが存在しない場合(データ不整合)は
    # 「未定」相当としてNoneを返すフォールバックが機能することを確認する
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    item.category_id = "orphaned-category-id"

    assert service.category_for_item(item.id) is None


def test_category_for_item_finds_category_that_is_not_first_in_the_list() -> None:
    service, _, _ = _service()
    first = service.add_category("仕事")
    second = service.add_category("趣味")
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item.id, second.id)

    assert service.category_for_item(item.id) == second
    assert first != second


def test_category_today_totals_excludes_records_from_other_days() -> None:
    # 境界値分析: 集計対象日と一致しない記録は合計に含まれない
    service, _, clock = _service()
    category = service.add_category("仕事")
    item = service.add_item("散歩", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item.id, category.id)

    service.start(item.id)
    clock.advance(600)
    service.stop_running()
    yesterday_record = service.records[0]
    yesterday_record.start_time = datetime(2026, 8, 29, 9, 0, 0)
    yesterday_record.end_time = datetime(2026, 8, 29, 9, 5, 0)

    service.start(item.id)
    clock.advance(120)
    service.stop_running()

    totals = service.category_today_totals(date(2026, 8, 30))

    assert totals == {category.id: 120}
