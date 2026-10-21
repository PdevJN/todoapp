"""メインパネル・編集一覧・各ダイアログを、ブラウザ無し(NiceGUIの`user`)で操作する画面テスト。

保存先は一時ディレクトリで、操作後の結果は`todos.json`の再読込で確認する。
"""

import json
from datetime import date, timedelta

from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from test.ui.harness import (
    AppEnv,
    click_displayed,
    click_row,
    displayed_elements,
    double_click_row,
    hides,
    input_value,
    make_item,
    press,
    select_toggle,
    shows,
)
from todoapp.domain.models import Category, ScheduleType
from todoapp.ui.formatting import format_weekday
from todoapp.ui.vendor.sortable_table.sortable_table import SortableTable

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


def _names(env: AppEnv) -> list[str]:
    return [item.name for item in env.todos().items]


# --- 表示 ---------------------------------------------------------------------------------


async def test_empty_main_panel_shows_no_items(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")

    await shows(app_user, "未完了のみ")
    await hides(app_user, "合計")


async def test_main_panel_shows_only_items_due_today(app_user: User, app_env: AppEnv) -> None:
    other_weekday = TODAY + timedelta(days=1)
    app_env.seed(
        items=[
            make_item("毎日の用事", ScheduleType.DAILY),
            make_item("今日だけ", ScheduleType.ONE_TIME),
            make_item("明日だけ", ScheduleType.ONE_TIME, anchor_date=TOMORROW),
            make_item("別の曜日", ScheduleType.WEEKLY, anchor_date=other_weekday),
        ]
    )
    await app_user.open("/")

    await shows(app_user, "毎日の用事")
    await shows(app_user, "今日だけ")
    await hides(app_user, "明日だけ")
    await hides(app_user, "別の曜日")


async def test_undecided_item_is_hidden_on_main_but_shown_in_list(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("いつかやる", ScheduleType.UNDECIDED, anchor_date=TOMORROW), make_item("今日だけ", anchor_date=TOMORROW)])
    await app_user.open("/")

    await hides(app_user, "いつかやる")

    await press(app_user, "Escape")  # 編集一覧(基準日の既定は当日)
    await shows(app_user, "編集一覧")
    [table] = [t for t in app_user.find(ui.table).elements if any(c["name"] == "anchor" for c in t.columns)]
    rows = {row["name"]: row for row in table.rows}
    assert rows["いつかやる"]["anchor"] == "-"
    assert rows["いつかやる"]["schedule"] == "未定"
    assert "今日だけ" not in rows  # 基準日が当日の絞り込みは、未定以外にも効く


async def test_work_balance_shows_standard_hours_minus_today_estimates(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(
        items=[
            make_item("設計", today_estimate_hours=3.0, today_estimate_date=TODAY),
            make_item("終わった", ScheduleType.ONE_TIME, today_estimate_hours=1.0, today_estimate_date=TODAY, done_date=TODAY),
            make_item("通常見積りのみ", estimate_hours=5.0),
        ]
    )
    await app_user.open("/")

    await shows(app_user, "残り 4時間")  # 標準労働時間8時間 - (3 + 1)。完了済みも含み、通常の見積りは含めない


async def test_work_balance_shows_over_when_estimates_exceed_standard_hours(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("設計", today_estimate_hours=9.0, today_estimate_date=TODAY)])
    await app_user.open("/")

    await shows(app_user, "超過 1時間")
    [label] = displayed_elements(app_user, "超過 1時間")
    assert "text-negative" in label.classes


async def test_work_balance_is_hidden_without_today_estimates(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(
        items=[
            make_item("見積りなし"),
            make_item("昨日の限定見積り", today_estimate_hours=2.0, today_estimate_date=TODAY - timedelta(days=1)),
        ]
    )
    await app_user.open("/")

    await shows(app_user, "見積りなし")
    await hides(app_user, "残り")
    await hides(app_user, "超過")


async def test_shift_s_skips_repeating_item_and_hides_it_by_default(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("毎日の用事"), make_item("残る用事")])
    await app_user.open("/")
    click_row(app_user, "毎日の用事")

    await press(app_user, "S", shift=True)

    await hides(app_user, "毎日の用事")
    await shows(app_user, "残る用事")
    [skipped, _] = app_env.todos().items
    assert skipped.skip_date == TODAY


