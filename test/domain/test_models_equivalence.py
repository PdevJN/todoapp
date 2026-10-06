"""`domain/models.py`の判定ルールを、同値クラスと境界値で網羅する(ドメイン分析)。"""

from datetime import date

import pytest

from todoapp.domain.models import (
    Category,
    DoneFilter,
    ScheduleType,
    TodoItem,
    is_category_expired,
    is_done,
    is_due_today,
    matches_done_filter,
    today_estimate_seconds,
)

ANCHOR = date(2026, 8, 24)  # 月曜
TODAY = date(2026, 9, 7)


def _item(
    schedule_type: ScheduleType = ScheduleType.DAILY,
    anchor: date = ANCHOR,
    *,
    done_date: date | None = None,
    today_estimate_hours: float = 0.0,
    today_estimate_date: date | None = None,
) -> TodoItem:
    return TodoItem(
        name="t",
        schedule_type=schedule_type,
        anchor_date=anchor,
        done_date=done_date,
        today_estimate_hours=today_estimate_hours,
        today_estimate_date=today_estimate_date,
    )


# --- is_due_today -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("schedule_type", "today", "expected"),
    [
        # 毎日: 基準日との前後関係に依らず常に対象
        (ScheduleType.DAILY, date(2026, 8, 23), True),
        (ScheduleType.DAILY, ANCHOR, True),
        (ScheduleType.DAILY, date(2026, 8, 25), True),
        # 週次: 同じ曜日かつ基準日以降のみ(基準日の前週・当日・翌日・翌週)
        (ScheduleType.WEEKLY, date(2026, 8, 17), False),
        (ScheduleType.WEEKLY, ANCHOR, True),
        (ScheduleType.WEEKLY, date(2026, 8, 25), False),
        (ScheduleType.WEEKLY, date(2026, 8, 31), True),
        # 月次: 同じ日かつ基準日以降のみ(基準日の前月・当日・翌日・翌月)
        (ScheduleType.MONTHLY, date(2026, 7, 24), False),
        (ScheduleType.MONTHLY, ANCHOR, True),
        (ScheduleType.MONTHLY, date(2026, 8, 25), False),
        (ScheduleType.MONTHLY, date(2026, 9, 24), True),
        # 当日(one_time): 基準日そのものだけ
        (ScheduleType.ONE_TIME, date(2026, 8, 23), False),
        (ScheduleType.ONE_TIME, ANCHOR, True),
        (ScheduleType.ONE_TIME, date(2026, 8, 25), False),
    ],
)
def test_is_due_today_equivalence_classes(schedule_type: ScheduleType, today: date, expected: bool) -> None:
    assert is_due_today(_item(schedule_type), today) is expected


@pytest.mark.parametrize(
    ("anchor", "today", "expected"),
    [
        # 基準日31日: 30日までの月は30日、2月は28日(平年)/29日(閏年)に調整される
        (date(2026, 1, 31), date(2026, 4, 30), True),
        (date(2026, 1, 31), date(2026, 4, 29), False),
        (date(2026, 1, 31), date(2026, 2, 28), True),
        (date(2028, 1, 31), date(2028, 2, 29), True),
        (date(2028, 1, 31), date(2028, 2, 28), False),
        # 31日がある月は調整されない
        (date(2026, 1, 31), date(2026, 5, 31), True),
        (date(2026, 1, 31), date(2026, 5, 30), False),
        # 基準日30日: 31日がある月の31日は対象外(調整は「超える場合」のみ)
        (date(2026, 1, 30), date(2026, 5, 31), False),
        (date(2026, 1, 30), date(2026, 5, 30), True),
        # 基準日29日: 平年の2月は28日に調整、閏年の2月は29日
        (date(2026, 1, 29), date(2027, 2, 28), True),
        (date(2028, 1, 29), date(2029, 2, 28), True),
        (date(2028, 1, 29), date(2032, 2, 29), True),
        (date(2028, 1, 29), date(2032, 2, 28), False),
        # 基準日1日: 月初
        (date(2026, 1, 1), date(2026, 12, 1), True),
        (date(2026, 1, 1), date(2026, 12, 2), False),
    ],
)
def test_monthly_day_clamping_boundaries(anchor: date, today: date, expected: bool) -> None:
    assert is_due_today(_item(ScheduleType.MONTHLY, anchor), today) is expected


