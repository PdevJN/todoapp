from todoapp.domain.models import Category
from todoapp.ui.category_summary_dialog import UNCATEGORIZED_COLOR, pie_chart_data


def test_pie_chart_data_uses_category_name_color_and_seconds() -> None:
    work = Category(name="仕事", color="#112233")

    data = pie_chart_data([(work, 3600)])

    assert data == [{"name": "仕事", "value": 3600, "itemStyle": {"color": "#112233"}}]


def test_pie_chart_data_excludes_zero_second_categories() -> None:
    work = Category(name="仕事")
    sales = Category(name="営業")

    data = pie_chart_data([(work, 60), (sales, 0)])

    assert [d["name"] for d in data] == ["仕事"]


def test_pie_chart_data_shows_uncategorized_in_gray_at_the_end() -> None:
    work = Category(name="仕事")

    data = pie_chart_data([(work, 60), (None, 1800)])

    assert data[-1] == {"name": "未定", "value": 1800, "itemStyle": {"color": UNCATEGORIZED_COLOR}}


def test_pie_chart_data_is_empty_without_records() -> None:
    assert pie_chart_data([]) == []
    assert pie_chart_data([(None, 0)]) == []
