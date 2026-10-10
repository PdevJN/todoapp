from datetime import date, datetime, time, timedelta
from typing import Any

from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from test.ui.harness import (
    AppEnv,
    click_displayed,
    click_row,
    displayed_elements,
    hides,
    is_displayed,
    make_item,
    make_record,
    press,
    select_toggle,
    shows,
)
from todoapp.domain.models import Category, ExecutionRecord, ScheduleType, TodoItem
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


# --- 画面操作(ブラウザ無しの画面テスト) ---------------------------------------------------
# 記録のタスク名がメインパネルの行と重なると、行の特定が曖昧になる。
# そのため、アイテムは完了済み(既定の絞り込みでメインパネルに出ない)にして用意する。

TODAY = date.today()


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(TODAY, time(hour, minute))


def _done_item(name: str, **kwargs: Any) -> TodoItem:
    return make_item(name, ScheduleType.ONE_TIME, done_date=TODAY, **kwargs)


def _seed_three_records(env: AppEnv) -> None:
    items = [_done_item("アルファ"), _done_item("ブラボー"), _done_item("チャーリー")]
    env.seed(
        items=items,
        records=[
            make_record(items[0], _at(9), _at(10)),
            make_record(items[1], _at(10), _at(11)),
            make_record(items[2], _at(11), _at(12)),
        ],
    )


def _record_names(env: AppEnv) -> list[str]:
    return [r.item_name for r in env.todos().records]


def _by_screen_order(elements: Any) -> list[Any]:
    """`find().elements`は集合で順序が不定のため、生成順(id順)に並べる。"""
    return sorted(elements, key=lambda e: e.id)


def _calendar_buttons(user: User) -> list[ui.button]:
    return [
        e
        for e in _by_screen_order(user.find(kind=ui.button).elements)
        if e.props.get("icon") == "calendar_month" and is_displayed(e)
    ]


def _copy_button(user: User) -> ui.button | None:
    buttons = [
        e
        for e in user.find(kind=ui.button).elements
        if isinstance(e, ui.button) and e.props.get("label") == "経過時間をコピー" and is_displayed(e)
    ]
    return buttons[0] if buttons else None


async def _open_log(user: User) -> None:
    await user.open("/")
    await press(user, "l")
    await shows(user, "本日の作業ログ")


async def test_log_without_records_shows_placeholder(app_user: User, app_env: AppEnv) -> None:
    await _open_log(app_user)

    await shows(app_user, "本日の記録はまだありません")


async def test_log_lists_todays_records_in_start_order_with_times(app_user: User, app_env: AppEnv) -> None:
    late = _done_item("午後の作業")
    early = _done_item("午前の作業")
    app_env.seed(
        items=[late, early],
        records=[make_record(late, _at(13), _at(14, 30)), make_record(early, _at(9), _at(9, 45))],
    )

    await _open_log(app_user)

    await shows(app_user, "09:00:00 - 09:45:00 (00:45:00)")
    await shows(app_user, "13:00:00 - 14:30:00 (01:30:00)")
    await hides(app_user, "本日の記録はまだありません")
    names = [e.text for e in _by_screen_order(app_user.find(kind=ui.label, marker=None).elements) if e.text in ("午前の作業", "午後の作業")]
    assert names == ["午前の作業", "午後の作業"]


async def test_log_excludes_records_of_other_days(app_user: User, app_env: AppEnv) -> None:
    item = _done_item("昨日の作業")
    yesterday = datetime.combine(TODAY - timedelta(days=1), time(9))
    app_env.seed(items=[item], records=[make_record(item, yesterday, yesterday + timedelta(hours=1))])

    await _open_log(app_user)

    await shows(app_user, "本日の記録はまだありません")
    await hides(app_user, "昨日の作業")


async def test_log_shows_running_record_as_running(app_user: User, app_env: AppEnv) -> None:
    item = _done_item("実行中の作業")
    app_env.seed(items=[item], records=[make_record(item, _at(0, 0), None)])

    await _open_log(app_user)

    await shows(app_user, "00:00:00 - 実行中")


