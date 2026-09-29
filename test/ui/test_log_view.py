from todoapp.domain.models import Category
from todoapp.ui.log_view import category_durations_text


def test_category_durations_text_lists_durations_line_by_line_in_order() -> None:
    work = Category(name="仕事")
    sales = Category(name="営業")

    text = category_durations_text([(work, 8100), (sales, 0)])

    assert text == "02:15:00\n00:00:00"


def test_category_durations_text_excludes_uncategorized() -> None:
    work = Category(name="仕事")

    text = category_durations_text([(work, 60), (None, 1800)])

    assert text == "00:01:00"


def test_category_durations_text_is_empty_without_categories() -> None:
    assert category_durations_text([(None, 1800)]) == ""
