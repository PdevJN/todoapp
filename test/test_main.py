from datetime import date, datetime
from pathlib import Path

from todoapp import main
from todoapp.domain.models import AppData, ExecutionRecord, ScheduleType, TodoItem
from todoapp.repository.alive_repository import AliveRepository
from todoapp.repository.json_repository import JsonTodoRepository


def test_main_module_importable() -> None:
    assert hasattr(main, "main")


def test_recover_interrupted_run_stops_leftover_running_record_at_last_alive_time(tmp_path: Path) -> None:
    repository = JsonTodoRepository(tmp_path / "todos.json")
    item = TodoItem(name="作業", schedule_type=ScheduleType.DAILY, anchor_date=date(2026, 10, 10))
    start = datetime(2026, 10, 10, 9)
    repository.save(AppData(items=[item], records=[ExecutionRecord(item.id, item.name, start)]))
    alive_store = AliveRepository(tmp_path / "alive.json")
    alive_store.save(datetime(2026, 10, 10, 9, 45))

    main.recover_interrupted_run(repository, alive_store)

    (record,) = repository.load().records
    assert record.end_time == datetime(2026, 10, 10, 9, 45)
