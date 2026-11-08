from datetime import date, timedelta
from typing import Any

import pytest

from todoapp.domain.work_summary import (
    MAX_PERIOD_DAYS,
    MonthRow,
    WorkSummary,
    build_work_summary,
    is_workday,
    month_bounds,
    monthly_breakdown,
    overtime_exceeds_target,
    recent_complete_months,
    recent_months_stats,
    validate_period,
)

STANDARD = 8 * 3600
MON = date(2026, 9, 7)  # 2026-09-07は月曜


def _build(start: date, end: date, today: date, **kwargs: Any) -> WorkSummary:
    params: dict[str, Any] = {"overrides": {}, "holidays": {}, "estimates": {}, "actuals": {}}
    params.update(kwargs)
    return build_work_summary(start=start, end=end, today=today, standard_seconds=STANDARD, **params)


def test_is_workday_defaults_to_weekdays_without_holidays() -> None:
    assert is_workday(MON, {}, {})
    assert not is_workday(date(2026, 9, 12), {}, {})  # 土曜
    assert not is_workday(date(2026, 9, 13), {}, {})  # 日曜


def test_is_workday_excludes_holiday_on_weekday() -> None:
    assert not is_workday(date(2026, 9, 21), {}, {date(2026, 9, 21): "敬老の日"})


def test_is_workday_uses_override_over_defaults() -> None:
    saturday = date(2026, 9, 12)
    assert is_workday(saturday, {saturday: True}, {})
    assert not is_workday(MON, {MON: False}, {})
    assert is_workday(date(2026, 9, 21), {date(2026, 9, 21): True}, {date(2026, 9, 21): "敬老の日"})


def test_month_bounds_handles_leap_february() -> None:
    assert month_bounds(2028, 2) == (date(2028, 2, 1), date(2028, 2, 29))
    assert month_bounds(2026, 12) == (date(2026, 12, 1), date(2026, 12, 31))


def test_validate_period_boundaries() -> None:
    assert validate_period(MON, MON) is None  # 1日だけ
    assert validate_period(MON, MON + timedelta(days=MAX_PERIOD_DAYS - 1)) is None  # 366日ちょうど
    assert validate_period(MON, MON + timedelta(days=MAX_PERIOD_DAYS)) == "期間は366日以内にしてください"
    assert validate_period(MON + timedelta(days=1), MON) == "開始日は終了日以前にしてください"


def test_build_work_summary_rejects_invalid_period() -> None:
    with pytest.raises(ValueError):
        _build(MON + timedelta(days=1), MON, today=MON)


def test_build_work_summary_totals_a_past_week() -> None:
    saturday = date(2026, 9, 12)
    summary = _build(
        MON,
        date(2026, 9, 13),
        today=date(2026, 9, 30),
        estimates={MON: 28800, MON + timedelta(days=1): 7200},
        actuals={MON: 30000.0, saturday: 3600.0},
    )

    assert summary.workday_count == 5
    assert summary.total_seconds == 5 * STANDARD
    assert summary.actual_seconds == 33600
    assert summary.overtime_seconds == 33600 - 5 * STANDARD  # 休日出勤の実績も含む
    assert summary.estimate_seconds == 36000
    assert summary.estimate_day_count == 2
    # 見積りのある日だけ: (30000-28800) + (0-7200)
    assert summary.gap_seconds == -6000
    assert [row.is_workday for row in summary.rows] == [True] * 5 + [False] * 2
    assert summary.rows[1].actual_seconds == 0.0
    assert summary.rows[2].estimate_seconds is None


def test_overtime_counts_only_workdays_up_to_today() -> None:
    summary = _build(MON, date(2026, 9, 13), today=date(2026, 9, 9))  # 水曜まで

    assert summary.workday_count == 5
    assert summary.total_seconds == 5 * STANDARD  # 合計は期間全体
    assert summary.overtime_seconds == -3 * STANDARD  # 残業時間は月・火・水だけ


def test_overtime_with_period_entirely_in_the_future_is_just_actual() -> None:
    summary = _build(MON, date(2026, 9, 11), today=date(2026, 9, 1), actuals={MON: 600.0})

    assert summary.overtime_seconds == 600