async def test_skipped_item_is_visible_with_badge_in_all_and_skipped_filters(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("スキップ済み", skip_date=TODAY), make_item("通常")])
    await app_user.open("/")
    await hides(app_user, "スキップ済み")

    select_toggle(app_user, "すべて")
    await shows(app_user, "スキップ済み")
    await shows(app_user, "通常")
    await shows(app_user, "スキップ")  # バッジ

    select_toggle(app_user, "スキップのみ")
    await shows(app_user, "スキップ済み")
    await hides(app_user, "通常")


async def test_shift_s_again_unskips_the_item(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("スキップ済み", skip_date=TODAY)])
    await app_user.open("/")
    select_toggle(app_user, "スキップのみ")
    await shows(app_user, "スキップ済み")
    click_row(app_user, "スキップ済み")

    await press(app_user, "S", shift=True)

    await hides(app_user, "スキップ済み")  # スキップのみの絞り込みから外れる
    assert app_env.todos().items[0].skip_date is None


async def test_shift_s_on_non_repeating_item_warns_and_does_nothing(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("今日だけ", ScheduleType.ONE_TIME)])
    await app_user.open("/")
    click_row(app_user, "今日だけ")

    await press(app_user, "S", shift=True)

    await app_user.should_see("スキップできるのは、毎日・週次・月次のアイテムです")
    assert app_env.todos().items[0].skip_date is None
    await shows(app_user, "今日だけ")


async def test_r_carries_item_to_tomorrow_with_badge_and_keeps_remaining(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("資料作成", ScheduleType.ONE_TIME, estimate_hours=2.0)])
    await app_user.open("/")
    click_row(app_user, "資料作成")

    await press(app_user, "r")

    await hides(app_user, "資料作成")
    item = app_env.todos().items[0]
    assert item.anchor_date == TOMORROW
    assert item.carried_from == TODAY
    await press(app_user, "ArrowRight", shift=True)
    await shows(app_user, "資料作成")
    await shows(app_user, f"繰越 {TODAY.strftime('%m/%d')}〜")
    await shows(app_user, "見積り 2時間")


async def test_r_in_past_day_view_carries_item_to_today(app_user: User, app_env: AppEnv) -> None:
    yesterday = TODAY - timedelta(days=1)
    app_env.seed(items=[make_item("前日の作業", ScheduleType.ONE_TIME, anchor_date=yesterday, estimate_hours=1.0)])
    await app_user.open("/")
    await press(app_user, "ArrowLeft", shift=True)
    await shows(app_user, "前日の作業")
    click_row(app_user, "前日の作業")

    await press(app_user, "r")

    await hides(app_user, "前日の作業")
    assert app_env.todos().items[0].anchor_date == TODAY
    await press(app_user, "ArrowRight", shift=True)
    await shows(app_user, "前日の作業")


async def test_r_warns_when_nothing_can_be_carried(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("見積りなし", ScheduleType.ONE_TIME)])
    await app_user.open("/")
    click_row(app_user, "見積りなし")

    await press(app_user, "r")

    await app_user.should_see("繰越できるアイテムがありません")
    assert app_env.todos().items[0].anchor_date == TODAY
    await shows(app_user, "見積りなし")


async def test_r_on_a_done_item_does_not_carry(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("終わった", ScheduleType.ONE_TIME, estimate_hours=1.0, done_date=TODAY)])
    await app_user.open("/")
    select_toggle(app_user, "すべて")
    await shows(app_user, "終わった")
    click_row(app_user, "終わった")

    await press(app_user, "r")

    await app_user.should_see("繰越できるアイテムがありません")
    assert app_env.todos().items[0].anchor_date == TODAY