@pytest.mark.parametrize("offset_days", range(7))
def test_weekly_is_due_only_on_the_anchor_weekday(offset_days: int) -> None:
    # 同値クラス: 1週間(7通りの曜日)のうち、基準日と同じ曜日だけが対象
    today = date(2026, 8, 24 + offset_days)
    assert is_due_today(_item(ScheduleType.WEEKLY), today) is (offset_days == 0)


def test_weekly_and_monthly_are_due_across_year_boundary() -> None:
    assert is_due_today(_item(ScheduleType.WEEKLY, date(2026, 12, 28)), date(2027, 1, 4))
    assert is_due_today(_item(ScheduleType.MONTHLY, date(2026, 12, 15)), date(2027, 1, 15))


# --- is_done / matches_done_filter --------------------------------------------------------


@pytest.mark.parametrize(
    ("schedule_type", "done_date", "expected"),
    [
        # 完了日なし: どの種別でも未完了
        *[(t, None, False) for t in ScheduleType],
        # 当日(one_time): 完了日が過去・当日・未来のいずれでも完了のまま
        (ScheduleType.ONE_TIME, date(2026, 9, 6), True),
        (ScheduleType.ONE_TIME, TODAY, True),
        (ScheduleType.ONE_TIME, date(2026, 9, 8), True),
        # 繰り返し: 完了日が当日の場合だけ完了(前日・翌日は未完了に戻る)
        *[
            (t, done, done == TODAY)
            for t in (ScheduleType.DAILY, ScheduleType.WEEKLY, ScheduleType.MONTHLY)
            for done in (date(2026, 9, 6), TODAY, date(2026, 9, 8))
        ],
    ],
)
def test_is_done_equivalence_classes(schedule_type: ScheduleType, done_date: date | None, expected: bool) -> None:
    assert is_done(_item(schedule_type, done_date=done_date), TODAY) is expected


@pytest.mark.parametrize(
    ("done", "done_filter", "expected"),
    [
        (False, DoneFilter.ACTIVE, True),
        (False, DoneFilter.DONE, False),
        (False, DoneFilter.ALL, True),
        (True, DoneFilter.ACTIVE, False),
        (True, DoneFilter.DONE, True),
        (True, DoneFilter.ALL, True),
    ],
)
def test_matches_done_filter_decision_table(done: bool, done_filter: DoneFilter, expected: bool) -> None:
    item = _item(ScheduleType.ONE_TIME, done_date=TODAY if done else None)
    assert matches_done_filter(item, TODAY, done_filter) is expected


# --- today_estimate_seconds ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("hours", "estimate_date", "expected"),
    [
        # 有効: 設定日が当日で、秒に丸めて1以上
        (1.0, TODAY, 3600),
        (0.5, TODAY, 1800),
        (1 / 6, TODAY, 600),  # 10分=0.1666…時間は秒へ丸めて10分になる
        (1 / 3600, TODAY, 1),  # 1秒(有効な最小の値)
        (1.5 / 3600, TODAY, 2),  # 1.5秒はPythonのround(偶数丸め)で2秒
        # 無効: 時間が0・負・丸めて0秒になる値
        (0.0, TODAY, None),
        (-1.0, TODAY, None),
        (0.4 / 3600, TODAY, None),  # 0.4秒は丸めて0秒
        (0.5 / 3600, TODAY, None),  # 0.5秒はround(偶数丸め)で0秒
        # 無効: 設定日が当日でない(前日・翌日・未設定)
        (1.0, date(2026, 9, 6), None),
        (1.0, date(2026, 9, 8), None),
        (1.0, None, None),
    ],
)
def test_today_estimate_seconds_equivalence_and_boundaries(
    hours: float, estimate_date: date | None, expected: int | None
) -> None:
    item = _item(today_estimate_hours=hours, today_estimate_date=estimate_date)
    assert today_estimate_seconds(item, TODAY) == expected


# --- is_category_expired ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expiry", "expected"),
    [
        (None, False),  # 有効期限なし
        (date(2026, 9, 6), True),  # 前日(期限切れ)
        (TODAY, False),  # 当日(期限日当日は有効)
        (date(2026, 9, 8), False),  # 翌日
    ],
)
def test_is_category_expired_boundaries(expiry: date | None, expected: bool) -> None:
    assert is_category_expired(Category(name="c", expiry_date=expiry), TODAY) is expected