def test_summary_without_estimates_has_zero_estimate_days() -> None:
    summary = _build(MON, MON, today=MON, actuals={MON: 100.0})

    assert summary.estimate_day_count == 0
    assert summary.gap_seconds == 0


def test_single_day_period_and_max_period_are_accepted() -> None:
    assert len(_build(MON, MON, today=MON).rows) == 1
    assert len(_build(MON, MON + timedelta(days=MAX_PERIOD_DAYS - 1), today=MON).rows) == MAX_PERIOD_DAYS


def test_holidays_reduce_workday_count() -> None:
    summary = _build(MON, date(2026, 9, 11), today=date(2026, 9, 30), holidays={date(2026, 9, 9): "臨時"})

    assert summary.workday_count == 4


@pytest.mark.parametrize(
    ("overtime", "target_hours", "expected"),
    [(72000, 20, False), (72001, 20, True), (71999, 20, False), (0, 0, False), (1, 0, True), (-5, 0, False)],
)
def test_overtime_exceeds_target_is_strictly_greater(overtime: float, target_hours: float, expected: bool) -> None:
    assert overtime_exceeds_target(overtime, target_hours) is expected


def test_summary_is_in_progress_until_the_end_date_has_passed() -> None:
    assert _build(MON, date(2026, 9, 13), today=date(2026, 9, 9)).in_progress  # 終了日が今日より後
    assert not _build(MON, date(2026, 9, 13), today=date(2026, 9, 13)).in_progress  # 今日が終了日
    assert not _build(MON, date(2026, 9, 13), today=date(2026, 9, 30)).in_progress


def test_monthly_breakdown_splits_a_period_by_month_with_partial_edges() -> None:
    # 8/31(月)は8月、9/1(火)〜9/4(金)は9月。期間の端の月は期間に含まれる日だけで集計する
    start, end = date(2026, 8, 31), date(2026, 9, 4)
    actuals = {start: 9 * 3600.0, date(2026, 9, 1): 8 * 3600.0}
    summary = _build(start, end, today=date(2026, 9, 30), actuals=actuals)

    rows = monthly_breakdown(summary)

    assert [(r.year, r.month) for r in rows] == [(2026, 8), (2026, 9)]
    assert [r.workday_count for r in rows] == [1, 4]
    assert [r.total_seconds for r in rows] == [STANDARD, 4 * STANDARD]
    assert [r.actual_seconds for r in rows] == [9 * 3600, 8 * 3600]
    assert [r.overtime_seconds for r in rows] == [3600, 8 * 3600 - 4 * STANDARD]
    assert [r.in_progress for r in rows] == [False, False]


def test_monthly_overtime_sums_to_the_total_overtime() -> None:
    start, end = date(2026, 8, 20), date(2026, 10, 10)
    actuals = {date(2026, 8, 25): 10 * 3600.0, date(2026, 9, 14): 9 * 3600.0, date(2026, 10, 5): 3600.0}
    summary = _build(start, end, today=date(2026, 10, 1), actuals=actuals)

    rows = monthly_breakdown(summary)

    assert sum(r.overtime_seconds for r in rows) == summary.overtime_seconds
    assert sum(r.workday_count for r in rows) == summary.workday_count
    assert sum(r.actual_seconds for r in rows) == summary.actual_seconds


def test_monthly_breakdown_marks_months_whose_last_day_is_after_today_as_in_progress() -> None:
    summary = _build(date(2026, 9, 1), date(2026, 10, 31), today=date(2026, 10, 22))

    rows = monthly_breakdown(summary)

    assert [r.in_progress for r in rows] == [False, True]


def test_monthly_breakdown_in_progress_month_does_not_subtract_future_workdays() -> None:
    summary = _build(date(2026, 10, 1), date(2026, 10, 31), today=date(2026, 10, 22), actuals={date(2026, 10, 1): 600.0})

    [row] = monthly_breakdown(summary)

    assert row.workday_count == 22  # 祝日データなしの10月の平日
    assert row.overtime_seconds == 600 - 16 * STANDARD  # 10/1〜10/22の稼働日は16日


