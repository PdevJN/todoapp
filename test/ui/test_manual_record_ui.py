from datetime import date, datetime
from pathlib import Path

from todoapp.domain.models import ScheduleType
from todoapp.domain.service import TodoService
from todoapp.repository.json_repository import JsonTodoRepository
from todoapp.ui.calendar_view import CalendarView


def _view(tmp_path: Path) -> tuple[CalendarView, TodoService]:
    service = TodoService(JsonTodoRepository(tmp_path / "todos.json"))
    view = CalendarView(
        service,
        open_record_edit_dialog=lambda _record_id: None,
        open_manual_record_dialog=lambda _day: None,
        initial_week_start="sunday",
        on_week_start_change=lambda _week_start: None,
        holidays={},
        refresh_holidays=lambda: True,
    )
    return view, service


def test_manual_record_event_is_drawn_in_light_red(tmp_path: Path) -> None:
    view, service = _view(tmp_path)
    work = service.add_category("仕事")
    start = datetime(2026, 8, 30, 9)
    service.add_manual_record(work.id, "打合せ", start, start.replace(hour=10))

    (event,) = view._build_events()

    assert event["color"] == "#ef9a9a"
    assert event["borderColor"] == "#c62828"
    assert event["textColor"] == "#7f0000"
    assert "手動追加" in event["extendedProps"]["tooltip"]
    assert event["extendedProps"]["manual"] is True
    assert "仕事" in event["extendedProps"]["tooltip"]


def test_normal_record_event_keeps_category_color(tmp_path: Path) -> None:
    view, service = _view(tmp_path)
    work = service.add_category("仕事")
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.set_item_category(item.id, work.id)
    service.start(item.id)
    service.stop_running()

    (event,) = view._build_events()

    assert event["color"] == work.color
    assert event["extendedProps"]["manual"] is False


def test_parse_manual_record_returns_datetimes() -> None:
    from todoapp.ui.manual_record_dialog import parse_manual_record

    parsed = parse_manual_record("2026-08-30", "09:00:00", "10:30:15")

    assert parsed == (datetime(2026, 8, 30, 9), datetime(2026, 8, 30, 10, 30, 15))


def test_parse_manual_record_returns_none_for_bad_input() -> None:
    from todoapp.ui.manual_record_dialog import parse_manual_record

    assert parse_manual_record("", "09:00:00", "10:00:00") is None
    assert parse_manual_record("2026-08-30", "", "10:00:00") is None
    assert parse_manual_record("2026-08-30", "9時", "10:00:00") is None
    assert parse_manual_record("2026-13-40", "09:00:00", "10:00:00") is None


def test_category_menu_entries_list_uncategorized_then_categories(tmp_path: Path) -> None:
    view, service = _view(tmp_path)
    work = service.add_category("仕事")
    hobby = service.add_category("趣味")
    record = service.add_manual_record(work.id, "", datetime(2026, 8, 30, 9), datetime(2026, 8, 30, 10))

    entries = view.category_menu_entries(record.id)

    assert [e.label for e in entries] == ["未定", "仕事", "趣味"]
    assert [e.category_id for e in entries] == [None, work.id, hobby.id]
    assert [e.current for e in entries] == [False, True, False]


def test_category_menu_entries_show_prj_code_and_expired_mark(tmp_path: Path) -> None:
    view, service = _view(tmp_path)
    service.add_category("案件", expiry_date=date(2000, 1, 1))
    service.categories[0].prj_code = "P-1"
    record = service.add_manual_record(None, "", datetime(2026, 8, 30, 9), datetime(2026, 8, 30, 10))

    entries = view.category_menu_entries(record.id)

    assert entries[1].label == "❗️案件(P-1)"


def test_category_menu_entries_empty_for_normal_record(tmp_path: Path) -> None:
    view, service = _view(tmp_path)
    item = service.add_item("設計", ScheduleType.DAILY, date(2026, 8, 30))
    service.start(item.id)
    service.stop_running()

    assert view.category_menu_entries(service.records[0].id) == []
