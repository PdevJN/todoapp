from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

MAX_PERIOD_DAYS = 366


@dataclass(frozen=True)
class WorkDayRow:
    day: date
    is_workday: bool
    estimate_seconds: int | None  # 履歴に1件も無い日は`None`
    actual_seconds: float


@dataclass(frozen=True)
class WorkSummary:
    start: date
    end: date
    rows: list[WorkDayRow]
    workday_count: int  # 期間全体の稼働日数
    total_seconds: float  # 稼働日数 × 標準労働時間
    actual_seconds: float  # 期間内の実績の合計
    overtime_seconds: float  # 実績 − (今日以前の稼働日数 × 標準労働時間)。マイナスあり
    estimate_seconds: int  # 期間内の見積りの合計
    estimate_day_count: int  # 見積りが記録された日の数(0なら見積り・GAPは`-`表示)
    gap_seconds: float  # 見積りのある日の (実績 − 見積り) の合計
    today: date  # 残業時間の基準にした今日(月別の内訳でも同じ日を使う)
    standard_seconds: int  # 1日の標準労働時間(秒)
    in_progress: bool  # 終了日が今日より後(まだ終わっていない期間)。残業ではなく過不足時間として扱う


@dataclass(frozen=True)
class MonthRow:
    """期間を月で分けた1行。期間の端の月は、期間に含まれる日だけで集計する。"""

    year: int
    month: int
    workday_count: int
    total_seconds: float
    actual_seconds: float
    overtime_seconds: float  # 実績 − (今日以前の稼働日数 × 標準労働時間)
    in_progress: bool  # その月の集計範囲の最終日が今日より後


def is_workday(day: date, overrides: Mapping[date, bool], holidays: Mapping[date, str]) -> bool:
    """稼働日か。上書きがあればその値、無ければ平日(月〜金)かつ祝日でない日。"""
    if day in overrides:
        return overrides[day]
    return day.weekday() < 5 and day not in holidays


def validate_period(start: date, end: date) -> str | None:
    """期間の問題を警告文言で返す。問題が無ければ`None`。"""
    if start > end:
        return "開始日は終了日以前にしてください"
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        return f"期間は{MAX_PERIOD_DAYS}日以内にしてください"
    return None


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def build_work_summary(
    *,
    start: date,
    end: date,
    today: date,
    standard_seconds: int,
    overrides: Mapping[date, bool],
    holidays: Mapping[date, str],
    estimates: Mapping[date, int],
    actuals: Mapping[date, float],
) -> WorkSummary:
    message = validate_period(start, end)
    if message is not None:
        raise ValueError(message)
    rows = [
        WorkDayRow(
            day=day,
            is_workday=is_workday(day, overrides, holidays),
            estimate_seconds=estimates.get(day),
            actual_seconds=actuals.get(day, 0.0),
        )
        for day in (start + timedelta(days=offset) for offset in range((end - start).days + 1))
    ]
    workday_count = sum(row.is_workday for row in rows)
    # 月の途中でも目標と比べられるよう、残業時間は今日までの稼働日で計算する(未来の稼働日分は引かない)
    elapsed_workdays = sum(row.is_workday and row.day <= today for row in rows)
    actual_seconds = sum(row.actual_seconds for row in rows)
    estimated = [row for row in rows if row.estimate_seconds is not None]
    return WorkSummary(
        start=start,
        end=end,
        rows=rows,
        workday_count=workday_count,
        total_seconds=workday_count * standard_seconds,
        actual_seconds=actual_seconds,
        overtime_seconds=actual_seconds - elapsed_workdays * standard_seconds,
        estimate_seconds=sum(row.estimate_seconds or 0 for row in rows),
        estimate_day_count=len(estimated),
        gap_seconds=sum(row.actual_seconds - (row.estimate_seconds or 0) for row in estimated),
        today=today,
        standard_seconds=standard_seconds,
        in_progress=end > today,
    )


def monthly_breakdown(summary: WorkSummary) -> list[MonthRow]:
    """期間を月で分けて、稼働日数・合計・実績・残業時間を返す。月ごとの残業時間の和は、期間全体の残業時間と一致する。"""
    months: dict[tuple[int, int], list[WorkDayRow]] = {}
    for row in summary.rows:
        months.setdefault((row.day.year, row.day.month), []).append(row)
    result = []
    for (year, month), rows in months.items():
        workday_count = sum(row.is_workday for row in rows)
        elapsed_workdays = sum(row.is_workday and row.day <= summary.today for row in rows)
        actual_seconds = sum(row.actual_seconds for row in rows)
        result.append(
            MonthRow(
                year=year,
                month=month,
                workday_count=workday_count,
                total_seconds=workday_count * summary.standard_seconds,
                actual_seconds=actual_seconds,
                overtime_seconds=actual_seconds - elapsed_workdays * summary.standard_seconds,
                in_progress=rows[-1].day > summary.today,
            )
        )
    return result


def overtime_exceeds_target(overtime_seconds: float, target_hours: float) -> bool:
    """残業時間が目標を上回ったか(秒に丸めて比べ、ちょうどは上回りにしない)。"""
    return round(overtime_seconds) > round(target_hours * 3600)