async def test_work_balance_ignores_skipped_items_estimates(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(
        items=[
            make_item("やる", today_estimate_hours=3.0, today_estimate_date=TODAY),
            make_item("やらない", today_estimate_hours=2.0, today_estimate_date=TODAY, skip_date=TODAY),
        ]
    )
    await app_user.open("/")

    await shows(app_user, "残り 5時間")  # 8 - 3(スキップ中の2は除く)


async def test_main_panel_hides_done_items_by_default(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("終わった", ScheduleType.ONE_TIME, done_date=TODAY), make_item("これから")])
    await app_user.open("/")

    await shows(app_user, "これから")
    await hides(app_user, "終わった")


async def test_done_filter_toggle_switches_between_active_all_and_done(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("終わった", ScheduleType.ONE_TIME, done_date=TODAY), make_item("これから")])
    await app_user.open("/")

    select_toggle(app_user, "すべて")
    await shows(app_user, "終わった")
    await shows(app_user, "これから")

    select_toggle(app_user, "完了のみ")
    await shows(app_user, "終わった")
    await hides(app_user, "これから")

    select_toggle(app_user, "未完了のみ")
    await hides(app_user, "終わった")
    await shows(app_user, "これから")


# --- 新規登録・入力補完 -------------------------------------------------------------------


