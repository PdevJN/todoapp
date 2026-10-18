import webbrowser

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from test.ui.harness import AppEnv, make_item, press, shows
from todoapp.domain.models import ItemLink, LinkTemplate
from todoapp.ui.item_links import build_link_entries, open_link_url

JIRA = LinkTemplate(name="Jira", url_template="https://example.com/{id}")


def test_build_link_entries_marks_unopenable_links() -> None:
    item = make_item(
        "A",
        links=[
            ItemLink(name="チケット", template_id=JIRA.id, values={"id": "1"}),
            ItemLink(name="空", template_id=JIRA.id, values={}),
            ItemLink(name="危険", url="javascript:alert(1)"),
        ],
    )
    entries = build_link_entries(item, [JIRA])
    assert [e.url for e in entries] == ["https://example.com/1", None, None]
    assert [e.label for e in entries] == ["チケット", "空(未入力)", "危険(未入力)"]


def test_label_falls_back_to_the_resolved_url_when_name_is_empty() -> None:
    item = make_item(
        "A",
        links=[
            ItemLink(name="", template_id=JIRA.id, values={"id": "1"}),
            ItemLink(name="", template_id=JIRA.id, values={}),
            ItemLink(name="", url="https://example.com/" + "a" * 100),
        ],
    )
    labels = [e.label for e in build_link_entries(item, [JIRA])]
    assert labels[0] == "https://example.com/1"
    assert labels[1] == "(未入力)"
    assert labels[2].startswith("https://example.com/aaa")
    assert len(labels[2]) <= 60
    assert labels[2].endswith("…")


def test_open_link_url_calls_opener_only_for_a_url() -> None:
    opened: list[str] = []
    def opener(url: str) -> None:
        opened.append(url)

    assert open_link_url("https://example.com", opener) is True
    assert open_link_url(None, opener) is False
    assert opened == ["https://example.com"]


def _link_buttons(user: User) -> list[ui.button]:
    return [b for b in user.find(kind=ui.button).elements if b.props.get("icon") == "link"]


async def test_main_panel_shows_one_link_icon_per_item_with_links(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(
        items=[
            make_item("リンクあり", links=[ItemLink(name="資料", url="https://example.com/doc")]),
            make_item("リンクなし"),
        ]
    )
    await app_user.open("/")
    assert len(_link_buttons(app_user)) == 1


async def test_clicking_a_single_link_opens_it_in_the_browser(
    app_user: User, app_env: AppEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []

    def fake_open(url: str) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)
    app_env.seed(items=[make_item("A", links=[ItemLink(name="資料", url="https://example.com/doc")])])
    await app_user.open("/")

    UserInteraction(app_user, set(_link_buttons(app_user)), None).trigger("click")

    assert opened == ["https://example.com/doc"]


async def test_multiple_links_show_a_menu_entry_for_each_link(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(
        items=[
            make_item(
                "A",
                links=[
                    ItemLink(name="資料1", url="https://example.com/1"),
                    ItemLink(name="資料2", url="https://example.com/2"),
                ],
            )
        ]
    )
    await app_user.open("/")
    [button] = _link_buttons(app_user)
    menu_items = [e for e in button.descendants() if isinstance(e, ui.menu_item)]
    sections = [e for item in menu_items for e in item.descendants() if isinstance(e, ui.item_section)]
    labels = [str(section._text) for section in sections]  # noqa: SLF001
    assert sorted(labels) == ["資料1", "資料2"]


async def test_list_view_rows_carry_link_entries(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("A", links=[ItemLink(name="資料", url="https://example.com/doc")])])
    await app_user.open("/")
    await press(app_user, "Escape")  # 編集一覧へ切り替え
    await shows(app_user, "編集一覧")

    [table] = [t for t in app_user.find(ui.table).elements if any(c["name"] == "anchor" for c in t.columns)]
    [link] = table.rows[0]["links"]
    assert link["label"] == "資料"
