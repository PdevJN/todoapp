from nicegui.testing import User

from test.ui.harness import AppEnv, click_displayed, click_row, make_item, press, shows
from todoapp.domain.models import AppData, ItemLink, LinkTemplate
from todoapp.ui.link_rows_editor import LinkRowsEditor

JIRA = LinkTemplate(name="Jira", url_template="https://example.com/{project}/issues/{id}")


async def _open_edit(user: User, name: str) -> None:
    await user.open("/")
    click_row(user, name)
    await press(user, "e")
    await shows(user, "アイテムの編集")


def test_collect_without_rows_returns_empty_list() -> None:
    assert LinkRowsEditor().collect() == []


async def test_edit_form_shows_inputs_for_the_selected_templates_placeholders(
    app_user: User, app_env: AppEnv
) -> None:
    item = make_item(
        "A", links=[ItemLink(name="チケット", template_id=JIRA.id, values={"project": "P", "id": "1"})]
    )
    app_env.todos_repository.save(AppData(items=[item], records=[], link_templates=[JIRA]))

    await _open_edit(app_user, "A")

    await shows(app_user, "project")
    await shows(app_user, "id")


async def test_saving_the_edit_form_persists_links(app_user: User, app_env: AppEnv) -> None:
    item = make_item("A", links=[ItemLink(name="資料", url="https://example.com/doc")])
    app_env.todos_repository.save(AppData(items=[item], records=[], link_templates=[JIRA]))

    await _open_edit(app_user, "A")
    click_displayed(app_user, "保存")

    saved = app_env.todos().items[0]
    assert [(link.name, link.url) for link in saved.links] == [("資料", "https://example.com/doc")]


async def test_saving_with_a_blank_placeholder_value_is_rejected(app_user: User, app_env: AppEnv) -> None:
    link = ItemLink(name="チケット", template_id=JIRA.id, values={"project": "P"})
    item = make_item("A", links=[link])
    app_env.todos_repository.save(AppData(items=[item], records=[], link_templates=[JIRA]))

    await _open_edit(app_user, "A")
    click_displayed(app_user, "保存")

    assert app_env.todos().items[0].links == [link]  # 未入力のidがあるので、保存されず元のまま