async def test_enter_in_new_item_input_registers_one_time_item_for_today(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")

    new_input = app_user.find(content="新しいアイテム")
    new_input.type("買い物").trigger("keydown.enter.exact")

    await shows(app_user, "買い物")
    [item] = app_env.todos().items
    assert (item.name, item.schedule_type, item.anchor_date, item.category_id) == (
        "買い物",
        ScheduleType.ONE_TIME,
        TODAY,
        None,
    )


async def test_item_registered_on_other_view_date_gets_that_date_as_anchor(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await press(app_user, "ArrowRight", shift=True)

    app_user.find(content="新しいアイテム").type("明日やる").trigger("keydown.enter.exact")

    await shows(app_user, "明日やる")  # 表示中の日に登録されるため、そのまま一覧に出る
    [item] = app_env.todos().items
    assert (item.name, item.anchor_date) == ("明日やる", TOMORROW)


async def test_blank_input_does_not_register_an_item(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")

    app_user.find(content="新しいアイテム").type("   ").trigger("keydown.enter.exact")

    assert _names(app_env) == []


async def test_input_is_trimmed_and_cleared_after_registration(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    new_input = app_user.find(content="新しいアイテム")

    new_input.type("  余白あり  ").trigger("keydown.enter.exact")

    assert _names(app_env) == ["余白あり"]
    assert input_value(new_input) == ""


async def test_shift_enter_registers_item_and_opens_category_picker(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")

    app_user.find(content="新しいアイテム").type("分類したい").trigger("keydown.enter.shift")

    assert _names(app_env) == ["分類したい"]
    await shows(app_user, "カテゴリを選択")


async def test_tab_completes_with_existing_item_name_without_registering(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("週次レビュー", ScheduleType.ONE_TIME, anchor_date=TOMORROW)])
    await app_user.open("/")
    new_input = app_user.find(content="新しいアイテム")

    new_input.type("週次").trigger("keydown.tab")

    assert input_value(new_input) == "週次レビュー"
    assert _names(app_env) == ["週次レビュー"]  # 補完しただけで、Enterまで登録されない


async def test_tab_does_not_complete_when_nothing_matches(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("週次レビュー")])
    await app_user.open("/")
    new_input = app_user.find(content="新しいアイテム")

    new_input.type("月次").trigger("keydown.tab")

    assert input_value(new_input) == "月次"


# --- 実行・停止・キャンセル --------------------------------------------------------------


async def test_enter_starts_and_stops_execution_of_selected_item(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")

    click_row(app_user, "朝のメール")
    await press(app_user, "Enter")
    [record] = app_env.todos().records
    assert record.end_time is None

    await press(app_user, "Enter")
    [record] = app_env.todos().records
    assert record.end_time is not None


async def test_double_click_toggles_execution(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")

    double_click_row(app_user, "朝のメール")
    assert [r.end_time is None for r in app_env.todos().records] == [True]

    double_click_row(app_user, "朝のメール")
    assert [r.end_time is None for r in app_env.todos().records] == [False]


async def test_starting_another_item_stops_the_running_one(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("アルファ"), make_item("ブラボー")])
    await app_user.open("/")

    double_click_row(app_user, "アルファ")
    double_click_row(app_user, "ブラボー")

    records = app_env.todos().records
    assert [(r.item_name, r.end_time is None) for r in records] == [("アルファ", False), ("ブラボー", True)]


async def test_enter_without_selection_does_nothing(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")

    await press(app_user, "Enter")

    assert app_env.todos().records == []


async def test_c_cancels_the_running_record(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")
    click_row(app_user, "朝のメール")
    await press(app_user, "Enter")

    await press(app_user, "c")

    assert app_env.todos().records == []


async def test_running_item_shows_in_floating_indicator(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール", estimate_hours=1.0)])
    await app_user.open("/")

    double_click_row(app_user, "朝のメール")

    await shows(app_user, "00:")  # 経過時間・残り時間の表示


# --- 完了 ---------------------------------------------------------------------------------


async def test_d_marks_selected_item_done_and_hides_it(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("やること", ScheduleType.ONE_TIME)])
    await app_user.open("/")
    click_row(app_user, "やること")

    await press(app_user, "d")

    [item] = app_env.todos().items
    assert item.done_date == TODAY
    await hides(app_user, "やること")


async def test_d_on_running_item_stops_it(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("やること")])
    await app_user.open("/")
    double_click_row(app_user, "やること")

    await press(app_user, "d")

    [record] = app_env.todos().records
    assert record.end_time is not None


# --- 削除 ---------------------------------------------------------------------------------


async def test_delete_key_removes_single_selected_item_without_confirmation(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("消す"), make_item("残す")])
    await app_user.open("/")
    click_row(app_user, "消す")

    await press(app_user, "Delete")

    assert _names(app_env) == ["残す"]
    await hides(app_user, "削除する")


async def test_delete_running_item_keeps_a_stopped_record(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("消す")])
    await app_user.open("/")
    double_click_row(app_user, "消す")

    await press(app_user, "Backspace")

    data = app_env.todos()
    assert data.items == []
    [record] = data.records
    assert record.end_time is not None


async def test_delete_of_multiple_items_asks_for_confirmation(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("アルファ"), make_item("ブラボー"), make_item("チャーリー")])
    await app_user.open("/")
    await press(app_user, "a", meta=True)  # 全選択

    await press(app_user, "Delete")

    await shows(app_user, "3件のアイテムを削除します")
    assert _names(app_env) == ["アルファ", "ブラボー", "チャーリー"]  # 確認前は消えない
    click_displayed(app_user, "削除する")
    assert _names(app_env) == []


async def test_confirmation_cancel_keeps_items(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("アルファ"), make_item("ブラボー")])
    await app_user.open("/")
    await press(app_user, "a", ctrl=True)
    await press(app_user, "Delete")

    click_displayed(app_user, "キャンセル")

    assert _names(app_env) == ["アルファ", "ブラボー"]


# --- 選択 ---------------------------------------------------------------------------------


async def test_ctrl_click_toggles_and_shift_click_selects_range(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("アルファ"), make_item("ブラボー"), make_item("チャーリー"), make_item("デルタ")])
    await app_user.open("/")

    click_row(app_user, "アルファ")
    click_row(app_user, "チャーリー", shift=True)  # A〜Cの範囲
    await press(app_user, "Delete")
    await shows(app_user, "3件のアイテムを削除します")
    click_displayed(app_user, "キャンセル")

    click_row(app_user, "ブラボー")
    click_row(app_user, "デルタ", ctrl=True)  # BとDを個別選択
    await press(app_user, "Delete")
    await shows(app_user, "2件のアイテムを削除します")


async def test_down_and_up_keys_move_single_selection(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("アルファ"), make_item("ブラボー"), make_item("チャーリー")])
    await app_user.open("/")

    await press(app_user, "j")  # 未選択からは先頭
    await press(app_user, "ArrowDown")
    await press(app_user, "Enter")  # ブラボー
    assert [r.item_name for r in app_env.todos().records] == ["ブラボー"]

    await press(app_user, "k")
    await press(app_user, "k")  # 先頭で止まる
    await press(app_user, "Enter")  # アルファ(ブラボーは停止)
    assert [r.item_name for r in app_env.todos().records] == ["ブラボー", "アルファ"]


