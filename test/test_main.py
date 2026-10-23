from datetime import date, datetime
from pathlib import Path

import pytest

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


def test_shutdown_app_stops_running_record_and_saves_alive_time(tmp_path: Path) -> None:
    repository = JsonTodoRepository(tmp_path / "todos.json")
    item = TodoItem(name="作業", schedule_type=ScheduleType.DAILY, anchor_date=date(2026, 10, 10))
    repository.save(AppData(items=[item], records=[ExecutionRecord(item.id, item.name, datetime(2026, 10, 10, 9))]))
    alive_store = AliveRepository(tmp_path / "alive.json")
    service = main.recover_interrupted_run(repository, AliveRepository(tmp_path / "none.json"))
    service.start(item.id)

    main.shutdown_app(service, alive_store)

    assert service.running_record() is None
    assert all(record.end_time is not None for record in repository.load().records)
    assert alive_store.load() is not None


def test_parse_args_defaults_to_native() -> None:
    args = main.parse_args([])
    assert args.mode == "native"
    assert args.port is None


def test_parse_args_accepts_each_mode() -> None:
    for mode in ("native", "web"):
        assert main.parse_args(["--mode", mode]).mode == mode


def test_parse_args_rejects_unknown_mode() -> None:
    with pytest.raises(SystemExit):
        main.parse_args(["--mode", "other"])


def test_run_options_per_mode() -> None:
    assert main.run_options("native", None)["native"] is True
    web = main.run_options("web", None)
    assert web["native"] is False
    assert web["show"] is True