async def test_log_shows_item_category_badge_and_uncategorized_for_deleted_item(
    app_user: User, app_env: AppEnv
) -> None:
    work = Category(name="開発")
    item = _done_item("設計", category_id=work.id)
    deleted = ExecutionRecord(item_id="gone", item_name="消えた作業", start_time=_at(10), end_time=_at(11))
    app_env.seed(items=[item], categories=[work], records=[make_record(item, _at(9), _at(10)), deleted])

    await _open_log(app_user)

    badges = {e.text for e in app_user.find(kind=ui.badge).elements if is_displayed(e)}
    assert badges == {"開発", "未定"}


async def test_calendar_button_is_disabled_only_for_running_record(app_user: User, app_env: AppEnv) -> None:
    done = _done_item("終了済み")
    running = _done_item("実行中")
    app_env.seed(
        items=[done, running],
        records=[make_record(done, _at(0, 0), _at(0, 30)), make_record(running, _at(1, 0), None)],
    )

    await _open_log(app_user)

    buttons = _calendar_buttons(app_user)
    assert [b.enabled for b in buttons] == [True, False]


async def test_calendar_button_opens_timeline_edit_for_that_record(app_user: User, app_env: AppEnv) -> None:
    _seed_three_records(app_env)
    await _open_log(app_user)
    buttons = _calendar_buttons(app_user)

    UserInteraction(app_user, {buttons[1]}, None).trigger("click.stop")

    await shows(app_user, "ブラボー  開始 10:00:00 / 終了 11:00:00 / 経過 01:00:00")


async def test_clicking_a_row_selects_it_and_delete_removes_only_that_record(
    app_user: User, app_env: AppEnv
) -> None:
    _seed_three_records(app_env)
    await _open_log(app_user)

    click_row(app_user, "ブラボー")
    await press(app_user, "Delete")

    assert _record_names(app_env) == ["アルファ", "チャーリー"]  # 1件は確認なしで削除


async def test_ctrl_click_and_shift_click_select_multiple_records(app_user: User, app_env: AppEnv) -> None:
    _seed_three_records(app_env)
    await _open_log(app_user)

    click_row(app_user, "アルファ")
    click_row(app_user, "チャーリー", shift=True)
    await press(app_user, "Delete")
    await shows(app_user, "3件の記録を削除します")
    click_displayed(app_user, "キャンセル")

    click_row(app_user, "ブラボー")
    click_row(app_user, "チャーリー", ctrl=True)
    click_row(app_user, "ブラボー", ctrl=True)  # 個別選択のトグルで外す
    await press(app_user, "Delete")

    assert _record_names(app_env) == ["アルファ", "ブラボー"]


async def test_arrow_keys_move_record_selection_and_stop_at_both_ends(app_user: User, app_env: AppEnv) -> None:
    _seed_three_records(app_env)
    await _open_log(app_user)

    await press(app_user, "j")  # 未選択からは先頭
    await press(app_user, "ArrowDown")
    await press(app_user, "ArrowDown")
    await press(app_user, "ArrowDown")  # 末尾で止まる
    await press(app_user, "Delete")
    assert _record_names(app_env) == ["アルファ", "ブラボー"]

    await press(app_user, "ArrowUp")  # 削除後は未選択のため、末尾から
    await press(app_user, "k")
    await press(app_user, "k")  # 先頭で止まる
    await press(app_user, "Delete")
    assert _record_names(app_env) == ["ブラボー"]


async def test_select_all_selects_every_record_and_delete_asks_for_confirmation(
    app_user: User, app_env: AppEnv
) -> None:
    _seed_three_records(app_env)
    await _open_log(app_user)

    await press(app_user, "a", meta=True)
    await press(app_user, "Delete")

    await shows(app_user, "3件の記録を削除します")
    click_displayed(app_user, "削除する")
    assert _record_names(app_env) == []
    await shows(app_user, "本日の記録はまだありません")


