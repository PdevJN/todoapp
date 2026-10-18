import pytest

from todoapp.domain.models import (
    ItemLink,
    LinkTemplate,
    resolve_link_url,
    template_placeholders,
    validate_item_link_fields,
    validate_link_template_fields,
)

JIRA = LinkTemplate(name="Jira", url_template="https://example.com/{project}/issues/{id}")


def test_template_placeholders_are_unique_in_first_appearance_order() -> None:
    assert template_placeholders("https://x/{b}/{a}/{b}?q={a}") == ["b", "a"]


def test_template_placeholders_ignore_invalid_names() -> None:
    assert template_placeholders("https://x/{a b}/{}/{id}") == ["id"]


def test_link_template_roundtrips_through_dict() -> None:
    assert LinkTemplate.from_dict(JIRA.to_dict()) == JIRA


def test_item_link_roundtrips_through_dict() -> None:
    link = ItemLink(name="チケット", template_id=JIRA.id, values={"project": "P", "id": "1"})
    assert ItemLink.from_dict(link.to_dict()) == link


def test_resolve_direct_url() -> None:
    link = ItemLink(name="資料", url="https://example.com/doc")
    assert resolve_link_url(link, []) == "https://example.com/doc"


def test_resolve_fills_all_placeholders() -> None:
    link = ItemLink(name="t", template_id=JIRA.id, values={"project": "PRJ", "id": "12"})
    assert resolve_link_url(link, [JIRA]) == "https://example.com/PRJ/issues/12"


def test_resolve_replaces_repeated_placeholder_everywhere() -> None:
    template = LinkTemplate(name="t", url_template="https://x/{id}/edit?ref={id}")
    link = ItemLink(name="t", template_id=template.id, values={"id": "7"})
    assert resolve_link_url(link, [template]) == "https://x/7/edit?ref=7"


def test_resolve_url_encodes_special_characters() -> None:
    link = ItemLink(name="t", template_id=JIRA.id, values={"project": "P", "id": "a/b?c#d&e 日本"})
    url = resolve_link_url(link, [JIRA])
    assert url == "https://example.com/P/issues/a%2Fb%3Fc%23d%26e%20%E6%97%A5%E6%9C%AC"


def test_resolve_does_not_expand_placeholder_inside_a_value() -> None:
    link = ItemLink(name="t", template_id=JIRA.id, values={"project": "{id}", "id": "1"})
    assert resolve_link_url(link, [JIRA]) == "https://example.com/%7Bid%7D/issues/1"


@pytest.mark.parametrize("values", [{"project": "P"}, {"project": "P", "id": ""}, {"project": "P", "id": "  "}])
def test_resolve_returns_none_when_a_value_is_missing_or_blank(values: dict[str, str]) -> None:
    link = ItemLink(name="t", template_id=JIRA.id, values=values)
    assert resolve_link_url(link, [JIRA]) is None


def test_resolve_returns_none_when_template_is_missing() -> None:
    link = ItemLink(name="t", template_id="gone", values={"project": "P", "id": "1"})
    assert resolve_link_url(link, [JIRA]) is None


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "ftp://example.com", ""])
def test_resolve_rejects_non_http_schemes(url: str) -> None:
    assert resolve_link_url(ItemLink(name="t", url=url), []) is None


def test_resolve_accepts_uppercase_scheme() -> None:
    assert resolve_link_url(ItemLink(name="t", url="HTTPS://example.com"), []) == "HTTPS://example.com"


def test_validate_template_accepts_valid_input() -> None:
    assert validate_link_template_fields("Jira", "https://example.com/{project}/{id}") is None


@pytest.mark.parametrize(
    ("name", "url_template", "expected"),
    [
        ("", "https://x/{id}", "テンプレート名"),
        ("a\tb", "https://x/{id}", "制御文字"),
        ("a" * 31, "https://x/{id}", "30文字以内"),
        ("n", "https://x/｛id｝", "全角の｛ ｝"),
        ("n", "https://x/日本/{id}", "ASCII以外"),
        ("n", "https://x/ {id}", "空白"),
        ("n", "https://x/{id}" + "a" * 500, "500文字以内"),
        ("n", "ftp://x/{id}", "http://"),
        ("n", "https://x/", "1つ以上"),
        ("n", "https://x/{id", "書いてください"),
        ("n", "https://x/{}", "書いてください"),
        ("n", "https://x/{a-b}", "書いてください"),
        ("n", "https://x/{a}{b}{c}{d}{e}{f}", "5個まで"),
    ],
)
def test_validate_template_rejects_invalid_input(name: str, url_template: str, expected: str) -> None:
    error = validate_link_template_fields(name, url_template)
    assert error is not None
    assert expected in error


def test_validate_template_accepts_five_placeholders() -> None:
    assert validate_link_template_fields("n", "https://x/{a}/{b}/{c}/{d}/{e}") is None


def test_validate_link_accepts_empty_display_name() -> None:
    assert validate_item_link_fields("", None, "https://example.com/doc", {}) is None
    assert validate_item_link_fields("", JIRA, "", {"project": "P", "id": "1"}) is None


def test_validate_link_accepts_direct_url_and_template_values() -> None:
    assert validate_item_link_fields("資料", None, "https://example.com/doc", {}) is None
    assert validate_item_link_fields("t", JIRA, "", {"project": "P", "id": "1"}) is None


@pytest.mark.parametrize(
    ("name", "url", "expected"),
    [
        ("a\nb", "https://example.com", "制御文字"),
        ("a" * 31, "https://example.com", "30文字以内"),
        ("n", "", "URL"),
        ("n", "javascript:alert(1)", "http://"),
        ("n", "https://example.com/日本", "ASCII以外"),
    ],
)
def test_validate_direct_link_rejects_invalid_input(name: str, url: str, expected: str) -> None:
    error = validate_item_link_fields(name, None, url, {})
    assert error is not None
    assert expected in error


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"project": "P"}, "id"),
        ({"project": "P", "id": "a\tb"}, "制御文字"),
        ({"project": "P", "id": "a" * 201}, "200文字以内"),
    ],
)
def test_validate_template_link_rejects_invalid_values(values: dict[str, str], expected: str) -> None:
    error = validate_item_link_fields("t", JIRA, "", values)
    assert error is not None
    assert expected in error


def test_validate_template_link_rejects_too_long_resolved_url() -> None:
    template = LinkTemplate(name="t", url_template="https://x/{a}/{b}")
    values = {"a": "あ" * 200, "b": "あ" * 200}
    error = validate_item_link_fields("t", template, "", values)
    assert error is not None
    assert "2000" in error