# ---- 直近の終わった3か月 ----


def test_recent_complete_months_excludes_base_month() -> None:
    assert recent_complete_months(date(2026, 11, 9)) == [(2026, 8), (2026, 9), (2026, 10)]


def test_recent_complete_months_follows_base_date() -> None:
    assert recent_complete_months(date(2026, 9, 30)) == [(2026, 6), (2026, 7), (2026, 8)]


def test_recent_complete_months_crosses_year_boundary() -> None:
    assert recent_complete_months(date(2026, 1, 1)) == [(2025, 10), (2025, 11), (2025, 12)]
    assert recent_complete_months(date(2026, 2, 28)) == [(2025, 11), (2025, 12), (2026, 1)]


def _month_rows(today: date, actuals: dict[date, float]) -> list[MonthRow]:
    (first_y, first_m), (last_y, last_m) = (m := recent_complete_months(today))[0], m[-1]
    start, end = month_bounds(first_y, first_m)[0], month_bounds(last_y, last_m)[1]
    return monthly_breakdown(_build(start, end, today, actuals=actuals))


def test_recent_months_stats_average_max_min() -> None:
    today = date(2026, 11, 9)
    # 8月=21稼働日(168h)、9月=21稼働日(祝日なし)、10月=22稼働日(176h)を基準に、実績で残業を作る
    months = _month_rows(
        today,
        {date(2026, 8, 3): 168 * 3600 + 3 * 3600, date(2026, 9, 1): 160 * 3600, date(2026, 10, 1): 176 * 3600 + 9 * 3600},
    )
    stats = recent_months_stats(months)
    assert stats is not None
    overtimes = [m.overtime_seconds for m in months]
    assert stats.raw_average_overtime_seconds == pytest.approx(sum(overtimes) / 3)
    assert stats.average_overtime_seconds == pytest.approx(sum(max(o, 0.0) for o in overtimes) / 3)
    assert (stats.max_month.year, stats.max_month.month) == (2026, 10)
    assert (stats.min_month.year, stats.min_month.month) == (2026, 9)
    assert stats.average_workday_count == pytest.approx(sum(m.workday_count for m in months) / 3)
    assert stats.average_actual_seconds == pytest.approx(sum(m.actual_seconds for m in months) / 3)


def test_recent_months_stats_ties_pick_earliest_month() -> None:
    def month(m: int) -> MonthRow:
        return MonthRow(2026, m, 20, 20 * STANDARD, 20 * STANDARD, 0.0, False)

    stats = recent_months_stats([month(8), month(9), month(10)])
    assert stats is not None
    assert stats.max_month.month == 8
    assert stats.min_month.month == 8
    assert stats.average_overtime_seconds == 0.0


def test_recent_months_stats_empty_is_none() -> None:
    assert recent_months_stats([]) is None


def _month(m: int, overtime: float) -> MonthRow:
    return MonthRow(2026, m, 20, 20 * STANDARD, 20 * STANDARD + overtime, overtime, False)


def test_recent_months_stats_treat_negative_overtime_as_zero() -> None:
    stats = recent_months_stats([_month(8, -3600.0), _month(9, 7200.0), _month(10, -7200.0)])
    assert stats is not None
    assert stats.average_overtime_seconds == pytest.approx(7200.0 / 3)  # (0 + 7200 + 0) / 3
    assert stats.raw_average_overtime_seconds == pytest.approx(-3600.0 / 3)  # マイナスを含めた実際の平均
    assert stats.max_month.month == 9
    assert stats.min_month.month == 8  # 0同士(8月・10月)は古い月
    assert stats.has_negative


def test_recent_months_stats_without_negative_has_no_flag() -> None:
    stats = recent_months_stats([_month(8, 0.0), _month(9, 3600.0), _month(10, 7200.0)])
    assert stats is not None
    assert not stats.has_negative
    assert stats.average_overtime_seconds == pytest.approx(stats.raw_average_overtime_seconds)
