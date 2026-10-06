"""メインパネル・編集一覧・各ダイアログを、ブラウザ無し(NiceGUIの`user`)で操作する画面テスト。

保存先は一時ディレクトリで、操作後の結果は`todos.json`の再読込で確認する。
"""

from datetime import date, timedelta

from nicegui import ui
from nicegui.testing import User

from test.ui.harness import (
    AppEnv,
    click_displayed,
    click_row,
    double_click_row,
    hides,
    input_value,
    make_item,
    press,
    select_toggle,
    shows,
)
from todoapp.domain.models import ScheduleType

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
