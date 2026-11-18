"""手動追加ダイアログの時刻補正(既存の記録の境界へ合わせる)の画面テスト。"""

from collections.abc import AsyncGenerator
from datetime import date, datetime
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from todoapp.domain.record_layout import snap_end_out, snap_start_out
from todoapp.domain.service import TodoService
from todoapp.repository.json_repository import JsonTodoRepository
from todoapp.ui.manual_record_dialog import ManualRecordDialog

DAY = date(2026, 11, 18)


def _at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second)


@pytest.fixture
async def dialog_env(tmp_path: Path) -> AsyncGenerator[tuple[User, TodoService, ManualRecordDialog]]:
    service = TodoService(JsonTodoRepository(tmp_path / "todos.json"))
    dialog = ManualRecordDialog(service, refresh_all=lambda: None)

    def root() -> None:
        ui.label("manual record")
        dialog.build()

    async with user_simulation(root=root) as user:
        await user.open("/")
        assert user.client is not None
        with user.client:
            dialog.open_for(DAY)
        yield user, service, dialog


def _snap(dialog: ManualRecordDialog, user: User, field: str, value: str) -> None:
    assert user.client is not None
    input_, snap = (
        (dialog._start_input, snap_start_out) if field == "start" else (dialog._end_input, snap_end_out)  # noqa: SLF001
    )
    with user.client:
        input_.value = value
        dialog._snap_input(input_, snap)  # noqa: SLF001


async def test_start_inside_record_snaps_to_its_end(dialog_env: tuple[User, TodoService, ManualRecordDialog]) -> None:
    user, service, dialog = dialog_env
    service.add_manual_record(None, "既存", _at(9), _at(10))

    _snap(dialog, user, "start", "09:30:00")

    assert dialog._start_input.value == "10:00:00"  # noqa: SLF001
    await user.should_see("10:00:00に合わせました")


async def test_end_inside_record_snaps_to_its_start(dialog_env: tuple[User, TodoService, ManualRecordDialog]) -> None:
    user, service, dialog = dialog_env
    service.add_manual_record(None, "既存", _at(10), _at(11))

    _snap(dialog, user, "end", "10:30:00")

    assert dialog._end_input.value == "10:00:00"  # noqa: SLF001


async def test_snap_that_would_invert_start_and_end_is_refused(
    dialog_env: tuple[User, TodoService, ManualRecordDialog],
) -> None:
    user, service, dialog = dialog_env
    service.add_manual_record(None, "既存", _at(9), _at(10))
    dialog._start_input.value = "09:20:00"  # noqa: SLF001
    dialog._end_input.value = "09:40:00"  # noqa: SLF001

    _snap(dialog, user, "start", "09:20:00")
    _snap(dialog, user, "end", "09:40:00")

    assert dialog._start_input.value == "09:20:00"  # noqa: SLF001
    assert dialog._end_input.value == "09:40:00"  # noqa: SLF001
    await user.should_see("空きがありません")


async def test_snap_fits_between_narrow_gap(dialog_env: tuple[User, TodoService, ManualRecordDialog]) -> None:
    user, service, dialog = dialog_env
    service.add_manual_record(None, "前", _at(9), _at(10))
    service.add_manual_record(None, "後", _at(10, 2), _at(11))
    dialog._end_input.value = "10:30:00"  # noqa: SLF001

    _snap(dialog, user, "start", "09:30:00")
    _snap(dialog, user, "end", "10:30:00")

    assert dialog._start_input.value == "10:00:00"  # noqa: SLF001
    assert dialog._end_input.value == "10:02:00"  # noqa: SLF001


async def test_submit_fits_to_earliest_gap_then_adds_on_second_press(
    dialog_env: tuple[User, TodoService, ManualRecordDialog],
) -> None:
    user, service, dialog = dialog_env
    service.add_manual_record(None, "既存", _at(10, 0, 27), _at(10, 0, 28))
    assert user.client is not None
    with user.client:
        dialog._start_input.value = "10:00:00"  # noqa: SLF001
        dialog._end_input.value = "10:05:00"  # noqa: SLF001

        assert dialog.submit() is False
        assert dialog._end_input.value == "10:00:27"  # noqa: SLF001
        assert len(service.records) == 1

        assert dialog.submit() is True
    assert len(service.records) == 2
