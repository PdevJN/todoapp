"""集計画面の`稼働集計`タブを、ブラウザ無し(NiceGUIの`user`)で操作する画面テスト。

期間は過去の固定日(2026-09-07〜)にして、今日の日付に依存させない。
"""

from datetime import date, datetime, timedelta

from nicegui import ui
from nicegui.testing import User

from test.ui.harness import (
    AppEnv,
    is_displayed,
    make_item,
    make_record,
    press,
    select_tab,
    select_toggle,
    set_value,
    shows,
)
from todoapp.domain.models import DailyEstimate, ScheduleType
from todoapp.domain.work_summary import month_bounds

MON = date(2026, 9, 7)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute)


async def _open_period(user: User, start: date, end: date) -> None:
    await user.open("/")
    await press(user, "T", shift=True)
    await shows(user, "集計画面")
    select_tab(user, "稼働集計")
    select_toggle(user, "期間")
    set_value(user, "work-start", start.isoformat())
    set_value(user, "work-end", end.isoformat())


def _marked(user: User, marker: str) -> list[ui.element]:
    """マーカーを付けた表示中の要素。`find`は非表示の要素を返さず、折りたたみの中も区別できないため、直接探す。"""
    assert user.client is not None
    return [e for e in user.client.elements.values() if marker in e._markers and is_displayed(e)]  # noqa: SLF001


def _overtime_label(user: User) -> ui.label:
    [label] = user.find(marker="work-overtime").elements
    return label  # type: ignore[return-value]