# --- 表示日の切り替え ---------------------------------------------------------------------


async def test_shift_arrow_moves_view_date_and_shows_items_of_that_day(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("明日の予定", ScheduleType.ONE_TIME, anchor_date=TOMORROW)])
    await app_user.open("/")
    await hides(app_user, "明日の予定")

    await press(app_user, "ArrowRight", shift=True)

    await shows(app_user, "明日の予定")
    await press(app_user, "ArrowLeft", shift=True)
    await hides(app_user, "明日の予定")


async def test_weekday_label_follows_view_date(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    await shows(app_user, format_weekday(TODAY))

    await press(app_user, "ArrowRight", shift=True)

    await shows(app_user, format_weekday(TOMORROW))


async def test_read_only_view_ignores_run_cancel_and_done_but_allows_selection(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("明日の予定", ScheduleType.ONE_TIME, anchor_date=TOMORROW)])
    await app_user.open("/")
    await press(app_user, "ArrowRight", shift=True)
    await shows(app_user, "明日の予定")
    click_row(app_user, "明日の予定")

    await press(app_user, "Enter")
    await press(app_user, "d")
    await press(app_user, "c")
    double_click_row(app_user, "明日の予定")

    data = app_env.todos()
    assert data.records == []
    assert data.items[0].done_date is None


# --- 画面切り替え・ダイアログ -------------------------------------------------------------


