"""複数の画面(ウィンドウ・ブラウザ)が同じ`TodoService`を共有するときの画面テスト。"""

from datetime import date

from nicegui.testing.user_simulation import user_simulation

from test.ui.harness import AppEnv, shows
from todoapp.domain.models import ScheduleType
from todoapp.domain.service import TodoService
from todoapp.main import build_app_ui
from todoapp.repository.config_repository import ConfigRepository
from todoapp.repository.holiday_repository import HolidayRepository
from todoapp.repository.json_repository import JsonTodoRepository


async def test_change_from_another_page_is_not_lost_by_next_save(app_env: AppEnv) -> None:
    repository = JsonTodoRepository(app_env.directory / "todos.json")
    shared = TodoService(repository)

    def root() -> None:
        build_app_ui(
            repository,
            ConfigRepository(app_env.directory / "config.json"),
            HolidayRepository(app_env.directory / "holidays.json"),
            service=shared,
        )

    async with user_simulation(root=root) as user:
        await user.open("/")
        # 別の画面での登録を、共有サービスへの操作として再現する
        shared.add_item("別画面の登録", ScheduleType.DAILY, date.today())

        user.find(content="新しいアイテム").type("この画面の登録").trigger("keydown.enter.exact")
        await shows(user, "この画面の登録")

    assert {item.name for item in app_env.todos().items} == {"別画面の登録", "この画面の登録"}