async def test_period_shows_workdays_total_actual_and_overtime(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    app_env.seed(
        items=[item],
        records=[
            make_record(item, _at(MON, 9), _at(MON, 18)),  # 9時間
            make_record(item, _at(MON + timedelta(days=1), 9), _at(MON + timedelta(days=1), 17, 30)),  # 8.5時間
        ],
    )

    await _open_period(app_user, MON, MON + timedelta(days=4))

    await shows(app_user, "5日")
    await shows(app_user, "40:00")  # 合計 = 5日 × 8時間
    await shows(app_user, "17:30")  # 実績
    await shows(app_user, "-22:30")  # 残業時間 = 17:30 - 40:00
    await shows(app_user, "残業時間(合計)")


async def test_estimate_and_gap_are_shown_from_history(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    app_env.seed(
        items=[item],
        records=[make_record(item, _at(MON, 9), _at(MON, 18))],
        estimate_history=[DailyEstimate(MON, item.id, 8 * 3600)],
    )

    await _open_period(app_user, MON, MON + timedelta(days=4))

    await shows(app_user, "08:00")  # 見積り
    await shows(app_user, "+01:00")  # 見積りGAP = 9時間 - 8時間


async def test_overtime_is_green_at_exactly_the_target_and_red_above_it(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    records = [
        make_record(item, _at(MON + timedelta(days=offset), 8), _at(MON + timedelta(days=offset), 20))
        for offset in range(5)
    ]  # 12時間 × 5日 = 60時間 → 残業 = 60 - 40 = 20:00(目標20時間ちょうど)
    saturday = MON + timedelta(days=5)
    app_env.seed(items=[item], records=records + [make_record(item, _at(saturday, 10), _at(saturday, 10, 1))])

    await _open_period(app_user, MON, MON + timedelta(days=4))
    await shows(app_user, "+20:00")
    assert "text-green-600" in _overtime_label(app_user).classes
    assert "text-red-600" not in _overtime_label(app_user).classes

    set_value(app_user, "work-end", saturday.isoformat())  # 土曜の1分を含める → +20:01
    await shows(app_user, "+20:01")
    assert "text-red-600" in _overtime_label(app_user).classes


async def test_invalid_period_warns_and_keeps_the_previous_summary(app_user: User, app_env: AppEnv) -> None:
    await _open_period(app_user, MON, MON + timedelta(days=4))
    await shows(app_user, "5日")

    set_value(app_user, "work-start", (MON + timedelta(days=10)).isoformat())

    await app_user.should_see("開始日は終了日以前にしてください")
    await shows(app_user, "5日")


async def test_month_mode_starts_from_this_month_and_moves_with_arrows(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "T", shift=True)
    select_tab(app_user, "稼働集計")
    today = date.today()
    [month_label] = _marked(app_user, "work-month-label")
    assert month_label.text == f"{today.year}年{today.month}月"

    app_user.find(marker="work-prev-month").click()

    previous = today.replace(day=1) - timedelta(days=1)
    assert month_label.text == f"{previous.year}年{previous.month}月"


async def test_month_mode_labels_in_progress_month_as_balance_and_finished_month_as_overtime(
    app_user: User, app_env: AppEnv
) -> None:
    await app_user.open("/")
    await press(app_user, "T", shift=True)
    select_tab(app_user, "稼働集計")
    today = date.today()
    this_month_end = month_bounds(today.year, today.month)[1]

    [title] = _marked(app_user, "work-overtime-title")
    assert title.text == ("過不足時間" if this_month_end > today else "残業時間")  # type: ignore[attr-defined]

    app_user.find(marker="work-prev-month").click()  # 終わった月は残業時間

    [title] = _marked(app_user, "work-overtime-title")
    assert title.text == "残業時間"  # type: ignore[attr-defined]


async def test_period_that_ends_after_today_is_labeled_balance_total(app_user: User, app_env: AppEnv) -> None:
    today = date.today()

    await _open_period(app_user, today.replace(day=1), today + timedelta(days=10))

    await shows(app_user, "過不足時間(合計)")


async def test_period_shows_monthly_breakdown_and_uncolored_total(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    weekdays = [
        date(2026, 8, 3) + timedelta(days=week * 7 + offset) for week in range(4) for offset in range(5)
    ]  # 8/3〜8/28の平日20日 × 12時間 = 240時間。8月の稼働日は21日(168時間)なので+72:00
    app_env.seed(items=[item], records=[make_record(item, _at(d, 8), _at(d, 20)) for d in weekdays])

    await _open_period(app_user, date(2026, 8, 3), date(2026, 9, 4))

    await shows(app_user, "月別の内訳")
    [august] = _marked(app_user, "work-month-2026-08")
    [september] = _marked(app_user, "work-month-2026-09")
    [total] = _marked(app_user, "work-month-total")
    assert august.text == "+72:00" and "text-red-600" in august.classes  # 目標20時間を上回る
    assert september.text == "-32:00" and "text-green-600" in september.classes
    assert total.text == "+40:00"  # 通算 = 240 - 25日 × 8時間
    assert "text-red-600" not in total.classes and "text-green-600" not in total.classes  # 通算は色なし


async def test_month_mode_has_no_monthly_breakdown(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "T", shift=True)
    select_tab(app_user, "稼働集計")

    assert not _marked(app_user, "work-month-total")


async def test_clicking_a_day_toggles_workday_and_saves_override(app_user: User, app_env: AppEnv) -> None:
    saturday = MON + timedelta(days=5)
    await _open_period(app_user, MON, MON + timedelta(days=6))
    await shows(app_user, "5日")

    app_user.find(marker=f"work-day-{saturday.isoformat()}").click()

    await shows(app_user, "6日")
    assert app_env.todos().workday_overrides == {saturday: True}

    app_user.find(marker=f"work-day-{saturday.isoformat()}").click()  # 既定に戻すと上書きが消える

    await shows(app_user, "5日")
    assert app_env.todos().workday_overrides == {}


async def test_saved_override_is_applied_when_reopened(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(workday_overrides={MON: False})  # 月曜を非稼働日に

    await _open_period(app_user, MON, MON + timedelta(days=4))

    await shows(app_user, "4日")


async def test_chart_is_hidden_until_the_toggle_button_is_pressed(app_user: User, app_env: AppEnv) -> None:
    item = make_item("設計", ScheduleType.ONE_TIME)
    app_env.seed(items=[item], records=[make_record(item, _at(MON, 9), _at(MON, 10))])
    await _open_period(app_user, MON, MON + timedelta(days=4))
    assert app_user.client is not None
    # 非表示の要素は`find`に出ないため、クライアントの要素から直接探す
    [chart] = [e for e in app_user.client.elements.values() if "work-chart" in e._markers]  # noqa: SLF001

    assert not is_displayed(chart)

    app_user.find(marker="summary-chart-toggle").click()

    assert is_displayed(chart)