async def test_category_mode_shows_every_category_and_uncategorized_last(app_user: User, app_env: AppEnv) -> None:
    work = Category(name="開発", prj_code="PRJ-1")
    sales = Category(name="営業")
    item = _done_item("設計", category_id=work.id)
    app_env.seed(items=[item], categories=[work, sales], records=[make_record(item, _at(9), _at(10, 30))])
    await _open_log(app_user)

    select_toggle(app_user, "カテゴリ別")

    await shows(app_user, "01:30:00")
    for text in ("開発", "PRJ-1", "営業", "未定"):
        await shows(app_user, text)
    await hides(app_user, "本日の記録はまだありません")
    labels = [e.text for e in _by_screen_order(app_user.find(kind=ui.label).elements) if is_displayed(e)]
    assert labels.index("開発") < labels.index("営業") < labels.index("未定")


async def test_category_mode_lists_tasks_of_category_in_tooltip(app_user: User, app_env: AppEnv) -> None:
    work = Category(name="開発")
    item = _done_item("設計", category_id=work.id)
    app_env.seed(items=[item], categories=[work], records=[make_record(item, _at(9), _at(10))])
    await _open_log(app_user)

    select_toggle(app_user, "カテゴリ別")

    await shows(app_user, "・設計")
    await shows(app_user, "本日のタスクはありません")  # 未定には本日のタスクが無い


async def test_copy_button_is_only_visible_in_category_mode_and_copies_registered_categories(
    app_user: User, app_env: AppEnv
) -> None:
    work = Category(name="開発")
    sales = Category(name="営業")
    item = _done_item("設計", category_id=work.id)
    app_env.seed(items=[item], categories=[work, sales], records=[make_record(item, _at(9), _at(10))])
    await _open_log(app_user)
    assert _copy_button(app_user) is None

    select_toggle(app_user, "カテゴリ別")
    await shows(app_user, "営業")  # カテゴリ別にだけ出る文言で再描画の完了を待つ(実行順の行にも01:00:00は含まれる)

    button = _copy_button(app_user)
    assert button is not None
    assert button.props["data-copy-text"] == "01:00:00\n00:00:00"  # 未定は含めない
    assert button.enabled


async def test_copy_result_is_notified(app_user: User, app_env: AppEnv) -> None:
    work = Category(name="開発")
    app_env.seed(categories=[work])
    await _open_log(app_user)
    select_toggle(app_user, "カテゴリ別")
    button = _copy_button(app_user)
    assert button is not None

    UserInteraction(app_user, {button}, None).trigger("click", True)
    await app_user.should_see("経過時間をコピーしました")

    UserInteraction(app_user, {button}, None).trigger("click", False)
    await app_user.should_see("クリップボードへのコピーに失敗しました")


async def test_copy_button_is_disabled_without_registered_categories(app_user: User, app_env: AppEnv) -> None:
    await _open_log(app_user)

    select_toggle(app_user, "カテゴリ別")
    await shows(app_user, "未定")  # 再描画の完了を待つ

    button = _copy_button(app_user)
    assert button is not None
    assert button.props["data-copy-text"] == ""
    assert not button.enabled


async def test_switching_mode_clears_record_selection(app_user: User, app_env: AppEnv) -> None:
    _seed_three_records(app_env)
    await _open_log(app_user)
    click_row(app_user, "アルファ")

    select_toggle(app_user, "カテゴリ別")
    select_toggle(app_user, "実行順")
    await press(app_user, "Delete")

    assert _record_names(app_env) == ["アルファ", "ブラボー", "チャーリー"]


async def test_category_mode_ignores_record_selection_keys(app_user: User, app_env: AppEnv) -> None:
    _seed_three_records(app_env)
    await _open_log(app_user)
    select_toggle(app_user, "カテゴリ別")

    await press(app_user, "a", meta=True)
    await press(app_user, "j")
    await press(app_user, "Delete")

    assert _record_names(app_env) == ["アルファ", "ブラボー", "チャーリー"]


async def test_reopening_log_returns_to_order_mode(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(categories=[Category(name="開発")])
    await _open_log(app_user)
    select_toggle(app_user, "カテゴリ別")
    await shows(app_user, "開発")
    click_displayed(app_user, "閉じる")
    await hides(app_user, "本日の作業ログ")

    await press(app_user, "l")

    await shows(app_user, "本日の記録はまだありません")
    assert _copy_button(app_user) is None
