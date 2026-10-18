from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from test.ui.harness import AppEnv, click_displayed, is_displayed, make_item, press, shows
from todoapp.domain.models import AppData, ItemLink, LinkTemplate


async def test_u_key_opens_the_template_dialog(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "u")
    await shows(app_user, "テンプレートを追加")


async def test_adding_a_template_saves_it(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "u")
    app_user.find(kind=ui.input, content="テンプレート名").type("Jira")
    app_user.find(kind=ui.input, content="URL雛形").type("https://example.com/{id}")
    click_displayed(app_user, "テンプレートを追加")

    templates = app_env.todos().link_templates
    assert [(t.name, t.url_template) for t in templates] == [("Jira", "https://example.com/{id}")]


async def test_invalid_template_is_not_saved(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "u")
    app_user.find(kind=ui.input, content="テンプレート名").type("Jira")
    app_user.find(kind=ui.input, content="URL雛形").type("https://example.com/｛id｝")
    click_displayed(app_user, "テンプレートを追加")

    assert app_env.todos().link_templates == []


async def test_deleting_a_template_without_links_deletes_immediately(app_user: User, app_env: AppEnv) -> None:
    template = LinkTemplate(name="Jira", url_template="https://example.com/{id}")
    app_env.todos_repository.save(AppData(items=[], records=[], link_templates=[template]))
    await app_user.open("/")
    await press(app_user, "u")

    delete_button = next(b for b in app_user.find(kind=ui.button).elements if b.props.get("icon") == "delete")
    UserInteraction(app_user, {delete_button}, None).trigger("click")

    assert app_env.todos().link_templates == []


async def test_deleting_a_template_with_links_asks_for_confirmation(app_user: User, app_env: AppEnv) -> None:
    template = LinkTemplate(name="Jira", url_template="https://example.com/{id}")
    item = make_item("A", links=[ItemLink(name="t", template_id=template.id, values={"id": "1"})])
    app_env.todos_repository.save(AppData(items=[item], records=[], link_templates=[template]))
    await app_user.open("/")
    await press(app_user, "u")

    delete_button = next(b for b in app_user.find(kind=ui.button).elements if b.props.get("icon") == "delete")
    UserInteraction(app_user, {delete_button}, None).trigger("click")
    await shows(app_user, "そのリンクも削除されます")
    assert app_env.todos().link_templates == [template]  # 確認前は消えない

    confirm = next(
        b for b in app_user.find(kind=ui.button, content="削除する").elements if is_displayed(b)
    )  # メッセージ文にも「削除する」を含むため、ボタンに絞る
    UserInteraction(app_user, {confirm}, None).trigger("click")

    saved = app_env.todos()
    assert saved.link_templates == []
    assert saved.items[0].links == []
