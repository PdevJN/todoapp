from datetime import date, timedelta

from todoapp.ui.app_state import AppState, Screen


def test_initial_state_is_main_screen_with_no_selection() -> None:
    state = AppState()
    assert state.screen is Screen.MAIN
    assert state.selected_item_id is None
    assert state.selected_record_id is None
    assert state.selected_category_id is None
    assert state.selected_item_ids == set()
    assert state.selected_record_ids == set()
    assert state.selected_category_ids == set()


def test_select_sets_and_clears_single_selection() -> None:
    # 同値分析: 単一選択は「IDを指定」「None(選択解除)」の2クラス
    state = AppState()
    state.select("item-1")
    assert state.selected_item_id == "item-1"
    state.select(None)
    assert state.selected_item_id is None


def test_select_record_and_select_category_are_independent_of_item_selection() -> None:
    state = AppState()
    state.select("item-1")
    state.select_record("record-1")
    state.select_category("category-1")

    assert state.selected_item_id == "item-1"
    assert state.selected_record_id == "record-1"
    assert state.selected_category_id == "category-1"


def test_select_items_replaces_the_entire_set() -> None:
    state = AppState()
    state.select_items({"a", "b"})
    assert state.selected_item_ids == {"a", "b"}

    # 境界値分析: 空集合(選択なし)への遷移
    state.select_items(set())
    assert state.selected_item_ids == set()


def test_select_records_and_select_categories_replace_their_sets() -> None:
    state = AppState()
    state.select_records({"r1"})
    state.select_categories({"c1", "c2"})

    assert state.selected_record_ids == {"r1"}
    assert state.selected_category_ids == {"c1", "c2"}


def test_toggle_screen_switches_from_main_to_list() -> None:
    # 境界値分析: Screenは2値のみ。MAIN→LISTの遷移を確認する
    state = AppState()
    state.toggle_screen()
    assert state.screen is Screen.LIST


def test_toggle_screen_switches_from_list_back_to_main() -> None:
    # 境界値分析: Screenは2値のみ。もう一方向(LIST→MAIN)の遷移を確認する
    state = AppState(screen=Screen.LIST)
    state.toggle_screen()
    assert state.screen is Screen.MAIN


def test_view_date_starts_today_and_is_not_read_only() -> None:
    state = AppState()
    assert state.view_date == date.today()
    assert state.is_read_only_view is False


def test_view_date_other_than_today_is_read_only_on_main_screen_only() -> None:
    state = AppState()
    state.view_date = date.today() + timedelta(days=1)
    assert state.is_read_only_view is True
    # 表示日はメインパネルだけの設定で、編集一覧では実行・完了の操作を妨げない
    state.screen = Screen.LIST
    assert state.is_read_only_view is False


def test_shift_view_date_moves_by_days_in_both_directions() -> None:
    state = AppState()
    state.shift_view_date(1)
    assert state.view_date == date.today() + timedelta(days=1)
    state.shift_view_date(-2)
    assert state.view_date == date.today() - timedelta(days=1)
