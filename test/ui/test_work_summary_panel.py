from datetime import date
from typing import Any

from todoapp.domain.work_summary import WorkDayRow
from todoapp.ui.work_summary_panel import work_chart_options

MON = date(2026, 9, 7)


def _series(options: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in options["series"] if s["name"] == name)


def test_chart_has_estimate_actual_and_gap_series_per_day() -> None:
    rows = [
        WorkDayRow(MON, True, 28800, 30600.0),
        WorkDayRow(date(2026, 9, 8), True, None, 3600.0),
    ]

    options = work_chart_options(rows)

    assert options["xAxis"]["data"] == ["9/7", "9/8"]
    assert [s["name"] for s in options["series"]] == ["見積り", "実績", "GAP"]
    assert _series(options, "見積り")["data"] == [{"value": 8.0, "seconds": 28800}, None]
    assert _series(options, "実績")["data"] == [
        {"value": 8.5, "seconds": 30600.0},
        {"value": 1.0, "seconds": 3600.0},
    ]
    # GAPは見積りのある日だけ(実績 − 見積り)
    assert _series(options, "GAP")["data"] == [{"value": 0.5, "seconds": 1800.0}, None]
    assert _series(options, "GAP")["type"] == "line"


def test_chart_omits_estimate_and_gap_series_without_any_estimate() -> None:
    options = work_chart_options([WorkDayRow(MON, True, None, 3600.0)])

    assert [s["name"] for s in options["series"]] == ["実績"]


def test_chart_gap_value_can_be_negative() -> None:
    options = work_chart_options([WorkDayRow(MON, True, 7200, 0.0)])

    assert _series(options, "GAP")["data"] == [{"value": -2.0, "seconds": -7200.0}]


def test_chart_includes_non_workday_with_actual() -> None:
    options = work_chart_options([WorkDayRow(date(2026, 9, 12), False, None, 600.0)])

    assert _series(options, "実績")["data"][0]["seconds"] == 600.0
