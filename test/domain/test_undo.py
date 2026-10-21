from datetime import date, datetime, timedelta

from todoapp.domain.models import AppData, ScheduleType
from todoapp.domain.service import TodoService

TODAY = date(2026, 8, 30)


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
    return TodoService(repository, clock=clock), repository, clock


def test_undo_and_redo_on_empty_history_return_none() -> None:
    service, _, _ = _service()
    assert service.undo() is None
    assert service.redo() is None


def test_undo_add_item_removes_it_and_redo_restores_it() -> None:
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.ONE_TIME, TODAY)

    assert service.undo() == "アイテムを追加"
    assert service.items == []
    assert service.redo() == "アイテムを追加"
    assert [i.id for i in service.items] == [item.id]


def test_undo_delete_restores_the_item_and_reattaches_its_records() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, TODAY)
    service.start(item.id)
    clock.advance(60)
    service.stop_running()
    service.delete_item(item.id)
    assert service.items == []

    assert service.undo() == "アイテムを削除"

    assert [i.id for i in service.items] == [item.id]
    assert service.cumulative_seconds(item.id) == 60


def test_undo_rename_restores_the_names_of_existing_records() -> None:
    service, _, clock = _service()
    item = service.add_item("旧名", ScheduleType.DAILY, TODAY)
    service.start(item.id)
    clock.advance(60)
    service.stop_running()
    service.edit_item(item.id, name="新名")
    assert [r.item_name for r in service.records] == ["新名"]

    service.undo()

    assert service.items[0].name == "旧名"
    assert [r.item_name for r in service.records] == ["旧名"]
    service.redo()
    assert [r.item_name for r in service.records] == ["新名"]


def test_operation_that_changes_nothing_is_not_recorded() -> None:
    service, _, _ = _service()

    assert service.carry_over([], TODAY) == []
    service.set_done([], True, TODAY)

    assert service.undo() is None


def test_nested_calls_are_recorded_as_one_operation() -> None:
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.ONE_TIME, TODAY)
    service.toggle_done([item.id], TODAY)  # toggle_doneはset_doneへ委譲する
    assert service.items[0].done_date == TODAY

    assert service.undo() == "完了の切り替え"
    assert service.items[0].done_date is None
    assert service.undo() == "アイテムを追加"
    assert service.undo() is None


def test_new_operation_clears_redo() -> None:
    service, _, _ = _service()
    service.add_item("a", ScheduleType.ONE_TIME, TODAY)
    service.undo()

    service.add_item("b", ScheduleType.ONE_TIME, TODAY)

    assert service.redo() is None


def test_history_is_limited_to_50_operations() -> None:
    service, _, _ = _service()
    for i in range(60):
        service.add_item(f"item{i}", ScheduleType.ONE_TIME, TODAY)

    undone = 0
    while service.undo() is not None:
        undone += 1

    assert undone == 50
    assert len(service.items) == 10


def test_undo_does_not_touch_records_made_after_the_operation() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, TODAY)
    service.start(item.id)
    clock.advance(60)
    service.stop_running()

    service.undo()  # 追加を取り消す

    assert service.items == []
    assert len(service.records) == 1  # 計測した記録は残る


def test_undo_of_adding_a_running_item_stops_its_record() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, TODAY)
    service.start(item.id)
    clock.advance(30)

    service.undo()

    assert service.running_record() is None
    [record] = service.records
    assert record.end_time is not None


def test_execution_and_record_operations_are_not_recorded() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, TODAY)
    service.start(item.id)
    clock.advance(60)
    service.stop_running()
    record = service.records[0]
    service.edit_record(record.id, start_time=record.start_time, end_time=record.end_time)
    service.start(item.id)
    service.cancel_running(item.id)
    service.delete_record(record.id)

    assert service.undo() == "アイテムを追加"  # 履歴に積まれているのは追加だけ
    assert service.undo() is None


def test_category_and_link_template_operations_can_be_undone() -> None:
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, TODAY)
    category = service.add_category("仕事")
    service.set_item_category(item.id, category.id)
    service.delete_category(category.id)
    assert service.items[0].category_id is None
    template = service.add_link_template("課題", "https://example.com/{id}")
    service.delete_link_templates([template.id])

    assert service.undo() == "リンクテンプレートを削除"
    assert [t.id for t in service.link_templates] == [template.id]
    assert service.undo() == "リンクテンプレートを追加"
    assert service.link_templates == []
    assert service.undo() == "カテゴリを削除"
    assert service.items[0].category_id == category.id
    assert [c.id for c in service.categories] == [category.id]


