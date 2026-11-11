from todoapp.ui.table_layout import fixed_width


def test_fixed_width_pins_header_and_cell_width_without_mutating_the_original() -> None:
    column = {"name": "kind", "label": "種別"}

    pinned = fixed_width(column, 5)

    assert pinned["style"] == "width: 5rem; max-width: 5rem"
    assert pinned["headerStyle"] == "width: 5rem; max-width: 5rem"
    assert "classes" not in pinned
    assert column == {"name": "kind", "label": "種別"}


def test_fixed_width_adds_ellipsis_class_only_when_requested() -> None:
    assert fixed_width({"name": "kind"}, 6.5, ellipsis=True)["classes"] == "ellipsis"
    assert "classes" not in fixed_width({"name": "kind"}, 6.5)
