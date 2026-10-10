"""画面テスト用のフィクスチャ。保存先を一時ディレクトリへ向け、`~/.todoapp`を汚さない。"""

from collections.abc import AsyncGenerator
from datetime import date
from pathlib import Path

import pytest
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from test.ui.harness import AppEnv
from todoapp.main import build_app_ui
from todoapp.repository.config_repository import ConfigRepository
from todoapp.repository.holiday_repository import HolidayRepository
from todoapp.repository.json_repository import JsonTodoRepository


@pytest.fixture
def app_env(tmp_path: Path) -> AppEnv:
    # 祝日キャッシュを用意し、初回起動時のネットワーク取得(内閣府CSV)が走らないようにする
    HolidayRepository(tmp_path / "holidays.json").save({date(2000, 1, 1): "元日"})
    return AppEnv(tmp_path)


@pytest.fixture
async def app_user(app_env: AppEnv) -> AsyncGenerator[User]:
    def root() -> None:
        build_app_ui(
            JsonTodoRepository(app_env.directory / "todos.json"),
            ConfigRepository(app_env.directory / "config.json"),
            HolidayRepository(app_env.directory / "holidays.json"),
        )

    async with user_simulation(root=root) as user:
        yield user
