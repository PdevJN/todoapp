from todoapp.domain.models import Category
from todoapp.domain.service import ItemGapRow
from todoapp.ui.category_summary_dialog import UNCATEGORIZED_COLOR, gap_pie_data, pie_chart_data


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


def test_gap_pie_data_uses_absolute_gap_and_gap_colors() -> None:
    over = ItemGapRow("超過", 600, 900, 600, 300)
    under = ItemGapRow("余り", 600, 300, 600, -300)

    data = gap_pie_data([over, under])

    assert [(d["name"], d["value"]) for d in data] == [("超過", 300), ("余り", 300)]
    assert data[0]["itemStyle"]["color"] == "rgba(229, 57, 53, 0.34)"
    assert data[1]["itemStyle"]["color"] == "rgba(30, 136, 229, 0.34)"


def test_gap_pie_data_tooltip_shows_signed_gap_estimate_and_cumulative() -> None:
    row = ItemGapRow("設計", 600, 967, 720, 247)

    data = gap_pie_data([row])

    assert data[0]["tooltip"] == "設計  GAP +00:04:07 (見積り 00:12:00 / 累積 00:16:07)"


def test_gap_pie_data_excludes_rows_without_gap_or_with_zero_gap() -> None:
    rows = [
        ItemGapRow("見積り無し", 60, 60, None, None),
        ItemGapRow("削除済み", 60, None, None, None),
        ItemGapRow("ぴったり", 60, 185, 185, 0.0),
        ItemGapRow("丸めて0", 60, 184.88, 185, -0.12),
        ItemGapRow("対象", 60, 100, 50, 50),
    ]

    assert [d["name"] for d in gap_pie_data(rows)] == ["対象"]


def test_gap_pie_data_is_empty_without_rows() -> None:
    assert gap_pie_data([]) == []
