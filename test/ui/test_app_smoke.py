from nicegui.testing import User

from test.ui.harness import AppEnv, make_item


async def test_main_panel_lists_items_due_today(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])

    await app_user.open("/")

    await app_user.should_see("朝のメール")