def test_reorder_and_move_can_be_undone() -> None:
    service, _, _ = _service()
    a = service.add_item("a", ScheduleType.ONE_TIME, TODAY)
    b = service.add_item("b", ScheduleType.ONE_TIME, TODAY)
    service.move_item_to(b.id, a.id)
    assert [i.name for i in service.items] == ["b", "a"]

    service.undo()

    assert [i.name for i in service.items] == ["a", "b"]


def test_undo_saves_the_restored_state() -> None:
    service, repository, _ = _service()
    service.add_item("散歩", ScheduleType.ONE_TIME, TODAY)

    service.undo()

    assert repository.saved is not None
    assert repository.saved.items == []


def test_restored_items_are_independent_of_the_history() -> None:
    service, _, _ = _service()
    item = service.add_item("散歩", ScheduleType.ONE_TIME, TODAY)
    service.edit_item(item.id, name="散歩2")
    service.undo()

    service.items[0].name = "別名"  # 復元した状態を履歴を通さず直接変更しても

    service.redo()  # Redoは、Undo時点の状態(散歩2)へ戻る
    assert service.items[0].name == "散歩2"


def test_undo_stops_a_running_item_that_becomes_done() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, TODAY)
    service.set_done([item.id], True, TODAY)
    service.set_done([item.id], False, TODAY)
    service.start(item.id)
    clock.advance(30)

    service.undo()  # 完了の解除を取り消す → 完了に戻る

    assert service.running_record() is None
    assert service.records[0].end_time is not None


def test_undo_stops_a_running_item_that_becomes_skipped() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.DAILY, TODAY)
    service.set_skipped([item.id], True, TODAY)
    service.set_skipped([item.id], False, TODAY)
    service.start(item.id)
    clock.advance(30)

    service.undo()  # スキップの解除を取り消す → スキップに戻る

    assert service.running_record() is None


def test_undo_stops_a_running_item_that_becomes_undecided() -> None:
    service, _, clock = _service()
    item = service.add_item("散歩", ScheduleType.UNDECIDED, TODAY)
    service.edit_item(item.id, schedule_type=ScheduleType.DAILY)
    service.start(item.id)
    clock.advance(30)

    service.undo()  # 未定に戻る(未定は実行できない)

    assert service.running_record() is None


def test_undo_rename_also_renames_records_created_after_the_rename() -> None:
    service, _, clock = _service()
    item = service.add_item("旧名", ScheduleType.DAILY, TODAY)
    service.edit_item(item.id, name="新名")
    service.start(item.id)  # 名前変更の後に作られた記録
    clock.advance(60)
    service.stop_running()
    assert [r.item_name for r in service.records] == ["新名"]

    service.undo()

    assert [r.item_name for r in service.records] == ["旧名"]


def test_undo_group_records_several_operations_as_one() -> None:
    service, _, _ = _service()
    item = service.add_item("a", ScheduleType.ONE_TIME, TODAY)
    category = service.add_category("仕事")

    with service.undo_group("アイテムを編集"):
        service.edit_item(item.id, name="b")
        service.set_item_category(item.id, category.id)

    assert service.undo() == "アイテムを編集"
    assert service.items[0].name == "a"
    assert service.items[0].category_id is None
    assert service.undo() == "カテゴリを追加"


def test_undo_group_without_changes_is_not_recorded() -> None:
    service, _, _ = _service()
    item = service.add_item("a", ScheduleType.ONE_TIME, TODAY)

    with service.undo_group("アイテムを編集"):
        service.edit_item(item.id, name="a")

    assert service.undo() == "アイテムを追加"


def test_undo_group_that_raises_is_not_recorded_and_resets_nesting() -> None:
    service, _, _ = _service()
    item = service.add_item("a", ScheduleType.ONE_TIME, TODAY)

    try:
        with service.undo_group("アイテムを編集"):
            service.edit_item(item.id, name="b")
            raise RuntimeError
    except RuntimeError:
        pass
    service.edit_item(item.id, name="c")  # 入れ子の深さが戻っていれば、通常どおり積まれる

    assert service.undo() == "アイテムを編集"
    assert service.items[0].name == "b"  # 例外前の変更は残る(例外で巻き戻しはしない)