async def test_escape_toggles_between_main_and_list_screens(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")

    await press(app_user, "Escape")
    await shows(app_user, "編集一覧")

    await press(app_user, "Escape")
    await hides(app_user, "編集一覧")


async def test_escape_first_clears_selection_before_switching_screen(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")
    click_row(app_user, "朝のメール")

    await press(app_user, "Escape")
    await hides(app_user, "編集一覧")  # 選択解除だけで、画面は切り替わらない

    await press(app_user, "Escape")
    await shows(app_user, "編集一覧")


async def test_e_opens_edit_dialog_for_selected_item(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")
    click_row(app_user, "朝のメール")

    await press(app_user, "e")

    await shows(app_user, "アイテムの編集")


async def test_e_without_selection_does_not_open_edit_dialog(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")

    await press(app_user, "e")

    await hides(app_user, "アイテムの編集")


async def test_dialog_shortcuts_open_their_dialogs(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("朝のメール")])
    await app_user.open("/")

    await press(app_user, "l")
    await shows(app_user, "本日の作業ログ")

    await press(app_user, "g")
    await shows(app_user, "カテゴリ一覧")
    await press(app_user, "Escape")

    await press(app_user, "T", shift=True)
    await shows(app_user, "集計画面")


# --- ドラッグ&ドロップの並べ替え(表の行) -------------------------------------------------


def _drop_row(user: User, *, fixed_rows: int, old_index: int, new_index: int) -> None:
    """表の行のドロップを擬似的に送る(実際のドラッグはブラウザ側のSortableJSが行う)。"""
    [sortable] = [e for e in user.find(SortableTable).elements if e.props["fixed-rows"] == fixed_rows]
    UserInteraction(user, {sortable}, None).trigger("reorder", {"old_index": old_index, "new_index": new_index})


async def test_dropping_a_row_in_edit_list_reorders_items(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("A"), make_item("B"), make_item("C")])
    await app_user.open("/")
    await press(app_user, "Escape")
    await shows(app_user, "編集一覧")

    _drop_row(app_user, fixed_rows=0, old_index=0, new_index=2)

    assert _names(app_env) == ["B", "C", "A"]


async def test_dropping_a_row_in_filtered_edit_list_moves_to_the_target_position(
    app_user: User, app_env: AppEnv
) -> None:
    # 絞り込みで見えない行(基準日が別の日のB)があっても、移動先の位置へ入る
    app_env.seed(items=[make_item("A"), make_item("B", anchor_date=TOMORROW), make_item("C")])
    await app_user.open("/")
    await press(app_user, "Escape")
    await shows(app_user, "編集一覧")

    _drop_row(app_user, fixed_rows=0, old_index=0, new_index=1)  # 見えているのはA, Cの2行

    assert _names(app_env) == ["B", "C", "A"]


async def test_dropping_a_row_in_category_list_reorders_categories_after_fixed_undecided_row(
    app_user: User, app_env: AppEnv
) -> None:
    a, b, c = Category(name="A"), Category(name="B"), Category(name="C")
    app_env.seed(categories=[a, b, c])
    await app_user.open("/")
    await press(app_user, "g")
    await shows(app_user, "カテゴリ一覧")

    _drop_row(app_user, fixed_rows=1, old_index=1, new_index=3)  # 添字0は固定の「未定」行

    assert [category.name for category in app_env.todos().categories] == ["B", "C", "A"]


# --- 設定 ---------------------------------------------------------------------------------


async def test_settings_dialog_toggles_suspend_detection_and_saves_to_config(app_user: User, app_env: AppEnv) -> None:
    config_path = app_env.directory / "config.json"
    await app_user.open("/")

    await press(app_user, "o")
    await shows(app_user, "スリープ検知")
    app_user.find(kind=ui.checkbox).click()
    click_displayed(app_user, "保存")

    assert json.loads(config_path.read_text(encoding="utf-8"))["suspend_detection"] is True


# --- Undo/Redo ----------------------------------------------------------------------------


async def test_ctrl_z_undoes_a_delete_and_shift_ctrl_z_redoes_it(app_user: User, app_env: AppEnv) -> None:
    app_env.seed(items=[make_item("消す"), make_item("残す")])
    await app_user.open("/")
    click_row(app_user, "消す")
    await press(app_user, "Delete")
    assert _names(app_env) == ["残す"]

    await press(app_user, "z", ctrl=True)

    assert _names(app_env) == ["消す", "残す"]
    await shows(app_user, "消す")
    await app_user.should_see("元に戻しました: アイテムを削除")

    await press(app_user, "Z", ctrl=True, shift=True)

    assert _names(app_env) == ["残す"]
    await hides(app_user, "消す")
    await app_user.should_see("やり直しました: アイテムを削除")


async def test_cmd_z_and_ctrl_y_work_as_undo_and_redo(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    app_user.find(content="新しいアイテム").type("買い物").trigger("keydown.enter.exact")
    assert _names(app_env) == ["買い物"]

    await press(app_user, "z", meta=True)
    assert _names(app_env) == []

    await press(app_user, "y", ctrl=True)
    assert _names(app_env) == ["買い物"]


async def test_undo_and_redo_with_empty_history_show_warnings(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")

    await press(app_user, "z", ctrl=True)
    await app_user.should_see("元に戻す操作がありません")

    await press(app_user, "Z", ctrl=True, shift=True)
    await app_user.should_see("やり直す操作がありません")


async def test_undo_is_ignored_while_a_dialog_is_open(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    app_user.find(content="新しいアイテム").type("買い物").trigger("keydown.enter.exact")
    await press(app_user, "e")  # 登録直後のアイテムが選択されているため、編集フォームが開く

    await press(app_user, "z", ctrl=True)

    assert _names(app_env) == ["買い物"]


async def test_undo_works_while_the_category_list_is_open(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    app_user.find(content="新しいアイテム").type("買い物").trigger("keydown.enter.exact")
    await press(app_user, "g")  # カテゴリ一覧を開く

    await press(app_user, "z", ctrl=True)

    assert _names(app_env) == []


async def test_undo_clears_selection_of_the_removed_item(app_user: User, app_env: AppEnv) -> None:
    await app_user.open("/")
    app_user.find(content="新しいアイテム").type("買い物").trigger("keydown.enter.exact")
    await press(app_user, "z", ctrl=True)  # 追加を取り消す(取り消したアイテムが選択中だった)

    await press(app_user, "e")  # 選択が残っていると、存在しないアイテムの編集でKeyErrorになる
    await press(app_user, "Enter")

    assert _names(app_env) == []
    assert app_env.todos().records == []
